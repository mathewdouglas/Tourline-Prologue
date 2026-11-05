"""Prepared pipelines at the player's MSAA sample count (Phase 223).

The starter was observed with multisampled targets at 2x and 4x (5,835 and 662 of 12,669 records). The renderer
gives every multisampled target the configured RSX_MSAA count, and the sample count is part of the native pipeline
(bits 16-19 of the key's cube field -> D3D12 SampleDesc.Count, descriptor word 154). At any other setting those
prepared pipelines are never used and the game creates them during play: about 6,300 at 8x.

Nothing else in the pipeline depends on the count: the vertex shader never does, and since Phase 213
(RSX_FP_SAMPLE_SHARE) the fragment text is the same for every sample count. So this stage re-targets each
multisampled prepared record of the translation the player runs: same shaders, descriptor word 154 and the key's
sample bits set to the player's count, a new native key. Only the driver creates anything; no shader is compiled.
Every request is checked against the renderer's own hash (created, actual == expected == derived key) and the blobs
must persist. The membership lists and the fast lookup table then name the re-targeted pipelines.

It never changes the preparation token, the template, prepared shaders or the default records. A failure leaves
the completed preparation in place (the game creates the pipelines on demand, as before).
GT5P_PREPARE_MSAA_MAP=0 skips the stage.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

SAMPLE_WORD = 154                   # D3D12_GRAPHICS_PIPELINE_STATE_DESC.SampleDesc.Count (x64, 656-byte descriptor)
QUALITY_WORD = 155
SAMPLE_BITS = 0xF0000
COUNTS = (1, 2, 4, 8)
MAX_CODE = 4 * 1024**2
MAX_INDEX = 4 * 1024**2


def enabled(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_MSAA_MAP', '1')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_MSAA_MAP must be unset, 0 or 1')
    return value == '1'


def samples_of(record):
    return (record['state']['cube'] >> 16) & 0xF


def retarget(record, msaa):
    """A deep copy of a multisampled resolved record at `msaa` samples (key left to the caller), or None when the
    record is single-sample or already at that count. msaa 1 means multisampling off: the renderer then binds
    single-sample targets, so the key's sample bits are 0 and the count is 1."""
    import copy
    if msaa not in COUNTS:
        raise ValueError('MSAA must be 1, 2, 4 or 8')
    words = record['native']['words']
    raw = samples_of(record)
    if raw <= 1:
        return None
    if words[SAMPLE_WORD] != raw or words[QUALITY_WORD] != 0:
        raise ValueError('Record sample count differs from its descriptor')
    if raw == msaa:
        return None
    out = copy.deepcopy(record)
    out['native']['words'][SAMPLE_WORD] = msaa
    out['state']['cube'] = (record['state']['cube'] & ~SAMPLE_BITS) | ((msaa if msaa > 1 else 0) << 16)
    return out


def _code(cache, source, memo):
    from preparation_reuse import regular_read
    if source not in memo:
        data = regular_read(Path(cache)/(source+'.dxbc'), MAX_CODE)
        if not data.startswith(b'DXBC'):
            raise ValueError('Prepared shader is not DXBC')
        memo[source] = data
    return memo[source]


