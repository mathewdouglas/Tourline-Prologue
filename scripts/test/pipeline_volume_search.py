"""Synthetic packed-container lookup; no game or native compiler starts."""
import copy
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline_volume_search import search
from pipeline_asset_map import identity
from shader_coverage import fnv64
from shader_reconstruct import word_swap


def rejected(call):
    try:call()
    except ValueError:return
    raise AssertionError('Unsafe original input accepted')


with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);trace=root/'trace';trace.mkdir()
    vp=struct.pack('<4I',3,4,5,1)
    fp=bytes(16)+struct.pack('>4I',0x10000,0,0,0)
    payload=b'prefix'+fp[:16]+bytes(32)+b'gap'+fp+b'other'+word_swap(vp)
    archive=root/'volume';archive.write_bytes(payload)
    elf=root/'elf';elf.write_bytes(bytes(64))
    sha=lambda b:hashlib.sha256(b).hexdigest()
    mapping=dict(schema='gt5p-volume-locations',version=1,elf_sha256=sha(elf.read_bytes()),
                 volume_sha256=sha(payload),volume_size=len(payload),
                 key_location=dict(magic_offset=0,magic_size=16,polynomials_offset=32),
                 records=[dict(container=sha(payload),size=len(payload),offset=0,
                               stored_size=len(payload),seed=0,compressed=False)])
    for stage,code in [('vp',vp),('fp',fp)]:
        (trace/f'{stage}_{fnv64(code):016x}.bin').write_bytes(code)
    record={s:dict(sha256=identity(s,code),size=len(code)) for s,code in [('vp',vp),('fp',fp)]}
    class Plain:
        def apply(self,data,keys,offset):return data
    with patch('game_volume.Crypt',return_value=Plain()):
        document,stats=search([record],[trace],archive,elf,mapping)
        assert stats['located']==2 and stats['unresolved']==0
        assert next(r for r in document['records'] if r['stage']=='vp')['encoding']=='swap32'
        assert next(r for r in document['records'] if r['stage']=='fp')['offset']==57
        known={(s,record[s]['sha256'],record[s]['size']) for s in ('vp','fp')}
        empty,stats=search([record],[trace],archive,elf,mapping,known)
        assert not empty['records'] and stats['requested']==0
        with patch('pipeline_volume_search.MAX_BUFFER',16):
            empty,stats=search([record],[trace],archive,elf,mapping)
            assert not empty['records'] and stats['unresolved']==2 and stats['oversize_members_skipped']==1
        with patch('pipeline_volume_search.MAX_ORACLES',16):
            rejected(lambda:search([record],[trace],archive,elf,mapping))
        with patch('pipeline_volume_search.MAX_TRACE_FILES',1):
            rejected(lambda:search([record],[trace],archive,elf,mapping))
        def cancel(*args):raise ValueError('Cancelled')
        rejected(lambda:search([record],[trace],archive,elf,mapping,progress=cancel))
        # Correct archive digest cannot authorize a different member digest.
        bad=copy.deepcopy(mapping);bad['records'][0]['container']='1'*64
        rejected(lambda:search([record],[trace],archive,elf,bad))
        archive.write_bytes(payload[:-1]+b'x')
        rejected(lambda:search([record],[trace],archive,elf,mapping))
        archive.write_bytes(payload);elf.write_bytes(bytes(63)+b'x')
        rejected(lambda:search([record],[trace],archive,elf,mapping))
    assert set(document['records'][0])=={'stage','id','size','offset','encoding','container','container_size'}
print('Packed search verifies original ELF/archive/member, complete program identity, bounds and unresolved results')
