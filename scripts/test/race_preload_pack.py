"""Pack layout: a recipe with a shared shader and a driver blob round-trips, and a stale index does not."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import race_preload_pack as pack
from cache_hash import python_fnv64


def _recipe(pipe, vs_hash, ps_hash, vs_len, ps_len):
    # Same field order as PsoWarmRecipe: hash, vs_hash, ps_hash, vs_bytes, ps_bytes
    # sit just after the 16-byte prologue. The rest is opaque to the packer.
    raw = bytearray(64)
    struct.pack_into('<QQQII', raw, 16, pipe, vs_hash, ps_hash, vs_len, ps_len)
    return bytes(raw)


def _blob(payload):
    header = struct.pack('<QQQ', pack.BLOB_MAGIC, len(payload), python_fnv64(payload))
    return header + payload


class RacePackTest(unittest.TestCase):
    def test_round_trip(self):
        vs = b'V' * 8
        ps = b'P' * 4
        vs_hash, ps_hash = python_fnv64(vs), python_fnv64(ps)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            warm = root / 'warmup-v1'
            warm.mkdir()
            blob = b'blob-bytes'
            (root / 'pso_0000000000000001.bin').write_bytes(_blob(blob))
            (warm / f'code_{vs_hash:016x}.dxbc').write_bytes(vs)
            (warm / f'code_{ps_hash:016x}.dxbc').write_bytes(ps)
            (warm / 'pso_0000000000000001.recipe').write_bytes(_recipe(1, vs_hash, ps_hash, len(vs), len(ps)))
            (warm / 'pso_0000000000000002.recipe').write_bytes(_recipe(2, vs_hash, ps_hash, len(vs), len(ps)))
            (warm / 'race-v1.txt').write_text('0000000000000001\n0000000000000002\n', encoding='ascii')
            report = pack.build(warm, dest=root / 'out.bin')
            parsed = pack.parse(root / 'out.bin')
        self.assertEqual(report['recipes'], 2)
        self.assertEqual(report['codes'], 2)
        self.assertEqual(parsed['count'], 2)
        self.assertEqual(parsed['records'][0][6], len(blob))
        self.assertEqual(parsed['records'][1][6], 0)
        self.assertEqual(parsed['records'][0][3], parsed['records'][1][3])
        off = parsed['records'][0][5]
        self.assertEqual(off & 15, 0)
        self.assertEqual(parsed['payload'][off:off + len(blob)], blob)

    def test_index_checksum_rejects_a_different_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            warm = root / 'warmup-v1'
            warm.mkdir()
            (warm / 'race-v1.txt').write_text('000000000000000a\n', encoding='ascii')
            pack.build(warm, dest=root / 'out.bin')
            parsed = pack.parse(root / 'out.bin')
        from cache_hash import python_fnv64 as fnv
        self.assertNotEqual(parsed['index_fnv'], fnv(struct.pack('<Q', 0xB)))


if __name__ == '__main__':
    unittest.main()
