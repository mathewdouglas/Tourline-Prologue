"""Atomic checkpoint identity, exclusive ownership and redirected-output safety."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).parents[1]))
from preparation_checkpoint import Checkpoint, generation_entry_budget, preflight_tree
from shader_coverage import ROOT

(ROOT/'scratch').mkdir(exist_ok=True)
base=Path(tempfile.mkdtemp(prefix='checkpoint-test-',dir=ROOT/'scratch'))
out=base/'owned';contract={'template':'synthetic-contract'}
try:
    with Checkpoint(out,contract) as checkpoint:
        checkpoint.stage('vertex',completed=1)
        raise KeyboardInterrupt()
except KeyboardInterrupt:pass
state=json.loads((out/'preparation-state.json').read_text())
assert state['phase']=='interrupted' and state['progress']=={'completed':1}
before=(out/'preparation-state.json').read_bytes()
try:
    with Checkpoint(out,{'template':'different'},resume=True):raise AssertionError('Contract accepted')
except ValueError:pass
assert (out/'preparation-state.json').read_bytes()==before

code="""
import sys
from pathlib import Path
sys.path.insert(0,'scripts')
from preparation_checkpoint import Checkpoint
with Checkpoint(Path(sys.argv[1]),{'template':'synthetic-contract'},resume=True) as checkpoint:
 checkpoint.stage('waiting')
 print('locked',flush=True)
 sys.stdin.readline()
"""
child=subprocess.Popen([sys.executable,'-c',code,str(out)],cwd=ROOT,stdin=subprocess.PIPE,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
    assert child.stdout.readline().strip()=='locked'
    before=(out/'preparation-state.json').read_bytes()
    try:
        with Checkpoint(out,contract,resume=True):raise AssertionError('Concurrent writer entered')
    except ValueError as exc:assert 'owns this output' in str(exc)
    assert (out/'preparation-state.json').read_bytes()==before
    child.communicate(input='done\n',timeout=15)
    assert child.returncode==0
finally:
    if child.poll() is None:child.terminate();child.wait(timeout=15)
with Checkpoint(out,contract,resume=True) as checkpoint:
    assert checkpoint.state['attempt']==3
    checkpoint.stage('complete')

external=base/'external';external.mkdir();(external/'keep.txt').write_text('preserved')
link=out/'redirect'
if os.name=='nt':
    env=dict(os.environ,GT5P_CP_LINK=str(link),GT5P_CP_TARGET=str(external))
    subprocess.run(['powershell','-NoProfile','-Command',
                    'New-Item -ItemType Junction -Path $env:GT5P_CP_LINK -Target $env:GT5P_CP_TARGET | Out-Null'],
                   env=env,check=True,capture_output=True)
else:link.symlink_to(external,target_is_directory=True)
try:
    with Checkpoint(out,contract,resume=True):raise AssertionError('Redirected output accepted')
except ValueError:pass
assert (external/'keep.txt').read_text()=='preserved'
hard=base/'hard'
with Checkpoint(hard,contract) as checkpoint:checkpoint.stage('complete')
os.link(external/'keep.txt',hard/'linked.txt')
try:
    with Checkpoint(hard,contract,resume=True):raise AssertionError('Hard-linked output accepted')
except ValueError:pass
assert (external/'keep.txt').read_text()=='preserved'
budget_root=base/'budget';budget_root.mkdir()
(budget_root/'a.txt').write_text('a');(budget_root/'b.txt').write_text('b')
preflight_tree(budget_root, budget=2)
try:
    preflight_tree(budget_root, budget=1)
    raise AssertionError('Entry budget accepted')
except ValueError as exc:
    assert str(exc)=='Preparation output entry budget exceeded'
# One played generation of a few thousand records, plus its warmup files,
# must fit. The old fixed cap of 100000 did not fit two such generations.
assert generation_entry_budget(2892)>63000
assert generation_entry_budget()*2>100000
print('Checkpoint identity, interruption, cross-process ownership and link/hard-link rejection passed:',base)
