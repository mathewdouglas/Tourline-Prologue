"""Synthetic enumeration policy, failure, cancellation and verified resume checks."""
import copy
import os
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
    assert enum.sample_share({}) and not enum.sample_share({'GT5P_PREPARE_ENUMERATE_SAMPLE_SHARE':'0'})
    rejected(lambda:enum.sample_share({'GT5P_PREPARE_ENUMERATE_SAMPLE_SHARE':'yes'}))
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
             patch('shader_vertex_batch.compile_jobs',side_effect=vertex),patch.object(enum,'CHUNK',1),patch.dict(os.environ,GT5P_PREPARE_ENUMERATE_BATCH='256'):
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
    # Grouped launches: 512 jobs per launch = two 256-job checkpoint chunks per compiler call.
    assert enum.batch_jobs({})==4096 and enum.batch_jobs({'GT5P_PREPARE_ENUMERATE_BATCH':'256'})==256
    for bad in ('','0','100','8192','1024 '):
        rejected(lambda:enum.batch_jobs({'GT5P_PREPARE_ENUMERATE_BATCH':bad}))
    two=copy.deepcopy(small);two['plan']=dict(small['plan'],fragment_jobs=[[0,0],[0,1]],vertex_jobs=[[vp,0]])
    sizes=[]
    def grouped(batch,work,cache,*args,**kwargs):
        sizes.append(len(batch))
        (work/'fragment-preparation-report.json').write_text('{"batches": [{"requests": %d, "seconds": 0.0}]}'%len(batch))
        out={}
        for n,job in enumerate(batch):
            code=b'DXBCgroup-%d'%n;key='%016x'%(n+1);(cache/(key+'.dxbc')).write_bytes(code);out[job['id']]=(key,code)
        return out,{}
    with tempfile.TemporaryDirectory(dir=ROOT/'scratch',prefix='enum-group-') as temp:
        output=Path(temp)/'generation'
        with patch('game_volume.resolve',return_value=({vp:b'vertex'},{identity:b'fragment'},{})),             patch('shader_fragment_batch.compile_batch',side_effect=grouped),             patch('shader_vertex_batch.compile_jobs',side_effect=vertex),patch.object(enum,'CHUNK',1),             patch.dict(os.environ,GT5P_PREPARE_ENUMERATE_BATCH='512'):
            with Checkpoint(output,{}) as checkpoint:
                (output/'shadercache').mkdir()
                grouped_report=enum.stage(two,output,None,None,None,None,checkpoint,volume=Path('synthetic'))
        assert sizes==[2] and grouped_report['prepared']==3 and grouped_report['failed']==0 and grouped_report['batch_jobs']==512
        assert len(list((output/'enumeration').glob('fragment-*.json')))==2
    # One vertex pool covers every remaining chunk, but each chunk's checkpoint is written the moment it
    # completes, so a cancellation after the first chunk keeps it (resume granularity stays one chunk).
    seen=[]
    vertex_two=copy.deepcopy(small);vertex_two['plan']=dict(small['plan'],fragment_jobs=[[0,0]],vertex_jobs=[[vp,0],[vp,1]])
    def pool(batch,decoder,work,**kwargs):
        assert len(batch)==2
        kwargs['on_ready'](batch[0],'abcdef1234567890','unused',b'DXBCvertex-0')
        seen.append(sorted(p.name for p in (kwargs_output/'enumeration').glob('vertex-*.json')))
        kwargs['poll']()
        raise KeyboardInterrupt('synthetic cancellation inside the vertex pool')
    with tempfile.TemporaryDirectory(dir=ROOT/'scratch',prefix='enum-early-') as temp:
        output=Path(temp)/'generation';kwargs_output=output
        with patch('game_volume.resolve',return_value=({vp:b'vertex'},{identity:b'fragment'},{})),             patch('shader_fragment_batch.compile_batch',side_effect=grouped),             patch('shader_vertex_batch.compile_jobs',side_effect=pool),patch.object(enum,'CHUNK',1),             patch.dict(os.environ,GT5P_PREPARE_ENUMERATE_BATCH='512'):
            try:
                with Checkpoint(output,{}) as checkpoint:
                    (output/'shadercache').mkdir()
                    enum.stage(vertex_two,output,None,None,None,None,checkpoint,volume=Path('synthetic'))
            except KeyboardInterrupt:pass
            else:raise AssertionError('Cancellation inside the vertex pool was swallowed')
        assert seen==[['vertex-0000.json']],seen
        assert sorted(p.name for p in (output/'enumeration').glob('vertex-*.json'))==['vertex-0000.json']
    print(json.dumps(dict(synthetic='passed',fragment_jobs=len(plan['fragment_jobs']),
                          collapsed_fragment_jobs=len(enum.fragment_jobs(plan,True)),vertex_jobs=len(plan['vertex_jobs']))))


if __name__=='__main__':main()
