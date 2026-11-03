"""Synthetic content conflicts, bounded handoff, legacy fallback and result guards."""
import json
import struct
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import preparation_native_handoff as h
import pipeline_native_batch as b

for value in ('auto','0','1'):assert h.choice({'GT5P_PREPARE_HANDOFF':value})==value
for value in ('','2',True):
    try:h.choice({'GT5P_PREPARE_HANDOFF':value})
    except ValueError:pass
    else:raise AssertionError('Invalid handoff accepted')

with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);cache=root/'cache';cache.mkdir()
    engine=root/'engine';engine.write_bytes(h.MARKER)
    with patch.object(h.os,'fstat',return_value=SimpleNamespace(st_size=256*1024*1024+1)):
        assert not h.supported_engine(engine)
    engine.write_bytes(bytes(1024*1024-7)+h.MARKER+b'end')
    assert h.supported_engine(engine)  # Marker spans the scan buffer boundary.
    engine.write_bytes(h.MARKER)
    with patch.dict(os.environ,{'GT5P_PREPARE_HANDOFF':'auto'}):
        writer=h.NativeRequests(engine,cache)
        assert writer.enabled
        vs,ps=b'DXBC-vertex',b'DXBC-fragment'
        recipe=bytes(2760)
        for i in range(4):writer.write(root/f'{i:064x}'/'pipeline',recipe,vs,ps)
        assert writer.report['file_checks_or_writes']==2 and writer.report['verified_memory_hits']==6
        assert len(list(root.rglob('*.dxbc')))==2 and not list(root.rglob('result.json'))
        with patch.object(h,'fnv64',return_value=h.fnv64(vs)):
            try:writer.write(root/('f'*64)/'pipeline',recipe,b'DXBC-conflict',ps)
            except ValueError:pass
            else:raise AssertionError('Content-key conflict accepted')
        writer.release();assert not writer.pool and writer.report['retained_bytes']==0
        assert len(writer.recipes)==5 and writer.recipe_bytes<=h.MAX_RECIPE_BYTES
        writer.finish();assert not writer.recipes
        with patch.object(h,'MAX_BYTES',1),patch.object(h,'MAX_RECIPE_BYTES',1):
            bounded=h.NativeRequests(engine,cache)
            proof=root/('d'*64)/'pipeline'
            bounded.write(proof,recipe,vs,ps)
            assert bounded.bytes==0 and not bounded.pool
            assert not bounded.recipes and (proof/'request.recipe').exists()
            assert bounded.recipe(root,'d'*64)==recipe
        engine.write_bytes(b'old-engine')
        old=h.NativeRequests(engine,cache);assert not old.enabled
        old.write(root/'old',recipe,vs,ps)
        assert len(list((root/'old').glob('*.dxbc')))==2 and (root/'old/result.json').exists()
    identity='1'*64;key='a'*16;manifest=root/'batch-results.jsonl'
    env={'RSX_PSO_PREPARE_RESULTS':str(manifest)}
    def runner(*args,**kwargs):
        manifest.write_text(json.dumps(dict(id=identity,expected=key,actual=key,created=True))+'\n')
        return '[pso-material-batch] valid=1 requests=1 created=1 driver_calls=1 cached_blob_calls=0\n[pso-offline-results] version=1 rows=1 published=1\n'
    results={}
    assert b.run_batches([identity],root,engine,root,env,root/'native.log',runner,results=results)==[1,1,1,0]
    assert results[identity]['actual']==key
    bundled=dict(env,RSX_PSO_PREPARE_REQUESTS=str(root/'batch-requests.bin'))
    results={}
    b.run_batches([identity],root,engine,root,bundled,root/'native.log',runner,
        results=results,recipes=lambda identity:recipe)
    payload=(root/'batch-requests.bin').read_bytes()
    assert struct.unpack('<8sII',payload[:16])==(b'GT5PPRQ2',1,2760)
    assert payload[16:80]==identity.encode() and payload[80:]==recipe
    for damage in ('missing','duplicate','wrong-id','wrong-key','not-created','unpublished'):
        def bad(*args,**kwargs):
            log=runner(*args,**kwargs)
            row=json.loads(manifest.read_text())
            if damage=='missing':manifest.write_text('')
            elif damage=='duplicate':manifest.write_text((json.dumps(row)+'\n')*2)
            elif damage=='wrong-id':row['id']='2'*64;manifest.write_text(json.dumps(row)+'\n')
            elif damage=='wrong-key':row['actual']='b'*16;manifest.write_text(json.dumps(row)+'\n')
            elif damage=='not-created':row['created']=False;manifest.write_text(json.dumps(row)+'\n')
            else:log=log.replace('published=1','published=0')
            return log
        results={}
        try:b.run_batches([identity],root,engine,root,env,root/'native.log',bad,results=results)
        except ValueError:pass
        else:raise AssertionError('Damaged results accepted: '+damage)
        assert not results
print('Bounded verified handoff, content conflicts, legacy fallback and atomic result guards passed')
