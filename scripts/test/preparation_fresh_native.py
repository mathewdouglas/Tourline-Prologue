"""Measure fresh, exact native preparation; remove this test's temporary cache.

Run under isolated_validation.ps1. Original game files and existing caches are
read-only inputs. Application-cache-cold does not imply OS/driver-cache-cold.
Only timings/counts survive; raw programs, bytecode and driver blobs are removed.
"""
import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import os
import pstats
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'decoder', 'game-root', 'elf', 'volume', 'hash-library', 'volume-library', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    ap.add_argument('--limit', type=int, default=0, help='Distinct vertex sample; 0 means the entire starter')
    ap.add_argument('--profile', action='store_true')
    args = ap.parse_args()
    from pipeline_template import prepare, read, bundle
    from shader_reconstruct import run_offline
    import pipeline_template
    import shader_fragment_batch

    os.environ['GT5P_PREPARE_HASH_LIBRARY'] = str(args.hash_library.resolve())
    os.environ['GT5P_PREPARE_VOLUME_LIBRARY'] = str(args.volume_library.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError('Use a new summary filename')
    template = ROOT/'assets/pipeline-templates/gt5p-disc-v2'
    plan = ROOT/'config/pipeline-warmup/gt5p-disc-v2.json'
    document = read(template)
    if not 0 <= args.limit <= len(document['records']):
        raise ValueError('Invalid subset size')
    stages = []
    current = [None, time.perf_counter()]
    last_status = [0.0]
    native_calls = []

    def progress(phase, values):
        now = time.perf_counter()
        changed = phase != current[0]
        if changed:
            if current[0] is not None:
                stages.append(dict(phase=current[0], seconds=now-current[1]))
            current[:] = [phase, now]
        if changed or now-last_status[0] >= 5:
            args.output.with_suffix('.status.json').write_text(json.dumps(dict(phase=phase, progress=values)))
            last_status[0] = now

    def measured_native(*pos, **kw):
        begin = time.perf_counter()
        text = run_offline(*pos, **kw)
        native_calls.append(dict(seconds=time.perf_counter()-begin, log=Path(pos[3]).name,
            warmup_replayed=[int(n) for n in re.findall(r'\[shader-warmup\] preparing (\d+) known pipelines', text)],
            native_counts=[list(map(int,m)) for m in re.findall(
                r'\[pso-material-batch\] valid=1 requests=(\d+) created=(\d+) driver_calls=(\d+) cached_blob_calls=(\d+)', text)],
            compiler_workers=[int(n) for n in re.findall(r'\[shader-async\] (\d+) compile workers', text)]))
        return text

    pipeline_template.run_offline = measured_native
    shader_fragment_batch.run_offline = measured_native
    report = None
    profiler = cProfile.Profile()
    started = time.perf_counter()
    test_parent = ROOT/'scratch'
    test_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='p208-', dir=test_parent) as fresh:
        fresh = Path(fresh)
        output = fresh/'run'
        if args.limit:
            chosen, seen = [], set()
            for row in document['records']:
                identity = (row['vp']['sha256'], row['vp_gpu'])
                if identity not in seen:
                    seen.add(identity)
                    chosen.append(row)
                if len(chosen) == args.limit:
                    break
            if len(chosen) != args.limit:
                raise ValueError('Insufficient distinct vertex variants')
            document['records'] = chosen
            subset = fresh/'template'
            bundle(document, subset)
            # Locations still come from the full verified map, without copying assets.
            for name in ('player-map.json', 'volume-map.json'):
                (subset/name).write_bytes((template/name).read_bytes())
            template, plan = subset, None
        if args.profile:
            profiler.enable()
        try:
            report = prepare(template, None, args.elf, args.engine, args.decoder, args.game_root,
                output, asset_map=ROOT/'assets/pipeline-templates/gt5p-disc-v2/player-map.json',
                volume=args.volume, volume_map=ROOT/'assets/pipeline-templates/gt5p-disc-v2/volume-map.json',
                progress=progress, warmup_plan=plan, shader_packs=plan is not None)
        finally:
            if args.profile:
                profiler.disable()
        assert report['counts'] == {'prepared': len(document['records'])}, dict(
            counts=report['counts'], rejected=[r for r in report['records'] if r['status'] != 'prepared'][:3])
        assert report['resume']['verified_cached_sources'] == 0
        assert report['resume']['vertex_programs_reused'] == report['resume']['fragment_jobs_reused'] == 0
        assert report['resume']['vertex_programs_compiled'] > 0
        assert report['fragment_preparation']['processes'] > 0
        progress('cleanup', {})
        counts = dict(files=sum(1 for p in output.rglob('*') if p.is_file()))
        timings = []
        if args.profile:
            stats = pstats.Stats(profiler)
            for (file, line, name), (cc, nc, tt, ct, _) in sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:35]:
                timings.append(dict(function=Path(file).name+':'+str(line)+':'+name, calls=nc, self_seconds=tt, cumulative_seconds=ct))
        summary = dict(passed=True, application_cache_cold=True, driver_cache_cleared=False,
            requested=report['requested'], counts=report['counts'], seconds=report['preparation_seconds'],
            vertex=report['vertex_preparation'], fragment=report['fragment_preparation'],
            resume=report['resume'], hashing=report['hashing'], lookup=report['lookup'],
            stages=stages, offline_processes=native_calls, profile=timings, temporary_files=counts,
            engine_sha256=hashlib.sha256(args.engine.read_bytes()).hexdigest(),
            shader_packs=report.get('shader_packs'), io_workers=os.environ.get('GT5P_PREPARE_IO_WORKERS', 'default'),
            offline_warmup=os.environ.get('GT5P_PREPARE_OFFLINE_WARMUP', '0'))
    summary.update(test_cache_removed=not fresh.exists(), total_with_cleanup_seconds=time.perf_counter()-started)
    assert summary['test_cache_removed']
    args.output.write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: summary[k] for k in ('passed','requested','seconds','test_cache_removed','total_with_cleanup_seconds')}), flush=True)


if __name__ == '__main__':
    main()
