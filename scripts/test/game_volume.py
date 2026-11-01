"""Synthetic packed-asset reads: bounds, integrity, cancellation and native parity."""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import game_volume as tool

LIBRARY=None


class VolumeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.elf=bytearray(128);self.elf[16:24]=b'toy-seed'
        struct.pack_into('>4I',self.elf,32,0x1b,0x5d,0x89,0xd3)
        self.elf_path=self.root/'game.elf';self.elf_path.write_bytes(self.elf)
        self.location=dict(magic_offset=16,magic_size=8,polynomials_offset=32)
        self.program=struct.pack('<4I',0,0,0,1)
        self.plain=b'prefix'*8+self.program+b'padding'*25
        self.container=hashlib.sha256(self.plain).hexdigest()
        self.member=dict(container=self.container,size=len(self.plain),offset=2048,stored_size=len(self.plain),seed=23,compressed=False)
        self.map=dict(schema=tool.SCHEMA,version=1,elf_sha256=hashlib.sha256(self.elf).hexdigest(),
            volume_sha256='a'*64,volume_size=4096,key_location=self.location,records=[self.member])
        self.programs=dict(schema='gt5p-program-locations',version=1,records=[dict(stage='vp',
            id=hashlib.sha256(self.program).hexdigest(),size=16,container=self.container,
            container_size=len(self.plain),offset=48,encoding='native')])

    def fixture(self,compressed=False,payload=None):
        self.member['compressed']=compressed
        raw=self.plain if not compressed else struct.pack('<Ii',0xfff7eec5,-len(self.plain))+zlib.compress(self.plain,wbits=-15)
        if payload is not None:raw=payload
        keys=tool.member_keys(tool.parameters(self.elf,self.location),23)
        encrypted=tool.xor_reference(raw,keys)
        self.member['stored_size']=len(encrypted)
        volume=bytes(2048)+encrypted
        self.map.update(volume_size=len(volume),volume_sha256=hashlib.sha256(volume).hexdigest())
        path=self.root/'GT.VOL';path.write_bytes(volume)
        return path

    def resolve(self,path,progress=None):
        if LIBRARY is None:self.skipTest('No native volume library supplied')
        with patch.dict(os.environ,GT5P_PREPARE_VOLUME_LIBRARY=str(LIBRARY)):
            return tool.resolve(self.programs,self.map,path,self.elf_path,progress=progress)

    def test_raw_and_compressed_members_write_no_extracted_files(self):
        for compressed in (False,True):
            path=self.fixture(compressed);before={p.name:p.read_bytes() for p in self.root.iterdir()}
            vp,fp,stats=self.resolve(path)
            self.assertEqual(vp,{hashlib.sha256(self.program).hexdigest():self.program});self.assertFalse(fp)
            self.assertEqual(stats['programs_found'],1)
            self.assertEqual({p.name:p.read_bytes() for p in self.root.iterdir()},before)

    def test_chunked_and_random_offset_native_xor(self):
        if LIBRARY is None:self.skipTest('No native volume library supplied')
        crypt=tool.Crypt(LIBRARY);keys=[0x12345,0x12345,0x123456,0x12345678]
        plain=bytes(range(251))*17
        for offset in (0,1,16,17,18,19,23,29,128*1024,2**32+123):
            code=crypt.apply(plain,keys,offset)
            self.assertEqual(code,tool.xor_reference(plain,keys,offset))
            self.assertEqual(crypt.apply(code,keys,offset),plain)
            self.assertEqual(crypt.apply(plain[:127],keys,offset)+crypt.apply(plain[127:],keys,offset+127),code)

    def test_map_versions_bounds_overlap_and_unknown_fields(self):
        self.fixture()
        changes=[lambda x:x.update(version=2),lambda x:x.update(keys='forbidden'),
            lambda x:x['records'][0].update(offset=-1),lambda x:x['records'][0].update(seed=True),
            lambda x:x['records'][0].update(offset=2049),lambda x:x['records'][0].update(size=2**31),
            lambda x:x['records'].append(copy.deepcopy(x['records'][0])),
            lambda x:x['key_location'].update(magic_size=129)]
        for change in changes:
            document=copy.deepcopy(self.map);change(document)
            with self.subTest(change=change),self.assertRaises(ValueError):tool.validate(document)

    def test_game_mismatch_rejected_before_native_loading(self):
        path=self.fixture();self.elf_path.write_bytes(b'other game')
        with patch('game_volume.Crypt',side_effect=AssertionError('Loaded for wrong game')):
            with self.assertRaises(ValueError):tool.resolve(self.programs,self.map,path,self.elf_path)

    def test_corrupt_volume_and_container_are_rejected(self):
        path=self.fixture();path.write_bytes(path.read_bytes()[:-1]+b'X')
        with self.assertRaises(ValueError):self.resolve(path)
        path=self.fixture();self.map['records'][0]['container']='b'*64
        self.programs['records'][0]['container']='b'*64
        with self.assertRaises(ValueError):self.resolve(path)

    def test_truncated_oversized_and_trailing_compressed_data(self):
        for raw in (b'not a compressed file',struct.pack('<Ii',0xfff7eec5,-len(self.plain))+zlib.compress(self.plain,wbits=-15)[:-2],
                    struct.pack('<Ii',0xfff7eec5,-len(self.plain))+zlib.compress(self.plain*2,wbits=-15),
                    struct.pack('<Ii',0xfff7eec5,-len(self.plain))+zlib.compress(self.plain,wbits=-15)+b'junk'):
            path=self.fixture(True,raw)
            with self.subTest(raw_size=len(raw)),self.assertRaises((ValueError,zlib.error)):self.resolve(path)

    def test_cancel_and_missing_container_preserve_inputs(self):
        path=self.fixture(True);before=path.read_bytes()
        def cancelled(*args):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.resolve(path,cancelled)
        self.assertEqual(path.read_bytes(),before)
        self.programs['records'][0]['container']='c'*64
        with patch('game_volume.Crypt',side_effect=AssertionError('Read before map join validation')):
            with self.assertRaises(ValueError):tool.resolve(self.programs,self.map,path,self.elf_path)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',type=Path)
    args,remaining=parser.parse_known_args();LIBRARY=args.library
    unittest.main(argv=[sys.argv[0],*remaining])
