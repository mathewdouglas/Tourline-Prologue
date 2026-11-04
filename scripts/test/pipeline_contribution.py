"""Contribution privacy, untrusted-input checks and proof-gated merging."""
import copy
import json
import os
import struct
from pathlib import Path
import sys
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pipeline_contribution as contribution
import pipeline_template as template
from pipeline_runtime_coverage import RESULT_BOOLS, Rejected
from pipeline_template_inputs import identity


def rejected(call):
    try:call()
    except (ValueError,Rejected):return
    raise AssertionError('Invalid contribution accepted')


def main():
    root=Path(__file__).resolve().parents[2]
    work=root/'scratch'/('contribution-test-'+uuid.uuid4().hex);work.mkdir()
    document=template.read(root/'assets/pipeline-templates/gt5p-disc-v2')
    document['records']=document['records'][:3]
    original=copy.deepcopy(document)
    shared=contribution.encode(document)
    assert document==original and contribution.decode(shared)==dict(document,records=sorted(document['records'],key=lambda r:r['key']))
    path=work/'share.json';contribution.write_json(path,shared)
    assert contribution.decode(contribution.read_json(path))==contribution.decode(shared)
    before=path.read_bytes()
    try:contribution.write_json(path,shared)
    except FileExistsError:pass
    else:raise AssertionError('Existing shared file overwritten')
    assert path.read_bytes()==before
    # Arbitrary text/code/paths have no permitted location in a contribution.
    for name in ('local_path','dxbc','shader_source','username','raw_program'):
        bad=copy.deepcopy(shared);bad[name]='private payload'
        rejected(lambda:contribution.decode(bad))
        bad=copy.deepcopy(shared);bad['template']['records'][0][name]='private payload'
        rejected(lambda:contribution.decode(bad))
    for version in (True,0,2,'1'):
        bad=copy.deepcopy(shared);bad['version']=version
        rejected(lambda:contribution.decode(bad))
    bad=copy.deepcopy(shared);bad['template_sha256']='f'*64
    rejected(lambda:contribution.decode(bad))
    bad=copy.deepcopy(shared);bad['template']['records'][0]['native']['words'][0]=1
    rejected(lambda:contribution.decode(bad))
    rejected(lambda:contribution.encode(dict(document,records=[])))
    with patch.object(contribution,'MAX_BYTES',64):
        rejected(lambda:contribution.encode(document))
        rejected(lambda:contribution.read_json(path))
    hostile=work/'hostile.json'
    for data in ('{"version":1,"version":1}', '{"value":NaN}', '['*1200+']'*1200):
        hostile.write_text(data)
        rejected(lambda:contribution.read_json(hostile))
    baseline=dict(document,records=document['records'][:1])
    report,candidates=contribution.review(baseline,[shared,shared])
    assert report['additional_records']==2 and len(candidates['records'])==2
    assert baseline['records']==original['records'][:1]
    baseline_path=work/'baseline.json';contribution.write_json(baseline_path,baseline)
    with patch.object(sys,'argv',['pipeline_contribution.py','review','--baseline',str(baseline_path),
            '--submission',str(path),'--output',str(work/'cli-review')]):
        contribution.main()
    assert len(template.read(work/'cli-review/candidates.json')['records'])==2
    with patch.object(sys,'argv',['pipeline_contribution.py','review','--baseline',str(baseline_path),
            '--submission',str(path),'--output',str(work/'too-large')]),patch.object(contribution,'MAX_BYTES',64):
        rejected(contribution.main)
    assert not (work/'too-large').exists()
    conflict=copy.deepcopy(document)
    conflict['records'][1]['state']['ghi']^=1
    bad_shared=copy.deepcopy(shared);bad_shared['template']=conflict;bad_shared['template_sha256']=contribution.digest(conflict)
    report,quarantined=contribution.review(baseline,[shared,bad_shared])
    assert len(report['quarantined_conflicts'])==1 and len(quarantined['records'])==1
    assert all(r['key']!=document['records'][1]['key'] for r in quarantined['records'])
    incompatible=copy.deepcopy(document);incompatible['compatibility']['elf_sha256']='f'*64
    rejected(lambda:contribution.review(baseline,[contribution.encode(incompatible)]))
    rejected(lambda:contribution.review(baseline,[shared]*17))
    candidate_path=work/'candidates.json';contribution.write_json(candidate_path,candidates)
    rows=[]
    for number,r in enumerate(candidates['records'],1):
        result={name:False for name in RESULT_BOOLS}
        native=f'{number:016x}'
        result.update(expected=native,actual=native,created=True,hresult='00000000')
        rows.append(dict(key=native,input_key=r['key'],status='prepared',result=result))
    proof=dict(schema=1,template_format=3,template_sha256=template.template_digest(candidate_path),
        engine_sha256='a'*64,decoder_sha256='b'*64,requested=len(rows),records=rows,
        counts={'prepared':len(rows)},preparation_seconds=1,
        inventory=dict(valid_driver_blobs=[r['key'] for r in rows],rejected=[]))
    proof['runtime_lookup_counts']=[len(rows)]*4
    assert len(contribution.accept(baseline,candidates,candidate_path,proof)['records'])==3
    for field,value in (('template_sha256','e'*64),('counts',{'prepared':1}),('requested',1)):
        bad=copy.deepcopy(proof);bad[field]=value
        rejected(lambda:contribution.accept(baseline,candidates,candidate_path,bad))
    bad=copy.deepcopy(proof);bad['records'][0]['result']['actual']='f'*16
    rejected(lambda:contribution.accept(baseline,candidates,candidate_path,bad))
    bad=copy.deepcopy(proof);bad['inventory']['valid_driver_blobs']=[]
    rejected(lambda:contribution.accept(baseline,candidates,candidate_path,bad))
    # Bound local recording names before the exporter can open recipe/raw files.
    trace=work/'trace';trace.mkdir();cache=work/'cache';cache.mkdir()
    link=dict(pipeline='../escape',vp_raw='a'*16,fp_raw='b'*16,vs='c'*16,ps='d'*16,
              vp_cache='e'*16,fp_cache='f'*16,vp_identity_bytes=16)
    (trace/'links_1.jsonl').write_text(json.dumps(link)+'\n')
    with patch.object(template,'export') as exporter:
        rejected(lambda:contribution.capture(trace,cache,document['compatibility']))
        assert not exporter.called
    # A conflict inside one recorder session must quarantine the first row too.
    raw=b'local-test-bytes!'
    row=dict(document['records'][0],key='1'*16,vs='2'*16,ps='3'*16,vp_source='4'*16,fp_source='5'*16)
    recorder=dict(pipeline=row['key'],vs=row['vs'],ps=row['ps'],fp_flags=0,
        vp_raw=f'{template.fnv64(raw):016x}',fp_raw=f'{template.fnv64(raw):016x}',
        vp_identity_bytes=16,vp_cache=row['vp_source'],fp_cache=row['fp_source'],
        vp_gpu=row['vp_gpu'],state=copy.deepcopy(row['state']))
    other=copy.deepcopy(recorder);other['state']['ghi']^=1
    (trace/'links_1.jsonl').write_text('\n'.join(json.dumps(c) for c in (recorder,other,recorder))+'\n')
    recipe=bytearray(2760);struct.pack_into('<QQ',recipe,24,int(row['vs'],16),int(row['ps'],16))
    with patch.object(template,'validate_recipe'), \
            patch.object(template,'bounded_read',side_effect=lambda p,n:bytes(recipe) if p.suffix=='.recipe' else raw), \
            patch.object(template,'has_flow',return_value=False), \
            patch.object(template,'fp_identity',return_value={'identity':row['fp']['sha256'],'size':16}), \
            patch.object(template,'native_state',return_value=row['native']):
        exported,excluded=template.export(trace,cache,document['compatibility'])
        assert len(exported['records'])==2 and not excluded
    # Collect starts only its launcher with a private opt-in recorder. It never
    # changes async settings, sends data or copies raw files into the share file.
    from types import SimpleNamespace
    import train_pipeline_cache,preparation_settings,pipeline_collection
    storage=work/'Storage';(storage/'shadercache').mkdir(parents=True)
    selected=storage/'preparation'/('a'*24)/'shadercache';selected.mkdir(parents=True)
    (storage/'prepared-cache.txt').write_text(selected.relative_to(storage).as_posix())
    install=work/'Install';install.mkdir()
    selection=dict(requested='auto',mode='default',source='launcher-settings',resolution=720)
    with patch.object(train_pipeline_cache,'idle'), patch.object(preparation_settings,'select',return_value=selection), \
            patch.object(preparation_settings,'verify') as verify, \
            patch.object(template,'read',return_value=document), \
            patch.object(template,'compatibility',return_value=document['compatibility']), \
            patch.object(contribution,'capture',return_value=(shared,{})) as capture, \
            patch.object(pipeline_collection,'begin') as begin, \
            patch.object(contribution.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run, \
            patch.object(contribution.shutil,'disk_usage',return_value=SimpleNamespace(free=2*1024**3)), \
            patch.dict(os.environ,{'RSX_SHADER_CACHE':str(storage/'wrong-cache')}):
        contribution.player_main(['--install',str(install),'--storage',str(storage)],collect=True)
        assert run.call_count==1 and verify.call_count==1
        env=run.call_args.kwargs['env']
        assert env['PS3_VERBOSE']=='0' and env['GT5P_USER_DIR']==str(storage)
        assert env['RSX_PSO_PROVENANCE_LIMIT']=='4096'
        for key in ('RSX_SHADER_ASYNC','RSX_PSO_ASYNC'):
            assert env.get(key)==os.environ.get(key)
        assert capture.call_args.args[1]==selected
        assert begin.call_count==1 and begin.call_args.args[3]==shared
        assert not list((storage/'pipeline-contributions').glob('*/share-this-template.json'))
    if os.name=='nt':
        home=work/'Home';home.mkdir()
        (home/'storage.ini').write_text('[game]\ndirectory='+str(storage)+'\n',encoding='utf-16')
        with patch.dict(os.environ,{'GT5P_LAUNCHER_HOME':str(home),'GT5P_USER_DIR':''}):
            assert contribution.default_storage()==storage
    (work/'validation.json').write_text(json.dumps(dict(metadata_only=True,conflicts_quarantined=True,
        proof_required=True,collection_opt_in=True,existing_output_preserved=True),indent=2))
    print('Contribution schema, privacy, conflicts, proof gate and collection command checks passed:',work)


if __name__=='__main__':main()
