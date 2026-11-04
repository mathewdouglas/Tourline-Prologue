"""Fresh starter preparation with per-stage wall times (private cache, removed afterwards).

    preparation_stage_times.py --engine E --decoder D --hash-library H --volume-library V --game-root G \
        --elf ELF --volume GT.VOL --output summary.json [--limit N]

Calls pipeline_template.prepare() exactly like the player helper (shader packs and warmup plan included),
watching the progress callback for the time spent in each phase. Honours the GT5P_PREPARE_* switches in the
environment (for example the shader text rollbacks). Application-cache-cold only: OS and driver caches are
not cleared. Run through run_locked.py; only timings and counts are kept.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('engine', 'decoder', 'game-root', 'elf', 'volume', 'hash-library', 'volume-library', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    from pipeline_template import prepare, read, bundle
    os.environ['GT5P_PREPARE_HASH_LIBRARY'] = str(a.hash_library.resolve())
    os.environ['GT5P_PREPARE_VOLUME_LIBRARY'] = str(a.volume_library.resolve())
    if a.output.exists():
        raise ValueError('Use a new summary filename')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    template = ROOT / 'assets/pipeline-templates/gt5p-disc-v2'
    plan = ROOT / 'config/pipeline-warmup/gt5p-disc-v2.json'
    document = read(template)
    phases = []   # (phase, start)
    started = time.perf_counter()

    def progress(phase, counts):
        if not phases or phases[-1][0] != phase:
            phases.append((phase, time.perf_counter() - started))

    parent = ROOT / 'scratch'
    with tempfile.TemporaryDirectory(prefix='ds-prep-', dir=parent) as fresh:
        fresh = Path(fresh)
        output = fresh / 'run'
        source = template
        if a.limit:
            document['records'] = document['records'][:a.limit]
            source = fresh / 'template'
            bundle(document, source)
            for name in ('player-map.json', 'volume-map.json'):
                (source / name).write_bytes((template / name).read_bytes())
            plan = None
        report = prepare(source, None, a.elf, a.engine, a.decoder, a.game_root, output,
                         asset_map=template / 'player-map.json', volume=a.volume,
                         volume_map=template / 'volume-map.json', progress=progress,
                         warmup_plan=plan, shader_packs=plan is not None)
        total = time.perf_counter() - started
        progress('end', {})
        stages = {phases[i][0]: phases[i + 1][1] - phases[i][1] for i in range(len(phases) - 1)}
        keep = {k: report.get(k) for k in ('counts', 'native_counts', 'runtime_lookup_counts', 'preparation_seconds',
                                           'vertex_preparation', 'fragment_preparation', 'lookup', 'resume')}
        native = report.get('native_timings') or []
        summary = dict(env={k: v for k, v in os.environ.items() if k.startswith(('GT5P_PREPARE_VFETCH', 'GT5P_PREPARE_FP_REG', 'GT5P_PREPARE_COMPILER'))},
                       records=len(document['records']), total_seconds=total, stage_seconds=stages,
                       phase_starts=phases, report=keep,
                       native_timings=[{k: v for k, v in row.items() if isinstance(v, (int, float))} for row in native],
                       cache_bytes=sum(p.stat().st_size for p in (output / 'shadercache').rglob('*') if p.is_file()),
                       engine_sha256=report.get('engine_sha256'))
        a.output.write_text(json.dumps(summary, indent=2, default=str) + '\n')
        print(json.dumps(dict(total_seconds=total, stage_seconds=stages), indent=1), flush=True)


if __name__ == '__main__':
    main()
