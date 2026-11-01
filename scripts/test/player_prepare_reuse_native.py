"""Frozen helper: reuse a prior generation, cancel, resume and verify real PSOs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline_template import read
from preparation_reuse import expected_shaders
from train_pipeline_cache import idle,isolated
from shader_coverage import ROOT


def hashes(root):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('helper-dir','zip','previous-cache','elf','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    source_args=ap.add_mutually_exclusive_group(required=True)
    source_args.add_argument('--assets',type=Path)
    source_args.add_argument('--game',type=Path)
    ap.add_argument('--expect-hash-backend',choices=('native','python'))
    a=ap.parse_args();idle();out=isolated(a.output)
    if out.exists():ap.error('Use a fresh ignored test output')
    install=out/'Install';storage=out/'Storage'
    (install/'runtime').mkdir(parents=True)
    (storage/'input').mkdir(parents=True)
    with zipfile.ZipFile(a.zip) as archive:
        (install/'runtime/gt5p.exe').write_bytes(archive.read('runtime/gt5p.exe'))
    shutil.copytree(a.helper_dir,install/'preparation')
    bundle=install/'assets/pipeline-templates/gt5p-disc-v2'
    shutil.copytree(ROOT/'assets/pipeline-templates/gt5p-disc-v2',bundle)
    shutil.copyfile(a.elf,storage/'input/EMAIN.ELF')
    document=read(bundle)
    source=storage/'preparation'/('a'*24)/'shadercache';source.mkdir(parents=True)
    names=[key+'.dxbc' for key in expected_shaders(document)]
    names += [f"pso_{r['key']}.bin" for r in document['records']]
    for name in names:shutil.copyfile(a.previous_cache/name,source/name)
    before=hashes(source)
    pointer=storage/'prepared-cache.txt'
    previous=source.relative_to(storage).as_posix();pointer.write_text(previous)
    helper=install/'preparation/GT5P-Prepare.exe'
    command=[str(helper.resolve()),'--install',str(install.resolve()),'--storage',str(storage.resolve()),
             '--game' if a.game else '--assets',str((a.game or a.assets).resolve())]
    env=dict(os.environ,PS3_VERBOSE='0',PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    env.pop('GT5P_PREPARE_REUSE',None)
    # A bad new template must not start work or disturb the selected old cache.
    index=bundle/'index.json';original=index.read_bytes();index.write_text('{"version":999}')
    with (out/'rejected.log').open('wb') as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=30,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode!=0 and pointer.read_text()==previous and hashes(source)==before
    index.write_bytes(original)
    with (out/'cancel.log').open('wb') as log:
        child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            begin=time.monotonic()
            while child.poll() is None:
                generations=[p for p in (storage/'preparation').iterdir() if p.is_dir() and p!=source.parent]
                if generations and any((generations[0]/'shadercache').glob('*.dxbc')):
                    (storage/'prepare.cancel').write_text('cancel');break
                if time.monotonic()-begin>60:raise AssertionError('Reuse did not make progress')
                time.sleep(.05)
            assert child.wait(timeout=30)==2,(out/'cancel.log').read_text(errors='replace')
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=15)
    state=generations[0]/'preparation-state.json'
    assert json.loads(state.read_text())['phase']=='interrupted'
    assert pointer.read_text()==previous and hashes(source)==before
    (storage/'prepare.cancel').unlink()  # Only the cancellation marker, never cache contents.
    started=time.monotonic()
    with (out/'resume.log').open('wb') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900,check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    report=json.loads((state.parent/'report.json').read_text())
    assert report['counts']=={'prepared':len(document['records'])}
    if a.game:assert report['lookup']['volume']['source']=='game-volume'
    if a.expect_hash_backend:
        assert report['hashing']['backend']==a.expect_hash_backend
        assert report['hashing'][a.expect_hash_backend+'_calls']>0
    assert report['resume']['vertex_programs_compiled']==0 and report['fragment_preparation']['processes']==0
    assert report['cache_reuse']['driver_blobs_copied']==len(document['records'])
    assert hashes(source)==before and pointer.read_text()==(state.parent/'shadercache').relative_to(storage).as_posix()
    assert json.loads(state.read_text())['phase']=='complete'
    match=re.search(r'requests=(\d+) created=(\d+) driver_calls=(\d+) cached_blob_calls=(\d+)',
                    (state.parent/'native.log').read_text(errors='replace'))
    assert match and list(map(int,match.groups()))==[len(document['records'])]*4
    (out/'validation.json').write_text(json.dumps(dict(template_rejection_preserved_selection=True,
        cancellation_preserved_selection=True,source_cache_unchanged=True,counts=report['counts'],
        clean_path=True,seconds=time.monotonic()-started,reuse=report['cache_reuse'],
        shader_work=report['resume'],hashing=report.get('hashing'),
        preparation_seconds=report['preparation_seconds'],lookup=report['lookup'],
        native_counts=list(map(int,match.groups()))),indent=2)+'\n')
    print('Frozen generation reuse, cancellation/resume, safe selection and every native pipeline passed')


if __name__=='__main__':main()
