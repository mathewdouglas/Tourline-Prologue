"""Run a command while other processes use the CPU, as a browser, a build or a scanner would.

    python scripts/test/background_load.py --threads 8 [--after-game 50] [--seconds 180] -- <command...>

Starts <threads> single-threaded busy processes at normal priority, not pinned, once gt5p.exe has been
running for --after-game seconds, and stops them after --seconds or when the command ends. The game's guest
threads are confined to four logical CPUs, so this is the test for frames lost to other programs
(GT5P_PRIORITY_CLASS, Phase 237). Call it inside the machine-wide test lock: it loads the whole machine.
"""
import argparse
import subprocess
import sys
import threading
import time


def game_running():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq gt5p.exe', '/NH'], capture_output=True, text=True).stdout
    return 'gt5p.exe' in out.lower()


def load(a, stop, log):
    while not stop.is_set() and not game_running():
        time.sleep(0.5)
    if stop.wait(a.after_game):
        return
    spin = [subprocess.Popen([sys.executable, '-c', 'while True: pass']) for _ in range(a.threads)]
    log.append(('start', time.time()))
    stop.wait(a.seconds)
    for p in spin:
        p.kill()
    for p in spin:
        p.wait()
    log.append(('stop', time.time()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--threads', type=int, default=8)
    ap.add_argument('--after-game', type=float, default=50)
    ap.add_argument('--seconds', type=float, default=180)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    command = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not command:
        ap.error('a command is required after --')
    stop, log = threading.Event(), []
    worker = threading.Thread(target=load, args=(a, stop, log), daemon=True)
    worker.start()
    try:
        code = subprocess.run(command).returncode
    finally:
        stop.set(); worker.join(timeout=30)
    for what, at in log:
        print(f'[background-load] {what} unix_ms={int(at * 1000)} threads={a.threads}', flush=True)
    sys.exit(code)


if __name__ == '__main__':
    main()
