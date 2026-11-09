"""Synthetic guest PSO keys, descriptor bounds and a fake root-signature COM path.

No system d3d12.dll, game, compiler or template calibration runs here. The
frozen digests below are the independent FNV of the documented byte order.
"""
import copy
import ctypes
from importlib import reload
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_pipeline_key as npk

MASK = (1 << 64) - 1
PRIME = 1099511628211
OFFSET = 1469598103934665603
ROOT = 0x1122334455667788
VS = b'DXBC' + b'V' * 28
PS = b'DXBC' + b'P' * 28
PREFIX_HEX = '0742d803ded0dd28'
PIPELINE_HEX = 'b52a0dbb589303b6'
CHANGED_WORD_HEX = '2c2a08148e47ede2'
SOURCE_HEX = 'c3a79183c9970866'


def spec_fnv(data, seed=OFFSET):
    value = seed
    for byte in data:
        value = ((value ^ byte) * PRIME) & MASK
    return value


def spec_descriptor(words):
    data = bytearray(struct.pack('<164I', *words))
    for offset in (0, 8, 24, 552, 632, 640):
        data[offset:offset + 8] = b'\x00' * 8
    if len(data) != 656:
        raise AssertionError('spec descriptor is not 656 bytes')
    return bytes(data)


def spec_key(words, inputs, vs, ps, root):
    digest = spec_fnv(b'gt5p-pso-v1')
    digest = spec_fnv(spec_descriptor(words), digest)
    digest = spec_fnv(b'rs', digest)
    digest = spec_fnv(struct.pack('<Q', root), digest)
    digest = spec_fnv(vs, digest)
    digest = spec_fnv(ps, digest)
    for fields in inputs:
        element = b'\x00' * 8 + struct.pack('<6I', *fields)
        if len(element) != 32:
            raise AssertionError('spec input is not 32 bytes')
        digest = spec_fnv(element, digest)
        digest = spec_fnv(b'ATTR\0', digest)
    return f'{digest:016x}'


def spec_source(source, target):
    flags = 0x2000 if target in (b'vs_6_0', b'ps_6_0') else 0
    return f'{((spec_fnv(source + target) ^ flags) * PRIME) & MASK:016x}'


def record(words=None, inputs=None):
    state = [0] * 164 if words is None else words
    elements = [] if inputs is None else inputs
    state[4] = len(VS)
    state[8] = len(PS)
    state[140] = len(elements)
    state[143] = 3
    state[144] = 1
    return {'native': {'words': state, 'inputs': elements}}


