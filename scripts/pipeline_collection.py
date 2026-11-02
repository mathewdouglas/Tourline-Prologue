"""Post-play original-asset verification. No verification runs during gameplay.

Only independently prepared rows reach the share file. Private inputs, lookup
results and checkpoints survive cancellation; the selected player cache is never
changed. Reports from players remain untrusted maintainer-review candidates.
"""
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

import pipeline_contribution as contribution
import pipeline_template as template
import pipeline_asset_map as locations
import game_volume
from preparation_checkpoint import Checkpoint
from preparation_reuse import cache_root, regular_read
from train_pipeline_cache import idle

VERSION=1
POINTER='last-pipeline-collection.txt'


def atomic_json(path, value):
    path=Path(path)
    cache_root(path.parent)
    if path.exists() or path.is_symlink():regular_read(path, contribution.MAX_BYTES)
    data=contribution.canonical(value)+b'\n'
    if len(data)>contribution.MAX_BYTES:raise ValueError('Collection metadata byte bound exceeded')
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('xb') as stream:stream.write(data)
    temporary.replace(path)


def immutable_json(path, value):
    if path.exists():
        if regular_read(path,contribution.MAX_BYTES)!=contribution.canonical(value)+b'\n':
            raise ValueError('Existing collection metadata differs; retained: '+str(path))
    else:contribution.write_json(path,value)


def publish_verified(session, document):
    value=contribution.encode(document)
    path=session/'share-this-template.json'
    if path.exists():
        previous=contribution.decode(contribution.read_json(path))
        if previous!=value['template']:
            rows={r['key']:r for r in document['records']}
            if (previous['compatibility']!=document['compatibility'] or
                    any(rows.get(r['key'])!=r for r in previous['records'])):
                raise ValueError('Existing verified export differs; retained unchanged')
            # A later search map/decoder may resolve more pending records.
            # Publish an additive version; preserve the earlier verified file.
            path=session/('share-this-template-'+contribution.digest(value)[:16]+'.json')
    immutable_json(path,value)
    return path


def session_path(storage, session=None):
    if session is None:
        relative=regular_read(storage/POINTER,256).decode('ascii').strip()
        if not re.fullmatch('pipeline-contributions/session-[0-9a-f]{32}',relative):
            raise ValueError('Invalid resumable collection selection')
        session=storage/relative
    session=cache_root(session)
    if session.parent!=storage/'pipeline-contributions' or not re.fullmatch('session-[0-9a-f]{32}',session.name):
        raise ValueError('Use an owned collection session inside player storage')
    return session


@contextmanager
def storage_lease(storage):
    # Same exclusive lease as the normal launcher. No deletion or new lock protocol.
    path=storage/'launcher.lock'
    if path.exists() or path.is_symlink():regular_read(path,4096)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p]
    kernel.CreateFileW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateFileW(str(path),0x40000000,0,None,4,0,None)
    if handle in (None,ctypes.c_void_p(-1).value):
        raise ValueError('Player storage is in use; collection kept for later verification')
    try:yield
    finally:kernel.CloseHandle(handle)


def configured_volume(storage):
    regular_read(storage/'setup.ini',64*1024)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetPrivateProfileStringW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_wchar_p]
    kernel.GetPrivateProfileStringW.restype=ctypes.c_ulong
    buffer=ctypes.create_unicode_buffer(32768)
    count=kernel.GetPrivateProfileStringW('game','directory','',buffer,len(buffer),str(storage/'setup.ini'))
    if not count or count>=len(buffer)-1:raise ValueError('Configured original game folder is unavailable')
    game=Path(buffer.value)
    if not (game/'PARAM.SFO').exists() and (game/'PS3_GAME').is_dir():game=game/'PS3_GAME'
    return game/'USRDIR/GT.VOL'


