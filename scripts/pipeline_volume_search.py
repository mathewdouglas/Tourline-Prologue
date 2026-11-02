"""Maintainer search for contributed programs inside verified packed containers.

Only members already identified by the numeric volume map are searched. Missing
programs remain unresolved. Captured bytes select search anchors; only original
ELF/member bytes that pass SHA-256 can supply published numeric locations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import game_volume as volume
import pipeline_asset_map as locations
from preparation_reuse import cache_root, regular_read
from shader_coverage import MAX_FP, fnv64, fp_identity
from shader_reconstruct import word_swap

MAX_BUFFER = 128 * 1024**2
MAX_ORACLES = 128 * 1024**2
MAX_TRACES = 16
MAX_TRACE_FILES = 8192


def search(records, traces, archive, elf, volume_map, known=(), progress=None):
    volume.validate(volume_map)
    if not 1 <= len(traces) <= MAX_TRACES:raise ValueError('Use 1..16 private recorder directories')
    wanted = {(s,r[s]['sha256'],r[s]['size']) for r in records for s in ('vp','fp')} - set(known)
    if len(wanted)>locations.MAX_RECORDS:raise ValueError('Program search bound exceeded')
    started=time.monotonic();targets={};invalid=0;trace_files=0;oracle_bytes=0
    def check():
        if time.monotonic()-started>600:raise ValueError('Packed program search time budget exceeded')
        if progress:progress(len(rows),len(wanted))
    rows=[]
    for trace in traces:
        trace=cache_root(trace)
        for stage in ('vp','fp'):
            for path in trace.glob(stage+'_*.bin'):
                check();trace_files+=1
                if trace_files>MAX_TRACE_FILES:raise ValueError('Private recorder file bound exceeded')
                try:
                    raw=regular_read(path,MAX_FP)
                    if path.stem!=f'{stage}_{fnv64(raw):016x}':raise ValueError('Invalid recorder program')
                except (OSError,ValueError):invalid+=1;continue
                # FP END fixes the identity length. Avoid normalizing every raw
                # program against every unrelated requested length (quadratic).
                sizes = {n for s,_,n in wanted if s==stage and n<=len(raw)}
                if stage == 'fp':
                    try:sizes = {fp_identity(raw)['size']} & sizes
                    except ValueError:invalid+=1;continue
                for size in sizes:
                    code=raw[:size]
                    try:key=(stage,locations.identity(stage,code),size)
                    except ValueError:continue
                    if key in wanted and key not in targets:
                        if oracle_bytes+len(code)>MAX_ORACLES:raise ValueError('Program oracle memory budget exceeded')
                        targets[key]=code;oracle_bytes+=len(code)
    stats=dict(requested=len(wanted),oracle_programs=len(targets),invalid_oracles=invalid,
               containers_searched=0,decoded_bytes=0,oversize_members_skipped=0,
               scope='Only verified members in the supplied volume map plus the ELF')
    def consume(data, container):
        # Verify the entire original member before accepting any candidate.
        if hashlib.sha256(data).hexdigest()!=container:raise ValueError('Original container SHA-256 mismatch')
        stats['containers_searched']+=1
        for key,code in list(targets.items()):
            check();stage,program_id,size=key
            variants=[('native',code)] if stage=='fp' else [('swap32',word_swap(code)),('native',code)]
            for encoding,needle in variants:
                pos=0
                for _ in range(4096):
                    check();pos=data.find(needle[:16],pos)
                    if pos<0:break
                    raw=data[pos:pos+size];candidate=word_swap(raw) if encoding=='swap32' else raw
                    try:matches=len(candidate)==size and locations.identity(stage,candidate)==program_id
                    except ValueError:matches=False
                    if matches:
                        rows.append(dict(stage=stage,id=program_id,size=size,offset=pos,encoding=encoding,
                                         container=container,container_size=len(data)))
                        del targets[key];break
                    pos+=1
                if key not in targets:break
    elf_data=regular_read(elf,64*1024**2)
    if hashlib.sha256(elf_data).hexdigest()!=volume_map['elf_sha256']:raise ValueError('Game ELF mismatch')
    params=volume.parameters(elf_data,volume_map['key_location'])
    with Path(archive).open('rb') as stream:
        before=os.fstat(stream.fileno())
        if before.st_size!=volume_map['volume_size']:raise ValueError('Game archive size mismatch')
        hasher=hashlib.sha256()
        while block:=stream.read(1024**2):check();hasher.update(block)
        if hasher.hexdigest()!=volume_map['volume_sha256']:raise ValueError('Game archive SHA-256 mismatch')
        consume(elf_data,volume_map['elf_sha256']);del elf_data
        crypt=volume.Crypt() if targets else None
        for row in sorted(volume_map['records'],key=lambda r:r['offset']):
            if not targets:break
            check()
            if row['size']>MAX_BUFFER:
                stats['oversize_members_skipped']+=1;continue
            data=bytearray()
            for block in volume.decoded_chunks(stream,row,crypt,params,check):
                if len(data)+len(block)>row['size']:raise ValueError('Decoded member size exceeded')
                data.extend(block)
            if len(data)!=row['size']:raise ValueError('Incomplete original member')
            stats['decoded_bytes']+=len(data)
            consume(data,row['container']);del data
        after=os.fstat(stream.fileno())
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Game archive changed during search')
    stats.update(located=len(rows),unresolved=len(wanted)-len(rows),seconds=time.monotonic()-started)
    return locations.validate(dict(schema=locations.SCHEMA,version=1,records=rows)),stats


def main():
    from pipeline_template import read
    from train_pipeline_cache import isolated,save_report
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('template','volume','volume-map','elf','output'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--trace',type=Path,action='append',required=True)
    ap.add_argument('--known-map',type=Path,action='append',default=[])
    a=ap.parse_args()
    if len(a.known_map)>16:ap.error('Use at most 16 known maps')
    output=isolated(a.output)
    if output.exists():ap.error('Use a fresh ignored output')
    known={(r['stage'],r['id'],r['size']) for p in a.known_map for r in locations.read(p)['records']}
    result,stats=search(read(a.template)['records'],a.trace,a.volume,a.elf,volume.read(a.volume_map),known)
    output.mkdir();save_report(output/'asset-map.json',result);save_report(output/'report.json',stats)
    print(json.dumps(stats))


if __name__=='__main__':main()
