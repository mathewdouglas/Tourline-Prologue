"""One in-game run of the shader-text comparison (Phase 215): copy a prepared cache, play a scene, parse GPU time.

    despecialize_ingame.py --variant A|B --scene dealer720|dealer1080|hsr720|hsr1080|daytona1080|fuji1080
        --engine E --cache <prepared shadercache> --game <private game root> --output <dir> --tag NAME

Variant A runs the engine with RSX_VFETCH_LOOP=0 RSX_FP_REG_SIZE=0 (the previous shader text); B uses the
defaults. Each run starts from its own fresh copy of the prepared cache (removed afterwards, DXBC files the
run added are counted first). The scene scripts are scripts/test/winshot.ps1 (dealership) and race.ps1
(-FrameTest for High Speed Ring / Daytona / Fuji). GPU time is the mean of the engine's 5-second
`[present-prof]` "gpu" averages with the first one dropped. Window shots are saved by the scene scripts
(PrintWindow). Run through run_locked.py, one scene at a time. The private game root needs gamedata/ (a copy),
assets/ and input/EMAIN.ELF + an input/pkg junction to the read-only dump.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCENES = {   # name: (script, extra args, resolution, msaa)
    'dealer720': ('winshot.ps1', ['-Settle', '40', '-Shots', '2', '-Gap', '3'], '720p', '1'),
    'dealer1080': ('winshot.ps1', ['-Settle', '40', '-Shots', '2', '-Gap', '3'], '1080p', '2'),
    'hsr720': ('race.ps1', ['-Track', 'HighSpeedRing', '-FrameTest', '-Seconds', '60'], '720p', '1'),
    'hsr1080': ('race.ps1', ['-Track', 'HighSpeedRing', '-FrameTest', '-Seconds', '60'], '1080p', '2'),
    'daytona1080': ('race.ps1', ['-Track', 'Daytona', '-FrameTest', '-Seconds', '60'], '1080p', '2'),
    'fuji1080': ('race.ps1', ['-Track', 'FujiSpeedwayF', '-FrameTest', '-Seconds', '60'], '1080p', '2'),
}


def gpu_means(text):
    values = [float(m) for m in re.findall(r'\[present-prof\][^\r\n]*\| gpu ([0-9.]+) ms avg', text)]
    return values


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--variant', choices=('A', 'B'), required=True)
    ap.add_argument('--scene', choices=sorted(SCENES), required=True)
    for name in ('engine', 'cache', 'game', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--env', action='append', default=[])
    a = ap.parse_args()
    script, extra, resolution, msaa = SCENES[a.scene]
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = out / (a.tag + '.cache')
    if cache.exists():
        raise ValueError('Use a new tag')
    shutil.copytree(a.cache, cache)
    before = {p.name for p in cache.glob('*.dxbc')}
    game = a.game.resolve()
    variables = ['GT5P_RESOLUTION=' + resolution, 'RSX_MSAA=' + msaa, 'GT5P_PRESENT_PROF=1', 'RSX_PSO_TIMING=1',
                 'RSX_SHADER_CACHE=' + str(cache), 'GT5P_GAME_DIR=input/pkg/', 'PS3_VFS_ROOT=' + str(game),
                 'PS3_GAMEDATA_ROOT=' + str(game / 'gamedata'), 'RSX_SHADER_WARMUP=1', 'RSX_SHADER_WARMUP_SCAN=0',
                 'RSX_SHADER_WARMUP_BACKGROUND=1', 'RSX_PSO_ASYNC=1', 'RSX_SHADER_ASYNC=1', 'RSX_PSO_RECIPES=1',
                 'RSX_RACE_PREWARM=1', 'RSX_RACE_PREWARM_WAIT_MS=0', 'PAD_HOLD_MERGE=0', 'RSX_PRESENT_SYNC=1']
    if a.variant == 'A':
        variables += ['RSX_VFETCH_LOOP=0', 'RSX_FP_REG_SIZE=0']
    variables += a.env
    command = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'scripts/test' / script),
               '-Tag', a.tag, '-Engine', str(a.engine.resolve()), '-GameRoot', str(game),
               '-OutputDirectory', str(out)] + extra + variables
    env = {k: v for k, v in os.environ.items() if not k.startswith(('GT5P_', 'RSX_', 'PS3_', 'PAD_'))}
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=1500)
    log = (out / (a.tag + '.err'))
    text = log.read_text(errors='replace') if log.exists() else ''
    outlog = out / (a.tag + '.out')
    text += outlog.read_text(errors='replace') if outlog.exists() else ''
    gpu = gpu_means(text)
    kept = gpu[1:]
    after = {p.name for p in cache.glob('*.dxbc')}
    frames = out / (a.tag + '.frames.txt')
    summary = dict(tag=a.tag, variant=a.variant, scene=a.scene, returncode=result.returncode,
                   gpu_samples=len(gpu), gpu_mean_ms=statistics.mean(kept) if kept else None,
                   gpu_last6_mean_ms=statistics.mean(gpu[-6:]) if gpu else None,
                   new_dxbc=len(after - before), pso_fail=len(re.findall(r'PSO FAIL', text)),
                   device_removed=len(re.findall(r'DEVICE_(REMOVED|HUNG)|device removed', text, re.I)),
                   frames=frames.read_text().strip().splitlines() if frames.exists() else None,
                   script_output=result.stdout.strip().splitlines()[-4:])
    (out / (a.tag + '.summary.json')).write_text(json.dumps(summary, indent=2) + '\n')
    shutil.rmtree(cache)
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if result.returncode == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
