"""Check the configured main patch + controls overlay on a clean pinned clone."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
r=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'scratch/controls/patch-check')
if not r.resolve().is_relative_to((ROOT/'scratch').resolve()):raise ValueError('Private scratch output required')
source=r'C:\Users\GGPC\Dev\Recomps\ps3recomp-gt5p-v018'
if r.exists():raise ValueError('Use a fresh patch-check directory')
subprocess.run(['git','clone','-q','--no-hardlinks','--no-checkout',source,str(r)],check=True)
m=json.loads((ROOT/'config/ps3recomp.json').read_text())
subprocess.run(['git','-C',str(r),'checkout','-q','--detach',m['commit']],check=True)
for check in (False,True):
 subprocess.run([sys.executable,str(ROOT/'scripts/setup_runtime.py'),'--path',str(r),*(['--check'] if check else [])],check=True)
for name in ('ps3recomp-frame-hitch-trace.patch','ps3recomp-pipeline-use-coverage.patch','ps3recomp-shader-interp.patch','ps3recomp-shader-source-dump.patch'):
 subprocess.run(['git','-C',str(r),'apply','--check',str(ROOT/'patches'/name)],check=True)
print('PASS: clean pinned main + controls apply, setup --check, four independent renderer overlays')
