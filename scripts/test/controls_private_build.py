"""Private engine for controls polish (includes required unpublished 0.2.5 source): changed runtime and src objects over the reference build.

Recompiles, with the reference build's own commands, every runtime source whose patch section differs from the
v0.2.3 reference (renderer backend and decompilers, cellPad, the PPU thread syscalls) from an already patched
runtime tree, plus the player-facing src/ files that changed since (settings, settings page, shader badges,
present, debug export), then relinks gt5p.exe against the read-only reference objects. Nothing outside --output
is written. Use an x64 VS environment and run through C:\\tmp\\gt5p-testlock\\run_locked.py.

    python scripts/test/controls_private_build.py --reference-build <ninja build dir> --tree <patched runtime tree> --output scratch/controls/engine

Outputs <output>/install/runtime/gt5p.exe (+ the reference DLLs) and <output>/decoder.dll.
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
from despecialize_build import CLANG, compile_object, build_decoder  # noqa: E402

RUNTIME_FILES = ('libs/video/rsx_d3d12_backend.c', 'libs/video/rsx_vp_decompiler.c', 'libs/video/rsx_fp_decompiler.c',
                 'libs/input/cellPad.c', 'runtime/syscalls/sys_ppu_thread.c')
SRC_FILES = ('main.cpp', 'gt5p_opening.cpp', 'gt5p_controls.cpp', 'gt5p_present.cpp', 'gt5p_settings.cpp', 'gt5p_settings_ui.cpp',
             'gt5p_shaderbusy.cpp', 'gt5p_debug_export.cpp', 'gt5p_keymap.cpp', 'gt5p_glyphs.cpp')


def compile_src(reference, name, objects):
    obj = r'CMakeFiles\gt5p.dir\src\%s.obj' % name
    recipe = 'gt5p_settings.cpp' if name in ('gt5p_opening.cpp', 'gt5p_controls.cpp') else name
    recipe_obj = r'CMakeFiles\gt5p.dir\src\%s.obj' % recipe
    command = subprocess.check_output(['ninja', '-t', 'commands', recipe_obj], cwd=reference, text=True).splitlines()[-1]
    command = command.replace(recipe, name)
    if name == 'gt5p_controls.cpp':
        target = json.loads((ROOT / 'config/targets.json').read_text())['BCUS98158']
        defines = ' '.join('/DGT5P_CONTROLS_' + k.upper() + '=' + target['controls_' + k] + 'u' for k in ('core', 'vtable', 'get', 'set', 'load'))
        command = command.replace(' -c -- ', ' ' + defines + ' -c -- ')
    source = str(reference.parent / 'src' / name)
    assert source in command, source
    command = command.replace(source, str(ROOT / 'src' / name))
    command = command.replace(r'CMakeFiles\gt5p.dir', str(objects))
    assert '/Fo' + str(objects) in command
    (objects / 'src').mkdir(parents=True, exist_ok=True)
    subprocess.run(command, cwd=objects, check=True)
    return obj, objects / 'src' / (name + '.obj')


def build(reference, tree, output):
    output = Path(output).resolve()
    if (ROOT / 'scratch').resolve() not in output.parents:
        raise ValueError('Output must stay under scratch')
    objects = output / 'objects'
    backend = output / 'backend-objects'
    objects.mkdir(parents=True, exist_ok=True)
    backend.mkdir(parents=True, exist_ok=True)
    runtime_objects = [compile_object(reference, Path(tree).resolve(), name, backend) for name in RUNTIME_FILES]
    replaced = dict(compile_src(reference, name, objects) for name in SRC_FILES)
    lines = (reference / 'build.ninja').read_text().splitlines()
    link = next(i for i, line in enumerate(lines) if line.startswith('build gt5p.exe: '))
    inputs = lines[link].split('Release ', 1)[1].split(' | ')[0].split()
    libraries = next(line.split(' = ', 1)[1] for line in lines[link + 1:link + 15]
                     if line.startswith('  LINK_LIBRARIES = ')).split()
    runtime = output / 'install/runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    args = [r'C:\Program Files\LLVM\bin\lld-link.exe', '/nologo', '/machine:x64', '/INCREMENTAL:NO', '/subsystem:console']
    args += [str(replaced[item]) if item in replaced else str(reference / item) for item in inputs]
    args += [str(value) for key, value in replaced.items() if key not in inputs]
    args += [str(item) for item in runtime_objects]   # before the read-only archive
    args += [str(reference / name) if '\\' in name else name for name in libraries]
    args += ['/out:' + str(runtime / 'gt5p.exe'), '/pdb:' + str(output / 'gt5p.pdb'), '/implib:' + str(output / 'gt5p.lib')]
    subprocess.run(args, cwd=output, check=True)
    for dll in reference.glob('*.dll'):
        shutil.copyfile(dll, runtime / dll.name)
    return runtime / 'gt5p.exe', build_decoder(Path(tree).resolve(), output)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference-build', type=Path, required=True)
    ap.add_argument('--tree', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    if os.environ.get('VSCMD_ARG_TGT_ARCH', '').lower() != 'x64':
        raise ValueError('Use an x64 VS environment (vcvars64.bat)')
    engine, decoder = build(a.reference_build.resolve(), a.tree, a.output)
    print('engine', engine)
    print('decoder', decoder)


if __name__ == '__main__':
    main()
