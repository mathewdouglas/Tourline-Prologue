"""Additive, locally derived translation variants for an observed numeric template.

The caller holds the parent preparation lock. Neither shipped template records
nor default shader identifiers are rewritten. Driver creation remains native.
"""
import hashlib
import json
from pathlib import Path
import re
import time

from shader_coverage import bounded_read, fnv64
from preparation_checkpoint import Checkpoint
from pipeline_native_batch import run_batches
from preparation_reuse import regular_read
from prepare_material_shaders import save_code
from train_pipeline_cache import inventory, save_report

MODES = ('default', 'native-scaled', 'ultrawide-native')
FOLDERS = {'native-scaled':'rs', 'ultrawide-native':'uw'}
MAX_CODE = 4 * 1024**2
MAX_POOL = 128 * 1024**2
HEX = re.compile('[0-9a-f]{16}')


def sidecar(output, mode):
    if mode not in FOLDERS:
        raise ValueError('Select an explicit additional translation')
    # Native CRT readers still have ordinary Windows path limits. Keep native
    # request paths no longer than the existing output/requests/<id>/pipeline.
    return output/'tr'/FOLDERS[mode]


def player_mode(environ):
    mode = environ.get('GT5P_PREPARE_TRANSLATION', 'default')
    if mode not in MODES:
        raise ValueError('GT5P_PREPARE_TRANSLATION must be default, native-scaled, or ultrawide-native')
    return mode


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def fragment_job(record, raw):
    from shader_coverage import fp_identity
    facts = fp_identity(raw)
    if facts['size'] != record['fp']['size'] or facts['identity'] != record['fp']['sha256']:
        raise ValueError('Located translation fragment differs from template')
    return dict(id=_sha(record['key'].encode()), fragment=raw, fragment_sha256=_sha(raw),
                state=record['state'], used=facts['textures'])


def _code(entry, cache):
    if (not isinstance(entry, dict) or set(entry) != {'source', 'code', 'length'} or
            any(not isinstance(entry[k], str) or not HEX.fullmatch(entry[k]) or int(entry[k], 16) == 0
                for k in ('source', 'code')) or type(entry['length']) is not int or
            not 0 < entry['length'] <= MAX_CODE):
        raise ValueError('Malformed derived shader identity')
    data = regular_read(cache/(entry['source']+'.dxbc'), MAX_CODE)
    if len(data) != entry['length'] or not data.startswith(b'DXBC') or f'{fnv64(data):016x}' != entry['code']:
        raise ValueError('Derived shader failed resume verification; cache preserved')
    return data


