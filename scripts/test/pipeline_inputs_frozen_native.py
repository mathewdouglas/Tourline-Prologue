"""Locked frozen format-3 acceptance, strict reference and legacy reuse.

Private outputs only. Run each mode separately under run_locked.py. The full
fresh mode cancels at native-input publication, checks selection preservation,
then resumes. Enumeration is disabled to isolate the starter pipeline proof.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pipeline_template as template
from pipeline_template_inputs import convert, reference_outputs, OUTPUTS
from pipeline_runtime_coverage import parse_report
from train_pipeline_cache import isolated, idle


def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('helper-dir','runtime','elf','game','reference-template','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--mode',choices=('fresh','incremental','legacy-seed'),default='fresh')
    ap.add_argument('--previous-cache',type=Path)
    ap.add_argument('--limit',type=int,default=0)
    ap.add_argument('--no-cancel',action='store_true')
    ap.add_argument('--source-comment-probe',action='store_true')
    a=ap.parse_args()
    for name in ('helper_dir','runtime','elf','game','reference_template','output','previous_cache'):
        if getattr(a,name) is not None:setattr(a,name,getattr(a,name).resolve())
    idle()
    out=isolated(a.output)
    if out.exists():raise ValueError('Use a fresh ignored output')
    original=template.ROOT/'assets/pipeline-templates/gt5p-disc-v2'
    document=template.read(original)
    old=template.read(a.reference_template,legacy=True)
    assert convert(old)==document
    from pipeline_warmup_plan import read as read_plan
    plan=read_plan(template.ROOT/'config/pipeline-warmup/gt5p-disc-v2.json')
    members=set(plan['phases']['menu'])|set(plan['phases']['race'])
    if a.limit:
        rows=[r for r in document['records'] if r['key'] in members][:a.limit]
        document=dict(document,records=rows)
        selected={r['key'] for r in rows}
        old=dict(old,records=[r for r in old['records']
            if convert(dict(old,records=[r]))['records'][0]['key'] in selected])
    install=out/'Install';storage=out/'Storage'
    (storage/'input').mkdir(parents=True)
    shutil.copyfile(a.elf,storage/'input/EMAIN.ELF')
    if a.mode=='legacy-seed':
        path=out/'legacy.json';path.write_text(json.dumps(old))
        generation=storage/'preparation'/('b'*24)
        env=dict(os.environ)
        os.environ['GT5P_PREPARE_INPUT_TEMPLATE']='0'
        os.environ['GT5P_PREPARE_VOLUME_LIBRARY']=str(a.helper_dir/'volume_reader.dll')
        os.environ['GT5P_PREPARE_HASH_LIBRARY']=str(a.helper_dir/'cache_hash.dll')
        try:
            report=template.prepare(path,None,storage/'input/EMAIN.ELF',a.runtime/'gt5p.exe',
                a.helper_dir/'decoder.dll',storage,generation,asset_map=original/'player-map.json',
                volume=a.game/'USRDIR/GT.VOL',volume_map=original/'volume-map.json')
        finally:
            os.environ.clear();os.environ.update(env)
        assert report['counts']=={'prepared':len(old['records'])}
        (out/'validation.json').write_text(json.dumps(dict(mode=a.mode,records=len(old['records']),
            counts=report['counts'],seconds=report['preparation_seconds']),indent=2)+'\n')
        print('Legacy seed:',generation/'shadercache',flush=True)
        return
    shutil.copytree(a.runtime,install/'runtime')
    shutil.copytree(a.helper_dir,install/'preparation')
    if a.source_comment_probe:
        # Change the old source-fingerprint resource too. No template or ABI
        # changes; this would invalidate the format-2 source contract gate.
        config=json.loads((install/'preparation/_internal/config/ps3recomp.json').read_text())
        patch_path=install/'preparation/_internal'/config['patch']
        patch_path.write_bytes(patch_path.read_bytes()+b'\n# harmless private source-comment probe\n')
    bundle=install/'assets/pipeline-templates/gt5p-disc-v2'
    template.bundle(document,bundle)
    for name in ('asset-map.json','player-map.json','volume-map.json','search-map.json','README.md'):
        shutil.copyfile(original/name,bundle/name)
    # The private subset carries only existing observed membership, never a
    # fabricated scope. Full mode retains every original target unchanged.
    selected={r['key'] for r in document['records']}
    plan=copy.deepcopy(plan)
    plan['template_sha256']=template.template_digest(bundle)
    plan['phases']={p:[k for k in keys if k in selected] for p,keys in plan['phases'].items()}
    plan_path=install/'preparation/_internal/config/pipeline-warmup/gt5p-disc-v2.json'
    plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    manifest_path=install/'preparation/files.json'
    files=json.loads(manifest_path.read_text())
    resources=[plan_path]+([patch_path] if a.source_comment_probe else [])
    for resource in resources:
        name=resource.relative_to(install/'preparation').as_posix()
        assert name in files['files']
        files['files'][name]=hashlib.sha256(resource.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(files,indent=2)+'\n')
    pointer=storage/'prepared-cache.txt'
    if a.mode=='incremental':
        if a.previous_cache is None:raise ValueError('Incremental needs a legacy cache')
        target=storage/'preparation'/a.previous_cache.parent.name/'shadercache'
        target.parent.mkdir(parents=True)
        shutil.copytree(a.previous_cache,target)
        if (a.previous_cache.parent/'di').exists():
            shutil.copytree(a.previous_cache.parent/'di',target.parent/'di')
    else:
        target=storage/'preparation'/('a'*24)/'shadercache';target.mkdir(parents=True)
        (target/'preserved.txt').write_text('Prior selection')
    before=snapshot(target)
    pointer.write_text(target.relative_to(storage).as_posix())
    previous=pointer.read_bytes()
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('GT5P_','RSX_'))}
    env.update(PS3_VERBOSE='0',GT5P_PREPARE_ENUMERATE='0',
        PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    command=[str(install/'preparation/GT5P-Prepare.exe'),'--install',str(install),
             '--storage',str(storage),'--game',str(a.game)]
    if a.mode=='fresh':command.append('--no-reuse')
    summary=dict(mode=a.mode,records=len(document['records']))
    if a.mode=='fresh' and not a.no_cancel:
        tick=time.perf_counter()
        with (out/'cancel.log').open('wb') as stream:
            child=subprocess.Popen(command,env=env,stdout=stream,stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline=time.monotonic()+1800
                while child.poll() is None:
                    try:text=(storage/'prepare-status.txt').read_text()
                    except OSError:text=''
                    # A subset finishes native input inside the status debounce, so
                    # its nonzero counts may never be written; the full run keeps
                    # the strict published-inputs trigger.
                    if text.startswith('Native input ') and (a.limit or not text.startswith('Native input 0/')):
                        (storage/'prepare.cancel').write_text('cancel');break
                    if time.monotonic()>deadline:raise TimeoutError('Native input never started')
                    time.sleep(.005)
                assert child.wait(timeout=120)==2,(out/'cancel.log').read_text(errors='replace')[-3000:]
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=15)
        assert pointer.read_bytes()==previous and snapshot(target)==before
        generations=[p for p in (storage/'preparation').iterdir() if p!=target.parent]
        assert len(generations)==1
        assert json.loads((generations[0]/'preparation-state.json').read_text())['phase']=='interrupted'
        summary['cancel_seconds']=time.perf_counter()-tick
        summary['retained_shaders']=len(list((generations[0]/'shadercache').glob('*.dxbc')))
        (storage/'prepare.cancel').unlink()
    tick=time.perf_counter()
    with (out/'prepare.log').open('wb') as stream:
        result=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT,
                              timeout=3600,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,(out/'prepare.log').read_text(errors='replace')[-4000:]
    generation=(storage/pointer.read_text()).parent
    report=json.loads((generation/'report.json').read_text())
    parsed=parse_report(report)
    assert report['counts']=={'prepared':len(document['records'])}
    expected=reference_outputs(old)
    actual={r['input_key']:{k:r[k] for k in OUTPUTS} for r in report['derived_records']}
    assert actual==expected,'Format-3 outputs differ from format-2 reference'
    assert set(parsed['default_keys'])==set(report['inventory']['valid_driver_blobs'])
    assert snapshot(target)==before
    if a.mode=='incremental':assert report['cache_reuse']['driver_blobs_copied']>0
    assert template.read(bundle)==document
    summary.update(seconds=time.perf_counter()-tick,internal_seconds=report['preparation_seconds'],
        exact_reference_outputs=len(actual),runtime_lookup_counts=report['runtime_lookup_counts'],
        native_counts=report['native_counts'],
        inventory={k:len(v) for k,v in report['inventory'].items()},resume=report['resume'],
        cache_reuse=report['cache_reuse'],shader_packs=report.get('shader_packs'),
        warmup_plan=report.get('warmup_plan'),old_selection_preserved=True,
        template_sha256=template.template_digest(bundle),engine_sha256=report['engine_sha256'],
        enumeration_disabled=True)
    summary['source_comment_probe']=a.source_comment_probe
    (out/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
