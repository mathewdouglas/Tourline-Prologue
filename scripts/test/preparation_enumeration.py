"""Synthetic enumeration policy, failure, cancellation and verified resume checks."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import preparation_enumeration as enum
from preparation_checkpoint import Checkpoint
from player_prepare import preparation_token


def rejected(call, error=ValueError):
    try:call()
    except error:return
    raise AssertionError('Invalid input accepted')


def main():
    metadata=enum.load(ROOT/'assets/shader-enumeration/gt5p-disc-v1',ROOT/'assets/pipeline-templates/gt5p-disc-v2')
    assert enum.enabled({}) and not enum.enabled({'GT5P_PREPARE_ENUMERATE':'0'})
    rejected(lambda:enum.enabled({'GT5P_PREPARE_ENUMERATE':'yes'}))
    assert not enum.sample_share({})
    plan=metadata['plan']
    assert len(enum.fragment_jobs(plan,True)) < len(enum.fragment_jobs(plan))
    for mutate in (lambda p:p.update(version=True),lambda p:p['profiles'][0].__setitem__(4,2**64),
                   lambda p:p['fragment_jobs'][0].__setitem__(0,-1),
                   lambda p:p['fragment_jobs'].append(p['fragment_jobs'][0]),
                   lambda p:p['vertex_jobs'][0].__setitem__(1,3)):
        bad=copy.deepcopy(plan);mutate(bad)
        rejected(lambda:enum.validate(bad))
    old=preparation_token('m','e','d',False)
    assert old==preparation_token('m','e','d',False,enumeration=None)
    assert old!=preparation_token('m','e','d',False,enumeration=metadata['sha256'])
    # One successful and one rejected fragment plus a vertex, in separate chunks.
    small=copy.deepcopy(metadata)
    identity=plan['identities'][0];vp=plan['vertex_jobs'][0][0]
    small['plan']=dict(plan,fragment_jobs=[[0,0],[0,1]],vertex_jobs=[[vp,0]])
    small['programs']=dict(metadata['programs'],records=[r for r in metadata['programs']['records']
                                                       if (r['stage'],r['id']) in {('fp',identity),('vp',vp)}])
    calls=[]
    def fragment(batch,work,cache,*args,**kwargs):
        calls.append('fragment')
        (work/'fragment-preparation-report.json').write_text('{"batches": []}')
        if len(calls)==1:
            code=b'DXBCsynthetic-fragment';key='1234567890abcdef'
            (cache/(key+'.dxbc')).write_bytes(code)
            return {'0':(key,code)},{}
        return {},{'0':'synthetic rejection'}
    def vertex(batch,decoder,work,**kwargs):
        calls.append('vertex')
        kwargs['on_ready'](batch[0],'abcdef1234567890','unused',b'DXBCsynthetic-vertex')
        return {},{},{}
    with tempfile.TemporaryDirectory(dir=ROOT/'scratch',prefix='enum-synthetic-') as temp:
        copied=Path(temp)/'metadata'
        shutil.copytree(ROOT/'assets/shader-enumeration/gt5p-disc-v1',copied)
        part=copied/'programs-0000.json';original=part.read_bytes()
        part.write_bytes(original+b' ')
        rejected(lambda:enum.load(copied,ROOT/'assets/pipeline-templates/gt5p-disc-v2'))
        part.write_bytes(original)
        output=Path(temp)/'generation';pointer=Path(temp)/'prepared-cache.txt';pointer.write_text('old selection')
        completed=[]
        def progress(phase,counts):
            if phase=='enumerating-shaders' and counts.get('completed',0)==1:
                completed.append(1)
                raise KeyboardInterrupt('synthetic cancellation')
        with patch('game_volume.resolve',return_value=({vp:b'vertex'},{identity:b'fragment'},{})),\
             patch('shader_fragment_batch.compile_batch',side_effect=fragment),\
             patch('shader_vertex_batch.compile_jobs',side_effect=vertex),patch.object(enum,'CHUNK',1):
            try:
                with Checkpoint(output,{},progress=progress) as checkpoint:
                    (output/'shadercache').mkdir()
                    enum.stage(small,output,None,None,None,None,checkpoint,volume=Path('synthetic'))
            except KeyboardInterrupt:pass
            assert completed and calls==['fragment'] and pointer.read_text()=='old selection'
            with Checkpoint(output,{},True) as checkpoint:
                report=enum.stage(small,output,None,None,None,None,checkpoint,volume=Path('synthetic'))
            assert report['prepared']==2 and report['failed']==1 and report['reused']==1
            assert report['failure_examples']==['synthetic rejection']
            assert not list((output/'shadercache').glob('pso_*'))
            assert calls==['fragment','fragment','vertex']
            with Checkpoint(output,{},True) as checkpoint:
                again=enum.stage(small,output,None,None,None,None,checkpoint,volume=Path('synthetic'))
            assert again['prepared']==2 and again['failed']==1 and again['reused']==2 and len(calls)==3
            (output/'shadercache/1234567890abcdef.dxbc').write_bytes(b'DXBCcorrupt')
            with Checkpoint(output,{},True) as checkpoint:
                rejected(lambda:enum.stage(small,output,None,None,None,None,checkpoint,volume=Path('synthetic')))
            assert pointer.read_text()=='old selection'
            failed=Path(temp)/'failed-process'
            def bad_process(batch,work,*args,**kwargs):
                (work/'fragment-preparation-report.json').write_text(json.dumps(dict(batches=[dict(error='offline guard missing')])))
                return {},{'0':'offline guard missing'}
            with patch('shader_fragment_batch.compile_batch',side_effect=bad_process):
                with Checkpoint(failed,{}) as checkpoint:
                    (failed/'shadercache').mkdir()
                    rejected(lambda:enum.stage(small,failed,None,None,None,None,checkpoint,volume=Path('synthetic')))
                    assert not list((failed/'enumeration').glob('fragment-*.json'))
                    assert pointer.read_text()=='old selection'
            conflicting=Path(temp)/'conflicting-cache'
            with Checkpoint(conflicting,{}) as checkpoint:
                (conflicting/'shadercache').mkdir()
                (conflicting/'shadercache/abcdef1234567890.dxbc').write_bytes(b'DXBCconflicting')
                rejected(lambda:enum.stage(small,conflicting,None,None,None,None,checkpoint,volume=Path('synthetic')),RuntimeError)
                assert not list((conflicting/'enumeration').glob('vertex-*.json'))
                assert pointer.read_text()=='old selection'
    print(json.dumps(dict(synthetic='passed',fragment_jobs=len(plan['fragment_jobs']),
                          collapsed_fragment_jobs=len(enum.fragment_jobs(plan,True)),vertex_jobs=len(plan['vertex_jobs']))))


if __name__=='__main__':main()
