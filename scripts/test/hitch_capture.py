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


REF=Path(r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\out\preparer\dist\GT5P-Prepare')


class Pauser:
    """What the launcher does (Phase 225): a job holding the helper and its children, a manual-reset event the
    game sets while racing (GT5P_RACE_EVENT), and a watcher suspending every job process while it is set."""
    def __init__(self, enabled, begin, log):
        import ctypes, os, threading
        from ctypes import wintypes as W
        self.k=k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.nt=nt=ctypes.WinDLL('ntdll')
        for f,res,args in (('CreateJobObjectW',W.HANDLE,[W.LPVOID,W.LPCWSTR]),('AssignProcessToJobObject',W.BOOL,[W.HANDLE,W.HANDLE]),
                           ('CreateEventW',W.HANDLE,[W.LPVOID,W.BOOL,W.BOOL,W.LPCWSTR]),('WaitForSingleObject',W.DWORD,[W.HANDLE,W.DWORD]),
                           ('OpenProcess',W.HANDLE,[W.DWORD,W.BOOL,W.DWORD]),('CloseHandle',W.BOOL,[W.HANDLE]),
                           ('QueryInformationJobObject',W.BOOL,[W.HANDLE,ctypes.c_int,W.LPVOID,W.DWORD,W.LPVOID])):
            getattr(k,f).restype=res;getattr(k,f).argtypes=args
        nt.NtSuspendProcess.argtypes=nt.NtResumeProcess.argtypes=[W.HANDLE]
        self.job=k.CreateJobObjectW(None,None)
        self.name=f'Local\\TourlinePrologue-Race-test-{os.getpid()}'
        self.event=k.CreateEventW(None,True,False,self.name) if enabled else None
        self.stop=threading.Event();self.begin=begin;self.log=log;self.pauses=0;self.paused=0.0
        self.thread=threading.Thread(target=self.watch,daemon=True) if enabled else None

    def assign(self, process):
        if not self.k.AssignProcessToJobObject(self.job,int(process._handle)):raise OSError('job assignment failed')
        if self.thread:self.thread.start()

    def watch(self):
        import ctypes, time
        held={}; since=None
        def release():
            nonlocal since
            for h in held.values():self.nt.NtResumeProcess(h);self.k.CloseHandle(h)
            held.clear()
            if since is not None:
                self.paused+=time.monotonic()-since;since=None
                self.log.write(f'{time.monotonic()-self.begin:8.1f} [pause] resumed\n');self.log.flush()
        while not self.stop.wait(.25):
            if self.k.WaitForSingleObject(self.event,0)!=0:release();continue
            if since is None:
                since=time.monotonic();self.pauses+=1
                self.log.write(f'{since-self.begin:8.1f} [pause] racing; helper suspended\n');self.log.flush()
            ids=(ctypes.c_ulonglong*514)()
            if not self.k.QueryInformationJobObject(self.job,3,ids,ctypes.sizeof(ids),None):continue
            count=ids[0]>>32   # NumberOfProcessIdsInList
            for i in range(count):
                pid=ids[1+i]
                if pid in held:continue
                h=self.k.OpenProcess(0x0800|0x1000,False,pid)
                if h and self.nt.NtSuspendProcess(h)>=0:held[pid]=h
                elif h:self.k.CloseHandle(h)
        release()

    def close(self):
        if self.thread and self.thread.is_alive():self.stop.set();self.thread.join()
        return dict(pauses=self.pauses,paused_seconds=round(self.paused,1))


def start_helper(storage, engine, out, pause=True):
    """The source helper in --background mode, at idle priority, in a job, paused while racing, as the launcher
    starts it. Its output lines are time-stamped from just before the game launch. Returns (helper, game env)."""
    import os, threading, time
    env=dict(os.environ,GT5P_PREPARE_HASH_LIBRARY=str(REF/'cache_hash.dll'),GT5P_PREPARE_VOLUME_LIBRARY=str(REF/'volume_reader.dll'))
    (storage/'prepare.cancel').unlink(missing_ok=True)
    begin=time.monotonic()
    log=(out/'background-helper.log').open('w',encoding='utf-8')
    pauser=Pauser(pause,begin,log)
    child=subprocess.Popen([sys.executable,str(ROOT/'scripts/player_prepare.py'),'--install',str(engine.parent.parent),
        '--storage',str(storage),'--game',str(GAME/'input/pkg'),'--background','--live-cache',str(storage/'shadercache')],
        cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',
        creationflags=subprocess.IDLE_PRIORITY_CLASS)
    pauser.assign(child)
    def pump():
        for line in child.stdout:
            log.write(f'{time.monotonic()-begin:8.1f} {line}');log.flush()
    thread=threading.Thread(target=pump,daemon=True);thread.start()
    return (child,thread,log,begin,pauser),(['GT5P_RACE_EVENT='+pauser.name] if pause else [])


def stop_helper(helper, storage):
    import time
    child,thread,log,begin,pauser=helper
    paused=pauser.close()
    running=child.poll() is None
    ended=time.monotonic()-begin
    if running:
        (storage/'prepare.cancel').write_text('cancel')
        try:child.wait(timeout=120)
        except subprocess.TimeoutExpired:child.kill();child.wait()
    thread.join(timeout=10);log.close()
    (storage/'prepare.cancel').unlink(missing_ok=True)
    return dict(running_at_route_end=running,route_end_seconds=round(ended,1),returncode=child.returncode,**paused)


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
    ap.add_argument('--menu-delay',type=int,default=0,help='race routes: seconds more on the top menu (race.ps1 -MenuDelaySec)')
    ap.add_argument('--background-no-pause',action='store_true',help='with --background-helper: never pause it while racing')
    ap.add_argument('--background-helper',type=Path,metavar='STORAGE',
                    help='Phase 225: run the source preparation helper in background mode beside the game, with this '
                         'scratch storage (input/EMAIN.ELF, gt5p_settings.toml) and STORAGE/shadercache as the game cache; '
                         '--engine must be the runtime of the scratch install the helper prepares for')
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
    if a.background_helper:
        if a.condition!='cold':ap.error('Background helper runs start from an empty cache')
        storage=a.background_helper.resolve()
        assert storage.is_relative_to((ROOT/'scratch').resolve())
        cache=storage/'shadercache'
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
        initial_dxbc_files=len(list(cache.glob('*.dxbc'))),menu_delay=a.menu_delay,background_helper=bool(a.background_helper),background_pause=not a.background_no_pause,foreground_policy='relaxed' if a.no_foreground else 'strict',extra_env=a.env,producer_timeline_seconds=130 if a.producer_timeline else 0,settings='1080p/16:9/2x MSAA, default SSAA, async on, interpreter off; OS/driver caches not cleared')
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
    if a.menu_delay:cmd+=['-MenuDelaySec',str(a.menu_delay)]
    if a.route!='dealer':cmd+=['-Track','HighSpeedRing' if a.route=='hsr' else 'Daytona','-FrameTest','-RaceShots','20','-Cpu','-IntroShots']+([] if a.no_foreground else ['-RequireForeground'])
    helper=None
    try:
        if a.background_helper:
            helper,signal=start_helper(storage,engine,out,pause=not a.background_no_pause)
            env+=signal
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
        if helper is not None:context['background_helper']=stop_helper(helper,storage)
        # No junctions are made; original disc path is a read-only VFS input.
        if game.resolve().is_relative_to((ROOT/'scratch').resolve()):shutil.rmtree(game)
        context['private_game_removed']=not game.exists()
        (out/'context.json').write_text(json.dumps(context,indent=2))


if __name__=='__main__':main()