def prepare(document, decoder, engine, game_root, output, parent_contract, vertices,
            fragments, mode, runner, progress=None, vertex_mode='batch'):
    """Prepare one extra translation mode; default preparation already succeeded."""
    if mode not in MODES or mode == 'default':
        raise ValueError('Select an explicit additional translation')
    from pipeline_template import cached_shaders, envelope
    from native_pipeline_key import calibrate, root_signature_hash, derive_record_from_ids
    from shader_vertex_batch import compile_jobs
    from shader_fragment_batch import compile_batch
    from shader_reconstruct import offline_env

    started = time.perf_counter()
    cache = output/'shadercache'
    root = sidecar(output, mode)
    root_hash = root_signature_hash()
    defaults = cached_shaders(document, cache)
    # Calibrate against every default record before writing any derived shader.
    calibrate(document['records'], defaults, root_hash)
    del defaults
    contract = dict(parent_contract, translation=mode+'-v1', root_signature=f'{root_hash:016x}')
    allowed_v = {r['vp']['sha256']+':'+str(r['vp_gpu']) for r in document['records']}
    allowed_f = {_sha(r['key'].encode()) for r in document['records']}
    with Checkpoint(root, contract, resume=root.exists(), progress=progress) as checkpoint:
        digest = checkpoint.state.get('progress', {}).get('manifest_sha256')
        manifest = dict(vertices={}, fragments={})
        if digest is not None:
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Malformed translation checkpoint manifest identity')
            payload = bounded_read(root/'manifests'/(digest+'.json'), 4*1024**2)
            if _sha(payload) != digest:
                raise ValueError('Translation manifest checksum differs; cache preserved')
            manifest = json.loads(payload)
        if (not isinstance(manifest, dict) or set(manifest) != {'vertices', 'fragments'} or
                not isinstance(manifest['vertices'], dict) or not isinstance(manifest['fragments'], dict) or
                not set(manifest['vertices']) <= allowed_v or not set(manifest['fragments']) <= allowed_f):
            raise ValueError('Translation manifest is outside this template')

        def stage(phase, **counts):
            checkpoint.stage(phase, manifest_sha256=digest, **counts)

        def publish(phase, **counts):
            nonlocal digest
            payload = _json(manifest)
            digest = _sha(payload)
            folder = root/'manifests'
            folder.mkdir(exist_ok=True)
            target = folder/(digest+'.json')
            if target.exists():
                if bounded_read(target, 4*1024**2) != payload:
                    raise ValueError('Existing translation manifest differs')
            else:
                pending = target.with_suffix('.tmp')
                pending.write_bytes(payload)
                pending.replace(target)
            stage(phase, **counts)

        vertex_codes, fragment_codes = {}, {}
        for group, pool in (('vertices', vertex_codes), ('fragments', fragment_codes)):
            total = 0
            shared = {}
            for identity, entry in manifest[group].items():
                pair = (entry.get('source'), entry.get('code'), entry.get('length')) if isinstance(entry, dict) else None
                if pair not in shared:
                    code = _code(entry, cache)
                    total += len(code)
                    if total > MAX_POOL:
                        raise ValueError('Derived shader pool exceeds its memory budget')
                    shared[pair] = code
                pool[identity] = shared[pair]
        reused_v = len(vertex_codes)
        reused_f = len(fragment_codes)
        stage('translation-vertex', completed=reused_v, total=len(allowed_v))
        jobs = {}
        for r in document['records']:
            identity = r['vp']['sha256']+':'+str(r['vp_gpu'])
            if identity in vertex_codes:
                continue
            raw = vertices[r['vp']['sha256']]
            if len(raw) != r['vp']['size'] or _sha(raw) != r['vp']['sha256']:
                raise ValueError('Located translation vertex differs from template')
            jobs[identity] = dict(sha256=r['vp']['sha256'], gpu=r['vp_gpu'], program=raw)
        if mode == 'native-scaled':
            # The vertex translator is identical to default in this mode.
            default_v = cached_shaders(document, cache)
            for r in document['records']:
                identity = r['vp']['sha256']+':'+str(r['vp_gpu'])
                vertex_codes[identity] = default_v[r['vp_source']]
                manifest['vertices'][identity] = dict(source=r['vp_source'], code=r['vs'],
                                                     length=len(vertex_codes[identity]))
            del default_v
            jobs.clear()
        vertex_bytes = sum(len(c) for c in vertex_codes.values())

        def ready(job, source, code_id, code):
            nonlocal vertex_bytes
            vertex_bytes += len(code)
            if vertex_bytes > MAX_POOL:
                raise ValueError('Derived vertex pool exceeds its memory budget')
            identity = job['sha256']+':'+str(int(job['gpu']))
            save_code(cache/(source+'.dxbc'), code)
            vertex_codes[identity] = code
            manifest['vertices'][identity] = dict(source=source, code=code_id, length=len(code))
            publish('translation-vertex', completed=len(vertex_codes), total=len(allowed_v))

        _, failures, vertex_report = compile_jobs(list(jobs.values()), decoder, root/'vertex-workers',
            translation=mode, derive=True, workers=1 if vertex_mode == 'serial' else 2,
            poll=lambda: progress('translation-vertex', dict(completed=len(vertex_codes), total=len(allowed_v)))
                if progress else None, on_ready=ready)
        if failures or set(vertex_codes) != allowed_v:
            raise ValueError('Some translated vertex variants could not be prepared')
        publish('translation-fragment', completed=reused_f, total=len(allowed_f))
        fragment_jobs = []
        for r in document['records']:
            identity = _sha(r['key'].encode())
            if identity in fragment_codes:
                continue
            raw = fragments[r['fp']['sha256']]
            fragment_jobs.append(fragment_job(r, raw))
        fp_root = root/'f'
        fp_root.mkdir(exist_ok=True)
        compiled, failures = compile_batch(fragment_jobs, fp_root, cache, engine, game_root, translation=mode)
        if failures:
            raise ValueError('Some translated fragment variants could not be prepared')
        fragment_total = {entry['source']: len(fragment_codes[i]) for i, entry in manifest['fragments'].items()}
        for identity, (source, code) in compiled.items():
            fragment_total[source] = len(code)
            if sum(fragment_total.values()) > MAX_POOL:
                raise ValueError('Derived fragment pool exceeds its memory budget')
            fragment_codes[identity] = code
            manifest['fragments'][identity] = dict(source=source, code=f'{fnv64(code):016x}', length=len(code))
        if set(fragment_codes) != allowed_f:
            raise ValueError('Incomplete derived fragment results')
        publish('translation-native', requested=len(document['records']))
        native_root = root/'r'
        native_root.mkdir(exist_ok=True)
        requests, derived, seen = [], [], {}
        for record in document['records']:
            vi = record['vp']['sha256']+':'+str(record['vp_gpu'])
            fi = _sha(record['key'].encode())
            vs, ps = vertex_codes[vi], fragment_codes[fi]
            row = derive_record_from_ids(record, manifest['vertices'][vi]['source'], vs,
                                manifest['fragments'][fi]['source'], ps, root_hash)
            if row['key'] not in seen:
                identity = _sha(row['key'].encode())
                proof = native_root/identity/'pipeline'
                proof.mkdir(parents=True, exist_ok=True)
                (proof/'request.recipe').write_bytes(envelope(row, vs, ps))
                for code in (vs, ps):
                    save_code(proof/f'code_{fnv64(code):016x}.dxbc', code)
                (proof/'result.json').write_text('{"pending":true}\n')
                requests.append(identity)
                seen[row['key']] = identity
            derived.append(dict(template_key=record['key'], key=row['key'],
                                vp_source=row['vp_source'], fp_source=row['fp_source']))
        native_counts = None
        if requests:
            env = offline_env(game_root, cache)
            env.update(RSX_PSO_PREPARE_BATCH=str(native_root), RSX_PSO_TEMPLATE_PREPARE='1',
                       RSX_PSO_RECIPE_KEEP_DAYS='0')
            native_counts = run_batches(requests, native_root, engine, game_root, env, root/'native.log', runner,
                lambda done, total: stage('translation-native', completed=done, requested=total))
        for row in derived:
            result = json.loads(bounded_read(native_root/seen[row['key']]/'pipeline/result.json', 65536))
            if not result.get('created') or result.get('actual') != result.get('expected') or result['actual'] != row['key']:
                raise ValueError('Derived native pipeline key/creation rejected')
        stage('translation-verifying')
        checked = inventory(cache, True)
        if checked['rejected'] or not set(seen) <= set(checked['valid_driver_blobs']):
            raise ValueError('Derived native cache persistence failed')
        report = dict(translation=mode, counts={'prepared': len(derived)}, unique_pipelines=len(seen),
            vertex_preparation=vertex_report, vertex_variants_reused=reused_v,
            fragment_jobs_reused=reused_f, fragment_preparation=json.loads(
                bounded_read(fp_root/'fragment-preparation-report.json', 1024*1024)),
            native_counts=native_counts, records=derived, root_signature=f'{root_hash:016x}',
            seconds=time.perf_counter()-started,
            limitation='Additional translations of observed numeric state; other settings and unseen draws use demand compilation.')
        save_report(root/'report.json', report)
        stage('complete', prepared=len(derived))
        return report
