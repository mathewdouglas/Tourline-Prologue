"""Read only verified shader containers from a supported user's GT.VOL.

Numeric locations and ELF parameter offsets contain no keys or file names.
Containers are decrypted/decompressed in bounded chunks and never unpacked to
disk. SHA-256 gates both the original volume and each decoded container.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import zlib

from shader_coverage import bounded_read
from pipeline_asset_map import identity
from preparation_reuse import cache_root,regular_read

SCHEMA='gt5p-volume-locations'
CHUNK=128*1024
MAX_MEMBER=1024**3
MAX_TOTAL=4*1024**3
SHA=re.compile('[0-9a-f]{64}')


def validate(document):
    try:
        if (set(document)!={'schema','version','elf_sha256','volume_sha256','volume_size','key_location','records'} or
                document['schema']!=SCHEMA or type(document['version']) is not int or document['version']!=1 or
                any(not isinstance(document[k],str) or not SHA.fullmatch(document[k]) for k in ('elf_sha256','volume_sha256')) or
                type(document['volume_size']) is not int or not 0<document['volume_size']<=16*1024**3 or
                not isinstance(document['records'],list) or not 1<=len(document['records'])<=1024):
            raise ValueError('Incompatible volume location map')
        k=document['key_location']
        if (set(k)!={'magic_offset','magic_size','polynomials_offset'} or
                any(type(v) is not int or not 0<=v<=64*1024**2 for v in k.values()) or not 1<=k['magic_size']<=128):
            raise ValueError('Invalid ELF parameter locations')
        seen=set();total=0;previous=0
        for r in sorted(document['records'],key=lambda r:r['offset']):
            if (set(r)!={'container','size','offset','stored_size','seed','compressed'} or
                    not isinstance(r['container'],str) or not SHA.fullmatch(r['container']) or r['container'] in seen or
                    type(r['compressed']) is not bool or
                    any(type(r[k]) is not int for k in ('size','offset','stored_size','seed')) or
                    not 0<r['size']<=MAX_MEMBER or not 0<r['stored_size']<=MAX_MEMBER or
                    not 0<=r['seed']<=0xffffffff or r['offset']<previous or r['offset']%2048 or
                    r['offset']+r['stored_size']>document['volume_size'] or
                    (not r['compressed'] and r['size']!=r['stored_size']) or (r['compressed'] and r['stored_size']<9)):
                raise ValueError('Invalid/overlapping volume member')
            previous=r['offset']+r['stored_size'];seen.add(r['container']);total+=r['size']
        if total>MAX_TOTAL:raise ValueError('Volume decode budget exceeded')
        return document
    except (TypeError,KeyError,AttributeError) as exc:
        raise ValueError('Malformed volume location map') from exc


def read(path):return validate(json.loads(bounded_read(path,1024**2)))


def parameters(elf,location):
    magic=elf[location['magic_offset']:location['magic_offset']+location['magic_size']]
    offset=location['polynomials_offset']
    if len(magic)!=location['magic_size'] or offset+16>len(elf):raise ValueError('ELF parameter range is unavailable')
    crc=0
    for byte in magic:
        crc^=byte<<24
        for _ in range(8):crc=((crc<<1)^ (0x04c11db7 if crc&0x80000000 else 0))&0xffffffff
    return (~crc)&0xffffffff,struct.unpack_from('>4I',elf,offset)


def member_keys(params,seed):
    value=params[0]^seed;result=[]
    for polynomial,width in zip(params[1],(17,19,23,29)):
        for _ in range(32):value=((value<<1)^(polynomial if value&0x80000000 else 0))&0xffffffff
        value=(~value)&0xffffffff
        result.append(value&((1<<width)-1))
    return result


def xor_reference(data,keys,offset=0):
    out=bytearray(data);states=[]
    for value,width in zip(keys,(17,19,23,29)):
        mask=(1<<width)-1;shift=(offset*8)%width;value&=mask
        states.append(((value>>shift)|(value<<(width-shift)))&mask if shift else value)
    for i in range(len(out)):
        out[i]^=(states[0]^states[1]^states[2]^states[3])&255
        states=[(v>>8)|((v&255)<<(w-8)) for v,w in zip(states,(17,19,23,29))]
    return bytes(out)


class Crypt:
    def __init__(self,path=None):
        if path is None:
            path=(Path(sys.executable).parent/'volume_reader.dll' if getattr(sys,'frozen',False)
                  else os.environ.get('GT5P_PREPARE_VOLUME_LIBRARY'))
        if not path:raise ValueError('Direct volume preparation needs its bundled volume_reader.dll')
        path=Path(path).absolute();cache_root(path.parent)
        data=regular_read(path,1024**2)
        library=ctypes.CDLL(str(path),winmode=0x100|0x800)
        abi=library.gt5p_volume_abi;abi.argtypes=[];abi.restype=ctypes.c_uint32
        if abi()!=1:raise ValueError('Incompatible volume reader ABI')
        self.function=library.gt5p_volume_xor
        self.function.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_uint32),ctypes.c_uint64]
        self.function.restype=None
        self.sha256=hashlib.sha256(data).hexdigest()
        keys=[0x12345,0x45678,0x123456,0x12345678]  # Synthetic self-test state.
        for offset in (0,1,16,31,215441,2**32+7):
            payload=bytes(range(256))*2
            if self.apply(payload,keys,offset)!=xor_reference(payload,keys,offset):
                raise ValueError('Volume reader self-test failed')

    def apply(self,data,keys,offset):
        out=bytearray(data)
        self.function((ctypes.c_ubyte*len(out)).from_buffer(out),len(out),(ctypes.c_uint32*4)(*keys),offset)
        return bytes(out)


def decoded_chunks(stream,row,crypt,params,check):
    stream.seek(row['offset']);left=row['stored_size'];position=0
    keys=member_keys(params,row['seed']);decoder=zlib.decompressobj(-15) if row['compressed'] else None
    while left:
        check()
        raw=stream.read(min(CHUNK,left))
        if not raw:raise ValueError('Truncated volume member')
        data=crypt.apply(raw,keys,position);left-=len(raw)
        if decoder and position==0:
            if len(data)<8:raise ValueError('Truncated compressed volume header')
            magic,size=struct.unpack_from('<Ii',data)
            if magic!=0xfff7eec5 or size!=-row['size']:raise ValueError('Invalid compressed volume header')
            data=data[8:]
        position+=len(raw)
        if decoder:
            while data:
                block=decoder.decompress(data,CHUNK)
                if block:yield block
                tail=decoder.unconsumed_tail
                if tail==data and not block:raise ValueError('Compressed volume stream made no progress')
                data=tail
            if decoder.unused_data:raise ValueError('Trailing compressed member data')
        else:yield data
    if decoder and not decoder.eof:raise ValueError('Incomplete compressed member')


def resolve(locations,volume_map,volume,elf,wanted=None,progress=None):
    from pipeline_asset_map import validate as validate_locations
    locations=validate_locations(locations)
    if sum(r['size'] for r in locations['records'])>128*1024**2:raise ValueError('Resolved volume program memory budget exceeded')
    volume_map=validate(volume_map)
    elf_data=bounded_read(elf,64*1024**2)
    if hashlib.sha256(elf_data).hexdigest()!=volume_map['elf_sha256']:raise ValueError('Volume map game ELF mismatch')
    params=parameters(elf_data,volume_map['key_location'])
    rows={r['container']:r for r in volume_map['records']}
    groups={}
    for r in locations['records']:
        if wanted is None or (r['stage'],r['id'],r['size']) in wanted:groups.setdefault(r['container'],[]).append(r)
    for digest,programs in groups.items():
        size=len(elf_data) if digest==volume_map['elf_sha256'] else rows.get(digest,{}).get('size')
        if size is None or any(r['container_size']!=size for r in programs):raise ValueError('Volume/program map container mismatch')
    crypt=Crypt();started=time.monotonic();found={'vp':{},'fp':{}}
    stats=dict(source='game-volume',volume_bytes_hashed=0,containers_matched=0,decoded_bytes=0,
               stored_bytes_read=0,programs_found=0,volume_reader_sha256=crypt.sha256)
    def check(phase='reading-game-assets',completed=0,total=len(groups)):
        if time.monotonic()-started>600:raise ValueError('Direct volume preparation time budget exceeded')
        if progress:progress(phase,dict(completed=completed,total=total))
    def consume(digest,blocks):
        programs=groups[digest];buffers=[bytearray() for _ in programs];hasher=hashlib.sha256();position=0
        expected=programs[0]['container_size']
        for block in blocks:
            if position+len(block)>expected:raise ValueError('Decoded volume member exceeds its declared size')
            hasher.update(block)
            for r,buffer in zip(programs,buffers):
                lo=max(position,r['offset']);hi=min(position+len(block),r['offset']+r['size'])
                if hi>lo:buffer.extend(block[lo-position:hi-position])
            position+=len(block)
        if position!=expected or hasher.hexdigest()!=digest:raise ValueError('Volume member SHA-256 verification failed')
        for r,buffer in zip(programs,buffers):
            from shader_reconstruct import word_swap
            code=word_swap(buffer) if r['encoding']=='swap32' else bytes(buffer)
            if len(code)!=r['size'] or identity(r['stage'],code)!=r['id']:raise ValueError('Volume program verification failed')
            found[r['stage']][r['id']]=code;stats['programs_found']+=1
        stats['containers_matched']+=1;stats['decoded_bytes']+=position
    with Path(volume).open('rb') as stream:
        before=os.fstat(stream.fileno())
        if before.st_size!=volume_map['volume_size']:raise ValueError('Game volume size mismatch')
        hasher=hashlib.sha256()
        while block:=stream.read(1024**2):
            hasher.update(block);stats['volume_bytes_hashed']+=len(block)
            check('checking-game-archive',stats['volume_bytes_hashed'],before.st_size)
        if hasher.hexdigest()!=volume_map['volume_sha256']:raise ValueError('Game volume SHA-256 mismatch')
        if volume_map['elf_sha256'] in groups:consume(volume_map['elf_sha256'],[elf_data])
        for number,row in enumerate(sorted((rows[d] for d in groups if d in rows),key=lambda r:r['offset']),1):
            check(completed=number-1)
            consume(row['container'],decoded_chunks(stream,row,crypt,params,lambda:check(completed=number-1)))
            stats['stored_bytes_read']+=row['stored_size']
        after=os.fstat(stream.fileno())
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Game volume changed during preparation')
    stats['seconds']=time.monotonic()-started
    return found['vp'],found['fp'],stats
