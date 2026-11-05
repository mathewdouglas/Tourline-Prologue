"""End to end: real launcher, frozen helper and private engine; first launch of a version. Invoke through run_locked.py.

Builds an install folder (launcher, private engine folder, frozen helper distribution, repository assets, a
release.ini carrying port_version) and a private data folder holding a copy of the configured ELF and a
setup.ini pointing at the original disc folder, which is only read. The first launch must show the one-time
update offer; "Prepare now" runs the full preparation through the real helper; the game then starts and is
stopped after a few seconds. A second launch must show no offer, ask the helper once more at most, and start
the game directly. Prints the wall time of each step. The game's own data stays in the private folder.

    python scripts/test/rc024_launcher_e2e.py --launcher <exe> --engine <runtime dir> --helper <dist dir> --output scratch/rc024/e2e
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
GAME = Path(r"C:\Users\GGPC\Dev\Recomps\GT5P")


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--helper', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--version', default='0.2.4')
    ap.add_argument('--drop-marker', action='store_true',
                    help='with --second-only: delete the answered marker first; a current selected preparation must recreate it without an offer')
    ap.add_argument('--second-only', action='store_true', help='reuse an existing --output: only the second launch')
    a = ap.parse_args()
    out = a.output.resolve()
    if (ROOT / 'scratch').resolve() not in out.parents or out.exists() != a.second_only:
        raise ValueError('Output must be a new folder under scratch (or an existing one with --second-only)')
    install, data = out / 'install', out / 'data'
    if not a.second_only:
        build_tree(a, out, install, data)
    run(a, out, install, data)


def build_tree(a, out, install, data):
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


def run(a, out, install, data):
    env = dict(os.environ, GT5P_USER_DIR=str(data), PS3_VERBOSE='0')
    for name in ('GT5P_PREPARE_OFFER', 'GT5P_PREPARE_UI', 'GT5P_PREPARE_VOLUME', 'PS3_HEADLESS'):
        env.pop(name, None)

    ui = C.WinDLL('user32')
    callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    ui.EnumWindows.argtypes = [callback, W.LPARAM]
    ui.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    ui.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    ui.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]

    def titles(pid):
        found = []

        @callback
        def visit(hwnd, unused):
            owner = W.DWORD()
            ui.GetWindowThreadProcessId(hwnd, C.byref(owner))
            if owner.value == pid:
                text = C.create_unicode_buffer(256)
                ui.GetWindowTextW(hwnd, text, len(text))
                found.append((hwnd, text.value))
            return True
        ui.EnumWindows(visit, 0)
        return found

    def game_running():
        listing = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq gt5p.exe', '/FO', 'CSV', '/NH'],
                                 capture_output=True, text=True).stdout
        return 'gt5p.exe' in listing.lower()

    def kill_game():
        subprocess.run(['taskkill', '/F', '/IM', 'gt5p.exe'], capture_output=True)

    def launch(label, answer, timeout):
        for name in ('play.out', 'play.err'):
            for attempt in range(40):   # the previous launch's handles close a moment after it exits
                try:
                    (data / 'logs' / name).unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(.5)
        begin = time.perf_counter()
        owner = subprocess.Popen([str(install / 'tourline-prologue.exe')], env=env)
        offered_at = prepared_at = started_at = None
        seen = set()
        try:
            while time.perf_counter() - begin < timeout:
                if owner.poll() is not None and not game_running():
                    break
                for hwnd, title in titles(owner.pid):
                    seen.add(title)
                    if title == 'Tourline Prologue' and offered_at is None and answer:
                        offered_at = time.perf_counter() - begin
                        ui.PostMessageW(hwnd, 0x400 + 102, answer, 0)   # TDM_CLICK_BUTTON
                # The helper's offline runs are gt5p.exe too; the launcher opens logs/play.out only for the game.
                if (data / 'logs' / 'play.out').exists() and started_at is None:
                    started_at = time.perf_counter() - begin
                    time.sleep(20)   # let it reach a window; then stop it
                    break
                time.sleep(.25)
        finally:
            kill_game()
            if owner.poll() is None:
                owner.terminate()
                owner.wait(timeout=30)
        row = dict(label=label, offer_seen_s=None if offered_at is None else round(offered_at, 1),
                   game_started_s=None if started_at is None else round(started_at, 1), windows=sorted(seen))
        print(row, flush=True)
        return row

    if game_running():
        raise SystemExit('Another gt5p.exe is running; nothing was stopped')
    marker = data / ('prepare-offer-%s.done' % a.version)
    first = None
    if not a.second_only:
        first = launch('first launch: Prepare now', 100, 3600)
        assert first['offer_seen_s'] is not None and first['game_started_s'] is not None, first
        time.sleep(3)
    if a.drop_marker:
        marker.unlink()
    else:
        assert marker.exists()
    assert (data / 'prepared-cache.txt').exists() and (data / 'prepared-identity.txt').exists()
    second = launch('second launch', None, 300)
    assert 'Tourline Prologue' not in second['windows'] and second['game_started_s'] is not None, second
    assert marker.exists(), 'the answered marker was not recorded'
    print('prepared cache:', (data / 'prepared-cache.txt').read_text(), flush=True)
    if first:
        print('first launch: offer at %.1f s, game start after %.1f s (preparation included)' % (first['offer_seen_s'], first['game_started_s']), flush=True)
    print('second launch: no offer, game start after %.1f s' % second['game_started_s'], flush=True)


if __name__ == '__main__':
    main()
