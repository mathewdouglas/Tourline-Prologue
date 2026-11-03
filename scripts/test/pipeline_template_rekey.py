"""Single-sample re-key scope, complete native proof, collision and plan guards."""
import copy
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_template import SCHEMA, VERSION, SETTINGS, native_state, validate
from prepare_material_shaders import request_envelope
from pipeline_template_rekey import propose, reissue, remap_plan
from native_pipeline_key import derive_record_from_ids
from pipeline_warmup_plan import SCHEMA as PLAN_SCHEMA, SCOPE, CONTEXT

vs = b'DXBC'+bytes(range(28))
ps = b'DXBC'+bytes(range(28,56))
new_ps = b'DXBC'+bytes(range(32))
raw = bytearray(request_envelope(vs,ps))
state = {k:0 for k in ('blend','nrt','rtfmt','exp32','cmask','cull','stencil','unnorm','cube','vmask','ghi','shd','unhi')}
state['samplers']='0'*16
record = dict(key='1'*16, vs='2'*16, ps='3'*16, vp_source='4'*16, fp_source='5'*16,
    vp=dict(sha256='6'*64,size=16), fp=dict(sha256='7'*64,size=16), vp_gpu=0,
    state=state,native=native_state(raw))
record = derive_record_from_ids(record,'4'*16,vs,'5'*16,ps,123)
msaa = copy.deepcopy(record);msaa['state']['cube']=2<<16;msaa['key']='8'*16
compat = dict(abi='windows-x64-recipe-v1',key_version=1,root_signature_keyed=True,
    renderer_sha256='a'*64,renderer_settings=SETTINGS.copy(),elf_sha256='b'*64,
    translation_policy='default-constbuf-v1')
document=validate(dict(schema=SCHEMA,version=VERSION,compatibility=compat,records=[record,msaa]))
changed=propose(record,record['vp_source'],vs,'9'*16,new_ps,123)
assert changed['key']!=record['key'] and changed['native']['words'][8]==len(new_ps)

def proof(old,new):
    return dict(template_key=old['key'],key=new['key'],status='prepared',rekey_record=new,
        result=dict(actual=new['key'],expected=new['key'],created=True))
report=dict(requested=2,counts={'prepared':2},records=[proof(record,changed),proof(msaa,msaa)])
out,mapping=reissue(document,report,'c'*64)
assert out['records']==[changed,msaa] and out['compatibility']['renderer_sha256']=='c'*64
assert document['records'][0]==record

def reject(action):
    try:action()
    except ValueError:return
    raise AssertionError('Unsafe re-key accepted')

reject(lambda:propose(record,'e'*16,vs,'9'*16,new_ps,123))
reject(lambda:propose(record,record['vp_source'],new_ps,'9'*16,new_ps,123))
reject(lambda:propose(msaa,msaa['vp_source'],vs,'9'*16,new_ps,123))
for mutate in (
    lambda r:r.update(counts={'prepared':1,'key-rejected':1}),
    lambda r:r['records'].pop(),
    lambda r:r['records'].append(r['records'][0]),
    lambda r:r['records'][0]['result'].update(created=False),
    lambda r:r['records'][0]['result'].update(actual='d'*16),
    lambda r:r['records'][0].update(status='incompatible'),
    lambda r:r['records'][0].update(template_key='d'*16),
    lambda r:r['records'][0]['rekey_record']['state'].update(cull=1),
    lambda r:r['records'][0]['rekey_record'].update(vs='d'*16),
):
    bad=copy.deepcopy(report);mutate(bad);reject(lambda:reissue(document,bad,'c'*64))
# Collision must reject even if both otherwise-valid records propose one key.
one=copy.deepcopy(record);one['key']='e'*16
dup=copy.deepcopy(document);dup['records']=[record,one]
collision=dict(requested=2,counts={'prepared':2},records=[proof(record,changed),proof(one,changed)])
reject(lambda:reissue(dup,collision,'c'*64))
plan=dict(schema=PLAN_SCHEMA,version=1,template_sha256='a'*64,context=CONTEXT,scope=SCOPE,
    phases=dict(menu=[record['key']],race=[msaa['key'],record['key']]),
    evidence=[dict(source_kind='local-notifier-indices',source_sha256='1'*64,
        report_sha256='2'*64,menu_index_sha256='3'*64,race_index_sha256='4'*64)])
updated=remap_plan(plan,mapping,'a'*64,'c'*64)
assert updated['phases']==dict(menu=[changed['key']],race=[msaa['key'],changed['key']])
assert updated['evidence']==plan['evidence'] and updated['template_sha256']=='c'*64
reject(lambda:remap_plan(plan,mapping,'b'*64,'c'*64))
reject(lambda:remap_plan(plan,{},'a'*64,'c'*64))
print('Re-key scope, vertex/MSAA preservation, native creation/actual, complete membership, collision and warmup pin guards passed')
