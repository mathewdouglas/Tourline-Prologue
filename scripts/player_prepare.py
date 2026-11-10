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
    import shader_source_policy
    policy=shader_source_policy.marker()
    if policy:marker+='source-policy:'+policy
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


def release_identity(install):
    """Cheap fingerprint of what a preparation was made from: the engine, the decoder, the bundled
    templates, the shader-pack plan and the enumeration metadata (not the player's settings).

    Parsing and validating the templates for the exact preparation token takes about ten seconds, too
    long for the launcher's one-time update check. A completed preparation records this fingerprint
    beside prepared-cache.txt; the check compares it, so only a preparation made by this version counts.
    """
    digest=hashlib.sha256(b'release-identity-v1\n')
    def add(name,path):
        with path.open('rb') as stream:digest.update(name.encode()+b'\0'+hashlib.file_digest(stream,'sha256').digest())
    add('engine',install/'runtime/gt5p.exe');add('decoder',install/'preparation/decoder.dll')
    add('plan',ROOT/'config/pipeline-warmup/gt5p-disc-v2.json')
    import shader_compiler
    if shader_compiler.mode()=='dxc':
        # Phase 231: the compiler is part of every shader key. FXC (RSX_SHADER_COMPILER=fxc) keeps the old identity.
        digest.update(b'shader-compiler\0dxc')
        dxc=install/'runtime/dxcompiler.dll'
        if dxc.is_file():add('dxcompiler',dxc)
    for name in ('pipeline-templates/gt5p-disc-v2','shader-enumeration/gt5p-disc-v1'):
        folder=install/'assets'/name
        for path in sorted(p for p in folder.rglob('*') if p.is_file()):
            if path.is_symlink():raise ValueError('Preparation inputs must not be links')
            add(path.relative_to(install).as_posix(),path)
    return digest.hexdigest()


def selected_is_current(storage, install, full=False):
    """Read only. True when prepared-cache.txt selects a completed preparation made by this release."""
    pointer=storage/'prepared-cache.txt'
    if not pointer.is_file() or pointer.is_symlink():return False
    try:
        selected=regular_read(pointer,512).decode('utf-8')
        if not re.fullmatch(r'preparation/[0-9a-f]{24}/shadercache',selected):return False
        recorded=regular_read(storage/'prepared-identity.txt',128).decode('ascii').strip()
        state=json.loads(regular_read(storage/selected.rpartition('/')[0]/'preparation-state.json',65536))
    except (OSError,ValueError):return False
    if not (isinstance(state,dict) and state.get('phase')=='complete' and recorded==release_identity(install)):
        return False
    try:
        import preparation_quick
        scope=preparation_quick.scope(storage/selected.rpartition('/')[0])
        if scope:
            if scope['settings']!=preparation_quick.settings_key(storage):return False
            if full and scope['kind']!='full':return False
    except (OSError,ValueError):return False
    return True


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


def race_stage(folder, document, bundle, translation, live, storage, engine, decoder, location_map, assets,
               volume, volume_map, progress, runner):
    """Phase 225 race stage (scripts/background_preparation.py). Errors are reported, never fatal: the full
    stage follows either way."""
    import background_preparation, msaa_pipeline_map
    from pipeline_warmup_plan import load as load_plan
    def prepare_stage(subset, output, resume, staged):
        return template.prepare(subset,None,storage/'input/EMAIN.ELF',engine,decoder,storage,output,
            assets=assets,asset_map=location_map,resume=resume,output_validator=lambda p:p,progress=staged,
            volume=volume,volume_map=volume_map,vertex_mode=shader_vertex_batch.player_mode(),translation=translation)
    def msaa_stage(output, report, staged):
        from interp_pipeline_classes import player_settings
        shape=player_settings(storage)
        if shape is None:return None
        result=msaa_pipeline_map.prepare(output,engine,storage,report,translation,shape[0],runner,staged)
        report['msaa_map']=msaa_pipeline_map.compact(result)
        return result['mapping'] if result['status']=='complete' else None
    try:
        plan=load_plan(ROOT/'config/pipeline-warmup/gt5p-disc-v2.json',bundle)
        return background_preparation.prepare_race(folder,document,plan,translation,live,prepare_stage,msaa_stage,progress)
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 - the full stage still runs
        print('Background race stage not merged: '+str(exc),file=sys.stderr,flush=True)
        return dict(status='failed',reason=str(exc))


