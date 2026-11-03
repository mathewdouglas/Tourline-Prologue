"""Link a private gt5p.exe with the fragment sample-qualifier overlay.

Applies patches/ps3recomp-4e8f3ca8-local.patch, then
patches/ps3recomp-fp-sample-share.patch, and recompiles libs/video/rsx_d3d12_backend.c
with the reference ninja command. The new object is linked ahead of the
read-only runtime archive. Every other object stays the reference build.
RSX_FP_SAMPLE_SHARE is off unless a later process sets it.

Run from an x64 VS environment (vcvars64.bat). Output stays under scratch.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(r'C:\GT5P-CI\tourline-runtime-cache\d2be355a7fe73c59750f')
NAME = 'libs/video/rsx_d3d12_backend.c'
HEADER = 'libs/video/rsx_offline_batch.h'


def patched_source(dest):
    """Upstream backend, current main patch, then the sample-share overlay."""
    dest = Path(dest).resolve()
    scratch = (ROOT / 'scratch').resolve()
    if dest != scratch and scratch not in dest.parents:
        raise ValueError('Patched runtime source must stay under scratch')
    if dest.exists():
        shutil.rmtree(dest)
    video = dest / 'libs' / 'video'
    video.mkdir(parents=True)
    original = subprocess.check_output(['git', '-C', str(RUNTIME), 'show', 'HEAD:' + NAME])
    (dest / NAME).write_bytes(original)
    subprocess.run(['git', 'init', '-q', str(dest)], check=True)
    subprocess.run(['git', '-C', str(dest), 'config', 'core.autocrlf', 'false'], check=True)
    main = ROOT / 'patches' / 'ps3recomp-4e8f3ca8-local.patch'
    overlay = ROOT / 'patches' / 'ps3recomp-fp-sample-share.patch'
    subprocess.run(['git', '-C', str(dest), 'apply', '--whitespace=nowarn',
                    '--include=' + NAME, '--include=' + HEADER, str(main)], check=True)
    subprocess.run(['git', '-C', str(dest), 'apply', '--whitespace=nowarn',
                    '--include=' + NAME, str(overlay)], check=True)
    text = (dest / NAME).read_text(encoding='utf-8')
    if text.count('if (ss && fp_sample_qualifier(cube_mask))') != 1:
        raise ValueError('Overlay did not install the sample-qualifier call')
    if 'if (ss && ((cube_mask >> 16) & 0xFu) > 1)' in text:
        raise ValueError('Overlay left the old sample-count test in place')
    return dest / NAME


def link_engine(reference, fresh, backend):
    """Same link as build_engine, without rebuilding gt5p_present.cpp or offline-test."""
    lines = (reference / 'build.ninja').read_text(encoding='utf-8').splitlines()
    link = next(i for i, line in enumerate(lines) if line.startswith('build gt5p.exe: '))
    inputs = lines[link].split('Release ', 1)[1].split(' | ')[0].split()
    libraries = next(line.split(' = ', 1)[1] for line in lines[link + 1:link + 15]
                     if line.startswith('  LINK_LIBRARIES = ')).split()
    runtime = fresh / 'install' / 'runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    linker = r'C:\Program Files\LLVM\bin\lld-link.exe'
    args = [linker, '/nologo', '/machine:x64', '/INCREMENTAL:NO', '/subsystem:console']
    args += [str(reference / item) for item in inputs]
    args.append(str(backend))
    args += [str(reference / name) if '\\' in name else name for name in libraries]
    args += ['/out:' + str(runtime / 'gt5p.exe'), '/pdb:' + str(fresh / 'gt5p.pdb'),
             '/implib:' + str(fresh / 'gt5p.lib')]
    subprocess.run(args, cwd=fresh, check=True)
    for dll in reference.glob('*.dll'):
        shutil.copyfile(dll, runtime / dll.name)
    return runtime / 'gt5p.exe'


def build(reference, fresh):
    if os.environ.get('VSCMD_ARG_TGT_ARCH', '').lower() != 'x64':
        raise ValueError('Use an x64 VS environment (vcvars64.bat)')
    source_root = fresh / 'runtime-source'
    source = patched_source(source_root)
    obj = r'ps3recomp\CMakeFiles\ps3recomp_runtime.dir\libs\video\rsx_d3d12_backend.c.obj'
    command = subprocess.check_output(['ninja', '-t', 'commands', obj], cwd=reference, text=True).splitlines()[-1]
    runtime_source = str(RUNTIME / NAME)
    if runtime_source not in command:
        raise ValueError('Reference compile command does not name the runtime backend')
    objects = fresh / 'backend-objects'
    (objects / 'libs' / 'video').mkdir(parents=True, exist_ok=True)
    command = command.replace(runtime_source, str(source))
    command = command.replace(r'ps3recomp\CMakeFiles\ps3recomp_runtime.dir', str(objects))
    if '/Fo' + str(objects) not in command or ' -c -- ' not in command:
        raise ValueError('Compile command did not retarget the object output')
    command = command.replace(' -c -- ', ' /D_CRT_SECURE_NO_WARNINGS /W0 -c -- ')
    subprocess.run(command, cwd=fresh, check=True)
    backend = objects / 'libs' / 'video' / 'rsx_d3d12_backend.c.obj'
    if not backend.is_file():
        raise ValueError('Backend object was not produced')
    return link_engine(reference, fresh, backend)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference-build', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    engine = build(args.reference_build.resolve(), args.output.resolve())
    print(f'engine {engine}')


if __name__ == '__main__':
    sys.exit(main())
