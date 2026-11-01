"""Hash ABI/parity, safe fallback and fixed-path native library selection."""
import argparse
import ctypes
import os
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cache_hash as tool

LIBRARY = None


class HashTests(unittest.TestCase):
    def setUp(self):
        self.environment=patch.dict(os.environ,{},clear=False)
        self.environment.start();self.addCleanup(self.environment.stop)
        os.environ.pop('GT5P_PREPARE_NATIVE_HASH',None)
        os.environ.pop('GT5P_PREPARE_HASH_LIBRARY',None)
        self.addCleanup(tool.configure)

    def test_renderer_seed_known_vectors(self):
        os.environ['GT5P_PREPARE_NATIVE_HASH']='0';tool.configure()
        for payload,expected in ((b'',0x14650fb0739d0383),(b'hello',0x005a0d15131ec7a1),
                                 (bytes(range(256)),0x16d173bdfcdae583)):
            self.assertEqual(tool.fnv64(payload),expected)

    def test_source_tools_do_not_search_current_directory(self):
        with patch.object(sys,'frozen',False,create=True),patch('cache_hash.ctypes.CDLL') as load:
            self.assertEqual(tool.configure()['backend'],'python')
            load.assert_not_called()

    def test_disable_overrides_an_explicit_library(self):
        os.environ['GT5P_PREPARE_NATIVE_HASH']='0'
        with patch('cache_hash.ctypes.CDLL') as load:
            self.assertEqual(tool.configure(LIBRARY or 'unused.dll')['reason'],'disabled')
            load.assert_not_called()

    def test_missing_library_falls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(tool.configure(Path(temporary)/'missing.dll')['backend'],'python')
            self.assertEqual(tool.fnv64(b'hello'),tool.python_fnv64(b'hello'))

    def test_abi_and_self_test_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            library=Path(temporary)/'cache_hash.dll';library.write_bytes(b'synthetic fixture')
            for abi,reason in ((2,'incompatible-abi'),(1,'self-test-failed')):
                fake=SimpleNamespace(gt5p_cache_hash_abi=lambda:abi,gt5p_cache_fnv64=lambda p,n:0)
                with patch('cache_hash.ctypes.CDLL',return_value=fake):
                    result=tool.configure(library)
                self.assertEqual(result,dict(backend='python',reason=reason))
                self.assertEqual(tool.fnv64(b'hello'),0x005a0d15131ec7a1)

    def test_frozen_uses_its_own_absolute_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            library=Path(temporary)/'cache_hash.dll';library.write_bytes(b'synthetic fixture')
            fake=SimpleNamespace(gt5p_cache_hash_abi=lambda:1,
                gt5p_cache_fnv64=lambda p,n:tool.python_fnv64(ctypes.string_at(p,n)))
            with (patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(library.parent/'helper.exe')),
                  patch('cache_hash.ctypes.CDLL',return_value=fake) as load):
                self.assertEqual(tool.configure()['backend'],'native')
                self.assertEqual(load.call_args.args,(str(library.absolute()),))

    def test_redirected_library_is_not_loaded(self):
        with patch('cache_hash.Path.is_symlink',return_value=True),patch('cache_hash.ctypes.CDLL') as load:
            self.assertEqual(tool.configure('redirected.dll')['reason'],'redirected-library')
            load.assert_not_called()

    def test_native_parity_and_counter_deltas(self):
        if LIBRARY is None:self.skipTest('No native library supplied')
        self.assertEqual(tool.configure(LIBRARY)['backend'],'native')
        before=tool.statistics()
        randomizer=random.Random(177)
        payloads=[randomizer.randbytes(n) for n in (*range(257),4095,4096,4097,65537,1024**2)]
        for payload in payloads:
            expected=tool.python_fnv64(payload)
            for data in (payload,bytearray(payload),memoryview(b'X'+payload)[1:]):
                self.assertEqual(tool.fnv64(data),expected)
        # Non-byte and signed views preserve the original Python iteration rules.
        for data in (memoryview(bytes(range(128))).cast('H'),memoryview(b'\xff\x01').cast('b')):
            self.assertEqual(tool.fnv64(data),tool.python_fnv64(data))
        delta=tool.statistics(before)
        self.assertEqual(delta['native_calls'],len(payloads)*3)
        self.assertEqual(delta['python_calls'],2)
        self.assertEqual(delta['calls'],len(payloads)*3+2)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path)
    args,remaining=parser.parse_known_args();LIBRARY=args.library
    unittest.main(argv=[sys.argv[0],*remaining])
