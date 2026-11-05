"""Unit tests for the Phase 220 interpreter pipeline class derivation (no game data, no engine).

Run: .venv\\Scripts\\python scripts\\test\\interp_pipeline_classes.py
"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import interp_pipeline_classes as c  # noqa: E402


def record(gpu=0, vmask=0x109, nrt=1, rtfmt=11, blend=19278219, cmask=15, cube=0, cull=0, stencil=0xF0000000):
    return dict(vp_gpu=gpu, state=dict(vmask=vmask, nrt=nrt, rtfmt=rtfmt, blend=blend, cmask=cmask, cube=cube,
                                       cull=cull, stencil=stencil, shd=0, samplers='0', unhi=0, unnorm=0, ghi=0, exp32=0))


class Derivation(unittest.TestCase):
    def test_reduces_to_native_state_only(self):
        a = record(cube=0x20000 | 0x10)         # texture-unit cube bits (0-15) are fragment state, not native class
        b = record(cube=0x20000)
        b['state']['shd'] = 401408; b['state']['samplers'] = 'ff'
        rows = c.base_classes([a, b])
        self.assertEqual(rows, [(0, 0x109, 1, 11, 19278219, 15, 0, 0xF0000000, 0x20000)])

    def test_gpu_fetch_ignores_attribute_mask(self):
        rows = c.base_classes([record(gpu=1, vmask=1), record(gpu=1, vmask=0xFFFF)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], 0)

    def test_deterministic_order(self):
        recs = [record(blend=i, cube=(i % 3) * 0x20000) for i in range(20)]
        self.assertEqual(c.base_classes(recs), c.base_classes(list(reversed(recs))))
        self.assertEqual(c.digest(c.base_classes(recs)), c.digest(c.base_classes(recs[::-1])))

    def test_rejects_malformed(self):
        bad = [
            [],
            [dict(vp_gpu=0)],
            [record(gpu=2)],
            [record(nrt=0)], [record(nrt=5)],
            [record(rtfmt=99)],
            [record(vmask=0x10000)],
            [record(cube=0x30000)],          # 3 samples
            [record(blend=-1)], [record(blend=1 << 32)], [record(blend=1.0)],
            [record(cmask='15')],
        ]
        for case in bad:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    c.base_classes(case)
        r = record(); r['vp_gpu'] = True    # bool is not an int here
        with self.assertRaises(ValueError):
            c.base_classes([r])

    def test_bounded(self):
        many = [record(blend=i) for i in range(c.MAX_CLASSES + 1)]
        with self.assertRaises(ValueError):
            c.base_classes(many)
        self.assertEqual(len(c.base_classes(many[:c.MAX_CLASSES])), c.MAX_CLASSES)


class Mapping(unittest.TestCase):
    rows = c.base_classes([record(cube=0), record(cube=0x20000), record(cube=0x40000), record(rtfmt=28, cube=0x20000)])

    def test_msaa_modes(self):
        # 1x: every multisampled class collapses onto its one-sample twin.
        one = c.map_settings(self.rows, msaa=1)
        self.assertTrue(all(k[8] == 1 and k[10] == 0 for k in one))
        self.assertEqual(len(one), 4)                 # (fmt 11, fmt 28) x (common, full)
        for n in (2, 4, 8):
            keys = c.map_settings(self.rows, msaa=n)
            self.assertEqual(sorted({k[8] for k in keys}), [1, n])
            self.assertEqual(len(keys), 6)            # 2x/4x starter rows map to the same n
            self.assertTrue(all(k[10] == (k[8] > 1) for k in keys))

    def test_sample_rate_variant(self):
        keys = c.map_settings(self.rows, msaa=8, sample_rate=False)
        self.assertTrue(all(k[10] == 0 for k in keys))

    def test_high_precision_format(self):
        on = c.map_settings(self.rows, msaa=2, high_precision=True)
        off = c.map_settings(self.rows, msaa=2, high_precision=False)
        self.assertIn(11, {k[3] for k in on})
        self.assertEqual({k[3] for k in off}, {28})
        self.assertLess(len(off), len(on))

    def test_full_variant_pairs(self):
        keys = c.map_settings(self.rows, msaa=2)
        self.assertEqual(sorted({k[9] for k in keys}), [0, 1])

    def test_rejects_bad_settings(self):
        for kw in (dict(msaa=3), dict(msaa=0), dict(msaa='2'), dict(high_precision=1), dict(sample_rate=None)):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    c.map_settings(self.rows, **kw)
        with self.assertRaises(ValueError):
            c.map_settings([(0, 0, 1, 11)])

    def test_starter(self):
        rows = c.base_classes(c.load_template(ROOT / 'assets/pipeline-templates/gt5p-disc-v2'))
        self.assertEqual(len(rows), 173)
        self.assertEqual(rows, sorted(rows))
        self.assertEqual(len(c.map_settings(rows, 1)), 188)
        for n in (2, 4, 8):
            self.assertEqual(len(c.map_settings(rows, n)), 318)
        self.assertEqual(c.map_settings(rows, 8), c.map_settings(copy.deepcopy(rows), 8))
        text = '\n'.join(c.render_c(rows))
        self.assertEqual(text.count('},'), 173)


class PlayerSettings(unittest.TestCase):
    def check(self, body, expected):
        with tempfile.TemporaryDirectory() as d:
            if body is not None:
                Path(d, 'gt5p_settings.toml').write_text(body, encoding='utf-8')
            self.assertEqual(c.player_settings(d), expected)

    def test_values(self):
        self.check(None, (2, True, 16))                    # launcher first-run preset
        self.check('[video]\nmsaa = 8\n[game]\nsmooth_colour = true\nanisotropy = 16\n', (8, True, 16))
        self.check('[video]\nmsaa = 1\n[game]\nsmooth_colour = false\nanisotropy = 4\n', (1, False, 4))
        self.check('[video]\nmsaa = 3\n', (4, True, 16))    # normalised as rsx_msaa_samples()
        self.check('[video]\nmsaa = "8"\n', None)
        self.check('not toml = = =', None)
        self.check('video = 3\n', None)


if __name__ == '__main__':
    unittest.main()
