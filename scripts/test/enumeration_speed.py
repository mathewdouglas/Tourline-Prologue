"""Private stage-only measurement of "Enumerating shaders". Invoke each step through run_locked.py.

`build` makes the private engine (reference objects + the patched backend; x64 VS environment).
`stage` runs preparation_enumeration.stage() in-process on a fixed plan subset, in a fresh cache
seeded with the template stage's DXBC files, and prints/saves its report. Inputs are named by a
private inputs.json (reference_root, reference_helper, runtime, game, elf); nothing machine-specific
is tracked. Original game files are only read.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT/'scripts'))
sys.path.append(str(ROOT/'scripts/test'))


def subset(plan, fragments, vertices):
    """Deterministic fixed subset: the first N plan jobs of each kind (plan order)."""
    plan = dict(plan)
    plan['fragment_jobs'] = plan['fragment_jobs'][:fragments] if fragments else plan['fragment_jobs']
    plan['vertex_jobs'] = plan['vertex_jobs'][:vertices] if vertices is not None else plan['vertex_jobs']
    return plan


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('step', choices=('build', 'helper', 'stage'))
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--inputs', type=Path)
    ap.add_argument('--label', default='run')
    ap.add_argument('--seed', type=Path, help='Directory of template-stage .dxbc files copied into the fresh cache')
    ap.add_argument('--fragments', type=int, default=0, help='First N fragment plan jobs (0 = all)')
    ap.add_argument('--vertices', type=int, help='First N vertex plan jobs (default all)')
    ap.add_argument('--overlay', type=Path, action='append', default=[], help='Extra ps3recomp overlay patch(es) for `build`')
    ap.add_argument('--build-name', default='build', help='Directory under --output for `build`')
    ap.add_argument('--decoder', type=Path, help='Decoder DLL (default: the reference helper decoder)')
    ap.add_argument('--resume', action='store_true', help='Reuse the label directory (resume)')
    a = ap.parse_args()
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    inputs = json.loads((a.inputs or out/'inputs.json').read_text())
    reference, helper, runtime, game, elf = (Path(inputs[k]).resolve() for k in
        ('reference_root', 'reference_helper', 'runtime', 'game', 'elf'))
    if a.step == 'build':
        from preparation_native_profile import build_backend
        from preparation_speed_acceptance import build_engine
        if os.environ.get('VSCMD_ARG_TGT_ARCH', '').lower() != 'x64':
            raise ValueError('Use an x64 VS environment')
        fresh = out/a.build_name; fresh.mkdir(exist_ok=True)
        backend = build_backend(reference/'build', runtime, fresh, [o.resolve() for o in a.overlay])
        engine = build_engine(reference/'build', fresh, backend)
        storage = out/'storage'/'input'; storage.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(elf, storage/'EMAIN.ELF')
        print('Private engine built:', engine, flush=True)
        return
    if a.step == 'helper':
        # Frozen helper + assets next to the private engine, in the layout player_enumeration_native.py expects
        # (use <output>/build as its --output, with a copy of inputs.json there).
        import subprocess
        build = out/'build'
        frozen = build/'helper'
        if frozen.exists():
            shutil.rmtree(frozen)
        subprocess.run([sys.executable, str(ROOT/'scripts/release/build_preparer.py'), '--runtime', str(runtime),
                        '--decoder', str(helper/'decoder.dll'), '--output', str(frozen)], check=True)
        install = build/'install'
        for name in ('preparation', 'assets'):
            if (install/name).exists():
                shutil.rmtree(install/name)
        shutil.copytree(frozen/'dist/GT5P-Prepare', install/'preparation')
        shutil.copytree(ROOT/'assets/pipeline-templates', install/'assets/pipeline-templates')
        shutil.copytree(ROOT/'assets/shader-enumeration', install/'assets/shader-enumeration')
        storage = build/'storage'
        if not storage.exists():
            (storage/'input').mkdir(parents=True)
            shutil.copyfile(elf, storage/'input/EMAIN.ELF')
            source = storage/'preparation'/('a'*24)/'shadercache'; source.mkdir(parents=True)
            (source/'preserved.txt').write_text('Prior selected cache remains intact')
            (storage/'prepared-cache.txt').write_text(source.relative_to(storage).as_posix())
        shutil.copyfile(out/'inputs.json', build/'inputs.json')
        print('Frozen helper installed', flush=True)
        return
    # scripts/test has a preparation_enumeration.py of its own; the real module must win.
    sys.path[:] = [p for p in sys.path if Path(p or '.').resolve() != ROOT/'scripts/test']
    import preparation_enumeration as enum
    from preparation_checkpoint import Checkpoint
    from train_pipeline_cache import save_report
    engine = out/a.build_name/'install/runtime/gt5p.exe'
    decoder = (a.decoder or helper/'decoder.dll').resolve()
    os.environ['GT5P_PREPARE_VOLUME_LIBRARY'] = str(helper/'volume_reader.dll')
    metadata = enum.load(ROOT/'assets/shader-enumeration/gt5p-disc-v1', ROOT/'assets/pipeline-templates/gt5p-disc-v2')
    metadata = dict(metadata, plan=subset(metadata['plan'], a.fragments, a.vertices))
    run = out/'runs'/a.label
    if run.exists() and not a.resume:
        shutil.rmtree(run)
    cache = run/'shadercache'
    seeded = 0
    with Checkpoint(run, dict(label=a.label), resume=a.resume) as checkpoint:
        if not a.resume:
            cache.mkdir()
            if a.seed:
                for path in a.seed.glob('*.dxbc'):
                    shutil.copyfile(path, cache/path.name); seeded += 1
        collapse = enum.sample_share()
        started = time.perf_counter()
        report = enum.stage(metadata, run, elf, engine, decoder, out/'storage', checkpoint,
                            volume=game/'USRDIR/GT.VOL', collapse=collapse)
    report['wall_seconds'] = time.perf_counter()-started  # includes seeding the cache copy when not resumed
    report['seeded_dxbc'] = seeded
    report['cache_files'] = len(list(cache.glob('*.dxbc')))
    save_report(out/f'{a.label}.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('failure_examples', 'batches', 'vertex_batches')}), flush=True)


if __name__ == '__main__':
    main()
