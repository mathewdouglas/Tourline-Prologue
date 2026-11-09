"""Compile/test the real runtime pack-index helper; invoke through run_locked.py."""
import argparse
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();out=a.output.resolve()
if not out.is_relative_to((ROOT/'scratch').resolve()):raise ValueError('Output must stay under scratch')
out.mkdir(parents=True,exist_ok=True)
s=a.source.read_text(encoding='utf8')
start=s.index('static int pso_pack_index_compare(')
end=s.index('static int pso_pack_bind(',start)
(out/'race_pack_order_impl.h').write_text(s[start:end],encoding='utf8',newline='\n')
subprocess.run([r'C:\Program Files\LLVM\bin\clang-cl.exe','/nologo','/TC','/O2',
 '/I'+str(out),'/Fo'+str(out/'race_pack_order.obj'),'/Fe'+str(out/'race_pack_order.exe'),
 str(ROOT/'scripts/test/race_pack_order.c')],check=True)
subprocess.run([str(out/'race_pack_order.exe')],check=True)
