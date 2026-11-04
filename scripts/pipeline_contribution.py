"""Share identifiers/numeric state, never local shader/cache/provenance bytes.

Contributions are untrusted candidates. A maintainer must locate original game
programs and pass shader/native preparation before accepting new template rows.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

import pipeline_template as template
from pipeline_catalogue_limits import SESSION_RECORDS
from pipeline_runtime_coverage import parse_report
from preparation_reuse import cache_root, regular_read

SCHEMA='tourline-pipeline-contribution'
VERSION=1
MAX_BYTES=32*1024**2
MAX_SUBMISSIONS=16
MAX_LINKS=8192


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON field')
        result[key]=value
    return result


def read_json(path, max_bytes=None):
    if max_bytes is None:max_bytes=MAX_BYTES
    path=Path(path).absolute()
    cache_root(path.parent)
    try:
        data=regular_read(path,max_bytes)
        depth=0;quoted=escaped=False
        for byte in data:
            if quoted:
                if escaped:escaped=False
                elif byte==92:escaped=True
                elif byte==34:quoted=False
            elif byte==34:quoted=True
            elif byte in (91,123):
                depth+=1
                if depth>24:raise ValueError('Contribution JSON nesting limit exceeded')
            elif byte in (93,125):depth-=1
        return json.loads(data,object_pairs_hook=_object,
                          parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
    except (RecursionError,UnicodeError) as exc:
        raise ValueError('Invalid contribution JSON') from exc


def encode(document):
    _session_bound(document)
    from pipeline_template_inputs import convert
    document=convert(document)
    if not document['records'] or len(document['records']) > SESSION_RECORDS:raise ValueError('No supported pipeline records to share')
    document['records'].sort(key=lambda r:r['key'])
    result=dict(schema=SCHEMA,version=VERSION,template_sha256=digest(document),template=document)
    if len(canonical(result))>MAX_BYTES:raise ValueError('Contribution exceeds its byte limit')
    return result


def _session_bound(document):
    if isinstance(document,dict) and isinstance(document.get('records'),list) and len(document['records']) > SESSION_RECORDS:
        raise ValueError('Contribution session record limit exceeded')


def decode(value, *, quarantine=False):
    if (not isinstance(value,dict) or set(value)!={'schema','version','template_sha256','template'}
            or value['schema']!=SCHEMA or type(value['version']) is not int or value['version']!=VERSION
            or not isinstance(value['template_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',value['template_sha256'])):
        raise ValueError('Unsupported contribution format/version')
    _session_bound(value['template'])
    if not isinstance(value['template'],dict):
        raise ValueError('Unsupported contribution template')
    if quarantine and value['template'].get('version') == 3:
        from pipeline_template_inputs import review_inputs
        document=review_inputs(value['template'])
    else:
        document=template.validate(copy.deepcopy(value['template']))
    if not document['records'] or len(document['records']) > SESSION_RECORDS or digest(document)!=value['template_sha256']:
        raise ValueError('Contribution checksum or record count rejected')
    from pipeline_template_inputs import convert
    return document if quarantine and document['version'] == 3 else convert(document)


def write_json(path, value, max_bytes=None):
    """Exclusive metadata-only publication; preserve an existing output."""
    if max_bytes is None:max_bytes=MAX_BYTES
    path=Path(path).absolute()
    if path.suffix.lower()!='.json':raise ValueError('Choose a .json output')
    cache_root(path.parent)
    data=canonical(value)+b'\n'
    if len(data)>max_bytes:raise ValueError('Metadata output exceeds its byte limit')
    with path.open('xb') as stream:
        try:stream.write(data)
        except BaseException:
            # Only the new metadata file this call exclusively created.
            stream.close();path.unlink();raise


def capture(trace, cache, compatibility):
    """Validate bounded local recorder inputs before the existing exporter."""
    trace,cache=cache_root(trace),cache_root(cache)
    paths=sorted(trace.glob('links_*.jsonl'))
    if not 1<=len(paths)<=16:raise ValueError('Expected 1..16 local recorder logs')
    total=lines=0
    for path in paths:
        data=regular_read(path,MAX_BYTES)
        total+=len(data)
        if total>MAX_BYTES:raise ValueError('Recorder log byte limit exceeded')
        for line in data.splitlines():
            lines+=1
            if lines>MAX_LINKS or len(line)>16384:raise ValueError('Recorder link limit exceeded')
            c=json.loads(line,object_pairs_hook=_object)
            for key in ('pipeline','vp_raw','fp_raw','vs','ps','vp_cache','fp_cache'):
                if not isinstance(c.get(key),str) or not re.fullmatch('[0-9a-f]{16}',c[key]):
                    raise ValueError('Invalid local recorder identifier')
            size=c.get('vp_identity_bytes')
            if type(size) is not int or not 16<=size<=template.MAX_FP or size%16:
                raise ValueError('Invalid recorded vertex length')
    document,rejected=template.export(trace,cache,compatibility)
    return encode(document),rejected


def review(baseline, submissions):
    """Reuse conflict quarantine; a review delta is never preparation proof."""
    if not 1<=len(submissions)<=MAX_SUBMISSIONS:raise ValueError('Supply 1..16 contributions')
    if sum(len(canonical(value)) for value in submissions)>MAX_BYTES:
        raise ValueError('Combined contribution byte limit exceeded')
    from pipeline_template_coverage import analyze
    sessions={f'submission-{i+1:02d}':decode(value,quarantine=True) for i,value in enumerate(submissions)}
    report,candidates=analyze(copy.deepcopy(baseline),sessions,quarantine_conflicts=True)
    report['submission_sha256']={name:digest(document) for name,document in sessions.items()}
    report['policy']='Untrusted contribution candidates only. Locate programs and validate both shaders/native keys locally before accepting.'
    return report,candidates


def accept(baseline, candidates, candidate_path, proof):
    """Maintainer-only: gate the union on local native preparation evidence."""
    candidate_keys={r['key'] for r in candidates['records']}
    if not candidate_keys:raise ValueError('No candidates to accept')
    successful=parse_report(proof)
    from preparation_template_inputs import successful_inputs
    if (proof.get('template_sha256')!=template.template_digest(candidate_path)
            or proof.get('requested')!=len(candidate_keys)
            or proof.get('counts')!={'prepared':len(candidate_keys)}
            or set(successful_inputs(proof))!=candidate_keys):
        raise ValueError('Local preparation proof does not verify these exact candidates')
    return template.merge([copy.deepcopy(baseline),copy.deepcopy(candidates)])


def default_storage():
    """Read the same Windows storage selection as the launcher; write nothing."""
    if os.environ.get('GT5P_USER_DIR'):return Path(os.environ['GT5P_USER_DIR']).absolute()
    import ctypes
    home=os.environ.get('GT5P_LAUNCHER_HOME')
    if home:
        home=Path(home).absolute()
    else:
        shell=ctypes.WinDLL('shell32')
        shell.SHGetFolderPathW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_wchar_p]
        local=ctypes.create_unicode_buffer(32768)
        if shell.SHGetFolderPathW(None,0x1c,None,0,local)!=0:raise ValueError('Cannot locate player storage')
        home=Path(local.value)/'GT5PRecomp'
    kernel=ctypes.WinDLL('kernel32')
    kernel.GetPrivateProfileStringW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_wchar_p]
    selected=ctypes.create_unicode_buffer(32768)
    count=kernel.GetPrivateProfileStringW('game','directory','',selected,len(selected),str(home/'storage.ini'))
    if count>=len(selected)-1:raise ValueError('Storage selection exceeds its bound')
    return Path(selected.value) if selected.value else home


def player_main(argv, collect=False, resume=False):
    """Frozen-helper export. Recorder data remains on this computer."""
    from preparation_settings import select, verify
    from train_pipeline_cache import idle
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--install',type=Path,required=True)
    for name in ('storage','trace','output','cache','session'):ap.add_argument('--'+name,type=Path)
    a=ap.parse_args(argv)
    idle()
    storage=cache_root(a.storage or default_storage())
    if resume:
        if any((a.trace,a.output,a.cache)):ap.error('Resume uses the saved collection session')
        from pipeline_collection import verify_session
        verify_session(a.install,storage,a.session,show_ui=True)
        return
    if a.session:ap.error('--session is only for --verify-contribution')
    selection=select(storage)
    if (selection['requested']!='auto' or selection['mode']!='default'
            or selection['source'] not in ('launcher-settings','launcher-first-run-preset')
            or (selection['source']=='launcher-settings' and 'resolution' not in selection)):
        raise ValueError('Contribution export currently requires automatic default translation: 720p/1080p 16:9, anisotropy 16 and smooth colour, without renderer overrides')
    install=a.install.resolve()
    compatibility=template.compatibility(install/'runtime/gt5p.exe',install/'preparation/decoder.dll',storage/'input/EMAIN.ELF')
    baseline=template.read(install/'assets/pipeline-templates/gt5p-disc-v2')
    if baseline['compatibility']!=compatibility:raise ValueError('Installed template/game/renderer mismatch')
    if collect:
        if a.trace or a.cache or a.output:raise ValueError('Collection chooses its own recorder, cache and verified output')
        if shutil.disk_usage(storage).free<1024**3:raise ValueError('Collection needs at least 1 GiB free for private recorder data')
        parent=storage/'pipeline-contributions'
        if parent.exists():cache_root(parent)
        parent.mkdir(exist_ok=True)
        session=parent/('session-'+uuid.uuid4().hex);session.mkdir()
        a.trace=session/'private-recorder';a.trace.mkdir()
        if not str(a.trace).isascii() or len(str(a.trace))>=448:
            raise ValueError('This recorder currently requires an ASCII path shorter than 448 characters')
        if a.output is None:a.output=session/'share-this-template.json'
        env=dict(os.environ,RSX_PSO_PROVENANCE=str(a.trace),RSX_PSO_PROVENANCE_LIMIT='4096',PS3_VERBOSE='0',GT5P_USER_DIR=str(storage))
        print('Play normally and keep these video settings. After closing the game, original-asset/native verification runs automatically. Ctrl+C cancels verification; Resume pipeline verification.cmd continues later.',flush=True)
        print('Private recording: '+str(session),flush=True)
        # The launcher owns its game job, storage locks and settings restarts.
        # Never terminate another game or change ordinary asynchronous draws.
        subprocess.run([str(install/'tourline-prologue.exe')],env=env,check=True)
        idle()
        verify(selection,storage)
    elif a.trace is None or a.output is None:
        ap.error('Export requires --trace and --output, or use --collect-contribution')
    cache=storage/'shadercache'
    if a.cache:
        cache=a.cache
    elif (storage/'prepared-cache.txt').exists():
        relative=regular_read(storage/'prepared-cache.txt',512).decode('utf-8')
        if not re.fullmatch('preparation/[0-9a-f]{24}/shadercache',relative):raise ValueError('Invalid prepared cache selection')
        cache=storage/relative
    elif os.environ.get('RSX_SHADER_CACHE'):
        cache=Path(os.environ['RSX_SHADER_CACHE'])
    cache=cache_root(cache)
    if not cache.is_relative_to(storage):raise ValueError('Selected contribution cache is outside player storage')
    result,rejected=capture(a.trace,cache,compatibility)
    if any(Path(a.output).absolute().is_relative_to(p) for p in (cache_root(a.trace),cache_root(cache))):
        raise ValueError('Keep the shared export separate from private recorder/cache inputs')
    if collect:
        from pipeline_collection import begin
        begin(install,storage,session,result,rejected,selection)
        return
    write_json(a.output,result)
    print(json.dumps(dict(output=str(a.output),pipelines=len(result['template']['records']),excluded=rejected,
        share='Send only the exported JSON. Keep recorder, shadercache, game files and logs private.')))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='command',required=True)
    e=sub.add_parser('export')
    e.add_argument('--template',type=Path,required=True)
    e.add_argument('--output',type=Path,required=True)
    c=sub.add_parser('capture')
    for name in ('trace','cache','engine','decoder','elf','output'):c.add_argument('--'+name,type=Path,required=True)
    r=sub.add_parser('review')
    r.add_argument('--baseline',type=Path,required=True)
    r.add_argument('--submission',type=Path,action='append',required=True)
    r.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('accept')
    for name in ('baseline','candidates','proof','output'):a.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args()
    if args.command=='export':
        write_json(args.output,encode(template.read(args.template)))
    elif args.command=='capture':
        result,rejected=capture(args.trace,args.cache,template.compatibility(args.engine,args.decoder,args.elf))
        if any(args.output.absolute().is_relative_to(cache_root(p)) for p in (args.trace,args.cache)):
            raise ValueError('Keep shared metadata separate from recorder/cache inputs')
        write_json(args.output,result)
        print(json.dumps(dict(pipelines=len(result['template']['records']),excluded=rejected)))
    elif args.command=='review':
        if len(args.submission)>MAX_SUBMISSIONS:raise ValueError('Contribution count limit exceeded')
        submissions=[];total=encoded_total=0
        for path in args.submission:
            total+=path.stat().st_size
            if total>MAX_BYTES:raise ValueError('Combined contribution byte limit exceeded')
            value=read_json(path)
            encoded_total+=len(canonical(value))
            if encoded_total>MAX_BYTES:raise ValueError('Combined contribution byte limit exceeded')
            submissions.append(value)
        report,candidates=review(template.read(args.baseline),submissions)
        from pipeline_runtime_coverage import require_output
        output=require_output(args.output)
        output.mkdir()
        write_json(output/'review.json',report)
        write_json(output/'candidates.json',candidates,template.MAX_FILE)
        print(json.dumps(dict(candidates=report['additional_records'],conflicts=len(report['quarantined_conflicts']))))
    else:
        candidates=template.read(args.candidates)
        result=accept(template.read(args.baseline),candidates,args.candidates,read_json(args.proof,template.MAX_FILE))
        write_json(args.output,result,template.MAX_FILE)


if __name__=='__main__':main()
