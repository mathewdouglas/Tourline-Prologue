"""Offline engine checks for the Phase 220 interpreter pipeline stage. Invoke through run_locked.py.

Each case runs the private engine with no guest entry into a private scratch cache:
  cold -> warm (disk hits), MSAA 1/2/4/8 and colour precision off, a cancellation
  (engine killed mid-run) followed by a resume, and an existing cache that already
  holds other files (they must be byte-identical afterwards).
Only the ELF is copied to a scratch game root; nothing outside scratch is written.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import interp_pipeline_prep as stage  # noqa: E402
from shader_reconstruct import offline_env, run_offline  # noqa: E402

GAME = Path(r'C:\Users\GGPC\Dev\Recomps\GT5P')
TEMPLATE = ROOT / 'assets/pipeline-templates/gt5p-disc-v2'


def tree_digest(cache, skip_prefixes=('ipso',)):
    h = hashlib.sha256()
    for p in sorted(cache.rglob('*')):
        if p.is_file() and not p.name.startswith(skip_prefixes):
            h.update(p.relative_to(cache).as_posix().encode() + b'\0' + p.read_bytes())
    return h.hexdigest()


def settings_file(storage, msaa, hp):
    storage.mkdir(parents=True, exist_ok=True)
    (storage / 'gt5p_settings.toml').write_text(
        f'[video]\nresolution = "1080p"\naspect = "21:9"\nmsaa = {msaa}\n[game]\nsmooth_colour = {"true" if hp else "false"}\nanisotropy = 16\n',
        encoding='utf-8')


def killing_runner(cache, blobs):
    def run(engine, game_root, env, log, timeout=180):
        with log.open('wb') as stream:
            child = subprocess.Popen([str(engine)], cwd=game_root, env=env, stdout=stream, stderr=subprocess.STDOUT)
            # Kill part-way through creation: once some blobs exist (stderr is flushed only once a second).
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and len(list(cache.glob('ipso_*.bin'))) < blobs:
                time.sleep(0.005)
            child.kill(); child.wait()
        raise KeyboardInterrupt('cancelled by test')
    return run


def case(name, engine, root, cache, msaa=8, hp=True, runner=run_offline):
    storage = root / ('storage-' + name)
    settings_file(storage, msaa, hp)
    out = root / ('out-' + name)
    out.mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    report = stage.prepare(engine, root / 'game', cache, storage, TEMPLATE, out, offline_env(root / 'game', cache), runner)
    report['wall_seconds'] = round(time.perf_counter() - began, 2)
    e = report.get('engine', {})
    print(f"[{name}] msaa={msaa} hp={hp} status={report['status']} expected={report.get('expected_pipelines')} "
          f"pipelines={e.get('pipelines')} created={e.get('created')} disk_hit={e.get('disk_hit')} "
          f"driver_ms={e.get('driver_ms')} max_ms={e.get('max_ms')} engine_wall_ms={e.get('wall_ms')} "
          f"identity={e.get('identity')} previously={e.get('previously_complete')} wall_s={report['wall_seconds']}", flush=True)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, default=ROOT / 'build' / 'gt5p.exe')
    ap.add_argument('--work', type=Path, default=ROOT / 'scratch' / 'interp-prep-offline')
    ap.add_argument('--existing-cache', type=Path, help='copy of a prepared cache to grow (scratch only)')
    a = ap.parse_args()
    root = a.work.resolve()
    if not root.is_relative_to((ROOT / 'scratch').resolve()):
        ap.error('work must be under scratch')
    if root.exists():
        shutil.rmtree(root)
    (root / 'game' / 'input').mkdir(parents=True)
    shutil.copyfile(GAME / 'input' / 'EMAIN.ELF', root / 'game' / 'input' / 'EMAIN.ELF')
    results = {}
    cache = root / 'cache-8x'
    cache.mkdir()
    results['cold-8x'] = case('cold-8x', a.engine, root, cache)
    results['warm-8x'] = case('warm-8x', a.engine, root, cache)
    assert results['warm-8x']['engine']['disk_hit'] == results['warm-8x']['engine']['pipelines']
    assert results['warm-8x']['engine']['identity'] == results['cold-8x']['engine']['identity']
    assert results['warm-8x']['engine']['previously_complete'] == 1
    ids = {results['cold-8x']['engine']['identity']}
    for msaa, hp in ((1, True), (2, True), (4, True), (2, False)):
        c = root / f'cache-{msaa}-{int(hp)}'
        c.mkdir()
        r = case(f'cold-{msaa}x-hp{int(hp)}', a.engine, root, c, msaa, hp)
        results[f'{msaa}-{int(hp)}'] = r
        assert r['engine']['identity'] not in ids, 'settings identity collided'
        ids.add(r['engine']['identity'])
    # Cancellation: kill the engine part-way through a cold run, then resume.
    c = root / 'cache-cancel'
    c.mkdir()
    try:
        case('cancel', a.engine, root, c, runner=killing_runner(c, 60))
    except KeyboardInterrupt:
        pass
    partial = len(list(c.glob('ipso_*.bin')))
    leftovers = [p.name for p in c.iterdir() if p.name.endswith('.tmp')]
    markers = list(c.glob('ipso-set-*.txt'))
    print(f'[cancel] blobs after kill={partial} tmp={leftovers} markers={len(markers)}', flush=True)
    assert not markers
    r = case('resume', a.engine, root, c)
    assert r['status'] == 'complete' and r['engine']['disk_hit'] >= partial - len(leftovers) - 1
    results['cancel'] = dict(blobs_after_kill=partial, tmp=leftovers, resume=r)
    if a.existing_cache:
        c = root / 'cache-existing'
        shutil.copytree(a.existing_cache, c)
        before = tree_digest(c)
        count = sum(1 for _ in c.rglob('*'))
        r = case('existing', a.engine, root, c)
        after = tree_digest(c)
        print(f'[existing] entries={count} other-files-unchanged={before == after}', flush=True)
        assert before == after
        results['existing'] = dict(entries=count, unchanged=before == after, report=r)
    (root / 'summary.json').write_text(json.dumps(results, indent=1, default=str), encoding='utf-8')
    print('all offline checks passed', flush=True)


if __name__ == '__main__':
    main()
