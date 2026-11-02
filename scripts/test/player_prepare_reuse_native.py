"""Frozen helper: reuse a prior generation, cancel, resume and verify real PSOs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
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


def learned_repeat(command, env, storage, out, document):
    """Modify only this test's selected cache, then cancel/resume its fork."""
    pointer=storage/'prepared-cache.txt';previous=pointer.read_text()
    cache=storage/previous
    pack=cache/'menu-shaders-v1.pack';raw=pack.read_bytes()
    assert raw[:8]==b'GT5PSPK1'
    count,=struct.unpack_from('<I',raw,8);offset=12;entries=[]
    for _ in range(count):
        _,size=struct.unpack_from('<QI',raw,offset)
        entries.append(raw[offset:offset+12+size]);offset+=12+size
    assert offset==len(raw) and len(entries)>1
    pack.write_bytes(raw[:12]+b''.join(reversed(entries)))
    index=cache/'warmup-v1/menu-v1.txt'
    known=set(index.read_text().splitlines())
    extra=next(r['key'] for r in document['records'] if r['key'] not in known)
    with index.open('ab') as stream:stream.write((extra+'\n').encode())
    def snapshot():
        return {str(p.relative_to(cache.parent)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in cache.parent.rglob('*') if p.is_file()}
    before=snapshot()
    generations=set(p for p in cache.parent.parent.iterdir() if p.is_dir())
    with (out/'learned-cancel.log').open('wb') as log:
        child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.monotonic()+90
            while child.poll() is None:
                fresh=set(p for p in cache.parent.parent.iterdir() if p.is_dir())-generations
                if fresh and any((next(iter(fresh))/'shadercache').glob('*.dxbc')):
                    (storage/'prepare.cancel').write_text('cancel');break
                if time.monotonic()>deadline:raise AssertionError('Learned cache did not start a fresh generation')
                time.sleep(.05)
            assert child.wait(timeout=30)==2,(out/'learned-cancel.log').read_text(errors='replace')
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=15)
    assert len(fresh)==1
    fork=next(iter(fresh))
    assert json.loads((fork/'preparation-state.json').read_text())['phase']=='interrupted'
    assert pointer.read_text()==previous and snapshot()==before
    (storage/'prepare.cancel').unlink()  # Request marker only.
    with (out/'learned-resume.log').open('wb') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900,check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    report=json.loads((fork/'report.json').read_text())
    assert report['counts']=={'prepared':len(document['records'])}
    assert report['shader_packs']['packs_written']==2
    assert report['resume']['vertex_programs_compiled']==0
    assert report['fragment_preparation']['processes']==0
    assert pointer.read_text()==(fork/'shadercache').relative_to(storage).as_posix()
    assert snapshot()==before
    assert json.loads((fork/'preparation-state.json').read_text())['attempt']==2
    result=dict(learned_cache_unchanged=True,cancelled_fork_resumed=True,selection_switched_after_success=True,
                counts=report['counts'],shader_packs=report['shader_packs'],resume=report['resume'])
    (out/'learned-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Post-play learned cache preserved; frozen fork cancellation/resume and every native pipeline passed')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('helper-dir','zip','previous-cache','elf','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    source_args=ap.add_mutually_exclusive_group(required=True)
    source_args.add_argument('--assets',type=Path)
    source_args.add_argument('--game',type=Path)
    ap.add_argument('--expect-hash-backend',choices=('native','python'))
    ap.add_argument('--expanding',action='store_true',help='Allow an older subset cache and require missing shaders/pipelines to be prepared')
    ap.add_argument('--learned-cache-repeat',action='store_true',help='Repeat preparation after valid local pack/index learning; verify preserved source and fork cancellation/resume')
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
    missing=[]
    for name in names:
        if a.expanding and not (a.previous_cache/name).is_file():missing.append(name)
        else:shutil.copyfile(a.previous_cache/name,source/name)
    before=hashes(source)
    seed_shaders=sum(name.endswith('.dxbc') for name in before)
    seed_drivers=sum(name.endswith('.bin') for name in before)
    if a.expanding:
        assert missing and seed_shaders>0 and 0<seed_drivers<len(document['records'])
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
    if a.expanding:
        assert report['resume']['vertex_programs_compiled']>0 and report['fragment_preparation']['processes']>0
        assert report['resume']['verified_cached_sources']==seed_shaders
    else:
        assert report['resume']['vertex_programs_compiled']==0 and report['fragment_preparation']['processes']==0
    assert report['cache_reuse']['driver_blobs_copied']==seed_drivers
    assert hashes(source)==before and pointer.read_text()==(state.parent/'shadercache').relative_to(storage).as_posix()
    assert json.loads(state.read_text())['phase']=='complete'
    match=re.search(r'requests=(\d+) created=(\d+) driver_calls=(\d+) cached_blob_calls=(\d+)',
                    (state.parent/'native.log').read_text(errors='replace'))
    assert match and list(map(int,match.groups()))==[len(document['records'])]*3+[seed_drivers]
    (out/'validation.json').write_text(json.dumps(dict(template_rejection_preserved_selection=True,
        cancellation_preserved_selection=True,source_cache_unchanged=True,counts=report['counts'],
        clean_path=True,seconds=time.monotonic()-started,reuse=report['cache_reuse'],
        expanding=a.expanding,seed_shaders=seed_shaders,seed_driver_blobs=seed_drivers,missing_seed_files=len(missing),
        shader_work=report['resume'],fragment_work=report['fragment_preparation'],hashing=report.get('hashing'),
        preparation_seconds=report['preparation_seconds'],lookup=report['lookup'],
        native_counts=list(map(int,match.groups()))),indent=2)+'\n')
    print('Frozen generation reuse, cancellation/resume, safe selection and every native pipeline passed')
    if a.learned_cache_repeat:learned_repeat(command,env,storage,out,document)


if __name__=='__main__':main()