def begin(install, storage, session, value, excluded, selection):
    """Persist input before any expensive work; Ctrl+C can never lose collection."""
    storage=cache_root(storage);session=session_path(storage,session)
    contribution.decode(value)
    immutable_json(session/'collected-template.json',value)
    immutable_json(session/'collection.json',dict(schema=1,selection=selection,excluded=excluded))
    pointer=storage/POINTER
    if pointer.exists() or pointer.is_symlink():regular_read(pointer,256)
    temporary=storage/(POINTER+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(session.relative_to(storage).as_posix()+'\n',encoding='ascii')
    temporary.replace(pointer)
    # Pending records are private even when verification is disabled or cancelled.
    atomic_json(session/'pending-template.json',value['template'])
    if os.environ.get('GT5P_COLLECT_VERIFY')=='0':
        print('Post-play verification disabled. Recording retained as pending; no share file published.',flush=True)
        return dict(verified=0,pending=len(value['template']['records']),disabled=True)
    return verify_session(install,storage,session)


def verify_session(install, storage, session=None):
    storage=cache_root(storage);session=session_path(storage,session)
    idle()
    with storage_lease(storage):
        idle()
        return _verify(Path(install).resolve(),storage,session)


def _verify(install, storage, session):
    value=contribution.read_json(session/'collected-template.json')
    document=contribution.decode(value)
    elf=storage/'input/EMAIN.ELF'
    engine=install/'runtime/gt5p.exe';decoder=install/'preparation/decoder.dll'
    if document['compatibility']!=template.compatibility(engine,decoder,elf):
        raise ValueError('Collected game/renderer context differs; recording retained')
    bundle=install/'assets/pipeline-templates/gt5p-disc-v2'
    map_path=bundle/'search-map.json'
    if not map_path.exists():map_path=bundle/'volume-map.json'
    search_map=game_volume.read(map_path)
    base=locations.read(bundle/'player-map.json')
    archive=configured_volume(storage)
    contract=dict(version=VERSION,input=contribution.digest(document),
        engine=hashlib.sha256(engine.read_bytes()).hexdigest(),decoder=hashlib.sha256(decoder.read_bytes()).hexdigest(),
        search_map=contribution.digest(search_map),known_map=contribution.digest(base))
    identity=contribution.digest(contract)[:24]
    parent=storage/'cv'
    if parent.exists():cache_root(parent)
    parent.mkdir(exist_ok=True)
    root=parent/identity;root.mkdir(exist_ok=True);cache_root(root)
    cancel=session/'verify.cancel'
    last=[None,0.0]
    def progress(phase,counts=None):
        if cancel.exists():raise KeyboardInterrupt('Collection verification cancelled; use Resume pipeline verification.cmd')
        now=time.monotonic()
        if phase!=last[0] or now-last[1]>=1:
            counts=counts or {}
            suffix=f" {counts['completed']}/{counts['total']}" if 'completed' in counts and 'total' in counts else ''
            print('Verifying collection: '+phase.replace('-',' ')+suffix,flush=True)
            last[:]=[phase,now]
    print('Game closed. Verifying original assets and native pipelines. Ctrl+C cancels; Resume pipeline verification.cmd continues later.',flush=True)
    lookup=root/'l'
    with Checkpoint(lookup,contract,resume=lookup.exists()) as checkpoint:
        if cancel.exists():
            regular_read(cancel,256);cancel.unlink()  # Only this session's explicit cancellation marker.
        checkpoint.stage('lookup')
        wanted={(s,r[s]['sha256'],r[s]['size']) for r in document['records'] for s in ('vp','fp')}
        location_path=lookup/'locations.json'
        if location_path.exists():
            resolved=locations.read(location_path)
        else:
            resolved=locations.validate(dict(schema=locations.SCHEMA,version=1,
                records=[r for r in base['records'] if (r['stage'],r['id'],r['size']) in wanted]))
            known={(r['stage'],r['id'],r['size']) for r in resolved['records']}
            audit=dict(requested=len(wanted-known),located=0,unresolved=0)
            if wanted-known:
                from pipeline_volume_search import search
                found,audit=search(document['records'],[session/'private-recorder'],archive,elf,search_map,known,
                    lambda done,total:progress('finding-original-programs',dict(completed=done,total=total)))
                resolved=locations.merge([resolved,found])
            atomic_json(location_path,resolved)
            atomic_json(lookup/'search-report.json',audit)
        known={(r['stage'],r['id'],r['size']) for r in resolved['records']}
        if not known<=wanted:raise ValueError('Resolved program list exceeds captured input')
        eligible=[r for r in document['records'] if all((s,r[s]['sha256'],r[s]['size']) in known for s in ('vp','fp'))]
        ready=dict(document,records=eligible)
        ready_path=lookup/'eligible.json'
        immutable_json(ready_path,ready)
        successful=set()
        if eligible:
            import shader_fragment_batch
            from collection_process import run_owned
            def runner(exe,game_root,env,log,timeout=180):
                idle()
                return run_owned([exe],game_root,env,log,
                    lambda:progress(last[0] or 'native'),timeout)
            old=(template.run_offline,shader_fragment_batch.run_offline)
            try:
                template.run_offline=shader_fragment_batch.run_offline=runner
                proof=template.prepare(ready_path,None,elf,engine,decoder,storage,root/'p',
                    asset_map=location_path,volume=archive,volume_map=map_path,resume=(root/'p').exists(),
                    output_validator=lambda p:p,progress=progress)
            finally:
                template.run_offline,shader_fragment_batch.run_offline=old
            checked=contribution.parse_report(proof)
            if proof['template_sha256']!=template.template_digest(ready_path):
                raise ValueError('Verification report differs from captured input')
            successful=set(checked['default_keys'])
        verified=dict(document,records=[r for r in document['records'] if r['key'] in successful])
        pending=dict(document,records=[r for r in document['records'] if r['key'] not in successful])
        progress('publishing')
        shared=publish_verified(session,verified) if verified['records'] else None
        atomic_json(session/'pending-template.json',pending)
        summary=dict(schema=1,verified=len(verified['records']),pending=len(pending['records']),
            resolved_programs=len(known),input_sha256=contract['input'],
            share_file=shared.name if shared else None,
            policy='Local verification only; maintainer original-asset/native acceptance remains mandatory.')
        atomic_json(session/'verification.json',summary)
        checkpoint.stage('complete',**summary)
        print(json.dumps(summary),flush=True)
        if shared:print('Share only: '+str(shared),flush=True)
        if pending['records']:print('Unresolved/rejected records remain private in pending-template.json.',flush=True)
        return summary
