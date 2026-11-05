"""Input schema/migration, legacy contributions, membership and output proof."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pipeline_template as template
import pipeline_template_inputs as inputs
import pipeline_contribution as contribution
from pipeline_runtime_coverage import parse_report, RESULT_BOOLS, Rejected
from pipeline_warmup_plan import native_plan, SCHEMA, SCOPE
from player_prepare import preparation_token


def reject(call):
    try: call()
    except (ValueError,Rejected): return
    raise AssertionError('Invalid input/proof accepted')


def main():
    document=template.read(template.ROOT/'assets/pipeline-templates/gt5p-disc-v2')
    assert document['version']==3 and 'renderer_sha256' not in document['compatibility']
    row=copy.deepcopy(document['records'][0])
    assert set(row)==inputs.FIELDS|{'key'} and row['key']==inputs.identity(row)
    assert all(row['native']['words'][i]==0 for i in inputs.LENGTH_WORDS)
    one=dict(document,records=[row])
    for field in ('vs','ps','vp_source','fp_source','renderer_sha256'):
        bad=copy.deepcopy(one);bad['records'][0][field]='a'*16
        reject(lambda:template.validate(bad))
    for change in (lambda r:r['state'].__setitem__('ghi',r['state']['ghi']^1),
                   lambda r:r['native']['words'].__setitem__(4,64),
                   lambda r:r['vp'].__setitem__('size',r['vp']['size']+16),
                   lambda r:r.__setitem__('key','f'*64)):
        bad=copy.deepcopy(one);change(bad['records'][0]);reject(lambda:template.validate(bad))
    assert len(template.validate(dict(one,records=[row,row]))['records'])==1
    # Regression expectations stay private. Changing every output changes no input.
    oldrow=copy.deepcopy(row)
    oldrow.update(key='1'*16,vs='2'*16,ps='3'*16,vp_source='4'*16,fp_source='5'*16)
    oldrow['native']['words'][4]=64;oldrow['native']['words'][8]=128
    old=dict(one,version=2,compatibility=dict(one['compatibility'],renderer_sha256='a'*64),records=[oldrow])
    assert inputs.convert(old)==one
    altered=copy.deepcopy(old)
    altered['compatibility']['renderer_sha256']='b'*64
    altered['records'][0].update(key='6'*16,vs='7'*16,ps='8'*16,vp_source='9'*16,fp_source='a'*16)
    altered['records'][0]['native']['words'][4]=128
    assert inputs.convert(altered)==one
    assert inputs.convert(dict(old,records=[oldrow,altered['records'][0]]))==one
    assert inputs.reference_outputs(old)!=inputs.reference_outputs(altered)
    shared=dict(schema=contribution.SCHEMA,version=1,template=old,template_sha256=contribution.digest(old))
    assert contribution.decode(shared)==one
    assert contribution.review(dict(one,records=[]),[shared])[1]==one
    with tempfile.TemporaryDirectory(dir=template.ROOT/'scratch') as folder:
        path=Path(folder)/'legacy.json';path.write_text(json.dumps(old))
        assert template.read(path)==one and template.read(path,legacy=True)==old
        path=Path(folder)/'new';template.bundle(one,path)
        assert template.read(path)==one
        with patch.object(template,'renderer_contract',side_effect=AssertionError('Source gate used')):
            assert template.read(path)==one
    result={name:False for name in RESULT_BOOLS}
    result.update(expected='1'*16,actual='1'*16,created=True,hresult='00000000')
    proof=dict(schema=1,template_format=3,template_sha256='a'*64,engine_sha256='b'*64,
        decoder_sha256='c'*64,requested=1,counts={'prepared':1},preparation_seconds=1,
        records=[dict(key='1'*16,input_key=row['key'],status='prepared',result=result)],
        inventory=dict(valid_driver_blobs=['1'*16],rejected=[]),runtime_lookup_counts=[1]*4)
    assert parse_report(proof)['default_keys']==['1'*16]
    bad=copy.deepcopy(proof);bad['runtime_lookup_counts']=[1,1,1,0];reject(lambda:parse_report(bad))
    bad=copy.deepcopy(proof);bad['records'][0]['result']['actual']='2'*16;reject(lambda:parse_report(bad))
    plan=dict(schema=SCHEMA,version=2,template_sha256='a'*64,context='default-template-inputs-v3',scope=SCOPE,
        phases=dict(menu=[row['key']],race=[row['key']]),evidence=[dict(source_kind='local-notifier-indices',
        source_sha256='b'*64,report_sha256='c'*64,menu_index_sha256='d'*64,race_index_sha256='e'*64)])
    assert native_plan(plan,proof)['phases']==dict(menu=['1'*16],race=['1'*16])
    bad=copy.deepcopy(plan);bad['phases']['menu']=['f'*64];reject(lambda:native_plan(bad,proof))
    token=preparation_token('inputs','engine-a','decoder',True,plan)
    assert preparation_token('inputs','engine-b','decoder',True,plan)!=token
    import shader_enumerate as enumeration
    observed=enumeration.template_rows([row],{row['fp']['sha256']:[dict(textures=0)]},{})
    assert observed[0][2] is None and observed[0][3]==row['key']
    recall=enumeration.vertex_recall([row],{})
    assert recall['covered_by_key'] is None and recall['covered_same_program']==0
    print('Format-3 inputs, output-free identity, legacy load/checksum, review, native persistence proof and membership passed')


if __name__=='__main__':main()
