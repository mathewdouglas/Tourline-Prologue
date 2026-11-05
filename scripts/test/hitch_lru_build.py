"""Private engine: main patch + frame-hitch trace overlay + texture-slot LRU overlay (+ optional extras).

Invoke through run_locked.py from a VS x64 environment with GT5P_RUNTIME set to the runtime source
that the reference build names. Every overlay stays default-off at run time (RSX_HITCH_LOG,
RSX_TEX_LRU, ...). Output stays under scratch; reference objects are read-only.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/test'))
from fp_sample_share_build import patched_source  # noqa: E402
from interp_private_build import compile_backend, link_engine  # noqa: E402


def apply(tree, patch):
    data = patch.read_bytes().replace(b'\r\n', b'\n')
    lf = tree.parent / (patch.name + '.lf')
    lf.write_bytes(data)
    subprocess.run(['git', '-C', str(tree), 'apply', '--whitespace=nowarn', str(lf)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=ROOT / 'scratch/hitch/build')
    ap.add_argument('--overlay', action='append', default=['ps3recomp-frame-hitch-trace.patch', 'ps3recomp-texture-slot-lru.patch'])
    a = ap.parse_args()
    if os.environ.get('VSCMD_ARG_TGT_ARCH', '').lower() != 'x64':
        raise SystemExit('Use a VS x64 environment')
    fresh = a.output.resolve()
    if not fresh.is_relative_to((ROOT / 'scratch').resolve()):
        raise SystemExit('Build must remain under scratch')
    if fresh.exists():
        shutil.rmtree(fresh)
    fresh.mkdir(parents=True)
    backend = patched_source(fresh / 'runtime-source')
    for name in a.overlay:
        apply(fresh / 'runtime-source', ROOT / 'patches' / name)
    obj = compile_backend(backend, fresh / 'backend-objects')
    print(link_engine(fresh, obj, []), flush=True)


if __name__ == '__main__':
    main()
