"""Private engine and decoder for the shader de-specialization work (Phase 215).

Builds a runtime tree (pinned ps3recomp commit + patches/ps3recomp-4e8f3ca8-local.patch + any overlays),
recompiles the three translator-facing sources (the D3D12 backend and both decompilers) with the reference
build's own compile commands, and relinks gt5p.exe from the read-only reference objects. It also builds the
production vertex decoder DLL from the same tree. Nothing outside --output is written; the reference build
and the runtime checkout are only read. Use an x64 VS environment (vcvars64.bat) and run through
C:\\tmp\\gt5p-testlock\\run_locked.py.

    python scripts/test/despecialize_build.py --reference-build <ninja build dir> --base-repo <ps3recomp
        checkout at the pinned commit, read only> --output scratch/ds/new [--overlay patch ...]
        [--tree <already patched runtime tree>]

--tree skips the clone and patching, for work in progress on an edited tree (it is not modified).
Outputs: <output>/install/runtime/gt5p.exe (+ DLLs), <output>/decoder.dll, <output>/runtime-tree when cloned.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/test'))
FILES = ('libs/video/rsx_d3d12_backend.c', 'libs/video/rsx_vp_decompiler.c', 'libs/video/rsx_fp_decompiler.c')
CLANG = r'C:\Program Files\LLVM\bin\clang-cl.exe'


def git(path, *args, check=True):
    return subprocess.run(['git', '-C', str(path), *args], check=check, capture_output=True, text=True)


def runtime_tree(dest, base_repo, overlays=()):
    """Fresh clone at the pinned commit with the main patch (and overlays) applied; line endings untouched."""
    manifest = json.loads((ROOT / 'config/ps3recomp.json').read_text())
    dest = Path(dest).resolve()
    scratch = (ROOT / 'scratch').resolve()
    if scratch not in dest.parents:
        raise ValueError('The runtime tree must stay under scratch')
    if dest.exists():
        shutil.rmtree(dest)
    subprocess.run(['git', 'clone', '-q', '-c', 'core.autocrlf=false', '--no-hardlinks', str(base_repo), str(dest)], check=True)
    git(dest, 'config', 'core.autocrlf', 'false')
    git(dest, 'checkout', '-q', '--detach', manifest['commit'])
    for patch in [ROOT / manifest['patch'], *[ROOT / o['patch'] for o in manifest.get('overlays', [])], *map(Path, overlays)]:
        git(dest, 'apply', '--whitespace=nowarn', str(patch))
    return dest


def compile_object(reference, tree, name, objects):
    """Recompile one runtime source from `tree` with the reference build's exact command."""
    stem = name.replace('/', '\\')
    obj = r'ps3recomp\CMakeFiles\ps3recomp_runtime.dir\%s.obj' % stem
    command = subprocess.check_output(['ninja', '-t', 'commands', obj], cwd=reference, text=True).splitlines()[-1]
    reference_runtime = None
    for token in command.replace('"', ' ').split():
        if token.replace('/', '\\').lower().endswith(stem.lower()):
            reference_runtime = token
            break
    if reference_runtime is None:
        raise ValueError('Reference compile command does not name ' + name)
    runtime_root = reference_runtime.replace('/', '\\')[:-len(stem)].rstrip('\\')
    command = command.replace(runtime_root, str(tree))                   # sources and include directories
    command = command.replace(runtime_root.replace('\\', '/'), str(tree).replace('\\', '/'))
    command = command.replace(r'ps3recomp\CMakeFiles\ps3recomp_runtime.dir', str(objects))
    if '/Fo' + str(objects) not in command or ' -c -- ' not in command:
        raise ValueError('Compile command did not retarget the object output')
    command = command.replace(' -c -- ', ' /D_CRT_SECURE_NO_WARNINGS /W0 -c -- ')
    (objects / Path(name).parent).mkdir(parents=True, exist_ok=True)
    subprocess.run(command, cwd=objects, check=True)
    result = objects / (name + '.obj')
    if not result.is_file():
        raise ValueError('Object was not produced: ' + name)
    return result


def build_decoder(tree, output):
    folder = Path(output)
    command = [CLANG, '/nologo', '/O2', '/MT', '/LD', '/D_CRT_SECURE_NO_WARNINGS',
               '/I' + str(tree / 'include'), '/I' + str(tree / 'libs/video'),
               '/Fo' + str(folder / 'decoder.obj'), '/Fe' + str(folder / 'decoder.dll'),
               str(tree / 'libs/video/rsx_vp_decompiler.c'), '/link',
               '/EXPORT:rsx_vp_decompile', '/EXPORT:rsx_vp_decompile_gpufetch']
    subprocess.run(command, check=True)
    return folder / 'decoder.dll'


def build(reference, output, base_repo=None, overlays=(), tree=None):
    if os.environ.get('VSCMD_ARG_TGT_ARCH', '').lower() != 'x64':
        raise ValueError('Use an x64 VS environment (vcvars64.bat)')
    from preparation_speed_acceptance import build_engine
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if tree is None:
        tree = runtime_tree(output / 'runtime-tree', base_repo, overlays)
    tree = Path(tree).resolve()
    objects = output / 'backend-objects'
    objects.mkdir(exist_ok=True)
    built = [compile_object(reference, tree, name, objects) for name in FILES]
    engine = build_engine(reference, output, built)
    decoder = build_decoder(tree, output)
    return engine, decoder


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference-build', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--base-repo', type=Path)
    ap.add_argument('--overlay', type=Path, action='append', default=[])
    ap.add_argument('--tree', type=Path)
    a = ap.parse_args()
    if a.tree is None and a.base_repo is None:
        ap.error('--base-repo or --tree is required')
    engine, decoder = build(a.reference_build.resolve(), a.output, a.base_repo, a.overlay, a.tree)
    print('engine', engine)
    print('decoder', decoder)


if __name__ == '__main__':
    main()
