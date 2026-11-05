"""Phase 220 helper acceptance: preparation + interpreter-pipeline stage, cancel/resume, stage-only rerun.

Source-run of scripts/player_prepare.py (no frozen helper) against a private install
(private engine, reference decoder/volume/hash DLLs, a 32-record template subset) and
private storage with the user's settings shape (1080p, 21:9, 8x MSAA). Invoke through
run_locked.py. Everything is written under scratch/.

1. Full preparation; cancel requested when the status reaches the interpreter stage.
   The cache selection must not have moved; prepared shaders are kept.
2. Resume: completes, interpreter stage reports disk hits for blobs made before the cancel.
3. --interp-pipelines-only on the selected cache: previously_complete=1, every blob a
   disk hit, and no other file of the prepared cache (shaders, driver blobs, recipes) changes.
4. GT5P_PREPARE_INTERP_PIPELINES=0 with --interp-pipelines-only: skipped, nothing written.
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
import pipeline_template as template  # noqa: E402

REFERENCE = Path(r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\out\preparer\dist\GT5P-Prepare')
GAME = Path(r'C:\Users\GGPC\Dev\Recomps\GT5P')
PY = Path(r'C:\GT5P-CI\venv\Scripts\python.exe')


def snapshot(root, interp=False):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and p.name.startswith(('ipso',)) == interp}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, default=ROOT / 'build' / 'gt5p.exe')
    ap.add_argument('--limit', type=int, default=32)
    ap.add_argument('--work', type=Path, default=ROOT / 'scratch' / 'interp-prep-helper')
    a = ap.parse_args()
    out = a.work.resolve()
    if not out.is_relative_to((ROOT / 'scratch').resolve()):
        ap.error('work must be under scratch')
    if out.exists():
        shutil.rmtree(out)
    install, storage = out / 'Install', out / 'Storage'
    (install / 'runtime').mkdir(parents=True)
    for f in a.engine.parent.iterdir():
        if f.suffix.lower() in ('.exe', '.dll'):
            shutil.copyfile(f, install / 'runtime' / f.name)
    (install / 'preparation').mkdir()
    for name in ('decoder.dll', 'volume_reader.dll', 'cache_hash.dll'):
        shutil.copyfile(REFERENCE / name, install / 'preparation' / name)
    original = ROOT / 'assets/pipeline-templates/gt5p-disc-v2'
    document = template.read(original)
    document = dict(document, records=document['records'][:a.limit])
    bundle = install / 'assets/pipeline-templates/gt5p-disc-v2'
    template.bundle(document, bundle)
    for name in ('asset-map.json', 'player-map.json', 'volume-map.json', 'search-map.json', 'README.md'):
        shutil.copyfile(original / name, bundle / name)
    (storage / 'input').mkdir(parents=True)
    shutil.copyfile(GAME / 'input/EMAIN.ELF', storage / 'input/EMAIN.ELF')
    (storage / 'gt5p_settings.toml').write_text(
        '[video]\nresolution = "1080p"\naspect = "21:9"\nmsaa = 8\n[game]\nsmooth_colour = true\nanisotropy = 16\n',
        encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('GT5P_', 'RSX_'))}
    env.update(PS3_VERBOSE='0', GT5P_PREPARE_ENUMERATE='0',
               GT5P_PREPARE_VOLUME_LIBRARY=str(install / 'preparation/volume_reader.dll'),
               GT5P_PREPARE_HASH_LIBRARY=str(install / 'preparation/cache_hash.dll'))
    base = [str(PY), str(ROOT / 'scripts/player_prepare.py'), '--install', str(install), '--storage', str(storage),
            '--game', str(GAME / 'input/pkg')]
    summary = dict(records=len(document['records']))
    status, pointer, cancel = storage / 'prepare-status.txt', storage / 'prepared-cache.txt', storage / 'prepare.cancel'

    # 1. full preparation, cancelled at the interpreter stage
    t = time.perf_counter()
    with (out / 'run1.log').open('wb') as stream:
        child = subprocess.Popen(base + ['--no-reuse'], env=env, stdout=stream, stderr=subprocess.STDOUT)
        seen = []
        while child.poll() is None:
            try:
                text = status.read_text(encoding='utf-8')
            except OSError:
                text = ''
            if text and (not seen or seen[-1] != text):
                seen.append(text)
            if text.startswith('Interpreter pipelines'):
                cancel.write_text('cancel')
                break
            time.sleep(0.005)
        code = child.wait(timeout=600)
    summary['run1'] = dict(code=code, seconds=round(time.perf_counter() - t, 1), statuses=seen[-6:])
    assert code == 2, (out / 'run1.log').read_text(errors='replace')[-3000:]
    assert seen and seen[-1].startswith('Interpreter pipelines'), seen
    assert not pointer.exists(), 'selection moved by a cancelled run'
    generations = list((storage / 'preparation').iterdir())
    assert len(generations) == 1
    generation = generations[0]
    cache = generation / 'shadercache'
    summary['run1']['ipso_after_cancel'] = len(list(cache.glob('ipso_*.bin')))
    summary['run1']['dxbc_after_cancel'] = len(list(cache.glob('*.dxbc')))
    cancel.unlink()

    # 2. resume
    t = time.perf_counter()
    r = subprocess.run(base, env=env, capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, (r.stdout + r.stderr)[-4000:]
    assert (storage / pointer.read_text()).parent == generation
    stage = json.loads((generation / 'interp-pipelines.json').read_text())
    summary['run2'] = dict(seconds=round(time.perf_counter() - t, 1), stage=stage)
    assert stage['status'] == 'complete' and stage['engine']['ready'] == stage['engine']['pipelines']
    report = json.loads((generation / 'report.json').read_text())
    assert report['counts'] == {'prepared': len(document['records'])}
    prepared = snapshot(cache)
    blobs = snapshot(cache, interp=True)

    # 3. stage only, on the selected cache
    t = time.perf_counter()
    r = subprocess.run(base + ['--interp-pipelines-only'], env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, (r.stdout + r.stderr)[-4000:]
    stage3 = json.loads((generation / 'interp-pipelines.json').read_text())
    summary['run3'] = dict(seconds=round(time.perf_counter() - t, 1), stage=stage3)
    assert stage3['engine']['previously_complete'] == 1 and stage3['engine']['disk_hit'] == stage3['engine']['pipelines']
    assert snapshot(cache) == prepared, 'interpreter stage changed prepared shaders or native blobs'
    assert snapshot(cache, interp=True) == blobs
    assert (storage / pointer.read_text()).parent == generation

    # 4. rollback switch
    env0 = dict(env, GT5P_PREPARE_INTERP_PIPELINES='0')
    r = subprocess.run(base + ['--interp-pipelines-only'], env=env0, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, (r.stdout + r.stderr)[-4000:]
    stage4 = json.loads((generation / 'interp-pipelines.json').read_text())
    assert stage4['status'] == 'skipped'
    assert snapshot(cache) == prepared and snapshot(cache, interp=True) == blobs
    summary['run4'] = stage4
    (out / 'validation.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps(summary, indent=1), flush=True)
    print('helper checks passed', flush=True)


if __name__ == '__main__':
    main()
