"""Phase 225 end to end: real launcher, frozen helper and private engine, nothing prepared. Invoke through run_locked.py.

Builds an install folder (launcher, engine folder, frozen helper distribution, repository assets, release.ini) and a
private data folder (copy of the configured ELF, setup.ini naming the original disc folder, which is only read).

First launch: no offer window; the game starts and the helper runs beside it at idle priority. The game stays on
its menus until the helper reports the race stage merged into data/shadercache (its race list and recipes are
checked), then the game window is closed: the launcher must stop the helper (no GT5P-Prepare.exe or gt5p.exe
left, no prepare.cancel left, pause record written) and exit; the preparation stays resumable, nothing selected.
Second launch: the helper starts again and reports the race stage already merged; closed the same way.

    python scripts/test/background_launcher_e2e.py --launcher <exe> --engine <runtime dir> --helper <dist dir> --output scratch/bg/e2e
"""
import argparse
import csv
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
GAME = Path(r"C:\Users\GGPC\Dev\Recomps\GT5P")
IDLE = 0x40


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pids(image):
    listing = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {image}', '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True).stdout
    return [int(r[1]) for r in csv.reader(listing.splitlines()) if len(r) > 1 and r[0].lower() == image.lower()]


k = C.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.restype = W.HANDLE
k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.GetPriorityClass.argtypes = [W.HANDLE]
k.CloseHandle.argtypes = [W.HANDLE]
ui = C.WinDLL('user32')
callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
ui.EnumWindows.argtypes = [callback, W.LPARAM]
ui.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
ui.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
ui.IsWindowVisible.argtypes = [W.HWND]
ui.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]


def priority(pid):
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return None
    try:
        return k.GetPriorityClass(h)
    finally:
        k.CloseHandle(h)


def windows(owners):
    found = []

    @callback
    def visit(hwnd, unused):
        owner = W.DWORD()
        ui.GetWindowThreadProcessId(hwnd, C.byref(owner))
        if owner.value in owners and ui.IsWindowVisible(hwnd):
            text = C.create_unicode_buffer(256)
            ui.GetWindowTextW(hwnd, text, len(text))
            found.append((hwnd, owner.value, text.value))
        return True
    ui.EnumWindows(visit, 0)
    return found


def build_tree(a, install, data):
    shutil.copytree(a.engine, install / 'runtime')
    shutil.copytree(a.helper, install / 'preparation')
    shutil.copytree(ROOT / 'assets', install / 'assets')
    shutil.copyfile(a.launcher, install / 'tourline-prologue.exe')
    elf = GAME / 'input' / 'EMAIN.ELF'
    (install / 'release.ini').write_text(
        '[release]\nschema=1\ntarget=BCUS98158\nversion=03.00\nport_version=%s\nelf_sha256=%s\ngame_sha256=%s\nprepare_sha256=%s\n'
        % (a.version, sha(elf), sha(install / 'runtime/gt5p.exe'), sha(install / 'preparation/GT5P-Prepare.exe')))
    (data / 'input').mkdir(parents=True)
    shutil.copyfile(elf, data / 'input' / 'EMAIN.ELF')
    (data / 'setup.ini').write_text('[game]\ndirectory=%s\n' % (GAME / 'input' / 'pkg'), encoding='utf-16')


