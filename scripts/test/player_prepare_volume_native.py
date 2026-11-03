"""Frozen direct-volume helper cancellation and rejection, without shader work."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from train_pipeline_cache import idle,isolated


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('install','elf','game','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--intermediate-completion',action='store_true',help='Simulate owner death after native completion but before pack/index publication')
    a=ap.parse_args();idle();out=isolated(a.output)
    if out.exists():ap.error('Use a fresh ignored test output')
    storage=out/'Storage';(storage/'input').mkdir(parents=True)
    shutil.copyfile(a.elf,storage/'input/EMAIN.ELF')
    previous='preparation/'+('a'*24)+'/shadercache'
    source=storage/previous;source.mkdir(parents=True)
    marker=source/'preserved.txt';marker.write_text('Existing cache must survive')
    pointer=storage/'prepared-cache.txt';pointer.write_text(previous)
    command=[str((a.install/'preparation/GT5P-Prepare.exe').resolve()),
             '--install',str(a.install.resolve()),'--storage',str(storage.resolve()),
             '--no-reuse','--game',str(a.game.resolve())]
    env=dict(os.environ,PS3_VERBOSE='0',GT5P_PREPARE_ENUMERATE='0',PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    with (out/'cancel.log').open('wb') as log:
        child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            begin=time.monotonic();cancelled=False
            while child.poll() is None:
                status=storage/'prepare-status.txt'
                try:text=status.read_text(encoding='utf-8') if status.exists() else ''
                except PermissionError:text=''
                if text.startswith('Checking game archive'):
                    (storage/'prepare.cancel').write_text('cancel');cancelled=True;break
                if time.monotonic()-begin>30:raise AssertionError('Archive verification did not start')
                time.sleep(.01)
            assert cancelled and child.wait(timeout=15)==2,(out/'cancel.log').read_text(errors='replace')
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=15)
    states=list((storage/'preparation').glob('*/preparation-state.json'))
    assert len(states)==1 and json.loads(states[0].read_text())['phase']=='interrupted'
    assert pointer.read_text()==previous and marker.read_text()=='Existing cache must survive'
    assert not list((storage/'preparation').rglob('*.dxbc'))
    assert not list((storage/'preparation').rglob('native.log'))
    (storage/'prepare.cancel').unlink()  # Only our cancellation marker, never a cache.
    game=out/'wrong-game';(game/'USRDIR').mkdir(parents=True)
    (game/'USRDIR/GT.VOL').write_bytes(b'unsupported volume')
    command[-1]=str(game.resolve())
    with (out/'rejected.log').open('wb') as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                              timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==1 and 'Game volume size mismatch' in (out/'rejected.log').read_text()
    assert json.loads(states[0].read_text())['phase']=='failed'
    if a.intermediate_completion:
        # No native producer ran. Reproduce its transient complete checkpoint
        # using only this private fixture, then reject the wrong game again.
        state=json.loads(states[0].read_text());state['phase']='complete'
        states[0].write_text(json.dumps(state))
        (states[0].parent/'report.json').write_text('{}')
        before=set((storage/'preparation').iterdir())
        with (out/'intermediate.log').open('wb') as log:
            result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                                  timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==1 and 'Game volume size mismatch' in (out/'intermediate.log').read_text()
        assert set((storage/'preparation').iterdir())==before
        assert pointer.read_text()==previous and marker.read_text()=='Existing cache must survive'
    assert pointer.read_text()==previous and marker.read_text()=='Existing cache must survive'
    assert not list((storage/'preparation').rglob('*.dxbc'))
    assert not list((storage/'preparation').rglob('native.log'))
    (out/'validation.json').write_text(json.dumps(dict(archive_cancellation=True,
        incompatible_volume_rejected=True,selection_and_cache_preserved=True,
        no_shader_or_native_work=True,clean_path=True),indent=2)+'\n')
    print('Archive-stage cancellation and incompatible-volume rejection preserve the selected cache')


if __name__=='__main__':main()
