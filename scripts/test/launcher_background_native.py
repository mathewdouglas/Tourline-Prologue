"""Phase 225 background preparation in the launcher, against owned synthetic children; never starts the game.

A configured install without a completed preparation of this release starts the helper beside the game: no
offer, idle priority, --background with the cache the game uses, and prepare.cancel when the game exits (the
helper's job is closed after it). A selected, current preparation starts nothing and is remembered so later
launches skip the helper check. GT5P_PREPARE_BACKGROUND=0, GT5P_PREPARE_OFFER=0 and --no-prepared start nothing.
Settings restarts keep the helper running. While the game signals a race (GT5P_RACE_EVENT) every process of the
helper's job is suspended, and resumed back in the menus (GT5P_PREPARE_BACKGROUND_PAUSE=0: no event, no pause).
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from launcher_native import sfo

IDLE = 0x40


def read(path):
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8-sig').splitlines() if '=' in line)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--probe', type=Path, required=True)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='Tourline background ') as temp:
        root = Path(temp)
        install, disc = root/'Install', root/'Game/PS3_GAME'
        for p in (install/'runtime', install/'preparation', install/'assets', disc/'USRDIR'):
            p.mkdir(parents=True)
        (install/'assets/probe.txt').write_text('synthetic distributable art')
        (disc/'PARAM.SFO').write_bytes(sfo())
        for name in ('GT.VOL', 'TV.DAT'):
            (disc/'USRDIR'/name).write_bytes(b'synthetic')
        launcher = install/'tourline-prologue.exe'
        shutil.copyfile(args.launcher, launcher)
        for destination in ('runtime/gt5p.exe', 'preparation/GT5P-Prepare.exe'):
            shutil.copyfile(args.probe, install/destination)
        elf = b'\x7fELF synthetic background executable'
        probe_hash = hashlib.sha256(args.probe.read_bytes()).hexdigest()
        version = '0.2.5'
        (install/'release.ini').write_text('[release]\nschema=1\ntarget=BCUS98158\nversion=03.00\nport_version='+version
            +'\nelf_sha256='+hashlib.sha256(elf).hexdigest()+'\ngame_sha256='+probe_hash+'\nprepare_sha256='+probe_hash+'\n')
        # label, extra env, launcher args, prepared pointer, expect background, expect helper checks
        cases = [('background', {}, [], None, True, 1),
                 ('background-old-selection', {}, [], 'preparation/0123456789abcdef01234567/shadercache', True, 1),
                 ('background-helper-finishes', {'GT5P_PROBE_BACKGROUND_MS': '50', 'GT5P_PROBE_DELAY_MS': '1500'}, [], None, True, 1),
                 ('background-restart', {'GT5P_PROBE_RESTART_ONCE': '1'}, [], None, True, 1),
                 ('background-race-pause', {'GT5P_PROBE_RACE': '1', 'GT5P_PROBE_DELAY_MS': '300'}, [], None, True, 1),
                 ('background-no-pause', {'GT5P_PROBE_RACE': '1', 'GT5P_PREPARE_BACKGROUND_PAUSE': '0'}, [], None, True, 1),
                 ('already-prepared', {'GT5P_PROBE_SELECTED': '1'}, [], 'preparation/0123456789abcdef01234567/shadercache', False, 1),
                 ('check-error', {'GT5P_PROBE_SELECTED': 'error'}, [], None, False, 1),
                 ('background-disabled', {'GT5P_PREPARE_BACKGROUND': '0', 'GT5P_PREPARE_OFFER': '0'}, [], None, False, 0),
                 ('offer-disabled', {'GT5P_PREPARE_OFFER': '0'}, [], None, False, 0),
                 ('no-prepared', {}, ['--no-prepared'], None, False, 0)]
        for label, extra, flags, pointer, expect, checks in cases:
            data = root/label
            (data/'input').mkdir(parents=True)
            (data/'input/EMAIN.ELF').write_bytes(elf)
            (data/'setup.ini').write_text('[game]\ndirectory='+str(disc)+'\n', encoding='utf-16')
            # Offer answered already: background mode must not depend on the old marker.
            (data/('prepare-offer-'+version+'.done')).write_text('answered\n')
            if pointer:
                (data/'prepared-cache.txt').write_text(pointer, encoding='utf-8')
                (data/pointer).mkdir(parents=True)
            env = dict(os.environ, GT5P_USER_DIR=str(data), PS3_VERBOSE='0', GT5P_PROBE_DELAY_MS='400',
                       GT5P_PROBE_SELECTED='0')
            for name in ('GT5P_PREPARE_OFFER', 'GT5P_PREPARE_BACKGROUND', 'GT5P_PREPARE_VOLUME', 'GT5P_PROBE_BACKGROUND_MS',
                         'GT5P_PREPARE_BACKGROUND_PAUSE', 'GT5P_RACE_EVENT', 'GT5P_PROBE_RACE'):
                env.pop(name, None)
            env.update(extra)
            done = subprocess.run([launcher]+flags, env=env, timeout=60)
            assert done.returncode == 0, (label, done.returncode, (data/'logs/setup.err').read_text() if (data/'logs/setup.err').exists() else '')
            assert (data/'probe.txt').exists(), (label, 'game did not start')
            record = data/'background.txt'
            assert record.exists() == expect, (label, 'background started' if record.exists() else 'background missing')
            asked = (data/'check.txt').read_text(encoding='utf-8-sig').count('argc=') if (data/'check.txt').exists() else 0
            assert asked == checks, (label, 'helper checks', asked)
            assert not (data/'prepare.cancel').exists(), (label, 'cancel request left behind')
            if expect:
                text = record.read_text(encoding='utf-8-sig')
                assert text.count('argc=') == 1, (label, 'helper started more than once', text)
                values = read(record)
                argv = [values['arg'+str(i)] for i in range(int(values['argc']))]
                assert int(values['priority']) == IDLE, (label, 'priority', values['priority'])
                assert '--background' in argv and argv[argv.index('--storage')+1] == str(data), (label, argv)
                assert Path(argv[argv.index('--game')+1]) == disc.resolve(), (label, argv)
                live = Path(argv[argv.index('--live-cache')+1])
                assert live == (data/pointer if pointer else data/'shadercache').resolve(), (label, live)
                assert live.is_dir(), (label, 'live cache not created')
                want = 'finished' if label == 'background-helper-finishes' else 'cancelled'
                assert values['outcome'] == want, (label, values['outcome'])
                assert (data/'logs/prepare-background.out').exists(), label
                game = read(data/'probe.txt')
                if label == 'background-race-pause':
                    assert game['race_event'] == 'opened' and game['race_paused'] == '1' and game['race_resumed'] == '1', (label, game)
                    pause = read(data/'logs/prepare-background-pause.txt')
                    assert int(pause['pauses']) == 1 and 1000 <= int(pause['paused_ms']) <= 3000, (label, pause)
                elif label == 'background-no-pause':
                    assert 'race_event' not in game, (label, game)   # no event was created or passed on
                else:
                    assert 'race_paused' not in game, label
                if label == 'background-restart':
                    assert len((data/'restart-pids.txt').read_text(encoding='utf-8-sig').split()) == 2, (label, 'no restart')
            if label == 'already-prepared':
                # Remembered: the next launch does not ask the helper again.
                remembered = data/('prepare-current-'+version+'.txt')
                assert remembered.read_text(encoding='utf-8') == pointer, (label, 'not remembered')
                again = subprocess.run([launcher], env=dict(env, GT5P_PROBE_DELAY_MS='0'), timeout=30)
                assert again.returncode == 0 and (data/'check.txt').read_text(encoding='utf-8-sig').count('argc=') == 1, label
                assert not record.exists(), label
            print(label+': passed', flush=True)


if __name__ == '__main__':
    main()
