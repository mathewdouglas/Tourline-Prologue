"""One Phase 220 in-game run (High Speed Ring FrameTest) with the interpreter on. Invoke through run_locked.py.

--shape user     1080p, 21:9 native ultrawide, 8x MSAA, per-sample shading (the user's settings)
--shape default  1080p, 16:9, 2x MSAA, per-sample shading
--seed DIR       copy this cache (scratch only) first; otherwise the private cache starts empty
--stage          run the helper's interpreter stage (offline engine) on the cache before the game
--prep 0|1       RSX_SHADER_INTERP_PIPELINE_PREP for the game (0 = rollback / Phase 216 behaviour)

Writes scratch/interp-prep-game/<tag>.json with the interpreter counters, the class-preparation
report and frame-interval statistics (startup and the FrameTest window).
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
PY = r'C:\GT5P-CI\venv\Scripts\python.exe'
SHAPES = {
    'user': dict(GT5P_RESOLUTION='1080p', GT5P_ULTRAWIDE='1', RSX_MSAA='8', RSX_SSAA='1'),
    'default': dict(GT5P_RESOLUTION='1080p', RSX_MSAA='2', RSX_SSAA='1'),
}


def last(pattern, text):
    found = re.findall(pattern, text)
    return found[-1] if found else None


def intervals(path):
    rows = [float(line.split(',')[0]) for line in path.read_text().splitlines() if line.count(',') == 2]
    return rows


def stats(times):
    d = [b - a for a, b in zip(times, times[1:])]
    if not d:
        return {}
    s = sorted(d)
    return dict(frames=len(d), mean=round(sum(d) / len(d), 2), p99=round(s[int(len(s) * 0.99) - 1], 1),
                max=round(s[-1], 1), over50=sum(x > 50 for x in d), over100=sum(x > 100 for x in d))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--shape', choices=SHAPES, required=True)
    ap.add_argument('--seed', type=Path)
    ap.add_argument('--stage', action='store_true')
    ap.add_argument('--prep', choices=('0', '1'), required=True)
    ap.add_argument('--engine', type=Path, default=ROOT / 'build' / 'gt5p.exe')
    a = ap.parse_args()
    scratch = (ROOT / 'scratch').resolve()
    cache = scratch / 'caches' / ('run-' + a.tag)
    if cache.exists():
        shutil.rmtree(cache)
    if a.seed:
        seed = a.seed.resolve()
        assert seed.is_relative_to(scratch)
        subprocess.run(['robocopy', str(seed), str(cache), '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/MT:8'])
    cache.mkdir(parents=True, exist_ok=True)
    result = dict(tag=a.tag, shape=a.shape, seed=str(a.seed) if a.seed else None, prep=a.prep, stage=a.stage)
    if a.stage:
        import interp_pipeline_prep as stage
        from shader_reconstruct import offline_env, run_offline
        storage = scratch / 'interp-prep-game' / ('stage-' + a.tag)
        if storage.exists():
            shutil.rmtree(storage)
        (storage / 'input').mkdir(parents=True)
        shutil.copyfile(r'C:\Users\GGPC\Dev\Recomps\GT5P\input\EMAIN.ELF', storage / 'input' / 'EMAIN.ELF')
        msaa = SHAPES[a.shape]['RSX_MSAA']
        (storage / 'gt5p_settings.toml').write_text(f'[video]\nmsaa = {msaa}\n', encoding='utf-8')
        r = stage.prepare(a.engine.resolve(), storage, cache, storage, ROOT / 'assets/pipeline-templates/gt5p-disc-v2',
                          storage, offline_env(storage, cache), run_offline)
        result['stage_report'] = r
        shutil.rmtree(storage / 'input')
    env = [f'{k}={v}' for k, v in SHAPES[a.shape].items()]
    env += ['RSX_SHADER_INTERP_PSO_DISK=1', 'RSX_SHADER_INTERP_PSO_ASYNC=1',
            'RSX_SHADER_INTERP_PIPELINE_PREP=' + a.prep]
    cmd = [PY, str(ROOT / 'scripts/test/interp_game_probe.py'), 'race', '--tag', a.tag, '--cache', str(cache),
           '--fp', '1', '--vp', '1', '--frame-test', '--no-foreground', '--engine', str(a.engine.resolve())]
    if not a.seed:
        cmd.append('--cold')
    for e in env:
        cmd += ['--env', e]
    runs = scratch / 'interp-runs' / a.tag
    if runs.exists():
        shutil.rmtree(runs)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, errors='replace')
    result['probe_returncode'] = p.returncode
    result['frame_test'] = last(r'FrameTest: ([^\r\n]+)', p.stdout)
    err = (ROOT / 'scratch/pv' / (a.tag + '.err'))
    text = err.read_text(errors='replace') if err.is_file() else ''
    for name, pattern in (('interp', r'\[interp\] draws [^\r\n]+'), ('interp_pso', r'\[interp-pso\] [^\r\n]+'),
                          ('interp_vp', r'\[interp-vp\] draws [^\r\n]+'), ('pending', r'\[interp-pending\] [^\r\n]+'),
                          ('prep_use', r'\[interp-prep\] use [^\r\n]+'), ('prep_queued', r'\[interp-prep\] queued [^\r\n]+'),
                          ('prep_report', r'\[interp-prep\] version=1 [^\r\n]+')):
        result[name] = last(pattern, text)
    frames = ROOT / 'scratch/pv' / (a.tag + '.frames.csv')
    if frames.is_file():
        t = intervals(frames)
        if t:
            result['startup_60s'] = stats([x for x in t if x - t[0] <= 60000])
            result['whole_run'] = stats(t)
    result['ipso_files'] = len(list(cache.glob('ipso_*.bin')))
    result['ipso_set_markers'] = [m.name for m in cache.glob('ipso-set-*.txt')]
    out = scratch / 'interp-prep-game'
    out.mkdir(exist_ok=True)
    (out / (a.tag + '.json')).write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps(result, indent=1), flush=True)
    if os.environ.get('INTERP_KEEP_CACHE') != '1' and a.seed:
        shutil.rmtree(cache, ignore_errors=True)   # keep only small cold caches; prepared copies are 1.2 GB


if __name__ == '__main__':
    main()