class KeyTests(unittest.TestCase):
    def fields(self):
        return [7, 28, 1, 16, 0, 3]

    def test_frozen_hash_vectors(self):
        self.assertEqual(spec_fnv(b''), OFFSET)
        self.assertEqual(npk.rs_bytes_hash(b''), OFFSET)
        self.assertEqual(f'{spec_fnv(b"gt5p-pso-v1"):016x}', PREFIX_HEX)
        self.assertEqual(f'{npk.rs_bytes_hash(npk.KEY_PREFIX):016x}', PREFIX_HEX)
        sample = record(inputs=[self.fields()])
        words = sample['native']['words']
        inputs = sample['native']['inputs']
        self.assertEqual(words[140], 1)
        self.assertEqual(spec_key(words, inputs, VS, PS, ROOT), PIPELINE_HEX)
        self.assertEqual(npk.native_key(sample, VS, PS, ROOT), PIPELINE_HEX)
        changed = copy.deepcopy(sample)
        changed['native']['words'][100] = 0x01020304
        self.assertEqual(spec_key(changed['native']['words'], inputs, VS, PS, ROOT), CHANGED_WORD_HEX)
        self.assertEqual(npk.native_key(changed, VS, PS, ROOT), CHANGED_WORD_HEX)
        self.assertNotEqual(PIPELINE_HEX, CHANGED_WORD_HEX)
        self.assertEqual(sample['native']['words'][100], 0)
        self.assertEqual(spec_source(b'synthetic', b'vs_5_0'), SOURCE_HEX)
        self.assertEqual(f'{npk.source_key(b"synthetic", b"vs_5_0"):016x}', SOURCE_HEX)
        # FNV with flags 0 is one extra multiply, also equivalent to one NUL byte.
        self.assertEqual(spec_source(b'synthetic', b'vs_5_0'), f'{spec_fnv(b"syntheticvs_5_0" + b"\x00"):016x}')

    def test_descriptor_and_input_differences(self):
        base = record(inputs=[self.fields()])
        other = record(inputs=[self.fields()])
        other['native']['words'][144] = 2
        swapped = record(inputs=[[7, 29, 1, 16, 0, 3]])
        empty = record()
        root_b = ROOT ^ 1
        self.assertNotEqual(npk.native_key(base, VS, PS, ROOT), npk.native_key(other, VS, PS, ROOT))
        self.assertNotEqual(npk.native_key(base, VS, PS, ROOT), npk.native_key(swapped, VS, PS, ROOT))
        self.assertNotEqual(npk.native_key(base, VS, PS, ROOT), npk.native_key(empty, VS, PS, ROOT))
        self.assertNotEqual(npk.native_key(base, VS, PS, ROOT), npk.native_key(base, VS, PS, root_b))
        other_vs = b'DXBC' + b'W' * 28
        self.assertNotEqual(npk.native_key(base, VS, PS, ROOT), npk.native_key(base, other_vs, PS, ROOT))
        self.assertEqual(npk.native_key(base, VS, PS, ROOT), spec_key(base['native']['words'], base['native']['inputs'], VS, PS, ROOT))
        self.assertEqual(len(spec_descriptor(base['native']['words'])), 656)

    def test_changed_lengths_and_original_record(self):
        original = record(inputs=[self.fields()])
        original['native']['words'][100] = 99
        original['vp'] = {'size': 16}
        before = copy.deepcopy(original)
        longer = b'DXBC' + b'Q' * 40
        with self.assertRaises(ValueError):
            npk.native_key(original, VS, longer, ROOT, True)
        mismatched = npk.native_key(original, VS, longer, ROOT, check_lengths=False)
        self.assertEqual(mismatched, spec_key(original['native']['words'], original['native']['inputs'], VS, longer, ROOT))
        derived = npk.derive_record(original, b'float4 main(){return 0;}', VS, b'float4 main():SV_TARGET{return 0;}', longer, ROOT)
        self.assertEqual(original, before)
        self.assertIsNot(derived['native']['words'], original['native']['words'])
        self.assertEqual(derived['native']['words'][4], len(VS))
        self.assertEqual(derived['native']['words'][5], 0)
        self.assertEqual(derived['native']['words'][8], len(longer))
        self.assertEqual(derived['native']['words'][9], 0)
        self.assertEqual(derived['native']['words'][100], 99)
        self.assertEqual(derived['native']['inputs'], original['native']['inputs'])
        self.assertEqual(derived['vp'], original['vp'])
        self.assertIsNot(derived['vp'], original['vp'])
        import shader_compiler  # Phase 231: the configured compiler's targets (vs_6_0/ps_6_0 in DXC mode)
        vs_target, ps_target = shader_compiler.targets()
        self.assertEqual(derived['vp_source'], spec_source(b'float4 main(){return 0;}', vs_target))
        self.assertEqual(derived['fp_source'], spec_source(b'float4 main():SV_TARGET{return 0;}', ps_target))
        with patch.dict('os.environ', {'RSX_SHADER_COMPILER': 'fxc'}):
            fxc = npk.derive_record(original, b'float4 main(){return 0;}', VS, b'float4 main():SV_TARGET{return 0;}', longer, ROOT)
        self.assertEqual(fxc['vp_source'], spec_source(b'float4 main(){return 0;}', b'vs_5_0'))
        self.assertEqual(fxc['fp_source'], spec_source(b'float4 main():SV_TARGET{return 0;}', b'ps_5_0'))
        self.assertEqual(derived['vs'], f'{spec_fnv(VS):016x}')
        self.assertEqual(derived['ps'], f'{spec_fnv(longer):016x}')
        self.assertEqual(derived['key'], npk.native_key(derived, VS, longer, ROOT))
        self.assertNotEqual(derived['key'], mismatched)
        again = npk.derive_record(original, b'other vertex source', VS, b'other fragment source', longer, ROOT)
        self.assertEqual(again['key'], derived['key'])
        self.assertNotEqual(again['vp_source'], derived['vp_source'])
        self.assertNotEqual(again['fp_source'], derived['fp_source'])
        self.assertEqual(original, before)

    def test_derive_failure_keeps_the_original(self):
        original = record()
        original['native']['words'][0] = 1
        before = copy.deepcopy(original)
        with self.assertRaises(ValueError):
            npk.derive_record(original, b'vs', VS, b'ps', PS, ROOT)
        self.assertEqual(original, before)

    def test_verified_source_ids_match_source_based_derivation(self):
        original = record(inputs=[self.fields()])
        expected = npk.derive_record(original, b'vertex source', VS, b'fragment source', PS, ROOT)
        actual = npk.derive_record_from_ids(original, expected['vp_source'], VS,
                                             expected['fp_source'], PS, ROOT)
        self.assertEqual(actual, expected)
        for invalid in ('../outside', '0'*16, 'f'*15, b'f'*16):
            with self.subTest(identity=invalid), self.assertRaises(ValueError):
                npk.derive_record_from_ids(original, invalid, VS, expected['fp_source'], PS, ROOT)

    def test_malformed_inputs_are_rejected(self):
        good = record(inputs=[self.fields()])
        cases = [
            lambda: npk.native_key(good, b'DXBC', PS, ROOT),
            lambda: npk.native_key(good, b'XXXX' + b'V' * 28, PS, ROOT),
            lambda: npk.native_key(good, VS, PS, 0),
            lambda: npk.native_key(good, VS, PS, True),
            lambda: npk.native_key(good, VS, PS, -1),
            lambda: npk.native_key(good, VS, PS, 1 << 64),
            lambda: npk.native_key(good, VS, PS, ROOT, check_lengths=1),
            lambda: npk.native_key({'native': {'words': [0] * 163, 'inputs': []}}, VS, PS, ROOT),
            lambda: npk.native_key(record(inputs=[self.fields() + [1]]), VS, PS, ROOT),
            lambda: npk.native_key(record(inputs=[[-1, 0, 0, 0, 0, 0]]), VS, PS, ROOT),
            lambda: npk.native_key(record(inputs=[[True, 0, 0, 0, 0, 0]]), VS, PS, ROOT),
        ]
        for case in cases:
            with self.assertRaises((ValueError, TypeError)):
                case()
        too_many = record(inputs=[self.fields()] * 33)
        too_many['native']['words'][140] = 33
        with self.assertRaises(ValueError):
            npk.native_key(too_many, VS, PS, ROOT)
        counted = record(inputs=[self.fields()])
        counted['native']['words'][140] = 0
        with self.assertRaises(ValueError):
            npk.native_key(counted, VS, PS, ROOT)
        for index in (0, 24, 140 + 4):
            broken = record(inputs=[self.fields()] if index == 144 else [])
            if index == 144:
                broken['native']['inputs'] = [self.fields()]
                broken['native']['words'][140] = 1
            broken['native']['words'][index] = 9
            with self.assertRaises(ValueError):
                npk.native_key(broken, VS, PS, ROOT)
        cached = record()
        cached['native']['words'][160] = 1
        with self.assertRaises(ValueError):
            npk.native_key(cached, VS, PS, ROOT)
        with patch.object(npk, 'MAX_DXBC', npk.MIN_DXBC - 1):
            with self.assertRaises(ValueError):
                npk.native_key(record(), VS, PS, ROOT)
        with self.assertRaises(ValueError):
            npk.derive_record(record(), b'a\x00b', VS, b'ps', PS, ROOT)
        with self.assertRaises(ValueError):
            npk.derive_record(record(), b'', VS, b'ps', PS, ROOT)
        with self.assertRaises(ValueError):
            npk.derive_record(record(), b'v' * (npk.MAX_VS_SOURCE + 1), VS, b'ps', PS, ROOT)
        with self.assertRaises(ValueError):
            npk.derive_record(record(), b'vs', VS, b'p' * (npk.MAX_PS_SOURCE + 1), PS, ROOT)

    def test_calibrate_matches_and_fails_closed(self):
        vs_source = b'vertex-source'
        ps_source = b'fragment-source'
        base = record(inputs=[self.fields()])
        derived = npk.derive_record(base, vs_source, VS, ps_source, PS, ROOT)
        shaders = {derived['vp_source']: VS, derived['fp_source']: PS}
        report = npk.calibrate([derived], shaders, ROOT)
        self.assertEqual(report, {'records': 1, 'matched': 1, 'root_hash': ROOT})
        self.assertEqual(derived['native']['words'][4], len(VS))
        shared = npk.derive_record(record(), vs_source, VS, b'other-fragment', PS, ROOT)
        both = npk.calibrate([derived, shared], {**shaders, shared['fp_source']: PS}, ROOT)
        self.assertEqual(both['matched'], 2)
        conflict = copy.deepcopy(shared)
        conflict['vs'] = 'f' * 16
        with self.assertRaises(ValueError) as caught:
            npk.calibrate([derived, conflict], shaders, ROOT)
        self.assertIn('mapping conflicts', str(caught.exception))
        tampered = copy.deepcopy(derived)
        tampered['key'] = f'{(int(derived["key"], 16) ^ 1):016x}'
        before = copy.deepcopy(tampered)
        blob_before = shaders[derived['vp_source']]
        with self.assertRaises(ValueError) as caught:
            npk.calibrate([tampered], shaders, ROOT)
        self.assertIn('pipeline key mismatch', str(caught.exception))
        self.assertEqual(tampered, before)
        self.assertEqual(shaders[derived['vp_source']], blob_before)
        with self.assertRaises(ValueError) as caught:
            npk.calibrate([derived], {derived['fp_source']: PS}, ROOT)
        self.assertIn('missing', str(caught.exception))
        wrong = bytearray(VS)
        wrong[-1] ^= 0x5a
        with self.assertRaises(ValueError) as caught:
            npk.calibrate([derived], {derived['vp_source']: bytes(wrong), derived['fp_source']: PS}, ROOT)
        self.assertIn('identity mismatch', str(caught.exception))
        short = copy.deepcopy(derived)
        short['native']['words'][4] = len(VS) - 1
        with self.assertRaises(ValueError) as caught:
            npk.calibrate([short], shaders, ROOT)
        self.assertIn('length mismatch', str(caught.exception))
        with self.assertRaises(ValueError):
            npk.calibrate([], shaders, ROOT)
        with self.assertRaises(ValueError):
            npk.calibrate([derived], shaders, ROOT ^ 0xff)


