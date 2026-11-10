"""Native settings parser round trips and environment precedence. No game."""
import os,subprocess,sys,tempfile
from pathlib import Path
probe=Path(sys.argv[1]).resolve()
env={k:v for k,v in os.environ.items() if not k.startswith(('PAD_','GT5P_','RSX_'))}
count=0
with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'scratch/controls') as td:
 p=Path(td)/'settings.toml'; out=Path(td)/'saved.toml'
 for content,expected,override in [
  ('[meta]\ndefaults_version=1\n[input]\n', '0 0 0 0 0 0 0',{}),
  ('[meta]\ndefaults_version=1\n[input]\ntrigger_deadzone=5\ntrigger_curve=1\nmodern_controls=true\nadaptive_triggers=true\ntrigger_rumble=true\nsdl_rumble=true\n','5 1 1 1 1 1 0',{}),
  ('[meta]\ndefaults_version=1\n[input]\ntrigger_deadzone=21\ntrigger_curve="quick"\nmodern_controls=1\n','0 0 0 0 0 0 0',{}),
  ('[meta]\ndefaults_version=1\n[input]\ntrigger_curve=1\n','0 2 0 0 0 0 1',{'PAD_TRIGGER_CURVE':'2'})]:
  p.write_text(content)
  runenv=dict(env,GT5P_SETTINGS=str(p),**override)
  r=subprocess.run([probe,out],env=runenv,capture_output=True,text=True,check=True)
  assert 'CONTROLS '+expected in r.stdout,r.stdout
  assert 'MODERN_ENV <unset>' in r.stdout, 'An observed TOML value became a boot command'
  assert p.read_text()==content
  r2=subprocess.run([probe],env=dict(runenv,GT5P_SETTINGS=str(out)),capture_output=True,text=True,check=True)
  assert 'CONTROLS '+expected in r2.stdout,r2.stdout
  count+=1
 print(f'PASS: {count} production settings parse/save/reload cases, invalid types/ranges, override and source preservation')
