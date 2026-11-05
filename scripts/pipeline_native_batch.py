"""Sequential manifests within the unchanged native 4,096-request budget.

The caller owns the preparation lock and process job. Proof directories remain
under the same root; only the owned jobs.txt manifest is replaced between runs.
"""
import re
import json
import struct
import time
from shader_coverage import bounded_read

MAX_REQUESTS = 4096
SUMMARY = re.compile(r'\[pso-material-batch\] valid=1 requests=(\d+) created=(\d+) driver_calls=(\d+) cached_blob_calls=(\d+)')


def run_batches(requests, root, engine, game_root, env, log_path, runner, progress=None, results=None, timings=None, recipes=None):
    if len(set(requests)) != len(requests) or any(not re.fullmatch('[0-9a-f]{64}', identity) for identity in requests):
        raise ValueError('Invalid/duplicate native request identity')
    counts = [0, 0, 0, 0]
    profiling=env.get('RSX_PSO_PREPARE_PROFILE')=='1'
    for start in range(0, len(requests), MAX_REQUESTS):
        host_begin=time.perf_counter() if profiling else 0
        chunk = requests[start:start + MAX_REQUESTS]
        expected = set(chunk)
        if progress:
            progress(start, len(requests))
        (root/'jobs.txt').write_text(''.join(identity+'\n' for identity in chunk), encoding='ascii')
        bundle = env.get('RSX_PSO_PREPARE_REQUESTS')
        if bundle:
            from pathlib import Path
            if recipes is None or Path(bundle).resolve().parent != root.resolve():
                raise ValueError('Missing native recipe source or escaped bundle path')
            body=bytearray(struct.pack('<8sII',b'GT5PPRQ2',len(chunk),2760))
            for number,identity in enumerate(chunk):
                if progress and number%128==0:progress(start,len(requests))
                recipe=recipes(identity)
                if len(recipe)!=2760:raise ValueError('Invalid native recipe size')
                body.extend(identity.encode('ascii'));body.extend(recipe)
            Path(bundle).write_bytes(body)
            del body
        grouped = env.get('RSX_PSO_PREPARE_RESULTS')
        if grouped:
            if results is None:raise ValueError('Native result sink missing')
            # Invalidate an earlier complete result before launching this chunk.
            from pathlib import Path
            if Path(grouped).resolve().parent != root.resolve():
                raise ValueError('Native result path escapes request root')
            Path(grouped).write_text('pending\n',encoding='ascii')
        path = log_path if start == 0 else log_path.with_name(f'{log_path.stem}-{start // MAX_REQUESTS:04d}{log_path.suffix}')
        runner_begin=time.perf_counter() if profiling else 0
        log = runner(engine, game_root, env, path, timeout=900)
        runner_end=time.perf_counter() if profiling else 0
        matches = SUMMARY.findall(log)
        if len(matches) != 1 or list(map(int, matches[0][:2])) != [len(chunk)] * 2:
            raise ValueError('Native batch completion was not confirmed')
        values = list(map(int, matches[0]))
        if not 0 <= values[3] <= values[2]:
            raise ValueError('Invalid native batch driver counts')
        if grouped:
            stamps = re.findall(r'\[pso-offline-results\] version=1 rows=(\d+) published=(\d+)',log)
            if stamps != [(str(len(chunk)),'1')]:raise ValueError('Native results publication not confirmed')
            found = {}
            for line in bounded_read(Path(grouped),4*1024*1024).splitlines():
                row = json.loads(line)
                identity = row.pop('id',None)
                if identity not in expected or identity in found:
                    raise ValueError('Unexpected/duplicate native result')
                if (row.get('created') is not True or row.get('expected') != row.get('actual') or
                        not re.fullmatch('[0-9a-f]{16}',str(row.get('actual')))):
                    raise ValueError('Native result key/creation rejected')
                found[identity]=row
            if set(found)!=set(chunk):raise ValueError('Incomplete native results')
            results.update(found)
        if timings is not None:
            profiles = re.findall(r'\[pso-offline-profile\] version=1 ([^\r\n]+)',log)
            if env.get('RSX_PSO_PREPARE_PROFILE')=='1' and len(profiles)!=1:
                raise ValueError('Native timing summary missing/ambiguous')
            if profiles:
                fields = dict(re.findall(r'(\w+)=(\d+)',profiles[0]))
                values_timing={key:int(value) for key,value in fields.items()}
                if profiling:
                    values_timing['host_input_us']=round((runner_begin-host_begin)*1e6)
                    values_timing['controller_process_wall_us']=round((runner_end-runner_begin)*1e6)
                    values_timing['host_result_us']=round((time.perf_counter()-runner_end)*1e6)
                    values_timing['controller_launch_wait_exit_us']=max(0,values_timing['controller_process_wall_us']-
                        values_timing.get('startup_us',0)-values_timing.get('batch_us',0))
                timings.append(values_timing)
        counts = [a+b for a, b in zip(counts, values)]
    return counts
