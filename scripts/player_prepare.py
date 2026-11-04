"""Standalone optional player preparation. Original assets and all outputs stay local."""
import sys
import shader_vertex_batch
# Frozen or source workers must dispatch before preparation parsing, UI, or a second prepare.
if __name__ == '__main__' and shader_vertex_batch.worker_requested(sys.argv):
    sys.exit(shader_vertex_batch.worker_main(sys.argv))

import argparse
import csv
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import pipeline_template as template
import shader_fragment_batch
from preparation_checkpoint import generation_entry_budget, preflight_tree
from shader_coverage import ROOT
from pipeline_asset_map import read as read_map
from preparation_reuse import cache_root, regular_read
from preparation_settings import select as select_settings, verify as verify_settings


def shader_pack_plan(translation):
    """Observed plan for the default translation only. Other modes stay plan-free."""
    if translation != 'default':
        return None
    plan = ROOT/'config/pipeline-warmup/gt5p-disc-v2.json'
    if plan.is_symlink() or plan.is_junction() or not plan.is_file():
        raise ValueError('Default shader-pack plan is missing or redirected')
    return plan


def preparation_token(metadata, engine_hash, decoder_hash, packs, plan=None, enumeration=None):
    """Pin the plan as well as pack format; preserve the older no-pack identity."""
    marker = ''
    if packs:
        from pipeline_warmup_plan import validate
        validate(plan)
        plan_hash=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        marker='shader-packs-v1:'+plan_hash
    if enumeration is not None:
        marker+='enumeration-v1:'+enumeration
    return hashlib.sha256((metadata+engine_hash+decoder_hash+marker).encode()).hexdigest()[:24]


MAX_GENERATIONS=64


def generation_path(parent, token, number=0):
    identity=token+'\nlearned-cache-v1\n'+str(number)
    name=token if number==0 else hashlib.sha256(identity.encode()).hexdigest()[:24]
    return parent/name


def learned_metadata_changed(output, plan, progress=None):
    """Read only: the renderer may reorder/extend seeded packs and indices."""
    from pipeline_warmup_plan import MAX_INDEX
    from pipeline_runtime_coverage import MAX_REPORT
    from preparation_shader_pack import _file_digest, MAX_BYTES, MAX_ENTRIES
    cache=cache_root(output/'shadercache')
    report=json.loads(regular_read(output/'report.json',MAX_REPORT))
    # The native producer checkpoints its own completion before the subsequent
    # pack/index stage. Owner death in that interval must resume that stage,
    # rather than treating an unpublished generation as a learned play cache.
    if report.get('shader_packs') is None or report.get('warmup_plan') is None:
        return False
    from pipeline_warmup_plan import native_plan
    plan = native_plan(plan, report)
    for phase, keys in plan['phases'].items():
        if progress:progress('checking-learned-cache',{})
        path=cache/'warmup-v1'/(phase+'-v1.txt')
        expected=''.join(key+'\n' for key in keys).encode('ascii')
        try:actual=regular_read(path,MAX_INDEX)
        except FileNotFoundError:return True
        if actual!=expected:return True
        row=report.get('shader_packs',{}).get('phases',{}).get(phase,{})
        size, digest=row.get('file_bytes'),row.get('sha256')
        if (type(size) is not int or not 12<=size<=MAX_BYTES+MAX_ENTRIES*12+12
                or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest)):
            raise ValueError('Completed preparation is missing valid shader-pack evidence; cache preserved')
        try:actual=_file_digest(cache/(phase+'-shaders-v1.pack'),MAX_BYTES+MAX_ENTRIES*12+12,
            (lambda:progress('checking-learned-cache',{})) if progress else None)
        except FileNotFoundError:return True
        if actual!=(size,digest):return True
    return False


def preparation_output(parent, token, plan=None, progress=None):
    """Resume interrupted/unchanged work, fork after completed cache learning.

    Never write to the selected learned cache to make it resemble a seed. The
    existing verified reuse path imports only shaders/driver hints into a fork.
    Deterministic bounded slots let an interrupted fork resume on the next run.
    """
    for number in range(MAX_GENERATIONS if plan is not None else 1):
        output=generation_path(parent,token,number)
        if not output.exists():return output
        state=json.loads(regular_read(output/'preparation-state.json',65536))
        if not isinstance(state,dict):raise ValueError('Malformed preparation state; cache preserved')
        if plan is None or state.get('phase')!='complete' or not learned_metadata_changed(output,plan,progress):
            return output
    raise ValueError('Preparation generation limit reached; existing caches preserved')


