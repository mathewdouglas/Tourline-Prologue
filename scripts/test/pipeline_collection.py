"""Verified-only publication, pending isolation, cancellation and immutable resume."""
import copy
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import pipeline_collection as p
import pipeline_contribution as c
import pipeline_template as t
from pipeline_runtime_coverage import RESULT_BOOLS

source=t.read(Path(__file__).parents[2]/'assets/pipeline-templates/gt5p-disc-v2')
first=copy.deepcopy(source['records'][0]);second=copy.deepcopy(first);second['key']='e'*16
unknown=copy.deepcopy(first);unknown['key']='d'*16;unknown['vp']['sha256']='f'*64
document=dict(source,records=[first,second,unknown]);value=c.encode(document)
original_map=p.locations.read(Path(__file__).parents[2]/'assets/pipeline-templates/gt5p-disc-v2/player-map.json')
wanted={(s,first[s]['sha256']) for s in ('vp','fp')}
known=dict(original_map,records=[r for r in original_map['records'] if (r['stage'],r['id']) in wanted])
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);storage=root/'Storage';storage.mkdir();install=root/'Install'
    (install/'runtime').mkdir(parents=True);(install/'preparation').mkdir()
    (install/'runtime/gt5p.exe').write_bytes(b'engine');(install/'preparation/decoder.dll').write_bytes(b'decoder')
    bundle=install/'assets/pipeline-templates/gt5p-disc-v2';bundle.mkdir(parents=True)
    (bundle/'player-map.json').write_text(json.dumps(known))
    mapping=json.loads((Path(__file__).parents[2]/'assets/pipeline-templates/gt5p-disc-v2/volume-map.json').read_text())
    (bundle/'volume-map.json').write_text(json.dumps(mapping))
    session=storage/'pipeline-contributions'/('session-'+'a'*32);session.mkdir(parents=True)
    (storage/'prepared-cache.txt').write_text('existing-selection')
    with patch.dict('os.environ',{'GT5P_COLLECT_VERIFY':'0'}):
        summary=p.begin(install,storage,session,value,{},dict(mode='default'))
    assert summary['pending']==3 and not (session/'share-this-template.json').exists()
    assert p.session_path(storage)==session
    # Player entry points show a window; console rollback uses the same verifier.
    with patch('collection_ui.show',return_value={'window':True}) as window:
        assert p.verify_session(install,storage,show_ui=True)=={'window':True}
        window.assert_called_once()
    with patch.dict('os.environ',{'GT5P_COLLECT_VERIFY_UI':'0'}), \
            patch.object(p,'idle'),patch.object(p,'storage_lease',return_value=nullcontext()), \
            patch.object(p,'_verify',return_value={'console':True}) as console, \
            patch('collection_ui.show',side_effect=AssertionError('Rollback opened a window')):
        assert p.verify_session(install,storage,show_ui=True)=={'console':True}
        assert console.call_count==1
    calls=[]
    updates=[]
    def prepare(path,*args,**kwargs):
        rows=t.read(path)['records'];calls.append((rows,kwargs))
        result={name:False for name in RESULT_BOOLS}
        result.update(expected=first['key'],actual=first['key'],created=True,hresult='00000000')
        return dict(schema=1,template_sha256=t.template_digest(path),engine_sha256='a'*64,decoder_sha256='b'*64,
            requested=2,counts={'prepared':1,'incompatible':1},preparation_seconds=1,
            records=[dict(key=first['key'],status='prepared',result=result),dict(key=second['key'],status='incompatible',reason='unsupported')],
            inventory=dict(valid_driver_blobs=[first['key']],rejected=[]))
    empty=dict(schema=p.locations.SCHEMA,version=1,records=[])
    patches=[patch.object(p,'idle'),patch.object(p,'storage_lease',return_value=nullcontext()),
        patch.object(p,'configured_volume',return_value=root/'original-volume'),
        patch.object(t,'compatibility',return_value=document['compatibility']),
        patch('pipeline_volume_search.search',return_value=(empty,dict(unresolved=1))),
        patch.object(t,'prepare',side_effect=KeyboardInterrupt('cancelled'))]
    with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5]:
        try:p.verify_session(install,storage)
        except KeyboardInterrupt:pass
        else:raise AssertionError('Cancellation ignored')
    assert not (session/'share-this-template.json').exists()
    assert c.read_json(session/'pending-template.json')['records']==value['template']['records']
    with patch.object(p,'idle'),patch.object(p,'storage_lease',return_value=nullcontext()), \
            patch.object(p,'configured_volume',return_value=root/'original-volume'), \
            patch.object(t,'compatibility',return_value=document['compatibility']), \
            patch('pipeline_volume_search.search',side_effect=AssertionError('Completed lookup repeated')), \
            patch.object(t,'prepare',side_effect=prepare):
        summary=p.verify_session(install,storage,progress=lambda phase,counts:updates.append((phase,counts)))
        assert updates[-1][0]=='publishing'
        assert summary['verified']==1 and summary['pending']==2
        assert {r['key'] for r in c.decode(c.read_json(session/'share-this-template.json'))['records']}=={first['key']}
        assert {r['key'] for r in c.read_json(session/'pending-template.json')['records']}=={second['key'],unknown['key']}
        assert len(calls[0][0])==2 and 'reuse_cache' not in calls[0][1]
        before=(session/'share-this-template.json').read_bytes()
        p.verify_session(install,storage)
        assert (session/'share-this-template.json').read_bytes()==before
    assert (storage/'prepared-cache.txt').read_text()=='existing-selection'
    # Promote newly verified pending rows without replacing the previous export.
    promoted=dict(document,records=[first,second])
    previous=(session/'share-this-template.json').read_bytes()
    versioned=p.publish_verified(session,promoted)
    assert versioned.name!='share-this-template.json'
    assert (session/'share-this-template.json').read_bytes()==previous
    assert {r['key'] for r in c.decode(c.read_json(versioned))['records']}=={first['key'],second['key']}
    (storage/p.POINTER).write_text('../escape')
    try:p.session_path(storage)
    except ValueError:pass
    else:raise AssertionError('Session traversal accepted')
print('Post-play verified-only export, pending rows, cancellation/resume, immutable publication and selected-cache preservation passed')