def player_records(report, translation, cache, root_hash):
    """Resolved records (native words, state, fp, vs/ps, sources, key) of the translation the player runs.
    Translated records are rebuilt from their default record plus the translated shaders in the cache, and
    must reproduce the translation pass's own native key."""
    from native_pipeline_key import derive_record_from_ids, native_key
    defaults = report.get('derived_records') or []
    if not defaults:
        raise ValueError('Preparation report has no resolved default records')
    memo = {}
    if translation == 'default':
        out = []
        for r in defaults:
            if samples_of(r) > 1:
                if native_key(r, _code(cache, r['vp_source'], memo), _code(cache, r['fp_source'], memo), root_hash) != r['key']:
                    raise ValueError('Prepared default record does not reproduce its native key')
                out.append(r)
        return out
    extra = report.get('additional_translation')
    if not isinstance(extra, dict) or extra.get('translation') != translation or not extra.get('records'):
        raise ValueError('Preparation report has no records for this translation')
    if extra.get('resolved_records'):
        return [r for r in extra['resolved_records'] if samples_of(r) > 1]
    by_key = {r['key']: r for r in defaults}
    out = []
    for row in extra['records']:
        base = by_key.get(row['template_key'])
        if base is None:
            raise ValueError('Translated record without its default record')
        if samples_of(base) <= 1:
            continue
        vs, ps = _code(cache, row['vp_source'], memo), _code(cache, row['fp_source'], memo)
        rebuilt = derive_record_from_ids(base, row['vp_source'], vs, row['fp_source'], ps, root_hash)
        if rebuilt['key'] != row['key']:
            raise ValueError('Translated record does not reproduce its native key')
        out.append(rebuilt)
    return out


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def prepare(output, engine, game_root, report, translation, msaa, runner, progress=None):
    """Create the re-targeted pipelines into output/shadercache. Returns a report with the key mapping
    (source -> re-targeted) and compact rows for the fast lookup table."""
    from native_pipeline_key import root_signature_hash, native_key
    from pipeline_native_batch import run_batches
    from pipeline_template import envelope
    from preparation_native_handoff import NativeRequests
    from shader_reconstruct import offline_env
    from train_pipeline_cache import inventory
    if not enabled():
        return dict(status='skipped', reason='GT5P_PREPARE_MSAA_MAP=0')
    if msaa not in COUNTS:
        raise ValueError('MSAA must be 1, 2, 4 or 8')
    started = time.perf_counter()
    output = Path(output)
    cache = output/'shadercache'
    root_hash = root_signature_hash()
    sources = player_records(report, translation, cache, root_hash)
    present = {r['key'] for r in sources}
    if translation == 'default':
        present |= {r['key'] for r in report['derived_records']}
    else:
        present |= {r['key'] for r in report['additional_translation']['records']}
    memo, mapping, rows, requests, seen = {}, {}, [], [], {}
    root = output/'ms'/str(msaa)
    native_root = root/'r'
    native_root.mkdir(parents=True, exist_ok=True)
    handoff = NativeRequests(engine, cache)
    for number, record in enumerate(sources):
        if progress and number % 64 == 0:
            progress('msaa-native-input', dict(completed=number, total=len(sources)))
        moved = retarget(record, msaa)
        if moved is None:
            continue
        vs, ps = _code(cache, record['vp_source'], memo), _code(cache, record['fp_source'], memo)
        moved['key'] = native_key(moved, vs, ps, root_hash)
        mapping[record['key']] = moved['key']
        rows.append(dict(fp=record['fp'], state=moved['state'], vs=record['vs'], key=moved['key']))
        if moved['key'] in seen or moved['key'] in present:
            continue
        identity = _sha(moved['key'])
        handoff.write(native_root/identity/'pipeline', envelope(moved, vs, ps), vs, ps)
        requests.append(identity)
        seen[moved['key']] = identity
    del memo
    handoff.release(native_root, None)
    counts, timings = None, []
    if requests:
        env = offline_env(game_root, cache)
        env.update(RSX_PSO_PREPARE_BATCH=str(native_root), RSX_PSO_TEMPLATE_PREPARE='1', RSX_PSO_RECIPE_KEEP_DAYS='0')
        handoff.environment(env, native_root)
        counts = run_batches(requests, native_root, engine, game_root, env, root/'native.log', runner,
            (lambda done, total: progress('msaa-native', dict(completed=done, total=total))) if progress else None,
            results=handoff.results, timings=timings, recipes=lambda identity: handoff.recipe(native_root, identity))
        for key, identity in seen.items():
            result = handoff.result(native_root, identity)
            if result.get('created') is not True or result.get('actual') != key or result.get('expected') != key:
                raise ValueError('Re-targeted native pipeline key/creation rejected')
    handoff.finish()
    if progress:
        progress('msaa-verifying', {})
    checked = inventory(cache, True)
    if checked['rejected'] or not set(seen) <= set(checked['valid_driver_blobs']):
        raise ValueError('Re-targeted native cache persistence failed')
    by_samples = {}
    for r in sources:
        by_samples[str(samples_of(r))] = by_samples.get(str(samples_of(r)), 0) + 1
    return dict(status='complete', msaa=msaa, translation=translation, source_records=len(sources),
                source_samples=by_samples, mapped=len(mapping), created=len(seen),
                already_prepared=len(set(mapping.values()) & present), native_counts=counts,
                native_timings=timings, seconds=round(time.perf_counter()-started, 2),
                mapping=mapping, lookup_rows=rows)


def stage_membership(folder, mapping):
    """Rewrite the preparation's own menu/race lists (just written by this preparation; the game has not learned
    into an unselected generation) so each re-targeted pipeline replaces its source. Keys without a local recipe
    are left out, as stage_translated does."""
    folder = Path(folder)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError('Expected a private regular warmup directory')
    counts = {}
    for phase in ('menu', 'race'):
        path = folder/(phase+'-v1.txt')
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_INDEX:
            continue
        keys = path.read_text(encoding='ascii').split()
        moved = list(dict.fromkeys(mapping.get(k, k) for k in keys))
        moved = [k for k in moved if (folder/('pso_'+k+'.recipe')).is_file()]
        temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        with temporary.open('x', encoding='ascii', newline='\n') as stream:
            stream.write(''.join(k+'\n' for k in moved))
        temporary.replace(path)
        counts[phase] = dict(before=len(keys), after=len(moved), retargeted=sum(1 for k in keys if k in mapping))
    return counts


def compact(result):
    """The report form: the mapping and lookup rows are large and already applied to the cache."""
    return {k: v for k, v in result.items() if k not in ('mapping', 'lookup_rows')}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--translation', default='default')
    a = ap.parse_args()
    from native_pipeline_key import root_signature_hash
    rep = json.loads(a.report.read_text(encoding='utf-8'))
    recs = player_records(rep, a.translation, a.report.parent/'shadercache', root_signature_hash())
    print(json.dumps(dict(multisampled=len(recs))))
