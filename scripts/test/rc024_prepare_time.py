"""Time one full player preparation through the frozen helper, per stage. Invoke through run_locked.py.

Assembles an install folder from a private engine, the frozen helper distribution and the repository's
assets, a fresh private storage (settings as the launcher's first-run preset writes them, a copy of the
configured ELF) and runs `GT5P-Prepare.exe --install ... --storage ... --game <disc>` exactly as the
launcher does, sampling prepare-status.txt twice a second. The original game files are only read.
Also times the read-only `--check-selected` question before (expect exit 3) and after (expect exit 0).

    python scripts/test/rc024_prepare_time.py --engine <runtime dir> --helper <GT5P-Prepare dist dir> --output scratch/rc024/prep
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
GAME = Path(r"C:\Users\GGPC\Dev\Recomps\GT5P")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine', type=Path, required=True, help='folder holding gt5p.exe and its DLLs')
    ap.add_argument('--helper', type=Path, required=True, help='frozen GT5P-Prepare distribution folder')
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    out = a.output.resolve()
    if (ROOT / 'scratch').resolve() not in out.parents:
        raise ValueError('Output must stay under scratch')
    if out.exists():
        raise ValueError('Use a fresh output folder')
    install, storage = out / 'install', out / 'storage'
    shutil.copytree(a.engine, install / 'runtime')
    shutil.copytree(a.helper, install / 'preparation')
    for name in ('pipeline-templates', 'shader-enumeration'):
        shutil.copytree(ROOT / 'assets' / name, install / 'assets' / name)
    (storage / 'input').mkdir(parents=True)
    shutil.copyfile(GAME / 'input' / 'EMAIN.ELF', storage / 'input' / 'EMAIN.ELF')
    (storage / 'gt5p_settings.toml').write_text(
        '[video]\nresolution = "720p"\naspect = "16:9"\nmsaa = 2\nshader_precompile = true\npipeline_async = true\n')
    helper = install / 'preparation' / 'GT5P-Prepare.exe'
    game = GAME / 'input' / 'pkg'
    env = {k: v for k, v in os.environ.items() if not k.startswith(('GT5P_PREPARE', 'GT5P_OFFLINE', 'RSX_'))}

    def check():
        begin = time.perf_counter()
        r = subprocess.run([str(helper), '--check-selected', '--install', str(install), '--storage', str(storage),
                            '--game', str(game)], cwd=storage, env=env, capture_output=True, text=True)
        return dict(exit=r.returncode, seconds=round(time.perf_counter() - begin, 2), stderr=r.stderr.strip()[-300:])

    result = dict(workers_note='helper picks 4 compiler workers on >=8 logical processors, else 2',
                  logical_processors=os.cpu_count(), check_before=check())
    print('check before:', result['check_before'], flush=True)
    status = storage / 'prepare-status.txt'
    stages, last = [], None
    begin = time.perf_counter()
    child = subprocess.Popen([str(helper), '--install', str(install), '--storage', str(storage), '--game', str(game)],
                             cwd=storage, env=env, stdout=(out / 'helper.out').open('wb'), stderr=(out / 'helper.err').open('wb'),
                             creationflags=subprocess.CREATE_NO_WINDOW)
    while child.poll() is None:
        try:
            text = status.read_text(encoding='utf-8')
        except OSError:
            text = ''
        word = ' '.join(text.split()[:2]) if text else ''
        if word and word != last:
            stages.append((round(time.perf_counter() - begin, 1), text))
            last = word
        time.sleep(.5)
    total = round(time.perf_counter() - begin, 1)
    result.update(exit=child.returncode, total_seconds=total, stages=stages,
                  final_status=status.read_text(encoding='utf-8') if status.exists() else '')
    result['check_after'] = check()
    print('check after:', result['check_after'], flush=True)
    selected = (storage / 'prepared-cache.txt')
    result['selected'] = selected.read_text() if selected.exists() else None
    size = sum(p.stat().st_size for p in (storage / 'preparation').rglob('*') if p.is_file()) if (storage / 'preparation').exists() else 0
    result['preparation_bytes'] = size
    (out / 'timing.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(child.returncode)


if __name__ == '__main__':
    main()
