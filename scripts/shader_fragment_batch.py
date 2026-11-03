"""Exact offline fragment requests through the renderer's bounded compiler queue."""
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import shader_translation
from shader_coverage import bounded_read,fnv64
from shader_reconstruct import offline_env,run_offline


def io_mode(environ=None):
    value=(os.environ if environ is None else environ).get('GT5P_PREPARE_FRAGMENT_IO','1')
    if value not in ('0','1'):
        raise ValueError('GT5P_PREPARE_FRAGMENT_IO must be unset, 0, or 1')
    return value=='1'


def _workspace(root, work_prefix):
    """Caller root, or one safe child directory. Never a path that can escape it."""
    root = Path(root)
    if work_prefix is None:
        return root
    if (not isinstance(work_prefix, str) or '..' in work_prefix or work_prefix.endswith('.') or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', work_prefix)):
        raise ValueError('Invalid fragment workspace component')
    child = root / work_prefix
    if child.parent != root:
        raise ValueError('Invalid fragment workspace component')
    return child


def compile_batch(jobs, root, cache, engine, game_root, translation='default', work_prefix=None,
                  batch_size=4096, on_batch_ready=None, poll=None):
    from prepare_material_shaders import fragment_profile,save_code
    # Fixed mode only. Overlay is applied after offline_env, which clears inherited renderer settings.
    shader_translation.overlay(translation)
    if type(batch_size) is not int or not 1 <= batch_size <= 4096:
        raise ValueError('Fragment batch size must be between 1 and 4096')
    base = _workspace(root, work_prefix)
    started=time.perf_counter()
    from preparation_profile import enabled
    profiling=enabled()
    compact_io=io_mode()
    from train_pipeline_cache import bounded_cache_read
    groups=defaultdict(dict)
    members=defaultdict(list)
    hashes={}
    job_requests={}
    for job in jobs:
        profile=fragment_profile(job)
        raw=job['fragment']
        digest=hashlib.sha256(raw).hexdigest()
        if digest!=job['fragment_sha256']:
            raise ValueError('Fragment payload differs from declared identifier')
        if (len(raw)==0 or len(raw)>32768 or len(raw)%16 or
                any(type(v) is not int or not 0<=v<(1<<(64 if i==4 else 32)) for i,v in enumerate(profile[:-1])) or
                profile[0]>1 or profile[2]&~(1<<26) or profile[8]>65535):
            raise ValueError('Invalid bounded fragment request')
        identity=hashlib.sha256(repr((digest,profile)).encode()).hexdigest()
        if job['id'] in job_requests and job_requests[job['id']]!=identity:
            raise ValueError('Conflicting fragment job identifier')
        job_requests[job['id']]=identity
        groups[profile[-1]][identity]=(digest,raw,profile)
        members[identity].append(job['id'])
        if digest not in hashes:hashes[digest]=fnv64(raw)
    compiled,failures,pool={},{},{}
    code_bytes=0
    if work_prefix is not None:
        base.mkdir(exist_ok=True)
    report=dict(mode='batch',translation=translation,batch_size=batch_size,
                requested_jobs=len(jobs),unique_requests=len(members),processes=0,batches=[],compact_io=compact_io,
                input_file_checks=0,code_file_reads=0)
    for dither,requests in sorted(groups.items()):
        items=sorted(requests.items())
        for offset in range(0,len(items),batch_size):
            if poll:poll()
            input_begin=time.perf_counter() if profiling else 0
            chunk=items[offset:offset+batch_size]
            work=base/f'fragment-batch-{dither}-{offset//batch_size}';work.mkdir(exist_ok=True)
            lines=[f'GT5P_FP_BATCH_V1 {len(chunk)}\n']
            written={}
            for identity,(digest,raw,profile) in chunk:
                path=work/(digest+'.fp')
                if compact_io and digest in written:
                    if written[digest]!=raw:raise ValueError('Conflicting fragment input identity')
                else:
                    report['input_file_checks']+=1
                    if path.exists():
                        if (bounded_cache_read if compact_io else bounded_read)(path,32768)!=raw:
                            raise ValueError('Existing fragment batch input differs')
                    else:path.write_bytes(raw)
                    if compact_io:written[digest]=raw
                lines.append(f'{identity} {digest} {hashes[digest]:016x} '+ ' '.join(f'{v:x}' for v in profile[:-1])+'\n')
            (work/'jobs.txt').write_text(''.join(lines),encoding='ascii')
            env=offline_env(game_root,cache)
            env.update(RSX_SHADER_LIBRARY_BATCH=str(work),RSX_FINAL_DITHER=str(dither))
            shader_translation.apply(env, translation)
            begin=time.perf_counter();report['processes']+=1
            input_us=round((begin-input_begin)*1e6) if profiling else 0
            print(f'Compiling exact fragment batch: {len(chunk)} requests, dither={dither}',flush=True)
            try:
                log=run_offline(engine,game_root,env,work/'fragment.log',timeout=900)
                process_end=time.perf_counter() if profiling else 0
                text=(bounded_cache_read if compact_io else bounded_read)(work/'compiled.tsv',4*1024**2).decode('ascii').splitlines()
                if not text or text[0]!=f'GT5P_FP_BATCH_RESULTS_V1 {len(chunk)}':
                    raise ValueError('Missing/incompatible fragment batch result header')
                rows={}
                expected={identity for identity,_ in chunk}
                for line in text[1:]:
                    fields=line.split()
                    if (len(fields)!=4 or fields[0] not in expected or fields[0] in rows or
                            any(not re.fullmatch('[0-9a-f]{16}',v) for v in fields[1:3]) or fields[3] not in ('0','1')):
                        raise ValueError('Malformed/duplicate/unexpected fragment batch result')
                    rows[fields[0]]=fields[1:]
                if set(rows)!=expected:
                    raise ValueError('Fragment batch result count mismatch')
                summary=re.search(r'\[fp-batch\] finished: requests=(\d+) rejected=(\d+) compiled=(\d+) elapsed_ms=(\d+)',log)
                if (not summary or int(summary[1]) != len(chunk) or
                        not 0 <= int(summary[2]) <= len(chunk) or
                        not 0 <= int(summary[3]) <= len(chunk)):
                    raise ValueError('Fragment batch completion summary missing/inconsistent')
                ready={}
                checked=set()
                for identity,(digest,raw,profile) in chunk:
                    try:
                        raw_hash,key,success=rows[identity]
                        if success!='1' or int(raw_hash,16)!=hashes[digest] or int(key,16)==0:
                            raise ValueError('Production compiler rejected exact fragment request')
                        if key not in checked:
                            code=(bounded_cache_read if compact_io else bounded_read)(cache/(key+'.dxbc'),4*1024**2)
                            report['code_file_reads']+=1
                            if not code.startswith(b'DXBC'):
                                raise ValueError('Invalid/oversized fragment bytecode pool')
                            if key in pool:
                                if pool[key]!=code:raise ValueError('Fragment bytecode changed across native chunks')
                            else:
                                if code_bytes+len(code)>128*1024**2:raise ValueError('Invalid/oversized fragment bytecode pool')
                                pool[key]=code;code_bytes+=len(code)
                            checked.add(key)
                        # The native owner has exited, and this caller owns the
                        # cache lock. Retain the complete checked bytes once per
                        # source key; the template still checks expected code IDs.
                        if not compact_io:save_code(cache/(key+'.dxbc'),pool[key])
                        for job_id in members[identity]:
                            compiled[job_id]=(key,pool[key]);ready[job_id]=(key,pool[key])
                    except (ValueError,OSError) as exc:
                        for job_id in members[identity]:failures[job_id]=str(exc)
                row=dict(requests=len(chunk),seconds=time.perf_counter()-begin,
                         native_summary=list(map(int,summary.groups())))
                if profiling:
                    profiles=re.findall(r'\[shader-prepare-profile\] version=1 ([^\r\n]+)',log)
                    if len(profiles)!=1:raise ValueError('Shader timing summary missing/ambiguous')
                    row['timings']={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',profiles[0])}
                    row['timings'].update(host_input_us=input_us,process_wall_us=round((process_end-begin)*1e6),
                        host_results_us=round((time.perf_counter()-process_end)*1e6))
                report['batches'].append(row)
            except (ValueError,OSError,subprocess.SubprocessError) as exc:
                for identity,_ in chunk:
                    for job_id in members[identity]:
                        compiled.pop(job_id,None);failures[job_id]=str(exc)
                report['batches'].append(dict(requests=len(chunk),seconds=time.perf_counter()-begin,error=str(exc)))
                continue
            # Publication/cancellation failures belong to the caller. Do not turn
            # them into per-request compiler failures or start another process.
            if on_batch_ready and ready:on_batch_ready(ready)
    report.update(seconds=time.perf_counter()-started,prepared_jobs=len(compiled),failed_jobs=len(failures))
    (base/'fragment-preparation-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return compiled,failures
