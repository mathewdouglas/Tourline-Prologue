"""Frozen packed-game fragment chunk cancellation/resume and selection preservation.

Run sequentially under the project's validation mutex. Original assets/install
are read-only; only a small template and private runtime/helper copies are used.
"""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_template as template
from pipeline_translation import sidecar
from train_pipeline_cache import idle, isolated


def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('helper-dir','reference-install','elf','game','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--count',type=int,default=32)
    ap.add_argument('--chunk',type=int,default=8)
    a=ap.parse_args();idle();out=isolated(a.output)
    if out.exists():raise ValueError('Use a fresh ignored output')
    if not 1<=a.chunk<a.count<=256:raise ValueError('Use a bounded multi-chunk sample')
    install=out/'Install';storage=out/'Storage'
    longest=storage/'preparation'/('a'*24)/'requests'/('b'*64)/'pipeline'/('code_'+'c'*16+'.dxbc')
    if len(str(longest))>=260:raise ValueError('Use a shorter ignored output for the native reader path budget')
    install.mkdir(parents=True);(storage/'input').mkdir(parents=True)
    shutil.copytree(a.reference_install/'runtime',install/'runtime')
    shutil.copytree(a.helper_dir,install/'preparation')
    shutil.copyfile(a.elf,storage/'input/EMAIN.ELF')
    original=template.ROOT/'assets/pipeline-templates/gt5p-disc-v2'
    document=template.read(original)
    chosen=[];seen=set()
    for record in document['records']:
        identity=(record['vp']['sha256'],record['vp_gpu'])
        if identity not in seen:
            seen.add(identity);chosen.append(record)
        if len(chosen)==a.count:break
    if len(chosen)!=a.count:raise ValueError('Insufficient distinct vertex variants')
    selected=dict(document,records=chosen)
    bundle=install/'assets/pipeline-templates/gt5p-disc-v2'
    template.bundle(selected,bundle)
    for name in ('player-map.json','volume-map.json'):
        shutil.copyfile(original/name,bundle/name)
    source=storage/'preparation'/('a'*24)/'shadercache'
    source.mkdir(parents=True);(source/'preserved.txt').write_text('Prior cache stays intact')
    before=snapshot(source)
    pointer=storage/'prepared-cache.txt'
    previous=source.relative_to(storage).as_posix();pointer.write_text(previous)
    command=[str(install/'preparation/GT5P-Prepare.exe'),'--install',str(install),
             '--storage',str(storage),'--game',str(a.game.resolve())]
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('GT5P_','RSX_'))}
    # Select the same compiler explicitly after sanitizing renderer variables.
    import shader_compiler
    env['RSX_SHADER_COMPILER'] = shader_compiler.mode()
    env.update(PS3_VERBOSE='0',GT5P_PREPARE_ENUMERATE='0',GT5P_PREPARE_TRANSLATION='ultrawide-native',
               GT5P_PREPARE_FRAGMENT_CHUNK=str(a.chunk),
               PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    cancel=storage/'prepare.cancel'
    started=time.perf_counter()
    with (out/'cancel.log').open('wb') as log:
        child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.monotonic()+240
            while child.poll() is None:
                generations=[p for p in source.parent.parent.iterdir() if p!=source.parent]
                if generations:
                    # Observe the player status, never open an actively replaced
                    # checkpoint without FILE_SHARE_DELETE on Windows.
                    try:text=(storage/'prepare-status.txt').read_text()
                    except OSError:text=''
                    match=re.fullmatch(r'Translation fragment (\d+)/(\d+)',text)
                    if match and 0<int(match[1])<a.count:
                        cancel.write_text('cancel');break
                if time.monotonic()>deadline:raise AssertionError('No translated fragment checkpoint')
                time.sleep(.02)
            assert child.wait(timeout=30)==2,(out/'cancel.log').read_text(errors='replace')
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=15)
    generation=generations[0]
    state=sidecar(generation,'ultrawide-native')/'preparation-state.json'
    value=json.loads(state.read_text());assert value['phase']=='interrupted'
    manifest=state.parent/'manifests'/(value['progress']['manifest_sha256']+'.json')
    kept=json.loads(manifest.read_text())['fragments']
    assert 0<len(kept)<a.count
    assert pointer.read_text()==previous and snapshot(source)==before
    cancel.unlink()  # Only this test's cancellation request; preserve every cache.

    def run(name,overrides=None,success=True):
        with (out/(name+'.log')).open('wb') as log:
            result=subprocess.run(command,env=dict(env,**(overrides or {})),stdout=log,stderr=subprocess.STDOUT,
                                  timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==(0 if success else 1),(out/(name+'.log')).read_text(errors='replace')

    run('resume')
    first=json.loads((generation/'report.json').read_text())
    extra=first['additional_translation']
    assert first['counts']==extra['counts']=={'prepared':a.count}
    assert extra['fragment_jobs_reused']==len(kept)
    selected_pointer=pointer.read_text()
    assert selected_pointer==(generation/'shadercache').relative_to(storage).as_posix()
    assert snapshot(source)==before
    run('cached',{'GT5P_PREPARE_FRAGMENT_CHUNK':'4096'})
    cached=json.loads((generation/'report.json').read_text())['additional_translation']
    assert cached['fragment_jobs_reused']==a.count and cached['fragment_preparation']['processes']==0
    assert pointer.read_text()==selected_pointer and snapshot(source)==before
    run('cached-handoff-rollback',{'GT5P_PREPARE_HANDOFF':'0'})
    rollback=json.loads((generation/'report.json').read_text())
    assert rollback['native_handoff']['enabled'] is False
    assert rollback['additional_translation']['native_handoff']['enabled'] is False
    assert rollback['additional_translation']['fragment_jobs_reused']==a.count
    assert pointer.read_text()==selected_pointer and snapshot(source)==before
    run('cached-code-rollback',{'GT5P_PREPARE_CODE_BUNDLE':'0'})
    code_rollback=json.loads((generation/'report.json').read_text())
    assert not code_rollback['native_handoff']['code_bundle']
    assert not code_rollback['additional_translation']['native_handoff']['code_bundle']
    assert pointer.read_text()==selected_pointer and snapshot(source)==before
    preserved=snapshot(state.parent)
    run('invalid-chunk',{'GT5P_PREPARE_FRAGMENT_CHUNK':'0'},False)
    assert pointer.read_text()==selected_pointer and snapshot(source)==before
    # Parent report/checkpoint can report rejection; all derived work stays intact.
    assert snapshot(state.parent)==preserved
    for name, overrides in (
            ('invalid-workers',{'GT5P_PREPARE_COMPILER_WORKERS':str(__import__('preparation_workers').MAX_COMPILER_WORKERS+1)}),
            ('invalid-handoff',{'GT5P_PREPARE_HANDOFF':'2'}),
            ('invalid-code-bundle',{'GT5P_PREPARE_CODE_BUNDLE':'2'}),
            ('invalid-shader-profile',{'GT5P_PREPARE_SHADER_PROFILE':'2'}),
            ('invalid-fragment-io',{'GT5P_PREPARE_FRAGMENT_IO':'2'}),
            ('invalid-verification',{'GT5P_PREPARE_VERIFY_BATCH':'0'})):
        run(name,overrides,False)
        assert pointer.read_text()==selected_pointer and snapshot(source)==before
        assert snapshot(state.parent)==preserved
    (out/'validation.json').write_text(json.dumps(dict(records=a.count,checkpointed_fragments=len(kept),
        resumed_fragments=extra['fragment_jobs_reused'],native_counts=extra['native_counts'],
        clean_path=True,old_selection_preserved_on_cancel=True,source_unchanged=True,
        chunk_rollback_reused_all=True,invalid_chunk_preserved_selection=True,
        invalid_worker_and_verification_preserved_selection=True,
        native_handoff_rollback_reused_all=True,
        code_bundle_rollback_reused_all=True,invalid_code_bundle_and_shader_profile_rejected=True,
        seconds=time.perf_counter()-started,
        limitation='Frozen offline subset on one GPU; no live rendering or stutter measurement.'),indent=2)+'\n')
    print('Frozen fragment checkpoint, resume, rollback and selection/source preservation passed:',out)


if __name__=='__main__':main()
