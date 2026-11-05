r"""Exercise launcher/storage_link.h through storage_link_probe.exe in private temporary folders.

Build: cl /nologo /std:c++17 /EHsc /DUNICODE /D_UNICODE scripts\test\storage_link_probe.cpp
then: python scripts/test/storage_link.py --probe storage_link_probe.exe
With --launcher (scripts\release\build_launcher.cmd output), the launcher's own storage change
and start-up repair are checked too. They use a private GT5P_LAUNCHER_HOME and a stand-in
engine that is hashed, never started.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def launcher_check(launcher):
    with tempfile.TemporaryDirectory(prefix='GT5P storage link launcher ') as temp:
        root = Path(temp)
        install, home, chosen = root/'Install', root/'Home', root/'Chosen storage'
        (install/'runtime').mkdir(parents=True)
        shutil.copyfile(launcher, install/'tourline-prologue.exe')
        engine = install/'runtime/gt5p.exe'
        engine.write_bytes(b'stand-in engine, never started')
        (install/'release.ini').write_text('[release]\nschema=1\ntarget=BCUS98158\nversion=03.00\n'
            'elf_sha256=' + '0'*64 + '\ngame_sha256=' + hashlib.sha256(engine.read_bytes()).hexdigest() + '\n')
        home.mkdir()
        (home/'gt5p_settings.toml').write_text('[video]\nresolution = "1440p"\n')
        env = {k: v for k, v in os.environ.items() if k not in ('GT5P_USER_DIR', 'GT5P_STORAGE_LINK')}
        env.update(GT5P_LAUNCHER_HOME=str(home), GT5P_PREPARE_OFFER='0')

        def run(*args, **extra):
            return subprocess.run([str(install/'tourline-prologue.exe'), *args], env=dict(env, **extra),
                                  capture_output=True, timeout=60).returncode

        link = home/'selected-storage'
        assert run('--set-storage', str(chosen)) == 0
        assert link.is_junction() and os.path.samefile(link, chosen), 'storage change did not link'
        assert 'resolution = "1440p"' in (link/'gt5p_settings.toml').read_text(), 'settings not copied'
        link.rmdir()
        run('--check')   # fails later (no setup), after the start-up repair
        assert link.is_junction() and os.path.samefile(link, chosen), 'start-up did not repair the link'
        link.rmdir()
        run('--check', GT5P_STORAGE_LINK='0')
        assert not link.exists(), 'GT5P_STORAGE_LINK=0 still linked'
        run('--check')
        (home/'storage.ini').unlink()
        run('--check')
        assert not link.exists(), 'a stale link survived the return to default storage'
        assert (chosen/'gt5p_settings.toml').exists(), 'relocated storage was touched'
        print('launcher: storage change links, start-up repairs and clears, rollback switch: passed')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe', type=Path, required=True)
    ap.add_argument('--launcher', type=Path)
    args = ap.parse_args()
    probe = args.probe.resolve()
    if args.launcher:
        launcher_check(args.launcher.resolve())
    with tempfile.TemporaryDirectory(prefix='GT5P storage link ') as temp:
        root = Path(temp)
        home, first, second = root/'Home', root/'Storage one', root/'Storage two'
        for p in (home, first, second):
            p.mkdir()
        (first/'gt5p_settings.toml').write_text('[video]\nresolution = "720p"\n')
        (second/'gt5p_settings.toml').write_text('[video]\nresolution = "1080p"\n')
        link = home/'selected-storage'

        def run(target, expect=0):
            r = subprocess.run([str(probe), str(home), str(target) if target else '-'], capture_output=True, text=True)
            assert r.returncode == expect, (target, r.returncode, r.stdout)
            return r.stdout.strip()

        def points_to(path):
            assert link.is_junction(), 'not a junction'
            assert os.path.samefile(link, path), (os.readlink(link), path)

        run(None)
        assert not link.exists(), 'default storage needs no link'
        run(first)
        points_to(first)
        assert 'resolution = "720p"' in (link/'gt5p_settings.toml').read_text()
        (link/'written-through-link.txt').write_text('x')
        assert (first/'written-through-link.txt').exists()
        before = os.stat(link).st_ctime_ns
        run(first)
        points_to(first)
        assert os.stat(link).st_ctime_ns == before, 'an unchanged link is recreated'
        run(str(second) + os.sep)
        points_to(second)
        assert 'resolution = "1080p"' in (link/'gt5p_settings.toml').read_text()
        run(None)
        assert not link.exists()
        assert (first/'gt5p_settings.toml').exists() and (second/'gt5p_settings.toml').exists(), 'storage was removed'
        drive = Path(Path(temp).anchor)
        run(drive)
        points_to(drive)
        run(None)
        print('create, reuse, retarget, drive root and removal: passed')

        link.mkdir()
        (link/'real.txt').write_text('keep')
        assert 'not a junction' in run(first, 1)
        assert (link/'real.txt').read_text() == 'keep'
        run(None, 1)
        assert (link/'real.txt').exists()
        (link/'real.txt').unlink(); link.rmdir()
        assert 'network' in run(2 * os.sep + os.path.join('server', 'share', 'GT5P'), 1)
        assert not link.exists()
        print('real folder kept, network target refused: passed')


if __name__ == '__main__':
    main()
