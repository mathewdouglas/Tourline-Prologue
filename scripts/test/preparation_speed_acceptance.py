"""Private engine/helper build and fresh preparation acceptance, with cleanup.

Run in an x64 VS environment under isolated_validation.ps1. Reuse unchanged
objects from a completed read-only Release build; every new output lives in a
TemporaryDirectory. This never rebuilds over the reference or copies a game.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def build_engine(reference, fresh):
    source_root = reference.parent
    source = source_root/'src/gt5p_present.cpp'
    obj = r'CMakeFiles\gt5p.dir\src\gt5p_present.cpp.obj'
    commands = subprocess.check_output(['ninja', '-t', 'commands', obj], cwd=reference, text=True)
    command = commands.splitlines()[-1]
    assert str(source) in command and command.startswith('"C:\\Program Files\\LLVM\\bin\\clang-cl.exe"')
    objects = fresh/'objects'
    (objects/'src').mkdir(parents=True)
    command = command.replace(str(source), str(ROOT/'src/gt5p_present.cpp'))
    command = command.replace(r'CMakeFiles\gt5p.dir', str(objects))
    assert str(objects/'src/gt5p_present.cpp.obj') in command
    assert '/Fo'+str(objects) in command and '/Fd'+str(objects) in command
    subprocess.run(command, cwd=fresh, check=True)
    lines = (reference/'build.ninja').read_text().splitlines()
    link = next(i for i, line in enumerate(lines) if line.startswith('build gt5p.exe: '))
    inputs = lines[link].split('Release ', 1)[1].split(' | ')[0].split()
    libraries = next(line.split(' = ',1)[1] for line in lines[link+1:link+15] if line.startswith('  LINK_LIBRARIES = ')).split()
    runtime = fresh/'install/runtime'
    runtime.mkdir(parents=True)
    clang = r'C:\Program Files\LLVM\bin\clang-cl.exe'
    linker = r'C:\Program Files\LLVM\bin\lld-link.exe'
    args = [linker, '/nologo', '/machine:x64', '/INCREMENTAL:NO', '/subsystem:console']
    args += [str(objects/'src/gt5p_present.cpp.obj') if item == obj else str(reference/item) for item in inputs]
    args += [str(reference/name) if '\\' in name else name for name in libraries]
    args += ['/out:'+str(runtime/'gt5p.exe'), '/pdb:'+str(fresh/'gt5p.pdb'), '/implib:'+str(fresh/'gt5p.lib')]
    subprocess.run(args, cwd=fresh, check=True)
    for dll in reference.glob('*.dll'):
        shutil.copyfile(dll, runtime/dll.name)
    subprocess.run([clang, '/nologo', '/std:c++20', '/O2', '/MD', '/EHsc',
        '/Fo'+str(fresh/'offline-test.obj'), '/Fe'+str(fresh/'offline-test.exe'),
        str(ROOT/'scripts/test/offline_prepare.cpp')], cwd=fresh, check=True)
    subprocess.run([str(fresh/'offline-test.exe')], check=True)
    return runtime/'gt5p.exe'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('reference-build', 'reference-helper', 'runtime', 'elf', 'volume', 'game-root', 'game', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    ap.add_argument('--skip-full', action='store_true')
    ap.add_argument('--worker-study', action='store_true', help='Fresh full 2/3/4-worker comparison plus verification ABBA reads')
    a = ap.parse_args()
    if os.environ.get('VSCMD_ARG_TGT_ARCH','').lower() != 'x64':
        raise ValueError('Use an x64 VS environment')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = []
    def run(name, args, env=None):
        begin = time.perf_counter()
        print('Starting '+name, flush=True)
        with (out/(name+'.log')).open('wb') as log:
            subprocess.run([str(x) for x in args], cwd=ROOT, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        results.append(dict(step=name, seconds=time.perf_counter()-begin))
        (out/'acceptance-status.json').write_text(json.dumps(results, indent=2)+'\n')

    with tempfile.TemporaryDirectory(prefix='p208-build-', dir=ROOT/'scratch') as directory:
        fresh = Path(directory)
        engine = build_engine(a.reference_build.resolve(), fresh)
        base = [sys.executable, ROOT/'scripts/test/preparation_fresh_native.py',
            '--engine', engine, '--decoder', a.reference_helper/'decoder.dll',
            '--hash-library', a.reference_helper/'cache_hash.dll',
            '--volume-library', a.reference_helper/'volume_reader.dll',
            '--game-root', a.game_root, '--elf', a.elf, '--volume', a.volume]
        chosen_workers = '2'
        run('fresh-32', base+['--limit','32','--output',out/'fresh-32.json'])
        if a.worker_study:
            reports = []
            for workers in ('2','3','4'):
                env = dict(os.environ,GT5P_PREPARE_COMPILER_WORKERS=workers,
                    GT5P_PREPARE_VERIFY_BATCH='1' if workers=='2' else '32')
                args = base+['--profile','--output',out/('workers-'+workers+'.json')]
                if workers=='4':args+=['--compare-verification']
                run('workers-'+workers,args,env)
                reports.append(json.loads((out/('workers-'+workers+'.json')).read_text()))
            pack_ids = lambda report: {phase:(values['sha256'],values['file_bytes'])
                for phase,values in report['shader_packs']['phases'].items()}
            assert all(pack_ids(report)==pack_ids(reports[0]) for report in reports)
            assert all(report['vertex']['limits']['worker_job_commit_bytes']==1024**3 for report in reports)
            assert all(report['test_cache_removed'] for report in reports)
            chosen_workers = min(reports,key=lambda report:report['vertex']['seconds']+report['fragment']['seconds'])['compiler_workers']
            (out/'worker-study.json').write_text(json.dumps(dict(chosen_workers=chosen_workers,
                identical_packs=True,unchanged_vertex_job_memory_bytes=1024**3,
                limitation='Ordered 2/3/4 fresh application-cache runs; OS/driver caches preserved.'),indent=2)+'\n')
        elif not a.skip_full:
            run('fresh-optimized', base+['--profile','--output',out/'fresh-optimized.json'])
        rollback = dict(os.environ, GT5P_PREPARE_VERTEX_POLL_MS='100', GT5P_PREPARE_OFFLINE_WARMUP='1',
            GT5P_PREPARE_COMPILER_WORKERS='2',GT5P_PREPARE_VERIFY_BATCH='1')
        run('fresh-rollback-32', base+['--limit','32','--output',out/'fresh-rollback-32.json'], rollback)
        fast = json.loads((out/'fresh-32.json').read_text())
        old = json.loads((out/'fresh-rollback-32.json').read_text())
        assert not any(p['warmup_replayed'] for p in fast['offline_processes'])
        assert any(p['warmup_replayed'] for p in old['offline_processes'])
        assert fast['vertex']['limits'] == old['vertex']['limits']
        assert fast['vertex']['poll_seconds'] == .01 and old['vertex']['poll_seconds'] == .1
        helper = fresh/'helper'
        run('freeze-helper', [sys.executable, ROOT/'scripts/release/build_preparer.py',
            '--runtime', a.runtime, '--decoder', a.reference_helper/'decoder.dll', '--output', helper])
        run('frozen-checkpoint', [sys.executable, ROOT/'scripts/test/player_fragment_checkpoint_native.py',
            '--helper-dir', helper/'dist/GT5P-Prepare', '--reference-install', engine.parent.parent,
            '--elf', a.elf, '--game', a.game, '--output', fresh/'f'],
            dict(os.environ,GT5P_PREPARE_COMPILER_WORKERS=chosen_workers,GT5P_PREPARE_VERIFY_BATCH='32'))
        validation = json.loads((fresh/'f/validation.json').read_text())
        (out/'frozen-validation.json').write_text(json.dumps(validation, indent=2)+'\n')
        engine_hash = hashlib.sha256(engine.read_bytes()).hexdigest()
    result = dict(passed=True, steps=results, private_build_removed=not fresh.exists(), engine_sha256=engine_hash)
    assert result['private_build_removed']
    (out/'acceptance.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
