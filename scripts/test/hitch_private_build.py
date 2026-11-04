"""Private frame-hitch diagnostic engine; invoke via run_locked.py in VS x64 env.

Uses current main patch then the separate default-off hitch overlay. Only the
backend and present-thread object are compiled; reference objects stay read-only.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/test'))
from fp_sample_share_build import patched_source
from interp_private_build import compile_backend, link_engine


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'scratch/hitch/build')
    a=ap.parse_args()
    if os.environ.get('VSCMD_ARG_TGT_ARCH','').lower()!='x64':raise ValueError('Use VS x64 environment')
    fresh=a.output.resolve()
    if not fresh.is_relative_to((ROOT/'scratch').resolve()):raise ValueError('Build must remain under scratch')
    if fresh.exists():raise ValueError('Choose a fresh build output')
    fresh.mkdir(parents=True)
    backend=patched_source(fresh/'runtime-source')
    overlay=fresh/'hitch.lf.patch'
    overlay.write_bytes((ROOT/'patches/ps3recomp-frame-hitch-trace.patch').read_bytes().replace(b'\r\n',b'\n'))
    subprocess.run(['git','-C',str(fresh/'runtime-source'),'apply','--whitespace=nowarn',str(overlay)],check=True)
    obj=compile_backend(backend,fresh/'backend-objects')
    print(link_engine(fresh,obj),flush=True)


if __name__=='__main__':main()
