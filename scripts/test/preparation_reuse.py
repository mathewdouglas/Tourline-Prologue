"""Cache generation reuse verifies bytes, bounds work and preserves its source.

The optional handoff publishes only shaders copied by that call. Pre-existing
destination files stay outside it and are hashed from disk.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import preparation_reuse
from preparation_reuse import (seed_cache, expected_shaders, shaders_for_locked_pass,
                               destination_holds_copy, VerifiedShaders)
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

    def watch_reads(self):
        calls = []
        real = preparation_reuse.bounded_read
        def spy(path, limit):
            calls.append(Path(path).name)
            return real(path, limit)
        return calls, spy

    def counters(self, report):
        return {key: value for key, value in report.items() if key != 'seconds'}

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

    def test_default_call_stays_a_report_and_opt_in_preserves_it(self):
        plain_dest = self.base/'plain'
        plain_dest.mkdir()
        plain = seed_cache(self.document, self.source, plain_dest)
        report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertIs(type(plain), dict)
        self.assertEqual(set(plain), set(report))
        self.assertEqual(self.counters(plain), self.counters(report))
        self.assertEqual(self.counters(report)['shaders_copied'], 2)
        self.assertEqual(self.counters(report)['driver_blobs_copied'], 1)
        json.dumps(report)
        for value in report.values():
            self.assertNotIsInstance(value, (bytes, bytearray, VerifiedShaders))
        with self.assertRaises(TypeError):
            json.dumps(verified)
        self.assertNotIn('DXBC', repr(verified))
        self.assertEqual(set(verified), {'2'*16, '3'*16})
        self.assertEqual(verified['2'*16], self.code)
        self.assertEqual((self.dest/('2'*16+'.dxbc')).read_bytes(), verified['2'*16])
        self.assertNotIn(self.record['key'], verified)
        with self.assertRaises(TypeError):
            verified['2'*16] = self.code
        with self.assertRaises(TypeError):
            seed_cache(self.document, self.source, plain_dest, handoff='yes')
        with self.assertRaises(TypeError):
            shaders_for_locked_pass(self.document, self.dest, {'2'*16: self.code})
        with self.assertRaises(TypeError):
            VerifiedShaders(object(), ())

    def test_handoff_stays_inside_the_shader_byte_cap(self):
        before = self.snapshot()
        with patch('preparation_reuse.MAX_SHADERS', len(self.code)), patch('preparation_reuse.MAX_BLOBS', 1):
            report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertEqual((report['shaders_copied'], report['driver_blobs_copied'], report['budget_skipped']), (1, 0, 2))
        self.assertEqual(set(verified), {'2'*16})
        self.assertEqual(verified['2'*16], self.code)
        self.assertLessEqual(sum(len(item) for item in verified.values()), len(self.code))
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_missing_and_mismatched_inputs_are_not_published(self):
        (self.source/('2'*16+'.dxbc')).write_bytes(self.code + b'corrupt')
        (self.source/('3'*16+'.dxbc')).unlink()
        (self.source/('pso_'+'1'*16+'.bin')).write_bytes(self.blob[:-1] + b'X')
        before = self.snapshot()
        report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertEqual((report['rejected_shaders'], report['missing_shaders'], report['rejected_driver_blobs']), (1, 1, 1))
        self.assertEqual(len(verified), 0)
        self.assertEqual(report['shaders_copied'], 0)
        self.assertFalse(list(self.dest.iterdir()))
        self.assertEqual(self.snapshot(), before)
        (self.source/('2'*16+'.dxbc')).write_bytes(self.code)
        (self.source/('3'*16+'.dxbc')).write_bytes(self.code)
        (self.source/('pso_'+'1'*16+'.bin')).write_bytes(self.blob)
        other = copy.deepcopy(self.document)
        other['records'][0]['vs'] = 'f'*16
        other['records'][0]['native']['words'][8] += 1
        report, verified = seed_cache(other, self.source, self.dest, handoff=True)
        self.assertEqual(report['rejected_shaders'], 2)
        self.assertEqual(report['shaders_copied'], 0)
        self.assertEqual(len(verified), 0)

    def test_preexisting_destination_is_not_trusted(self):
        bad = bytearray(self.code)
        bad[-1] ^= 0xff
        (self.dest/('2'*16+'.dxbc')).write_bytes(bytes(bad))
        before = self.snapshot()
        calls, spy = self.watch_reads()
        with patch('preparation_reuse.bounded_read', spy):
            report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertNotIn('2'*16+'.dxbc', calls)
        self.assertNotIn('2'*16, verified)
        self.assertEqual(verified['3'*16], self.code)
        self.assertEqual(report['already_present'], 1)
        self.assertEqual(report['shaders_copied'], 1)
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(ValueError) as caught:
            shaders_for_locked_pass(self.document, self.dest, verified)
        self.assertIn('Cached shader failed resume verification', str(caught.exception))
        self.assertIn('2'*16, str(caught.exception))
        self.assertEqual((self.dest/('2'*16+'.dxbc')).read_bytes(), bytes(bad))
        self.assertEqual(self.snapshot(), before)

    def test_published_bytes_skip_reread_and_preexisting_are_hashed(self):
        (self.dest/('2'*16+'.dxbc')).write_bytes(self.code)
        report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertEqual(report['already_present'], 1)
        self.assertNotIn('2'*16, verified)
        self.assertEqual(verified['3'*16], self.code)
        calls, spy = self.watch_reads()
        with patch('preparation_reuse.bounded_read', spy):
            found = shaders_for_locked_pass(self.document, self.dest, verified)
        self.assertEqual(calls, ['2'*16+'.dxbc'])
        self.assertEqual(found['2'*16], self.code)
        self.assertIs(found['3'*16], verified['3'*16])

    def test_published_bytes_and_preexisting_files_share_the_cap(self):
        (self.dest/('2'*16+'.dxbc')).write_bytes(self.code)
        with patch('preparation_reuse.MAX_SHADERS', len(self.code)):
            report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
            self.assertEqual(set(verified), {'3'*16})
            self.assertLessEqual(sum(len(item) for item in verified.values()), len(self.code))
            with self.assertRaises(ValueError) as caught:
                shaders_for_locked_pass(self.document, self.dest, verified)
        self.assertIn('Resume shader memory budget exceeded', str(caught.exception))
        self.assertEqual(report['shaders_copied'], 1)

    def test_changed_identity_or_foreign_key_does_not_reuse_published_bytes(self):
        report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        changed = copy.deepcopy(self.document)
        changed['records'][0]['vs'] = 'f'*16
        changed['records'][0]['ps'] = 'e'*16
        with self.assertRaises(ValueError) as caught:
            shaders_for_locked_pass(changed, self.dest, verified)
        self.assertIn('Cached shader failed resume verification', str(caught.exception))
        foreign = copy.deepcopy(self.document)
        foreign['records'][0]['fp_source'] = '5'*16
        calls, spy = self.watch_reads()
        with patch('preparation_reuse.bounded_read', spy):
            with self.assertRaises(ValueError) as caught:
                shaders_for_locked_pass(foreign, self.dest, verified)
        self.assertIn('outside the template', str(caught.exception))
        self.assertIn('3'*16, str(caught.exception))
        self.assertEqual(calls, [])

    def test_cancel_publishes_nothing_and_preserves_source(self):
        before = self.snapshot()
        def cancel(phase, counts):
            if counts['completed'] == 1:
                raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            seed_cache(self.document, self.source, self.dest, cancel, handoff=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({p.name for p in self.dest.iterdir()}, {'2'*16+'.dxbc'})
        self.assertEqual((self.dest/('2'*16+'.dxbc')).read_bytes(), self.code)
        report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertEqual(report['already_present'], 1)
        self.assertEqual(report['shaders_copied'], 1)
        self.assertEqual(set(verified), {'3'*16})
        self.assertEqual(verified['3'*16], self.code)
        self.assertEqual(self.snapshot(), before)
        calls, spy = self.watch_reads()
        with patch('preparation_reuse.bounded_read', spy):
            found = shaders_for_locked_pass(self.document, self.dest, verified)
        self.assertEqual(calls, ['2'*16+'.dxbc'])
        self.assertEqual(found['2'*16], self.code)

    def test_write_failure_publishes_nothing_and_preserves_source(self):
        before = self.snapshot()
        real = Path.write_bytes
        seen = {'n': 0}
        def fail_second(self, data):
            seen['n'] += 1
            if seen['n'] >= 2:
                raise OSError('destination write failed')
            return real(self, data)
        with patch.object(Path, 'write_bytes', fail_second):
            with self.assertRaises(OSError):
                seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({p.name for p in self.dest.iterdir()}, {'2'*16+'.dxbc'})
        report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertNotIn('2'*16, verified)
        self.assertEqual(verified['3'*16], self.code)
        self.assertEqual(report['already_present'], 1)
        self.assertEqual(self.snapshot(), before)

    def test_post_write_shape_failure_is_revalidated_from_disk(self):
        before = self.snapshot()
        with patch('preparation_reuse.destination_stamp', return_value=None):
            report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertEqual(report['shaders_copied'], 2)
        self.assertEqual(len(verified), 0)
        self.assertEqual((self.dest/('3'*16+'.dxbc')).read_bytes(), self.code)
        calls, spy = self.watch_reads()
        with patch('preparation_reuse.bounded_read', spy):
            found = shaders_for_locked_pass(self.document, self.dest, verified)
        self.assertEqual(sorted(calls), ['2'*16+'.dxbc', '3'*16+'.dxbc'])
        self.assertEqual(found['2'*16], self.code)
        self.assertEqual(found['3'*16], self.code)
        self.assertEqual(self.snapshot(), before)

    def test_truncated_or_relinked_destination_is_not_taken_from_memory(self):
        report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertIn('2'*16, verified)
        os.link(self.dest/('3'*16+'.dxbc'), self.base/'linked.dxbc')
        with self.assertRaisesRegex(ValueError, 'regular unlinked'):
            shaders_for_locked_pass(self.document, self.dest, verified)
        (self.base/'linked.dxbc').unlink()
        (self.dest/('2'*16+'.dxbc')).write_bytes(self.code[:-1])
        self.assertEqual(verified['2'*16], self.code)
        with self.assertRaises(ValueError) as caught:
            shaders_for_locked_pass(self.document, self.dest, verified)
        self.assertIn('Cached shader failed resume verification', str(caught.exception))
        self.assertIn('2'*16, str(caught.exception))

    def test_equal_size_mutation_and_replacement_are_rehashed(self):
        _, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        path = self.dest/('2'*16+'.dxbc')
        previous = path.stat()
        bad = self.code[:-1] + bytes([self.code[-1] ^ 1])
        path.write_bytes(bad)
        os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1000000000))
        with self.assertRaisesRegex(ValueError, 'Cached shader failed'):
            shaders_for_locked_pass(self.document, self.dest, verified)
        replacement = self.dest/'replacement.tmp'
        replacement.write_bytes(self.code)
        replacement.replace(path)
        calls, spy = self.watch_reads()
        with patch('preparation_reuse.bounded_read', spy):
            found = shaders_for_locked_pass(self.document, self.dest, verified)
        self.assertIn(path.name, calls)
        self.assertEqual(found['2'*16], self.code)

    def test_handoff_rollback_and_invalid_switch(self):
        self.assertTrue(preparation_reuse.handoff_enabled({}))
        self.assertTrue(preparation_reuse.handoff_enabled({'GT5P_PREPARE_REUSE_HANDOFF':'1'}))
        self.assertFalse(preparation_reuse.handoff_enabled({'GT5P_PREPARE_REUSE_HANDOFF':'0'}))
        with self.assertRaises(ValueError):
            preparation_reuse.handoff_enabled({'GT5P_PREPARE_REUSE_HANDOFF':''})

    def test_time_budget_and_redirect_and_conflict_publish_nothing(self):
        before = self.snapshot()
        with patch('preparation_reuse.MAX_SECONDS', -1):
            report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertEqual(report['budget_skipped'], 3)
        self.assertEqual(len(verified), 0)
        self.assertEqual(shaders_for_locked_pass(self.document, self.dest, verified), {})
        self.assertFalse(list(self.dest.iterdir()))
        with patch('preparation_reuse.Path.is_symlink', return_value=True):
            with self.assertRaises(ValueError):
                seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertFalse(list(self.dest.iterdir()))
        other = copy.deepcopy(self.record)
        other['vs'] = '4'*16
        with self.assertRaises(ValueError):
            seed_cache(dict(records=[self.record, other]), self.source, self.dest, handoff=True)
        self.assertFalse(list(self.dest.iterdir()))
        with self.assertRaises(ValueError):
            seed_cache(self.document, self.source, self.source, handoff=True)
        self.assertEqual(self.snapshot(), before)

    def test_linked_source_is_omitted_and_manifest_is_not_authoritative(self):
        path = self.source/('2'*16+'.dxbc')
        os.link(path, self.base/'alias')
        (self.source/'reuse-manifest.json').write_text('{"trust":true}', encoding='utf-8')
        (self.dest/'reuse-manifest.json').write_text('stay', encoding='utf-8')
        before = self.snapshot()
        report, verified = seed_cache(self.document, self.source, self.dest, handoff=True)
        self.assertEqual(report['rejected_shaders'], 1)
        self.assertNotIn('2'*16, verified)
        self.assertEqual(verified['3'*16], self.code)
        self.assertEqual(path.read_bytes(), self.code)
        self.assertEqual((self.dest/'reuse-manifest.json').read_text(encoding='utf-8'), 'stay')
        self.assertFalse(any(item.name.startswith('reuse-manifest') and item.name != 'reuse-manifest.json'
                             for item in self.dest.iterdir()))
        self.assertEqual(self.snapshot(), before)

    def test_destination_shape_check_rejects_links_wrong_sizes_and_missing_files(self):
        path = self.dest/'one.dxbc'
        path.write_bytes(self.code)
        self.assertTrue(destination_holds_copy(path, len(self.code)))
        self.assertFalse(destination_holds_copy(path, len(self.code) - 1))
        self.assertFalse(destination_holds_copy(self.dest/'missing.dxbc', len(self.code)))
        os.link(path, self.base/'one-link.dxbc')
        self.assertFalse(destination_holds_copy(path, len(self.code)))


if __name__=='__main__':unittest.main()
