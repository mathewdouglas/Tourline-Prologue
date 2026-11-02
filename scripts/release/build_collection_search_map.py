"""Verify a bounded numeric search map for original SHDS-bearing containers.

Maintainer-only catalogue/listing/reference assets stay private. Output contains
only original hashes, numeric packed locations and the existing ELF parameters.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import game_volume as volume
from preparation_reuse import cache_root, regular_read


def build(catalog, assets, entries, elf, archive, baseline):
    assets=cache_root(assets);mapping=volume.read(baseline)
    elf_data=regular_read(elf,64*1024**2)
    if hashlib.sha256(elf_data).hexdigest()!=mapping['elf_sha256']:
        raise ValueError('Original ELF mismatch')
    pattern=re.compile(r'^(.*?) - Flags: (.*?) \| FileIndex: (\d+) .*?\| SegIndex: (\d+), ZSize: ([0-9A-Fa-f]+) \| Size: ([0-9A-Fa-f]+) \|')
    listing={};seeds={}
    for line in regular_read(entries,4*1024**2).decode('utf-8-sig').splitlines():
        match=pattern.match(line)
        if not match or match[2] not in ('Compressed','None'):continue
        if match[1] in listing:raise ValueError('Duplicate archive entry')
        prior=seeds.get(int(match[3]))
        if prior and any(prior[i]!=match[i] for i in (2,4,5,6)):
            raise ValueError('Conflicting archive alias')
        listing[match[1]]=match;seeds[int(match[3])]=match
    bases=set()
    for row in mapping['records']:
        match=seeds[row['seed']]
        if int(match[5],16)!=row['stored_size'] or int(match[6],16)!=row['size']:
            raise ValueError('Listing differs from verified baseline')
        bases.add(row['offset']-2048*int(match[4]))
    if len(bases)!=1:raise ValueError('Archive base is ambiguous')
    base=bases.pop();rows={r['container']:r for r in mapping['records']}
    index=json.loads(regular_read(catalog/'index.json',128*1024**2))
    files={Path(r['file']).absolute() for r in index['sources']}
    if len(files)>1024:raise ValueError('Search container count exceeded')
    for path in sorted(files):
        if path==elf.absolute():continue
        if not path.is_relative_to(assets):raise ValueError('Catalogue source outside original assets')
        cache_root(path.parent)
        data=regular_read(path,128*1024**2)
        digest=hashlib.sha256(data).hexdigest()
        if digest in rows:continue
        entry=listing[path.relative_to(assets).as_posix()]
        if len(data)!=int(entry[6],16):raise ValueError('Original asset/listing size mismatch')
        rows[digest]=dict(container=digest,size=len(data),offset=base+2048*int(entry[4]),
            stored_size=int(entry[5],16),seed=int(entry[3]),compressed=entry[2]=='Compressed')
    result=volume.validate(dict(mapping,records=sorted(rows.values(),key=lambda r:r['offset'])))
    started=time.monotonic();parameters=volume.parameters(elf_data,result['key_location'])
    with archive.open('rb') as stream:
        before=os.fstat(stream.fileno())
        if stream.seek(0,2)!=result['volume_size']:raise ValueError('Original volume size mismatch')
        stream.seek(0)
        if hashlib.file_digest(stream,'sha256').hexdigest()!=result['volume_sha256']:
            raise ValueError('Original volume digest mismatch')
        crypt=volume.Crypt()
        def check():
            if time.monotonic()-started>600:raise ValueError('Search map verification time bound exceeded')
        for row in result['records']:
            count=0;hasher=hashlib.sha256()
            for block in volume.decoded_chunks(stream,row,crypt,parameters,check):
                count+=len(block)
                if count>row['size']:raise ValueError('Member size exceeded')
                hasher.update(block)
            if count!=row['size'] or hasher.hexdigest()!=row['container']:
                raise ValueError('Original packed container verification failed')
        after=os.fstat(stream.fileno())
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('Original volume changed while verifying the map')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','assets','entries','elf','archive','baseline','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Choose a fresh metadata output')
    result=build(*(getattr(args,n) for n in ('catalog','assets','entries','elf','archive','baseline')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='ascii')
    print(json.dumps(dict(containers=len(result['records']),decoded_bytes=sum(r['size'] for r in result['records']))))