def safe_storage(storage):
    storage=storage.absolute()
    for p in (storage,*storage.parents):
        if p.is_symlink() or p.is_junction():raise ValueError('Preparation storage must not be redirected')
    if not storage.is_dir():raise ValueError('Player storage is missing')
    return storage.resolve()


def previous_cache(storage, output):
    """Only reuse the launcher's storage-relative, generated cache selection."""
    pointer=storage/'prepared-cache.txt'
    if not pointer.exists() and not pointer.is_symlink():return None
    relative=regular_read(pointer,512).decode('utf-8')
    if not re.fullmatch(r'preparation/[0-9a-f]{24}/shadercache',relative):
        raise ValueError('Invalid previous preparation cache selection; caches preserved')
    selected=storage/relative
    # Resume already verifies the destination. Importing it into itself would
    # confuse ownership and cannot provide any additional reuse.
    if selected==output/'shadercache':return None
    return cache_root(selected)


def main():
    if shader_vertex_batch.worker_requested(sys.argv):
        sys.exit(shader_vertex_batch.worker_main(sys.argv))
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('install','storage'):ap.add_argument('--'+name,type=Path,required=True)
    source=ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--assets',type=Path,help='Legacy unpacked asset directory')
    source.add_argument('--game',type=Path,help='The already configured disc/PS3_GAME folder')
    ap.add_argument('--launcher-pid',type=int,default=0)
    ap.add_argument('--no-reuse',action='store_true',help='Prepare without reading the previous selected cache')
    a=ap.parse_args()
    storage=safe_storage(a.storage)
    selection=select_settings(storage)
    translation=selection['mode']
    install=a.install.resolve()
    def idle_for_player():
        # Verify the optional visible launcher owner. Exclude only our actual
        # parent, after verifying its full image path; never ignore another game.
        allowed=0
        if a.launcher_pid:
            if a.launcher_pid!=os.getppid():raise ValueError('Preparation launcher owner mismatch')
            api=ctypes.WinDLL('kernel32',use_last_error=True)
            api.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_bool,ctypes.c_ulong];api.OpenProcess.restype=ctypes.c_void_p
            api.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
            api.CloseHandle.argtypes=[ctypes.c_void_p]
            handle=api.OpenProcess(0x1000,False,a.launcher_pid)
            path=ctypes.create_unicode_buffer(32768);size=ctypes.c_ulong(len(path))
            try:
                if not handle or not api.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)):
                    raise ValueError('Cannot verify preparation launcher owner')
                if Path(path.value).resolve()!=install/'tourline-prologue.exe':raise ValueError('Preparation launcher image mismatch')
            finally:
                if handle:api.CloseHandle(handle)
            allowed=a.launcher_pid
        result=subprocess.run(['tasklist','/FI','IMAGENAME eq gt5p.exe','/FO','CSV','/NH'],capture_output=True,text=True,check=True)
        for row in csv.reader(result.stdout.splitlines()):
            if len(row)>1 and row[0].lower()=='gt5p.exe' and int(row[1])!=allowed:
                raise ValueError('Another GT5P process is running; nothing was stopped')
    template.idle=idle_for_player
    engine=install/'runtime/gt5p.exe';decoder=install/'preparation/decoder.dll'
    bundle=install/'assets/pipeline-templates/gt5p-disc-v2'
    document=template.read(bundle,legacy=os.environ.get('GT5P_PREPARE_INPUT_TEMPLATE')=='0')
    from pipeline_template_inputs import input_contract
    if input_contract(document['compatibility'])!=template.compatibility(engine,decoder,storage/'input/EMAIN.ELF'):
        raise ValueError('This template does not match the installed game/renderer')
    location_map=bundle/'player-map.json'
    metadata_items=[document,read_map(location_map)]
    if document.get('version') == 3:
        metadata_items.append(selection)
    volume=volume_map=None
    if a.game:
        from game_volume import read as read_volume
        game=a.game.resolve()
        if not (game/'PARAM.SFO').exists() and (game/'PS3_GAME').is_dir():game=game/'PS3_GAME'
        volume=game/'USRDIR/GT.VOL';volume_map=bundle/'volume-map.json'
        metadata_items.append(read_volume(volume_map))
    metadata=json.dumps(metadata_items,sort_keys=True,separators=(',',':'))
    plan=shader_pack_plan(translation)
    packs=plan is not None
    from pipeline_warmup_plan import read as read_plan, load as load_plan
    plan_document=(load_plan(plan,bundle) if document.get('version') == 3 else read_plan(plan)) if packs else None
    from preparation_enumeration import enabled as enumerate_enabled, load as load_enumeration, sample_share
    enumeration=load_enumeration(install/'assets/shader-enumeration/gt5p-disc-v1',bundle) if enumerate_enabled() else None
    collapse=sample_share() if enumeration is not None else False
    token=preparation_token(metadata,hashlib.sha256(engine.read_bytes()).hexdigest(),
                            hashlib.sha256(decoder.read_bytes()).hexdigest(),packs,plan_document,
                            enumeration['sha256']+':'+str(collapse) if enumeration is not None else None)
    parent=storage/'preparation'
    # Retained generations share this directory. A few thousand records across
    # two generations can exceed the old 100000-entry scan limit.
    if parent.exists():preflight_tree(parent, generation_entry_budget()*MAX_GENERATIONS)
    parent.mkdir(exist_ok=True)
    cancel=storage/'prepare.cancel';status=storage/'prepare-status.txt'
    last_status=['',0.0]
    def progress(phase,counts):
        if cancel.exists():raise KeyboardInterrupt('Preparation cancelled; completed files kept')
        text=phase.replace('-',' ').capitalize()
        if 'completed' in counts:text+=f" {counts['completed']}/{counts['total']}"
        now=time.monotonic()
        if phase==last_status[0] and now-last_status[1]<.1:return
        status.write_text(text,encoding='utf-8')
        last_status[:]=[phase,now]
    out=preparation_output(parent,token,plan_document,progress)
    reuse=None if a.no_reuse or os.environ.get('GT5P_PREPARE_REUSE')=='0' else previous_cache(storage,out)
    def run_owned(exe,game_root,env,log,timeout=180):
        idle_for_player()
        begin=time.monotonic()
        with log.open('wb') as stream:
            child=subprocess.Popen([str(exe)],cwd=game_root,env=env,stdout=stream,stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                while child.poll() is None:
                    if cancel.exists():raise KeyboardInterrupt('Preparation cancelled; completed files kept')
                    if time.monotonic()-begin>timeout:raise TimeoutError('Preparation process exceeded its time budget')
                    time.sleep(.1)
                if child.returncode:raise ValueError('Preparation process failed; see '+str(log))
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=15)
        text=log.read_text(encoding='utf-8',errors='replace')
        if 'guest entry was not executed' not in text or '[GT5P] Executing' in text:
            raise ValueError('Offline execution guard was not confirmed')
        return text
    # The same owned runner is used by native PSO and exact fragment batches.
    template.run_offline=run_owned
    shader_fragment_batch.run_offline=run_owned
    report=template.prepare(bundle,None,storage/'input/EMAIN.ELF',engine,decoder,storage,out,
        assets=a.assets.resolve() if a.assets else None,asset_map=location_map,resume=out.exists(),
        output_validator=lambda p:p,progress=progress,reuse_cache=reuse,volume=volume,volume_map=volume_map,
        vertex_mode=shader_vertex_batch.player_mode(),translation=translation,
        warmup_plan=plan,shader_packs=packs,enumeration=enumeration,enumeration_sample_share=collapse)
    if report['counts']!={'prepared':len(document['records'])}:
        raise ValueError('Some entries could not be prepared; normal play remains available. See '+str(out/'report.json'))
    verify_settings(selection,storage)
    report['player_settings']=selection
    template.save_report(out/'report.json',report)
    # Switch only after successful shader/native/persistence validation. Existing
    # caches remain intact; game demand can add missing/settings-specific entries.
    pointer=storage/'prepared-cache.txt';pending=pointer.with_suffix('.tmp')
    pending.write_text((out/'shadercache').relative_to(storage).as_posix(),encoding='utf-8');pending.replace(pointer)
    status.write_text('Complete. Normal demand compilation handles uncovered pipelines.',encoding='utf-8')


if __name__=='__main__':
    try:
        modes=('--export-contribution','--collect-contribution','--verify-contribution')
        if any(mode in sys.argv[1:] for mode in modes):
            from pipeline_contribution import player_main
            if sum(mode in sys.argv for mode in modes)!=1:
                raise ValueError('Choose collection, verification resume or export')
            player_main([arg for arg in sys.argv[1:] if arg not in modes],
                        collect='--collect-contribution' in sys.argv,resume='--verify-contribution' in sys.argv)
        else:main()
    except KeyboardInterrupt:
        print('Cancelled. Completed preparation is retained for resume.',flush=True);sys.exit(2)
    except Exception as exc:
        print(str(exc),file=sys.stderr,flush=True);sys.exit(1)