class RootSignatureTests(unittest.TestCase):
    def test_layouts_and_sampler_bank_do_not_load_d3d12(self):
        self.assertIsNone(npk._d3d12_library)
        npk.validate_layouts()
        self.assertIsNone(npk._d3d12_library)
        desc = npk._build_root_signature()
        self.assertEqual(desc.NumParameters, 5)
        self.assertEqual(desc.NumStaticSamplers, 16)
        self.assertEqual(desc.Flags, 1)
        parameters = ctypes.cast(desc.pParameters, ctypes.POINTER(npk._RootParameter))
        ranges = ctypes.cast(parameters[1].u.DescriptorTable.pDescriptorRanges, ctypes.POINTER(npk._DescriptorRange))
        samplers = ctypes.cast(desc.pStaticSamplers, ctypes.POINTER(npk._StaticSampler))
        self.assertEqual(parameters[0].ParameterType, 2)
        self.assertEqual(parameters[0].u.Descriptor.ShaderRegister, 0)
        self.assertEqual(parameters[0].ShaderVisibility, 1)
        self.assertEqual(parameters[1].ParameterType, 0)
        self.assertEqual(parameters[1].u.DescriptorTable.NumDescriptorRanges, 1)
        self.assertEqual(parameters[1].ShaderVisibility, 5)
        self.assertEqual(ranges[0].NumDescriptors, 16)
        self.assertEqual(ranges[0].RangeType, 0)
        self.assertEqual(ranges[0].OffsetInDescriptorsFromTableStart, 0xffffffff)
        self.assertEqual(parameters[2].u.Descriptor.ShaderRegister, 1)
        self.assertEqual(parameters[2].ShaderVisibility, 5)
        self.assertEqual(parameters[3].ParameterType, 3)
        self.assertEqual(parameters[3].u.Descriptor.ShaderRegister, 20)
        self.assertEqual(parameters[3].ShaderVisibility, 1)
        self.assertEqual(parameters[4].u.Descriptor.ShaderRegister, 2)
        self.assertEqual(struct.pack('<f', samplers[0].MaxLOD), b'\xff\xff\x7f\x7f')
        self.assertEqual((samplers[0].Filter, samplers[0].AddressU, samplers[0].ShaderRegister), (0, 3, 0))
        self.assertEqual((samplers[1].Filter, samplers[1].AddressU, samplers[1].AddressW), (0x15, 1, 1))
        self.assertEqual((samplers[3].Filter, samplers[3].ShaderRegister), (0x15, 3))
        self.assertEqual((samplers[4].Filter, samplers[4].MaxAnisotropy, samplers[4].AddressW), (0, 0, 3))
        self.assertEqual((samplers[5].AddressU, samplers[5].AddressV), (3, 3))
        self.assertEqual((samplers[6].AddressU, samplers[6].AddressV), (1, 3))
        self.assertEqual((samplers[7].AddressU, samplers[7].AddressV), (3, 1))
        self.assertEqual((samplers[8].Filter, samplers[8].MaxAnisotropy), (0x55, 16))
        self.assertEqual((samplers[15].Filter, samplers[15].MaxAnisotropy, samplers[15].ShaderRegister), (0x55, 16, 15))
        self.assertEqual(samplers[15].ShaderVisibility, 5)
        self.assertEqual(samplers[15].ComparisonFunc, 0)
        self.assertEqual(samplers[8].AddressU, 1)
        self.assertEqual(samplers[8].AddressV, 1)
        self.assertIsNone(npk._d3d12_library)

    def blob(self, payload, releases, size=None):
        owner = self

        class Blob:
            def __init__(self):
                self.buffer = ctypes.create_string_buffer(payload)
                self.callbacks = []
                get_pointer = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(
                    lambda this: ctypes.addressof(self.buffer))
                get_size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(
                    lambda this: len(payload) if size is None else size)
                release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
                    lambda this: releases.append(this) or 0)
                self.callbacks.extend((get_pointer, get_size, release))
                self.table = npk.ID3DBlobVtbl()
                self.table.GetBufferPointer = get_pointer
                self.table.GetBufferSize = get_size
                self.table.Release = release
                self.object = npk.ID3DBlob(ctypes.pointer(self.table))
                self.pointer = ctypes.pointer(self.object)

        blob = Blob()
        owner._keep = getattr(owner, '_keep', [])
        owner._keep.append(blob)
        return blob.pointer

    def test_fake_serializer_hashes_and_releases_both_blobs(self):
        payload = b'DXBC' + b'\x11' * 28
        releases = []
        signature = self.blob(payload, releases)
        error = self.blob(b'unused error', releases)

        def invoke(desc):
            self.assertEqual((desc.NumParameters, desc.NumStaticSamplers, desc.Flags), (5, 16, 1))
            samplers = ctypes.cast(desc.pStaticSamplers, ctypes.POINTER(npk._StaticSampler))
            self.assertEqual(samplers[8].Filter, 0x55)
            self.assertEqual(samplers[8].MaxAnisotropy, 16)
            return 0, signature, error

        with patch.object(npk, '_invoke_serialize', invoke):
            self.assertEqual(npk.root_signature_hash(), spec_fnv(payload))
        self.assertEqual(len(releases), 2)
        self.assertIsNone(npk._d3d12_library)

    def test_serialize_failure_releases_and_does_not_hash(self):
        releases = []
        signature = self.blob(b'DXBC' + b'\x22' * 28, releases)
        error = self.blob(b'root signature rejected', releases)

        def invoke(desc):
            return 0x80070057, signature, error

        with patch.object(npk, '_invoke_serialize', invoke):
            with self.assertRaises(RuntimeError) as caught:
                npk.root_signature_hash()
        self.assertIn('80070057', str(caught.exception))
        self.assertIn('root signature rejected', str(caught.exception))
        self.assertEqual(len(releases), 2)

    def test_oversize_blob_is_released(self):
        releases = []
        signature = self.blob(b'DXBC' + b'\x33' * 28, releases, size=npk.MAX_ROOT_BLOB + 1)

        def invoke(desc):
            return 0, signature, ctypes.POINTER(npk.ID3DBlob)()

        with patch.object(npk, '_invoke_serialize', invoke):
            with self.assertRaises(RuntimeError):
                npk.root_signature_hash()
        self.assertEqual(len(releases), 1)

    def test_layout_failure_does_not_call_the_serializer(self):
        order = []

        def layouts():
            order.append('layout')
            raise RuntimeError('stop')

        def invoke(desc):
            order.append('dll')
            return 0, ctypes.POINTER(npk.ID3DBlob)(), ctypes.POINTER(npk.ID3DBlob)()

        with patch.object(npk, 'validate_layouts', layouts), patch.object(npk, '_invoke_serialize', invoke):
            with self.assertRaises(RuntimeError):
                npk.root_signature_hash()
        self.assertEqual(order, ['layout'])

    def test_import_does_not_load_system_dll(self):
        real = ctypes.WinDLL

        def guard(*args, **kwargs):
            raise AssertionError('d3d12 loaded')

        ctypes.WinDLL = guard
        try:
            reload(npk)
            self.assertIsNone(npk._d3d12_library)
            npk.validate_layouts()
        finally:
            ctypes.WinDLL = real
            reload(npk)


if __name__ == '__main__':
    unittest.main()
