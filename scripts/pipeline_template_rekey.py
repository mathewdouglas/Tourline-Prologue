"""Maintainer-only single-sample re-keying from fresh shader/native proof.

Does not relax player preparation. Never imports identifiers from an unverified
collection. Run under the shared test lock with a private engine/cache. Export
is separate from the tracked starter; a subsequent strict fresh preparation is
mandatory before accepting the exported metadata.
"""
import argparse
import copy
import json
from pathlib import Path
import time

from pipeline_template import (read, validate, renderer_contract, template_digest,
    bundle, prepare_document, sha, isolated)
from native_pipeline_key import derive_record_from_ids


def single_sample(record):
    return ((record['state']['cube'] >> 16) & 15) <= 1


def check_change(before, after):
    """Only 1x fragment ids, native key and PS length may change."""
    if not single_sample(before):
        if before != after:
            raise ValueError('MSAA record changed')
        return
    allowed = copy.deepcopy(before)
    for field in ('key', 'fp_source', 'ps'):
        allowed[field] = after[field]
    allowed['native']['words'][8:10] = after['native']['words'][8:10]
    if allowed != after:
        raise ValueError('Vertex or numeric state changed')


def propose(record, vertex_source, vs, fragment_source, ps, root_hash):
    row = derive_record_from_ids(record, vertex_source, vs, fragment_source, ps, root_hash)
    check_change(record, row)
    return row


def reissue(document, report, contract):
    """Fail closed before exporting any metadata; keys come from native actual."""
    before = {r['key']: r for r in document['records']}
    if report.get('requested') != len(before) or report.get('counts') != {'prepared': len(before)}:
        raise ValueError('Incomplete or failed re-key preparation')
    rows = report.get('records', [])
    if len(rows) != len(before):
        raise ValueError('Missing/duplicate re-key results')
    seen, keys, records, mapping = set(), set(), [], {}
    by_old = {}
    for proof in rows:
        old = proof.get('template_key')
        result = proof.get('result', {})
        row = copy.deepcopy(proof.get('rekey_record'))
        if old not in before or old in seen or proof.get('status') != 'prepared':
            raise ValueError('Unexpected, failed or duplicate re-key result')
        if (not isinstance(row, dict) or result.get('created') is not True or
                result.get('actual') != result.get('expected') or
                result.get('actual') != row['key'] or proof.get('key') != row['key']):
            raise ValueError('Native actual key/creation rejected')
        check_change(before[old], row)
        if row['key'] in keys:
            raise ValueError('Re-key collision')
        row['key'] = result['actual']
        keys.add(row['key']); seen.add(old); by_old[old] = row
        mapping[old] = row['key']
    if seen != set(before):
        raise ValueError('Missing re-key record')
    records = [by_old[r['key']] for r in document['records']]
    out = copy.deepcopy(document)
    out['records'] = records
    out['compatibility']['renderer_sha256'] = contract
    return validate(out), mapping


def remap_plan(plan, mapping, old_digest, new_digest, inputs=False):
    from pipeline_warmup_plan import validate as validate_plan
    out = copy.deepcopy(validate_plan(plan))
    if out['template_sha256'] != old_digest:
        raise ValueError('Warmup plan does not pin the source template')
    for phase, keys in out['phases'].items():
        if any(key not in mapping for key in keys):
            raise ValueError('Warmup plan contains an unknown source key')
        out['phases'][phase] = [mapping[key] for key in keys]
    out['template_sha256'] = new_digest
    if inputs:
        out.update(version=2, context='default-template-inputs-v3')
    return validate_plan(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('template', 'engine', 'decoder', 'elf', 'game-root', 'volume',
                 'work', 'output', 'warmup-plan', 'output-plan'):
        ap.add_argument('--'+name, type=Path, required=True)
    a = ap.parse_args()
    from train_pipeline_cache import idle
    from preparation_checkpoint import Checkpoint
    from cache_hash import statistics
    idle()
    work = isolated(a.work)
    if work.exists() or a.output.exists() or a.output_plan.exists():
        raise ValueError('Use fresh private work and export paths')
    document = read(a.template, legacy=True)
    from pipeline_template import compatibility
    current = dict(compatibility(a.engine, a.decoder, a.elf), renderer_sha256=renderer_contract())
    previous = dict(document['compatibility'], renderer_sha256=current['renderer_sha256'])
    if previous != current:
        raise ValueError('Only the renderer contract may be explicitly reissued')
    started = time.perf_counter()
    contract = dict(template=template_digest(a.template), engine=sha(a.engine.read_bytes()),
                    decoder=sha(a.decoder.read_bytes()), rekey='fp-sample-share-v1')
    with Checkpoint(work, contract, False) as checkpoint:
        report = prepare_document(document, a.template, None, a.elf, a.engine, a.decoder,
            a.game_root, work, a.template/'player-map.json', None, 'batch', checkpoint,
            {}, started, 0, hash_before=statistics(), volume=a.volume,
            volume_map=a.template/'volume-map.json', rekey=True)
    updated, mapping = reissue(document, report, renderer_contract())
    from pipeline_warmup_plan import read as read_plan
    plan = read_plan(a.warmup_plan)
    # Validate all source membership before writing the exported bundle.
    remap_plan(plan, mapping, template_digest(a.template), '0'*64)
    bundle(updated, a.output)
    for name in ('asset-map.json', 'player-map.json', 'volume-map.json', 'search-map.json'):
        source = a.template/name
        if source.exists():
            (a.output/name).write_bytes(source.read_bytes())
    plan = remap_plan(plan, mapping, template_digest(a.template), template_digest(a.output))
    a.output_plan.write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8', newline='\n')
    summary = dict(records=len(mapping), rekeyed=sum(k != v for k,v in mapping.items()),
        single_sample=sum(single_sample(r) for r in document['records']),
        unchanged_msaa=sum(not single_sample(r) for r in document['records']),
        renderer_sha256=renderer_contract(), seconds=time.perf_counter()-started,
        strict_fresh_acceptance_required=True)
    (work/'rekey-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