def interp_stage(install, storage, out, progress, runner):
    """Interpreter pipelines into out/shadercache. Skips are recorded; errors are reported, not fatal."""
    import interp_pipeline_prep
    from shader_reconstruct import offline_env
    cache=out/'shadercache'
    try:
        return interp_pipeline_prep.prepare(install/'runtime/gt5p.exe',storage,cache,storage,
            install/'assets/pipeline-templates/gt5p-disc-v2',out,offline_env(storage,cache),runner,progress)
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 - the shader preparation itself already succeeded
        (out/interp_pipeline_prep.REPORT).write_text(json.dumps(dict(schema=1,status='failed',reason=str(exc))),encoding='utf-8')
        print('Interpreter pipelines not prepared: '+str(exc),file=sys.stderr,flush=True)
        return None


def interp_only(install, storage, progress, runner):
    """--interp-pipelines-only: add the stage to the selected, completed preparation without redoing it."""
    pointer=storage/'prepared-cache.txt'
    if not pointer.is_file() or pointer.is_symlink():raise ValueError('No completed preparation is selected')
    selected=regular_read(pointer,512).decode('utf-8')
    if not re.fullmatch(r'preparation/[0-9a-f]{24}/shadercache',selected):raise ValueError('Invalid cache selection')
    out=storage/selected.rpartition('/')[0]
    state=json.loads(regular_read(out/'preparation-state.json',65536))
    if not isinstance(state,dict) or state.get('phase')!='complete':raise ValueError('Selected preparation is not complete')
    report=interp_stage(install,storage,out,progress,runner)
    if report is None or report.get('status') not in ('complete','skipped'):sys.exit(1)
    print(json.dumps(report))


