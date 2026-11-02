"""Translation opt-in and local derived-cache rejection without native execution."""
import os
import hashlib
import struct
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_template
import pipeline_translation as translation
from shader_coverage import fnv64
from shader_coverage import fp_identity


class TranslationTests(unittest.TestCase):
    def test_fragment_checkpoint_bounds_and_rollback(self):
        self.assertEqual(translation.fragment_batch_size({}), 256)
        self.assertEqual(translation.fragment_batch_size({'GT5P_PREPARE_FRAGMENT_CHUNK':'4096'}), 4096)
        for value in ('0','4097','-1','1.0',' 256','',True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                translation.fragment_batch_size({'GT5P_PREPARE_FRAGMENT_CHUNK':value})

    def test_fragment_identity_normalizes_inline_constants(self):
        words = [1 | (0x17 << 24) | (7 << 17), 2, 0, 0]
        instruction = struct.pack('>4I', *[((w << 16) | (w >> 16)) & 0xffffffff for w in words])
        first, second = instruction + bytes(16), instruction + bytes(range(16))
        facts = fp_identity(first)
        record = dict(key='1'*16, fp=dict(sha256=facts['identity'], size=facts['size']), state={})
        job = translation.fragment_job(record, second)
        self.assertEqual(job['fragment_sha256'], hashlib.sha256(second).hexdigest())
        self.assertNotEqual(job['fragment_sha256'], record['fp']['sha256'])
        self.assertEqual(job['used'], 1 << 7)
        with self.assertRaises(ValueError):
            translation.fragment_job(dict(record, fp=dict(sha256='0'*64, size=len(second))), second)

    def test_explicit_modes_and_default_rollback(self):
        self.assertEqual(translation.player_mode({}), 'default')
        for mode in translation.MODES:
            self.assertEqual(translation.player_mode({'GT5P_PREPARE_TRANSLATION':mode}), mode)
        for mode in ('', 'auto', '1', '../outside'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                translation.player_mode({'GT5P_PREPARE_TRANSLATION':mode})

    def test_native_staging_does_not_extend_existing_path_budget(self):
        output = Path('Storage')/'preparation'/('a'*24)
        old = output/'requests'/('b'*64)/'pipeline'/'code_0123456789abcdef.dxbc'
        for mode in ('native-scaled', 'ultrawide-native'):
            path = translation.sidecar(output, mode)/'r'/('b'*64)/'pipeline'/'code_0123456789abcdef.dxbc'
            self.assertLessEqual(len(str(path)), len(str(old)))

    def test_invalid_mode_rejected_before_idle_or_output_changes(self):
        with patch('pipeline_template.idle') as idle, self.assertRaises(ValueError):
            pipeline_template.prepare(None, None, None, None, None, None, None, translation='invalid')
        idle.assert_not_called()

    def test_invalid_chunk_rejected_before_idle_or_output_changes(self):
        with patch.dict(os.environ, GT5P_PREPARE_FRAGMENT_CHUNK='0'), patch('pipeline_template.idle') as idle:
            with self.assertRaisesRegex(ValueError, 'GT5P_PREPARE_FRAGMENT_CHUNK'):
                pipeline_template.prepare(None, None, None, None, None, None, None, translation='native-scaled')
        idle.assert_not_called()

    def test_derived_shader_identity_bounds_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            code = b'DXBCderived-test-code'
            entry = dict(source='1'*16, code=f'{fnv64(code):016x}', length=len(code))
            path = cache/(entry['source']+'.dxbc')
            path.write_bytes(code)
            self.assertEqual(translation._code(entry, cache), code)
            for changed in (dict(entry, source='../outside'), dict(entry, code='0'*16),
                            dict(entry, length=True), dict(entry, length=translation.MAX_CODE+1),
                            dict(entry, extra=1)):
                with self.subTest(entry=changed), self.assertRaises(ValueError):
                    translation._code(changed, cache)
            path.write_bytes(code[:-1]+b'!')
            with self.assertRaisesRegex(ValueError, 'resume verification'):
                translation._code(entry, cache)
            path.write_bytes(code)
            os.link(path, cache/'alias')
            with self.assertRaisesRegex(ValueError, 'regular unlinked'):
                translation._code(entry, cache)


if __name__ == '__main__':
    unittest.main()
