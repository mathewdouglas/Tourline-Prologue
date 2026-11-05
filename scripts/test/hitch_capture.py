"""One private attribution route; invoke through the machine-wide run_locked.py."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
GAME=Path(r'C:\Users\GGPC\Dev\Recomps\GT5P')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('route',choices=('dealer','hsr','daytona'))
    ap.add_argument('condition',choices=('cold','prepared','warm'))
    ap.add_argument('--producer-timeline',action='store_true',help='Additional warm HSR diagnostic using the existing 130-second guest timeline')
    ap.add_argument('--env',action='append',default=[],metavar='NAME=VALUE',help='extra game variable (e.g. RSX_TEX_LRU=1)')
    ap.add_argument('--suffix',default='',help='tag suffix for repeated/AB runs')
    ap.add_argument('--seed-cache',type=Path,help='prepared condition: copy this scratch cache instead of scratch/hitch/preparation')
    ap.add_argument('--engine',type=Path,help='private engine (default scratch/hitch/build)')
    ap.add_argument('--no-foreground',action='store_true',help='do not reject the run when focus moves (timing then unfocused)')
    a=ap.parse_args()
    if a.producer_timeline and (a.route!='hsr' or a.condition!='warm'):ap.error('Producer diagnostic requires hsr warm')
    tasklist=subprocess.check_output(['tasklist','/FI','IMAGENAME eq gt5p.exe'])
    print(tasklist.decode(errors='replace'),flush=True)
    if b'gt5p.exe' in tasklist.lower():raise ValueError('Another game is running')
    home=ROOT/'scratch/hitch'; tag=a.route+'-'+a.condition+('-producer' if a.producer_timeline else '')+(('-'+a.suffix) if a.suffix else '')
    out=home/'routes'/tag;out.mkdir(parents=True,exist_ok=False)
    game=out/'game';(game/'input').mkdir(parents=True)
    shutil.copyfile(GAME/'input/EMAIN.ELF',game/'input/EMAIN.ELF')
    shutil.copytree(GAME/'gamedata',game/'gamedata',ignore=shutil.ignore_patterns('contents'))
    seed=hashlib.sha256()
    for p in sorted((game/'gamedata').rglob('*')):
        if p.is_file():
            seed.update(p.relative_to(game).as_posix().encode()+b'\0')
            with p.open('rb') as f:seed.update(hashlib.file_digest(f,'sha256').digest())
    cache=home/'caches'/(a.route+'-prepared' if a.condition=='warm' else tag)
    if a.producer_timeline:
        source=cache
        cache=home/'caches/hsr-producer'
        shutil.copytree(source,cache)
    if a.condition=='prepared':
        if cache.exists():shutil.rmtree(cache)
        src_cache=(a.seed_cache or home/'preparation/shadercache').resolve()
        assert src_cache.is_relative_to((ROOT/'scratch').resolve())
        subprocess.run(['robocopy',str(src_cache),str(cache),'/E','/NFL','/NDL','/NJH','/NJS','/NP','/MT:8'])
    if a.condition=='cold' and cache.exists():raise ValueError('Cold cache already exists')
    if a.condition=='warm' and not cache.is_dir():raise ValueError('Run prepared condition first')
    cache.mkdir(parents=True,exist_ok=True)
    engine=(a.engine or home/'build/install/runtime/gt5p.exe').resolve()
    context=dict(route=a.route,condition=a.condition,save_sha256=seed.hexdigest(),engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
        initial_dxbc_files=len(list(cache.glob('*.dxbc'))),foreground_policy='relaxed' if a.no_foreground else 'strict',extra_env=a.env,producer_timeline_seconds=130 if a.producer_timeline else 0,settings='1080p/16:9/2x MSAA, default SSAA, async on, interpreter off; OS/driver caches not cleared')
    (out/'context.json').write_text(json.dumps(context,indent=2))
    env=['PS3_VERBOSE=0','GT5P_NO_SETTINGS=1','FS_HIDE=grim/file/contents','GT5P_ROOT='+str(game),
        'PS3_VFS_ROOT='+str(game),'GT5P_GAME_DIR='+str(GAME/'input/pkg')+'/',
        'RSX_SHADER_CACHE='+str(cache),'GT5P_RESOLUTION=1080p','RSX_MSAA=2',
        'RSX_SHADER_INTERP=0','RSX_SHADER_INTERP_VP=0','GT5P_PRESENT_PROF=1',
        'RSX_PSO_TIMING=1','RSX_PIPELINE_METRICS=1','RSX_GPU_TIME=1',
        'RSX_HITCH_LOG='+str(out/(tag+'.trace.csv')),'GT5P_HITCH_HOST_LOG='+str(out/(tag+'.host.csv')),'GT5P_FRAME_LOG='+str(out/(tag+'.frames.csv'))]
    env+=a.env
    if a.producer_timeline:env+=['PS3_TIMELINE=0,130','PS3_TIMELINE_OUT='+str(out/'producer-raw.csv')]
    cmd=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/test'/('hitch_dealer.ps1' if a.route=='dealer' else 'race.ps1')),
         '-Engine',str(engine),'-GameRoot',str(game),'-OutputDirectory',str(out),'-Tag',tag]
    if a.route!='dealer':cmd+=['-Track','HighSpeedRing' if a.route=='hsr' else 'Daytona','-FrameTest','-RaceShots','20','-Cpu','-IntroShots']+([] if a.no_foreground else ['-RequireForeground'])
    try:
        with (out/'route.log').open('w') as f:
            subprocess.run(cmd+env,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
        if a.producer_timeline:
            sys.path.insert(0,str(ROOT/'scripts/diag'))
            from hitch_attribution import read_producer
            raw=out/'producer-raw.csv';parsed=read_producer(raw)
            if parsed['overflow']:raise ValueError('Producer timeline overflowed; diagnostic rejected')
            with raw.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            written=0;anchor=False
            with raw.open(encoding='ascii') as source,(out/'producer.csv').open('x',encoding='ascii') as compact:
                for line in source:
                    if line.startswith('#'):continue
                    t,tid,kind,_a,_b=line.strip().split(',')
                    keep=int(tid)==parsed['tid'] and kind in ('C','Y','S','Q')
                    if not anchor and kind=='P' and int(t)==parsed['first_present_us']:keep=True;anchor=True
                    if keep:compact.write(line);written+=1
                compact.write(f'#events {written} (capacity 4194304)\n')
            context['timeline']=dict(raw_sha256=digest,raw_events=parsed['recorded_events'],compact_events=written,overflow=False)
            assert raw.resolve().parent==out.resolve() and out.resolve().is_relative_to((ROOT/'scratch').resolve())
            raw.unlink()
        context['completed']=True
        context['final_dxbc_files']=len(list(cache.glob('*.dxbc')))
    finally:
        # No junctions are made; original disc path is a read-only VFS input.
        if game.resolve().is_relative_to((ROOT/'scratch').resolve()):shutil.rmtree(game)
        context['private_game_removed']=not game.exists()
        (out/'context.json').write_text(json.dumps(context,indent=2))


if __name__=='__main__':main()
