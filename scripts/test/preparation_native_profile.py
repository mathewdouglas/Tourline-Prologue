"""Private patched backend, native timing and handoff comparison; delete test caches.

Use an x64 VS environment under isolated_validation.ps1. Original runtime/build
and game files remain read-only. Only metadata/log summaries survive cleanup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/test'))
from preparation_speed_acceptance import build_engine


def build_backend(reference,runtime,fresh):
    source=fresh/'runtime-source';video=source/'libs/video';video.mkdir(parents=True)
    name='libs/video/rsx_d3d12_backend.c'
    original=subprocess.check_output(['git','-C',str(runtime),'show','HEAD:'+name])
    baseline=subprocess.check_output(['git','-C',str(ROOT),'show','7a5c950:patches/ps3recomp-4e8f3ca8-local.patch'])
    baseline_file=fresh/'baseline.patch';baseline_file.write_bytes(baseline)
    subprocess.run(['git','init','-q',str(source)],check=True)
    subprocess.run(['git','-C',str(source),'config','core.autocrlf','false'],check=True)
    (source/name).write_bytes(original)
    def apply(patch,header=False):
        cmd=['git','-C',str(source),'apply','--whitespace=nowarn','--include='+name]
        if header:cmd+=['--include=libs/video/rsx_offline_batch.h']
        subprocess.run(cmd+[str(patch)],check=True)
    apply(baseline_file)
    assert (source/name).read_bytes().replace(b'\r\n',b'\n')==(runtime/name).read_bytes().replace(b'\r\n',b'\n'),'Reference runtime differs from tracked baseline'
    (source/name).write_bytes(original)
    apply(ROOT/'patches/ps3recomp-4e8f3ca8-local.patch',True)
    for path in (runtime/'libs/video').glob('*.h'):shutil.copyfile(path,video/path.name)
    obj=r'ps3recomp\CMakeFiles\ps3recomp_runtime.dir\libs\video\rsx_d3d12_backend.c.obj'
    command=subprocess.check_output(['ninja','-t','commands',obj],cwd=reference,text=True).splitlines()[-1]
    assert str(runtime/name) in command
    objects=fresh/'backend-objects';(objects/'libs/video').mkdir(parents=True)
    command=command.replace(str(runtime/name),str(source/name))
    command=command.replace(r'ps3recomp\CMakeFiles\ps3recomp_runtime.dir',str(objects))
    assert '/Fo'+str(objects) in command and '/Fd'+str(objects) in command
    assert ' -c -- ' in command
    command=command.replace(' -c -- ',' /D_CRT_SECURE_NO_WARNINGS /W0 -c -- ')
    subprocess.run(command,cwd=fresh,check=True)
    return objects/'libs/video/rsx_d3d12_backend.c.obj'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('reference-build','reference-helper','runtime','elf','volume','game-root','game','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--full',action='store_true')
    ap.add_argument('--shared-only',action='store_true',help='Final transport proof using a previously measured legacy control')
    a=ap.parse_args()
    if os.environ.get('VSCMD_ARG_TGT_ARCH','').lower()!='x64':raise ValueError('Use x64 VS environment')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    results=[]
    def run(name,args,env=None):
        print('Starting '+name,flush=True);begin=time.perf_counter()
        with (out/(name+'.log')).open('wb') as log:
            subprocess.run([str(arg) for arg in args],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        results.append(dict(step=name,seconds=time.perf_counter()-begin))
        (out/'status.json').write_text(json.dumps(results,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='p210-',dir=ROOT/'scratch') as directory:
        fresh=Path(directory)
        backend=build_backend(a.reference_build.resolve(),a.runtime.resolve(),fresh)
        engine=build_engine(a.reference_build.resolve(),fresh,backend)
        base=[sys.executable,ROOT/'scripts/test/preparation_fresh_native.py','--engine',engine,
            '--decoder',a.reference_helper/'decoder.dll','--hash-library',a.reference_helper/'cache_hash.dll',
            '--volume-library',a.reference_helper/'volume_reader.dll','--game-root',a.game_root,
            '--elf',a.elf,'--volume',a.volume]
        modes=(('shared','1'),) if a.shared_only else (('legacy','0'),('shared','1'))
        for name,enabled in modes:
            args=base+['--profile','--output',out/(name+'.json')]
            if not a.full:args+=['--limit','32']
            run(name,args,dict(os.environ,GT5P_PREPARE_HANDOFF=enabled,GT5P_PREPARE_NATIVE_PROFILE='1'))
        new=json.loads((out/'shared.json').read_text())
        old=None if a.shared_only else json.loads((out/'legacy.json').read_text())
        assert new['test_cache_removed']
        if old is not None:assert old['counts']==new['counts'] and old['test_cache_removed']
        if a.full and old is not None:
            ids=lambda report:{phase:row['sha256'] for phase,row in report['shader_packs']['phases'].items()}
            assert ids(old)==ids(new)
        assert new['native_timings'] and new['native_handoff']['enabled']
        if old is not None:assert old['native_timings'] and not old['native_handoff']['enabled']
        helper=fresh/'helper'
        run('freeze-helper',[sys.executable,ROOT/'scripts/release/build_preparer.py','--runtime',a.runtime,
            '--decoder',a.reference_helper/'decoder.dll','--output',helper])
        run('frozen',[sys.executable,ROOT/'scripts/test/player_fragment_checkpoint_native.py',
            '--helper-dir',helper/'dist/GT5P-Prepare','--reference-install',engine.parent.parent,
            '--elf',a.elf,'--game',a.game,'--output',fresh/'f'],dict(os.environ,GT5P_PREPARE_HANDOFF='1'))
        (out/'frozen-validation.json').write_bytes((fresh/'f/validation.json').read_bytes())
        engine_hash=hashlib.sha256(engine.read_bytes()).hexdigest()
    assert not fresh.exists()
    (out/'acceptance.json').write_text(json.dumps(dict(passed=True,steps=results,
        private_build_removed=True,engine_sha256=engine_hash),indent=2)+'\n')
    print('Native timing/handoff acceptance and cleanup passed',flush=True)


if __name__=='__main__':main()
