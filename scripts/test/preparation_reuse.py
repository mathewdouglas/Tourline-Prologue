"""Cache generation reuse verifies bytes, bounds work and preserves its source."""
import copy
import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preparation_reuse import seed_cache, expected_shaders
from shader_coverage import fnv64
from player_prepare import previous_cache


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base/'source'; self.source.mkdir()
        self.dest = self.base/'destination'; self.dest.mkdir()
        self.code = b'DXBCverified-test-shader'
        self.words = [0]*164
        self.words[4] = self.words[8] = len(self.code)
        self.record = dict(key='1'*16, vp_source='2'*16, fp_source='3'*16,
                           vs=f'{fnv64(self.code):016x}', ps=f'{fnv64(self.code):016x}',
                           native=dict(words=self.words))
        self.document = dict(records=[self.record])
        self.blob = b'local-driver-hint'
        self.blob = struct.pack('<QQQ', 0x31534f5035505447, len(self.blob), fnv64(self.blob))+self.blob
        for key in ('2'*16, '3'*16):
            (self.source/(key+'.dxbc')).write_bytes(self.code)
        (self.source/('pso_'+'1'*16+'.bin')).write_bytes(self.blob)

    def snapshot(self):
        return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir()}

    def test_only_requested_verified_files_and_no_source_writes(self):
        (self.source/'unrequested.dxbc').write_bytes(b'ignored')
        before = self.snapshot()
        report = seed_cache(self.document,self.source,self.dest)
        self.assertEqual(report['shaders_copied'],2)
        self.assertEqual(report['driver_blobs_copied'],1)
        self.assertEqual(len(list(self.dest.iterdir())),3)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(seed_cache(self.document,self.source,self.dest)['already_present'],3)

    def test_corrupt_and_missing_inputs_fall_back(self):
        (self.source/('2'*16+'.dxbc')).write_bytes(self.code+b'corrupt')
        (self.source/('3'*16+'.dxbc')).unlink()
        (self.source/('pso_'+'1'*16+'.bin')).write_bytes(self.blob[:-1]+b'X')
        before=self.snapshot()
        report=seed_cache(self.document,self.source,self.dest)
        self.assertEqual((report['rejected_shaders'],report['missing_shaders'],report['rejected_driver_blobs']),(1,1,1))
        self.assertFalse(list(self.dest.iterdir()))
        self.assertEqual(self.snapshot(),before)

    def test_different_shader_identity_and_length_are_not_reused(self):
        other=copy.deepcopy(self.document)
        other['records'][0]['vs']='f'*16
        other['records'][0]['native']['words'][8]+=1
        report=seed_cache(other,self.source,self.dest)
        self.assertEqual(report['rejected_shaders'],2)
        self.assertEqual(report['shaders_copied'],0)

    def test_redirected_root_rejected_before_any_copy(self):
        with patch('preparation_reuse.Path.is_symlink',return_value=True):
            with self.assertRaises(ValueError):seed_cache(self.document,self.source,self.dest)
        self.assertFalse(list(self.dest.iterdir()))

    def test_memory_and_time_budgets_leave_remaining_work_to_compilation(self):
        with patch('preparation_reuse.MAX_SHADERS',len(self.code)),patch('preparation_reuse.MAX_BLOBS',1):
            report=seed_cache(self.document,self.source,self.dest)
        self.assertEqual((report['shaders_copied'],report['driver_blobs_copied'],report['budget_skipped']),(1,0,2))
        with patch('preparation_reuse.MAX_SECONDS',-1):
            self.assertEqual(seed_cache(self.document,self.source,self.dest)['budget_skipped'],3)

    def test_overlap_and_mapping_conflicts_rejected(self):
        with self.assertRaises(ValueError):seed_cache(self.document,self.source,self.source)
        child=self.source/'child';child.mkdir()
        with self.assertRaises(ValueError):seed_cache(self.document,self.source,child)
        other=copy.deepcopy(self.record);other['vs']='4'*16
        with self.assertRaises(ValueError):expected_shaders(dict(records=[self.record,other]))

    def test_hard_link_rejected_without_touching_it(self):
        path=self.source/('2'*16+'.dxbc')
        os.link(path,self.base/'alias')
        report=seed_cache(self.document,self.source,self.dest)
        self.assertEqual(report['rejected_shaders'],1)
        self.assertEqual(path.read_bytes(),self.code)

    def test_cancel_keeps_only_complete_files(self):
        def cancel(phase,counts):
            if counts['completed']==1:raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):seed_cache(self.document,self.source,self.dest,cancel)
        self.assertEqual([p.read_bytes() for p in self.dest.iterdir()],[self.code])
        self.assertEqual(seed_cache(self.document,self.source,self.dest)['shaders_copied'],1)

    def test_player_pointer_stays_inside_owned_generations(self):
        pointer=self.base/'prepared-cache.txt'
        self.assertIsNone(previous_cache(self.base,self.dest))
        old=self.base/'preparation'/('a'*24)/'shadercache';old.mkdir(parents=True)
        pointer.write_text(old.relative_to(self.base).as_posix())
        self.assertEqual(previous_cache(self.base,self.dest),old)
        self.assertIsNone(previous_cache(self.base,old.parent))
        for invalid in ('../source','C:/outside','preparation/../shadercache','preparation/'+'a'*24+'/shadercache\n'):
            pointer.write_text(invalid)
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):previous_cache(self.base,self.dest)


if __name__=='__main__':unittest.main()
