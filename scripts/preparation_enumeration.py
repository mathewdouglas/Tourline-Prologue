"""Bounded metadata-only player enumeration; never creates native pipelines."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time

from preparation_reuse import regular_read, cache_root

SCHEMA = 'gt5p-player-shader-enumeration'
MAX_PLAN = 8 * 1024**2
MAX_JOBS = 65536
CHUNK = 256
SHA = re.compile('[0-9a-f]{64}')
HEX = re.compile('[0-9a-f]{16}')


def enabled(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_ENUMERATE', '1')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_ENUMERATE must be unset, 0, or 1')
    return value == '1'


def sample_share(environ=None):
    # Default on since Phase 213: the renderer's default RSX_FP_SAMPLE_SHARE makes
    # 1x and multisampled fragment sources identical, so one class is compiled.
    # =0 compiles both classes (needed only for an engine without sharing).
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_ENUMERATE_SAMPLE_SHARE', '1')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_ENUMERATE_SAMPLE_SHARE must be 0 or 1')
    return value == '1'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(plan):
    try:
        fields = {'schema','version','elf_sha256','volume_sha256','template_sha256','files',
                  'identities','profiles','fragment_jobs','vertex_jobs'}
        if set(plan) != fields or plan['schema'] != SCHEMA or type(plan['version']) is not int or plan['version'] != 1:
            raise ValueError('Incompatible enumeration plan')
        for key in ('elf_sha256','volume_sha256','template_sha256'):
            if not isinstance(plan[key], str) or not SHA.fullmatch(plan[key]):
                raise ValueError('Invalid enumeration pin')
        pins=plan['files']
        if (set(pins) != {'programs','volume'} or not isinstance(pins['programs'],list) or not 1<=len(pins['programs'])<=8 or
                any(not isinstance(v,str) or not SHA.fullmatch(v) for v in pins['programs']+[pins['volume']])):
            raise ValueError('Invalid enumeration file pins')
        ids = plan['identities']
        if not isinstance(ids,list) or not 1 <= len(ids) <= 8192 or ids != sorted(set(ids)) or any(not SHA.fullmatch(i) for i in ids):
            raise ValueError('Invalid enumeration identities')
        profiles = plan['profiles']
        if not isinstance(profiles,list) or not 1 <= len(profiles) <= MAX_JOBS:
            raise ValueError('Enumeration profile bound exceeded')
        for p in profiles:
            if (not isinstance(p,list) or len(p) != 10 or
                    any(type(v) is not int or not 0 <= v < (1 << (64 if i == 4 else 32)) for i,v in enumerate(p)) or
                    p[0] > 1 or p[2] & ~(1 << 26) or p[8] > 65535 or p[9] not in (0,1) or
                    ((p[1] >> 16) & 15) not in (0,2)):
                raise ValueError('Invalid numeric enumeration profile')
        jobs = plan['fragment_jobs']
        if not isinstance(jobs,list) or not 1 <= len(jobs) <= MAX_JOBS:
            raise ValueError('Enumeration job bound exceeded')
        for row in jobs:
            if not isinstance(row,list) or len(row) != 2 or any(type(v) is not int for v in row) or not 0 <= row[0] < len(ids) or not 0 <= row[1] < len(profiles):
                raise ValueError('Invalid enumeration job')
        vertices = plan['vertex_jobs']
        if not isinstance(vertices,list) or not 1 <= len(vertices) <= 8192:
            raise ValueError('Vertex enumeration bound exceeded')
        for row in vertices:
            if not isinstance(row,list) or len(row) != 2 or not isinstance(row[0],str) or not SHA.fullmatch(row[0]) or type(row[1]) is not int or row[1] not in (0,1):
                raise ValueError('Invalid vertex enumeration job')
        if len({tuple(j) for j in jobs}) != len(jobs) or len({tuple(j) for j in vertices}) != len(vertices):
            raise ValueError('Duplicate enumeration job')
        return plan
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError('Malformed enumeration plan') from exc


def load(folder, template):
    from pipeline_asset_map import validate as validate_programs, merge
    from game_volume import validate as validate_volume
    from pipeline_template import template_digest, read
    folder=cache_root(folder)
    plan_bytes = regular_read(folder/'plan.json', MAX_PLAN)
    plan = validate(json.loads(plan_bytes))
    volume_bytes = regular_read(folder/'volume.json', 1024**2)
    if digest(volume_bytes) != plan['files']['volume']:
        raise ValueError('Enumeration metadata checksum mismatch')
    parts=[]
    for number,pin in enumerate(plan['files']['programs']):
        data=regular_read(folder/f'programs-{number:04d}.json',1_000_000)
        if digest(data)!=pin:raise ValueError('Enumeration program metadata checksum mismatch')
        parts.append(validate_programs(json.loads(data)))
    programs = merge(parts)
    volume = validate_volume(json.loads(volume_bytes))
    if (plan['template_sha256'] != template_digest(template) or
            plan['elf_sha256'] != read(template)['compatibility']['elf_sha256'] or
            plan['elf_sha256'] != volume['elf_sha256'] or plan['volume_sha256'] != volume['volume_sha256']):
        raise ValueError('Enumeration game/template pin mismatch')
    available = {(r['stage'],r['id']) for r in programs['records']}
    if not ({('fp',i) for i in plan['identities']} | {('vp',i) for i,_ in plan['vertex_jobs']}) <= available:
        raise ValueError('Enumeration programs are missing locations')
    containers = {r['container']:r['size'] for r in volume['records']}
    for r in programs['records']:
        if r['container'] != volume['elf_sha256'] and containers.get(r['container']) != r['container_size']:
            raise ValueError('Enumeration container mismatch')
    if sum(r['size'] for r in programs['records']) > 128*1024**2:
        raise ValueError('Enumeration program memory bound exceeded')
    return dict(plan=plan, programs=programs, volume=volume, sha256=digest(plan_bytes))


def fragment_jobs(plan, collapse=False):
    result = []
    seen = set()
    for i,p in plan['fragment_jobs']:
        profile = list(plan['profiles'][p])
        if collapse:
            profile[1] &= ~0xf0000
        key = (plan['identities'][i], tuple(profile))
        if key not in seen:
            result.append(key)
            seen.add(key)
    return result


def stage(metadata, output, elf, engine, decoder, game_root, checkpoint, volume=None, assets=None, collapse=False):
    from game_volume import resolve
    from pipeline_asset_map import resolve as resolve_assets
    from prepare_material_shaders import save_code
    from shader_enumerate import state_of
    from shader_fragment_batch import compile_batch
    from shader_vertex_batch import compile_jobs
    from train_pipeline_cache import save_report
    if type(collapse) is not bool:raise ValueError('Enumeration sample sharing must be explicit')
    if collapse:
        supported=False;tail=b''
        with engine.open('rb') as stream:
            while block:=stream.read(1024**2):
                if b'RSX_FP_SAMPLE_SHARE' in tail+block:
                    supported=True;break
                tail=block[-32:]
        if not supported:
            raise ValueError('Sample sharing requires a matching renderer; cache selection preserved')
    started = time.perf_counter()
    checkpoint.stage('enumerating-shaders', completed=0, total=0)
    locations = metadata['programs']
    if volume is not None:
        vertices, fragments, lookup = resolve(locations, metadata['volume'], volume, elf, progress=checkpoint.progress)
    elif assets is not None:
        wanted = {(r['stage'],r['id'],r['size']) for r in locations['records']}
        vertices, fragments, lookup = resolve_assets(locations, assets, elf, wanted, seconds=600)
    else:
        raise ValueError('Enumeration needs original game assets')
    expected={(r['stage'],r['id']) for r in locations['records']}
    if expected != {('vp',i) for i in vertices}|{('fp',i) for i in fragments}:
        raise ValueError('Enumeration lookup did not verify every program')
    plan = metadata['plan']
    fragments_plan = fragment_jobs(plan, collapse)
    vertices_plan = [tuple(j) for j in plan['vertex_jobs']]
    contract = dict(plan=metadata['sha256'], sample_share=collapse)
    root = output/'enumeration'
    root.mkdir(exist_ok=True)
    cache = output/'shadercache'
    report = dict(plan_sha256=metadata['sha256'], sample_share=collapse, lookup=lookup,
                  requested=len(fragments_plan)+len(vertices_plan), prepared=0, failed=0, reused=0, chunks=0,
                  compile_seconds=0.0, failure_examples=[])
    def poll():
        if checkpoint.progress:
            checkpoint.progress('enumerating-shaders', dict(completed=report['prepared']+report['failed'],total=report['requested']))
    for kind, jobs in (('fragment', fragments_plan), ('vertex', vertices_plan)):
        for start in range(0,len(jobs),CHUNK):
            poll()
            block = jobs[start:start+CHUNK]
            result = root/f'{kind}-{start//CHUNK:04d}.json'
            rows = None
            if result.exists():
                saved = json.loads(regular_read(result, 1024**2))
                if saved.get('contract') != contract or saved.get('start') != start or len(saved.get('rows',[])) != len(block):
                    raise ValueError('Enumeration checkpoint mismatch')
                rows = saved['rows']
                # Successful chunks resume only after verifying every cached file.
                for row in rows:
                    if row is not None:
                        if not isinstance(row,list) or len(row)!=3 or not HEX.fullmatch(row[0]) or not SHA.fullmatch(row[1]) or type(row[2]) is not int:
                            raise ValueError('Invalid enumeration checkpoint row')
                        data = regular_read(cache/(row[0]+'.dxbc'), 4*1024**2)
                        if not data.startswith(b'DXBC') or len(data)!=row[2] or digest(data)!=row[1]:
                            raise ValueError('Enumeration cache verification failed')
                report['reused'] += sum(row is not None for row in rows)
            else:
                chunk_started = time.perf_counter()
                work = root/'work'
                work.mkdir(exist_ok=True)
                try:
                    if kind == 'fragment':
                        batch = [dict(id=str(n), fragment=fragments[i], fragment_sha256=digest(fragments[i]),
                                      state=state_of(p), used=p[8]) for n,(i,p) in enumerate(block)]
                        compiled, failures = compile_batch(batch, work, cache, engine, game_root, batch_size=CHUNK, poll=poll)
                        batch_report=json.loads(regular_read(work/'fragment-preparation-report.json',4*1024**2))
                        process_errors=[r['error'] for r in batch_report['batches'] if 'error' in r]
                        if process_errors:
                            # A rejected shader is best-effort. A missing offline
                            # guard, malformed process result or failed child is
                            # an interrupted stage, never a completed chunk.
                            raise ValueError('Enumeration fragment process failed: '+str(process_errors[0])[:500])
                        rows = [[compiled[str(n)][0], digest(compiled[str(n)][1]), len(compiled[str(n)][1])]
                                if str(n) in compiled else None for n in range(len(block))]
                    else:
                        batch = [dict(sha256=i, gpu=g, program=vertices[i]) for i,g in block]
                        ready = {}
                        def accept(job, source, code_id, code):
                            try:save_code(cache/(source+'.dxbc'),code)
                            except (ValueError,OSError) as exc:
                                # compile_jobs treats translator ValueError as a
                                # per-job rejection. A conflicting/unwritable
                                # durable file belongs to the stage owner.
                                raise RuntimeError('Enumeration vertex cache write failed') from exc
                            ready[(job['sha256'],job['gpu'])] = [source,digest(code),len(code)]
                        compiled, failures, _ = compile_jobs(batch, decoder, work/'vertex', derive=True, on_ready=accept, poll=poll)
                        rows = [ready.get(j) for j in block]
                    saved = dict(contract=contract,start=start,rows=rows,
                                 seconds=time.perf_counter()-chunk_started,
                                 failures={str(k):str(v)[:500] for k,v in failures.items()})
                    save_report(result, saved)
                finally:
                    # Only the private transient workspace, after owned compilers exit.
                    shutil.rmtree(work)
            report['chunks'] += 1
            report['compile_seconds'] += saved.get('seconds',0.0)
            report['failure_examples'].extend(list(saved.get('failures',{}).values())[:max(0,16-len(report['failure_examples']))])
            report['prepared'] += sum(row is not None for row in rows)
            report['failed'] += sum(row is None for row in rows)
            checkpoint.stage('enumerating-shaders',completed=report['prepared']+report['failed'],total=report['requested'])
    report['seconds'] = time.perf_counter()-started
    return report