def launch(label, install, data, env, want, timeout):
    """Start the launcher; wait for `want` in the helper's output; close the game window; wait for exit."""
    for name in ('play.out', 'prepare-background.out'):
        for attempt in range(40):
            try:
                (data / 'logs' / name).unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(.5)
    begin = time.perf_counter()
    owner = subprocess.Popen([str(install / 'tourline-prologue.exe')], env=env)
    row = dict(label=label, game_started_s=None, wanted_s=None, closed_s=None, exited_s=None, priorities=set(),
               offer=False)
    out = data / 'logs' / 'prepare-background.out'
    try:
        while time.perf_counter() - begin < timeout:
            if owner.poll() is not None:
                break
            if any(t == 'Tourline Prologue' for _, _, t in windows({owner.pid})):
                row['offer'] = True
            if row['game_started_s'] is None and (data / 'logs' / 'play.out').exists():
                row['game_started_s'] = round(time.perf_counter() - begin, 1)
            for pid in pids('GT5P-Prepare.exe'):
                p = priority(pid)
                if p:
                    row['priorities'].add(p)
            text = out.read_text(encoding='utf-8', errors='replace') if out.exists() else ''
            if want in text:
                row['wanted_s'] = round(time.perf_counter() - begin, 1)
                row['line'] = next(line for line in text.splitlines() if want in line)[:1000]
                break
            time.sleep(1)
        # Close the game the way a player does; the launcher must then stop the helper and exit.
        games = set(pids('gt5p.exe'))
        targets = [w for w in windows(games) if w[2]]
        for hwnd, pid, title in targets:
            ui.PostMessageW(hwnd, 0x10, 0, 0)   # WM_CLOSE
        row['closed_s'] = round(time.perf_counter() - begin, 1)
        row['closed_windows'] = [t for _, _, t in targets]
        owner.wait(timeout=180)
        row['exited_s'] = round(time.perf_counter() - begin, 1)
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.wait(timeout=30)
    row['priorities'] = sorted(row['priorities'])
    row['left_running'] = dict(helper=pids('GT5P-Prepare.exe'), game=pids('gt5p.exe'))
    print(json.dumps(row), flush=True)
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--helper', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--version', default='0.2.5')
    a = ap.parse_args()
    out = a.output.resolve()
    if (ROOT / 'scratch').resolve() not in out.parents or out.exists():
        raise ValueError('Output must be a new folder under scratch')
    if pids('gt5p.exe') or pids('GT5P-Prepare.exe'):
        raise SystemExit('Another gt5p.exe or GT5P-Prepare.exe is running; nothing was stopped')
    install, data = out / 'install', out / 'data'
    build_tree(a, install, data)
    env = dict(os.environ, GT5P_USER_DIR=str(data), PS3_VERBOSE='0')
    for name in ('GT5P_PREPARE_OFFER', 'GT5P_PREPARE_UI', 'GT5P_PREPARE_VOLUME', 'PS3_HEADLESS', 'GT5P_PREPARE_BACKGROUND',
                 'GT5P_PREPARE_BACKGROUND_PAUSE', 'GT5P_RACE_EVENT', 'GT5P_NO_SETTINGS'):
        env.pop(name, None)
    first = launch('first launch', install, data, env, 'Background race stage:', 900)
    assert not first['offer'] and first['game_started_s'] is not None and first['wanted_s'] is not None, first
    assert '"status": "merged"' in first['line'] and first['priorities'] == [IDLE], first
    assert first['exited_s'] is not None and first['left_running'] == dict(helper=[], game=[]), first
    race = (data / 'shadercache/warmup-v1/race-v1.txt').read_text().split()
    recipes = len(list((data / 'shadercache/warmup-v1').glob('pso_*.recipe')))
    assert len(set(race)) >= 2000 and recipes >= 2000, (len(race), recipes)
    assert not (data / 'prepare.cancel').exists() and (data / 'logs/prepare-background-pause.txt').is_file()
    assert not (data / 'prepared-cache.txt').exists(), 'selected before the full stage completed'
    states = [json.loads(p.read_text()) for p in (data / 'preparation').glob('*/preparation-state.json')]
    assert all(s.get('phase') != 'complete' for s in states), states   # resumable (the full stage may not have begun)
    print(f'first launch: game at {first["game_started_s"]} s, race stage merged at {first["wanted_s"]} s, '
          f'launcher exited {first["exited_s"] - first["closed_s"]:.1f} s after the window closed; '
          f'race list {len(set(race))} keys, {recipes} recipes', flush=True)
    time.sleep(3)
    second = launch('second launch', install, data, env, 'Background race stage:', 300)
    assert not second['offer'] and '"already-merged"' in second['line'], second
    assert second['left_running'] == dict(helper=[], game=[]), second
    print(f'second launch: race stage already merged at {second["wanted_s"]} s; exited cleanly', flush=True)


if __name__ == '__main__':
    main()
