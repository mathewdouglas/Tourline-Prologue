"""Private frozen player acceptance. Invoke each step separately through run_locked.py.

Build uses existing read-only engine objects. Runs use original packed assets,
private storage and clean PATH. Budgeted runs cancel through the real player
marker between chunks so the shared test lock can be released for other agents.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from train_pipeline_cache import idle


def check_sources(install, selected, records):
    import preparation_enumeration as enum
    from shader_enumerate import profile_of
    metadata=enum.load(install/'assets/shader-enumeration/gt5p-disc-v1',install/'assets/pipeline-templates/gt5p-disc-v2')
    plan=metadata['plan'];jobs=enum.fragment_jobs(plan);memo={}
    for path in (selected.parent/'enumeration').glob('fragment-*.json'):
        chunk=json.loads(path.read_text())
        for job,row in zip(jobs[chunk['start']:],chunk['rows']):
            if row:memo[job]=row[0]
    used={i:p[8] for i,p in jobs}
    fragments=0
    for r in records:
        i=r['fp']['sha256']
        if i not in used:continue
        profile=list(profile_of(r['state'],used[i]))
        if profile[1]&0xf0000:profile[1]=(profile[1]&~0xf0000)|0x20000
        actual=memo.get((i,tuple(profile)))
        if actual:
            assert actual==r['fp_source'],(i,actual,r['fp_source'])
            fragments+=1
    vertices={}
    for path in (selected.parent/'enumeration').glob('vertex-*.json'):
        chunk=json.loads(path.read_text())
        for job,row in zip(plan['vertex_jobs'][chunk['start']:],chunk['rows']):
            if row:vertices[tuple(job)]=row[0]
    vertex_matches=0
    for r in records:
        actual=vertices.get((r['vp']['sha256'],r['vp_gpu']))
        if actual:
            assert actual==r['vp_source']
            vertex_matches+=1
    assert fragments and vertex_matches
    return dict(fragment_template_matches=fragments,vertex_template_matches=vertex_matches,mismatches=0)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('step',choices=('build','freeze','run','rollback','verify','reject'))
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--inputs',type=Path,help='Private path JSON; defaults to <output>/inputs.json')
    ap.add_argument('--budget',type=int,default=0,help='Cancel after this many new enumeration chunks')
    a=ap.parse_args();idle();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    install=out/'install';storage=out/'storage'
    inputs=json.loads((a.inputs or out/'inputs.json').read_text())
    if set(inputs)!={'reference_root','reference_helper','runtime','game','elf'}:
        raise ValueError('Private inputs JSON must name the reference root/helper, runtime, game and ELF')
    reference,helper,runtime,game,elf=(Path(inputs[k]).resolve() for k in
        ('reference_root','reference_helper','runtime','game','elf'))
    if a.step=='freeze':
        frozen=out/'helper-final'
        subprocess.run([sys.executable,str(ROOT/'scripts/release/build_preparer.py'),'--runtime',str(runtime),
                        '--decoder',str(helper/'decoder.dll'),'--output',str(frozen)],check=True)
        destination=(install/'preparation').resolve()
        if out not in destination.parents:raise ValueError('Private helper destination escaped output')
        shutil.rmtree(destination)
        shutil.copytree(frozen/'dist/GT5P-Prepare',destination)
        print('Updated frozen helper installed in private test directory',flush=True)
        return
    if a.step=='build':
        from preparation_native_profile import build_backend
        from preparation_speed_acceptance import build_engine
        backend=build_backend(reference/'build',runtime,out)
        engine=build_engine(reference/'build',out,backend)
        assert engine==install/'runtime/gt5p.exe'
        subprocess.run([sys.executable,str(ROOT/'scripts/release/build_preparer.py'),'--runtime',str(runtime),
                        '--decoder',str(helper/'decoder.dll'),'--output',str(out/'helper')],check=True)
        shutil.copytree(out/'helper/dist/GT5P-Prepare',install/'preparation')
        shutil.copytree(ROOT/'assets/pipeline-templates',install/'assets/pipeline-templates')
        shutil.copytree(ROOT/'assets/shader-enumeration',install/'assets/shader-enumeration')
        (storage/'input').mkdir(parents=True)
        shutil.copyfile(elf,storage/'input/EMAIN.ELF')
        source=storage/'preparation'/('a'*24)/'shadercache';source.mkdir(parents=True)
        (source/'preserved.txt').write_text('Prior selected cache remains intact')
        (storage/'prepared-cache.txt').write_text(source.relative_to(storage).as_posix())
        print('Private engine and frozen helper built',flush=True)
        return
    if a.step=='verify':
        import preparation_enumeration as enum
        metadata=enum.load(ROOT/'assets/shader-enumeration/gt5p-disc-v1',ROOT/'assets/pipeline-templates/gt5p-disc-v2')
        from game_volume import resolve
        os.environ['GT5P_PREPARE_VOLUME_LIBRARY']=str(helper/'volume_reader.dll')
        vp,fp,stats=resolve(metadata['programs'],metadata['volume'],game/'USRDIR/GT.VOL',elf)
        assert len(vp)==1120 and len(fp)==5864
        (out/'metadata-verification.json').write_text(json.dumps(stats,indent=2))
        print(json.dumps(dict(vertices=len(vp),fragments=len(fp),lookup=stats)))
        return
    rollback=a.step=='rollback'
    pointer=storage/'prepared-cache.txt'
    before=pointer.read_text() if pointer.exists() else None
    def fingerprint(cache):
        return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in cache.iterdir() if p.is_file()}
    old_cache=storage/before if before else None
    preserved=fingerprint(old_cache) if rollback else None
    cancel=storage/'prepare.cancel';cancel.unlink(missing_ok=True)
    prior={str(p) for p in storage.glob('preparation/*/enumeration/*-*.json')}
    rejected=a.step=='reject';damaged=None;original=None
    if rejected:
        damaged=Path(sorted(prior)[0]);original=damaged.read_bytes()
        value=json.loads(original);value['contract']['plan']='0'*64
        damaged.write_text(json.dumps(value))
    command=[str(install/'preparation/GT5P-Prepare.exe'),'--install',str(install),'--storage',str(storage),'--game',str(game)]
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('GT5P_','RSX_'))}
    env.update(PS3_VERBOSE='0',GT5P_NO_SETTINGS='1',FS_HIDE='grim/file/contents',
               PATH=str(Path(os.environ['SystemRoot'])/'System32'),GT5P_PREPARE_TRANSLATION='default')
    if rollback:env['GT5P_PREPARE_ENUMERATE']='0'
    number=len(list(out.glob('run-*.json')))
    logpath=out/f'run-{number:03d}.log';started=time.perf_counter();cancelled=False
    with logpath.open('wb') as log:
        child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while child.poll() is None:
                if time.perf_counter()-started>1200:raise TimeoutError('Player acceptance exceeded 20 minutes')
                if a.budget:
                    current={str(p) for p in storage.glob('preparation/*/enumeration/*-*.json')}
                    if len(current-prior)>=a.budget:
                        cancel.write_text('Acceptance chunk budget');cancelled=True
                time.sleep(.05)
            code=child.wait()
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=20)
            if damaged is not None:damaged.write_bytes(original)
    elapsed=time.perf_counter()-started
    if rejected:
        assert code==1 and 'Enumeration checkpoint mismatch' in logpath.read_text(errors='replace')
        assert pointer.read_text()==before
        summary=dict(step='reject',code=code,seconds=elapsed,selection_preserved=True,checkpoint_restored=True)
        (out/f'run-{number:03d}.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
        return
    if code not in (0,2):raise AssertionError(logpath.read_text(errors='replace'))
    if code==0:
        selected=storage/pointer.read_text()
        report=json.loads((selected.parent/'report.json').read_text())
    else:
        reports=list(storage.glob('preparation/*/report.json'))
        report=json.loads(reports[0].read_text())
    if code==2:
        assert cancelled and pointer.read_text()==before
        states=[json.loads(p.read_text()) for p in storage.glob('preparation/*/preparation-state.json')]
        assert any(s['phase']=='interrupted' for s in states)
    else:
        assert selected.is_dir() and report['counts']=={'prepared':5669}
        if rollback:
            assert 'enumeration' not in report and not (selected.parent/'enumeration').exists()
            assert pointer.read_text()!=before and fingerprint(old_cache)==preserved
            assert report['resume']['vertex_programs_compiled']==0 and report['fragment_preparation']['processes']==0
            for phase in ('menu','race'):
                name=phase+'-shaders-v1.pack'
                assert (selected/name).read_bytes()==(old_cache/name).read_bytes()
        else:assert report['enumeration']['requested']==30112
        from pipeline_template import read
        records=read(install/'assets/pipeline-templates/gt5p-disc-v2')['records']
        keys={r['key'] for r in records}
        assert {p.stem[4:] for p in selected.glob('pso_*.bin')}==keys
    assert (out/'storage/preparation'/('a'*24)/'shadercache/preserved.txt').read_text()=='Prior selected cache remains intact'
    summary=dict(step=a.step,code=code,seconds=elapsed,cancelled=cancelled,prior_chunks=len(prior),
                 chunks=len(list(storage.glob('preparation/*/enumeration/*-*.json'))),
                 template_seconds=report['preparation_seconds']-report.get('enumeration',{}).get('seconds',0),
                 enumeration=report.get('enumeration'))
    if code==0:
        summary['dxbc_files']=len(list(selected.glob('*.dxbc')))
        summary['dxbc_bytes']=sum(p.stat().st_size for p in selected.glob('*.dxbc'))
        if not rollback:
            expected={r[k] for r in records for k in ('vp_source','fp_source')}
            extra=[p for p in selected.glob('*.dxbc') if p.stem not in expected]
            summary['added_dxbc_files']=len(extra)
            summary['added_dxbc_bytes']=sum(p.stat().st_size for p in extra)
            summary['enumeration_checkpoint_bytes']=sum(p.stat().st_size for p in (selected.parent/'enumeration').glob('*.json'))
            summary['source_validation']=check_sources(install,selected,records)
    (out/f'run-{number:03d}.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