def process_image(pid):
    """Full image path of a running process, or None."""
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_bool,ctypes.c_ulong];api.OpenProcess.restype=ctypes.c_void_p
    api.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
    api.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=api.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:
        path=ctypes.create_unicode_buffer(32768);size=ctypes.c_ulong(len(path))
        return Path(path.value).resolve() if api.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) else None
    finally:api.CloseHandle(handle)


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
    ap.add_argument('--full',action='store_true',help='Prepare the full starter and catalogue instead of the focused foreground step')
    ap.add_argument('--interp-pipelines-only',action='store_true',
                    help='Only prepare shader-interpreter pipelines into the selected completed preparation')
    ap.add_argument('--check-selected',action='store_true',
                    help='Read only: exit 0 if a completed preparation of the current identity is selected, 3 if not')
    ap.add_argument('--check-full-selected',action='store_true',help='Read only: require full preparation, not just quick menu/race readiness')
    ap.add_argument('--offer-cache-cleanup',action='store_true',
                    help='Offer removal of older completed generations after successful preparation, with no game running')
    ap.add_argument('--background',action='store_true',
                    help='Phase 225: run beside the game at idle priority; race stage merged into --live-cache first')
    ap.add_argument('--live-cache',type=Path,help='With --background: the shader cache the running game uses')
    a=ap.parse_args()
    storage=safe_storage(a.storage)
    install=a.install.resolve()
    if a.check_selected or a.check_full_selected:
        sys.exit(0 if selected_is_current(storage,install,full=a.check_full_selected) else 3)
    import preparation_quick
    quick=preparation_quick.enabled() and not (a.full or a.background or a.interp_pipelines_only or a.offer_cache_cleanup)
    live=None
    if a.background:
        import background_preparation
        if a.live_cache is None or a.interp_pipelines_only:raise ValueError('--background needs --live-cache and a full preparation')
        live=a.live_cache.absolute()
        if not live.is_relative_to(storage):
            raise ValueError('The live cache must be inside the player storage')
        # Before any compiler pool sizes itself. An explicit GT5P_PREPARE_COMPILER_WORKERS still wins.
        os.environ.setdefault('GT5P_PREPARE_COMPILER_WORKERS',str(background_preparation.workers()))
        background_preparation.lower_priority()
    selection=select_settings(storage)
    translation=selection['mode']
    quick_settings=preparation_quick.settings_key(storage) if quick else None
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
                # Background mode works beside this install's own game (and its restarts). A game of any
                # other install, or one whose image cannot be read, still stops preparation.
                if a.background and process_image(int(row[1]))==install/'runtime/gt5p.exe':continue
                raise ValueError('Another GT5P process is running; nothing was stopped')
    template.idle=idle_for_player
    if a.offer_cache_cleanup:
        if a.background:raise ValueError('Cache cleanup cannot run beside the game')
        import preparation_cleanup
        preparation_cleanup.offer(storage,idle_for_player)
        return
    engine=install/'runtime/gt5p.exe';decoder=install/'preparation/decoder.dll'
    bundle=install/'assets/pipeline-templates/gt5p-disc-v2'
    document=template.read(bundle,legacy=os.environ.get('GT5P_PREPARE_INPUT_TEMPLATE')=='0')
    quick_plan=None
    if quick:
        from pipeline_warmup_plan import load as load_quick_plan
        quick_plan=load_quick_plan(ROOT/'config/pipeline-warmup/gt5p-disc-v2.json',bundle)
        if quick_plan['template_sha256']!=template.template_digest(bundle):
            raise ValueError('Quick warmup plan does not match the starter')
        preparation_quick.records(document,quick_plan)
    from pipeline_template_inputs import input_contract
    if input_contract(document['compatibility'])!=template.compatibility(engine,decoder,storage/'input/EMAIN.ELF'):
        raise ValueError('This template does not match the installed game/renderer')
    location_map=bundle/'player-map.json'
    metadata_items=[document,read_map(location_map)]
    if quick:metadata_items.append(dict(quick_preparation_v1=quick_plan,settings=quick_settings))
    if document.get('version') == 3:
        metadata_items.append(selection)
    volume=volume_map=None
    if a.game:
        from game_volume import read as read_volume
        game=a.game.resolve()
        if not (game/'PARAM.SFO').exists() and (game/'PS3_GAME').is_dir():game=game/'PS3_GAME'
        volume=game/'USRDIR/GT.VOL';volume_map=bundle/'volume-map.json'
        metadata_items.append(read_volume(volume_map))
    # Phase 231: guest shaders compile with DXC (the dxcompiler.dll beside the engine) when
    # RSX_SHADER_COMPILER=dxc. Offline engine runs get the same setting (offline_env); a DXC generation has its
    # own token, so FXC and DXC caches are never resumed into each other.
    import shader_compiler
    if shader_compiler.mode()=='dxc':
        dxc=install/'runtime/dxcompiler.dll'
        os.environ['GT5P_PREPARE_DXC_LIBRARY']=str(dxc)
        shader_compiler.Dxc()  # refuse early and clearly when it is missing
        metadata_items.append(dict(shader_compiler='dxc',dxcompiler_sha256=hashlib.sha256(dxc.read_bytes()).hexdigest()))
    metadata=json.dumps(metadata_items,sort_keys=True,separators=(',',':'))
    plan=shader_pack_plan(translation)
    packs=plan is not None
    from pipeline_warmup_plan import read as read_plan, load as load_plan
    plan_document=(load_plan(plan,bundle) if document.get('version') == 3 else read_plan(plan)) if packs else None
    from preparation_enumeration import enabled as enumerate_enabled, load as load_enumeration, sample_share
    enumeration=load_enumeration(install/'assets/shader-enumeration/gt5p-disc-v1',bundle) if not quick and enumerate_enabled() else None
    collapse=sample_share() if enumeration is not None else False
    token=preparation_token(metadata,hashlib.sha256(engine.read_bytes()).hexdigest(),
                            hashlib.sha256(decoder.read_bytes()).hexdigest(),packs,plan_document,
                            enumeration['sha256']+':'+str(collapse) if enumeration is not None else None)
    parent=storage/'preparation'
    # Retained generations share this directory. A few thousand records across
    # two generations can exceed the old 100000-entry scan limit.
    if parent.exists():preflight_tree(parent, generation_entry_budget()*MAX_GENERATIONS)
    parent.mkdir(exist_ok=True)
    if quick:
        bundle,quick_path,quick_plan=preparation_quick.stage_inputs(document,quick_plan,parent/('quick-inputs-'+token))
        document=template.read(bundle)
        if translation=='default':plan,plan_document=quick_path,quick_plan
    cancel=storage/'prepare.cancel';status=storage/'prepare-status.txt'
    last_status=['',0.0]
    def progress(phase,counts):
        if cancel.exists():raise KeyboardInterrupt('Preparation cancelled; completed files kept')
        text=phase.replace('-',' ').capitalize()
        if 'completed' in counts:
            text+=f" {counts['completed']}/{counts['total']}" if 'total' in counts else f" {counts['completed']}"
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
    if a.interp_pipelines_only:
        interp_only(install,storage,progress,run_owned)
        status.write_text('Interpreter pipelines complete.',encoding='utf-8')
        return
    race_folder=None
    if a.background and not (reuse is not None and selected_is_current(storage,install) and
            (preparation_quick.scope(reuse.parent) or {}).get('kind')=='quick'):
        race_folder=parent/('race-'+token)
        race=race_stage(race_folder,document,bundle,translation,live,storage,engine,decoder,location_map,
                        a.assets.resolve() if a.assets else None,volume,volume_map,progress,run_owned)
        print('Background race stage: '+json.dumps(race),flush=True)
        # The full stage reuses the race stage's verified shaders and driver blobs.
        if (race_folder/'stage/shadercache').is_dir() and not a.no_reuse and os.environ.get('GT5P_PREPARE_REUSE')!='0':
            reuse=race_folder/'stage/shadercache'
    report=template.prepare(bundle,None,storage/'input/EMAIN.ELF',engine,decoder,storage,out,
        assets=a.assets.resolve() if a.assets else None,asset_map=location_map,resume=out.exists(),
        output_validator=lambda p:p,progress=progress,reuse_cache=reuse,volume=volume,volume_map=volume_map,
        vertex_mode=shader_vertex_batch.player_mode(),translation=translation,
        warmup_plan=plan,shader_packs=packs,enumeration=enumeration,enumeration_sample_share=collapse)
    if report['counts']!={'prepared':len(document['records'])}:
        raise ValueError('Some entries could not be prepared; normal play remains available. See '+str(out/'report.json'))
    verify_settings(selection,storage)
    report['player_settings']=selection
    # Phase 223: the multisampled pipelines again at the player's MSAA sample count (driver creation only; the
    # shaders are shared). Never changes the token or prepared shaders; a failure keeps the preparation.
    msaa_rows,msaa_mapping=None,None
    try:
        import msaa_pipeline_map
        from interp_pipeline_classes import player_settings
        shape=player_settings(storage)
        if shape is None:
            report['msaa_map']=dict(status='skipped',reason='settings file unreadable')
        else:
            result=msaa_pipeline_map.prepare(out,engine,storage,report,translation,shape[0],run_owned,progress)
            if result['status']=='complete':
                msaa_rows,msaa_mapping={translation:result['lookup_rows']},result['mapping']
            report['msaa_map']=msaa_pipeline_map.compact(result)
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 - optional; the game creates these pipelines on demand
        report['msaa_map']=dict(status='failed',reason=str(exc))
    if quick and msaa_pipeline_map.enabled() and report['msaa_map'].get('status')!='complete':
        raise ValueError('Focused preparation could not validate the settings-specific MSAA pipelines; previous selection kept')
    # Phase 221: the renderer's fast pipeline lookup table for each prepared translation (hints only; never
    # changes prepared shaders, native blobs or the token). GT5P_PREPARE_FAST_LOOKUP=0 skips it.
    try:
        import fast_lookup_table, shader_source_policy
        from interp_pipeline_classes import player_settings
        shape=player_settings(storage)
        report['fast_lookup']=fast_lookup_table.write_for_preparation(out,engine,report,
            high_precision=shape[1] if shape else True,translation_env=shader_source_policy.overlay(),
            extra_rows=msaa_rows)
    except Exception as exc:  # noqa: BLE001 - optional; the game learns the table during play
        report['fast_lookup']=dict(status='failed',reason=str(exc))
    if translation!='default':
        # Phase 221: membership lists for the translation the player runs (default plan mapped through the
        # translation pass); the race prewarm and fast lookup otherwise have nothing resident at 21:9 / >1080p.
        try:
            from pipeline_warmup_plan import load as load_plan_v3, stage_translated
            report['translated_plan']=stage_translated(quick_plan if quick else load_plan_v3(ROOT/'config/pipeline-warmup/gt5p-disc-v2.json',bundle),
                report,out/'shadercache/warmup-v1')
        except Exception as exc:  # noqa: BLE001 - optional; the game learns membership during play
            report['translated_plan']=dict(status='failed',reason=str(exc))
    if msaa_mapping:
        try:
            report['msaa_map']['membership']=msaa_pipeline_map.stage_membership(out/'shadercache/warmup-v1',msaa_mapping)
        except Exception as exc:  # noqa: BLE001 - optional; the game learns membership during play
            report['msaa_map']['membership']=dict(status='failed',reason=str(exc))
    # One sequential read for the race prewarm. Written after membership lists are final.
    # RSX_RACE_PREWARM_PACK=0 keeps the per-file opens. A failure leaves the recipes in place.
    try:
        import race_preload_pack
        warm=out/'shadercache'/'warmup-v1'
        if (warm/'race-v1.txt').is_file():
            report['race_pack']=race_preload_pack.build(warm)
        else:
            report['race_pack']=dict(status='skipped',reason='no race index')
    except Exception as exc:  # noqa: BLE001 - optional; the next race can write this pack from the files
        report['race_pack']=dict(status='failed',reason=str(exc))
    template.save_report(out/'report.json',report)
    # Phase 220: interpreter pipelines, a separate cheap stage. It has its own report, never changes the
    # preparation token, prepared shaders or native blobs, and a failure here keeps the full preparation.
    if not quick:interp_stage(install,storage,out,progress,run_owned)
    # Switch only after successful shader/native/persistence validation. Existing
    # caches remain intact; game demand can add missing/settings-specific entries.
    pointer=storage/'prepared-cache.txt';pending=pointer.with_suffix('.tmp')
    identity=storage/'prepared-identity.txt'
    verify_settings(selection,storage)
    if quick and preparation_quick.settings_key(storage)!=quick_settings:
        raise ValueError('Settings changed during focused preparation; previous selection kept')
    if quick or preparation_quick.enabled():
        preparation_quick.publish_scope(out,storage,quick,len(document['records']))
    # Recorded first: a pointer without a matching fingerprint only costs one more offer.
    identity.write_text(release_identity(install)+'\n',encoding='ascii')
    pending.write_text((out/'shadercache').relative_to(storage).as_posix(),encoding='utf-8');pending.replace(pointer)
    status.write_text('Complete. Normal demand compilation handles uncovered pipelines.',encoding='utf-8')
    # The launcher offers this after the foreground helper exits, or next launch
    # after background completion. Cleanup never interrupts a running game.
    try:
        import preparation_cleanup
        if not quick:preparation_cleanup.schedule(storage)
    except (OSError,ValueError) as exc:
        print('Cache cleanup offer not scheduled: '+str(exc),flush=True)
    if race_folder is not None and race_folder.is_dir() and not race_folder.is_symlink():
        # Its files are in the live cache and in the selected preparation now.
        import shutil
        shutil.rmtree(race_folder,ignore_errors=True)


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
