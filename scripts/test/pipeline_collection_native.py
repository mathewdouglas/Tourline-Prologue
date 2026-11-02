"""Frozen post-play verification of a real private recording, including resume.

Original game/recording/install inputs are read-only. No game copy or launch.
The caller owns the shared validation mutex for this operation and all children.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import pipeline_collection as collection
import pipeline_contribution as contribution
from train_pipeline_cache import idle,isolated


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('install-base','helper-dir','share','trace','elf','game','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();idle();out=isolated(args.output)
    if out.exists():raise ValueError('Use fresh private output')
    out.mkdir();install=out/'Install';storage=out/'Storage'
    shutil.copytree(args.install_base,install,ignore=shutil.ignore_patterns('preparation'))
    shutil.copytree(args.helper_dir,install/'preparation')
    shutil.copyfile(Path(__file__).parents[2]/'assets/pipeline-templates/gt5p-disc-v2/search-map.json',
        install/'assets/pipeline-templates/gt5p-disc-v2/search-map.json')
    (storage/'input').mkdir(parents=True);shutil.copyfile(args.elf,storage/'input/EMAIN.ELF')
    (storage/'setup.ini').write_text('[game]\ndirectory='+str(args.game.resolve())+'\n',encoding='utf-16')
    old='preparation/'+('a'*24)+'/shadercache';cache=storage/old;cache.mkdir(parents=True)
    marker=cache/'preserved.txt';marker.write_text('Preserve selected cache')
    pointer=storage/'prepared-cache.txt';pointer.write_text(old)
    session=storage/'pipeline-contributions'/('session-'+uuid.uuid4().hex);session.mkdir(parents=True)
    shutil.copytree(args.trace,session/'private-recorder')
    value=contribution.read_json(args.share)
    with patch.dict(os.environ,{'GT5P_COLLECT_VERIFY':'0'}):
        collection.begin(install,storage,session,value,{},dict(mode='default',source='retained-supported-session'))
    command=[str((install/'preparation/GT5P-Prepare.exe').resolve()),'--verify-contribution',
        '--install',str(install.resolve()),'--storage',str(storage.resolve())]
    env=dict(os.environ,PS3_VERBOSE='0',PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    env.pop('GT5P_COLLECT_VERIFY',None)
    started=time.monotonic()
    with (out/'cancel.log').open('wb') as log:
        child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while child.poll() is None:
                # Observe the non-atomic append log, never open checkpoint files
                # while Windows atomic publication is in progress.
                text=(out/'cancel.log').read_text(errors='replace')
                if 'Verifying collection: native' in text:
                    (session/'verify.cancel').write_text('cancel');break
                if time.monotonic()-started>900:raise AssertionError('Native stage did not start')
                time.sleep(.1)
            assert child.wait(timeout=30)==2,(out/'cancel.log').read_text(errors='replace')
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=20)
    assert pointer.read_text()==old and marker.read_text()=='Preserve selected cache'
    assert not (session/'share-this-template.json').exists()
    assert len(contribution.read_json(session/'pending-template.json')['records'])==len(value['template']['records'])
    with (out/'resume.log').open('wb') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    result=contribution.read_json(session/'verification.json')
    shared=contribution.read_json(session/'share-this-template.json')
    assert contribution.decode(shared)==contribution.decode(value)
    assert result['verified']==len(value['template']['records']) and result['pending']==0
    assert contribution.read_json(session/'pending-template.json')['records']==[]
    assert pointer.read_text()==old and marker.read_text()=='Preserve selected cache'
    proof=json.loads(next((storage/'cv').glob('*/p/report.json')).read_text())
    assert proof['counts']=={'prepared':result['verified']}
    assert proof['resume']['vertex_programs_compiled']==0 and proof['fragment_preparation']['processes']==0
    original_share=hashlib.sha256((session/'share-this-template.json').read_bytes()).hexdigest()
    # Reject a different archive after completed proof without changing the share,
    # pending records, cache or ordinary player selection.
    wrong=out/'wrong-game/USRDIR';wrong.mkdir(parents=True);(wrong/'GT.VOL').write_bytes(b'incompatible')
    (storage/'setup.ini').write_text('[game]\ndirectory='+str(wrong.parent.resolve())+'\n',encoding='utf-16')
    with (out/'rejected.log').open('wb') as log:
        rejected=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
    assert rejected.returncode!=0
    assert hashlib.sha256((session/'share-this-template.json').read_bytes()).hexdigest()==original_share
    assert pointer.read_text()==old and marker.read_text()=='Preserve selected cache'
    result.update(cancel_resume=True,zero_resume_shader_compiles=True,cache_selection_unchanged=True,
        incompatible_volume_rejected=True,share_preserved_on_failure=True,seconds=time.monotonic()-started,
        search=json.loads(next((storage/'cv').glob('*/l/search-report.json')).read_text()),proof_seconds=proof['preparation_seconds'])
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
