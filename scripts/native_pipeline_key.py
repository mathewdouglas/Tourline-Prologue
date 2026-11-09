"""Windows x64 guest_pso_hash_ex keys from numeric template records.

The production descriptor is 656 bytes. A template stores it as 164
little-endian words plus up to 32 input elements whose semantic is ATTR.
The key hashes b'gt5p-pso-v1', that descriptor, b'rs' and the root-signature
hash, both DXBC images, then each 32-byte input with SemanticName cleared
and the bytes b'ATTR\\0'.

root_signature_hash asks system d3d12.dll to serialize the backend's
five-parameter root signature: 16 static samplers and anisotropy 16, which
is the template default. Importing this module does not load the DLL, and
neither a root-signature hash nor a pipeline key is hardcoded.
"""
import copy
import ctypes
import os
import re
import struct
from shader_coverage import fnv64

FNV_OFFSET = 1469598103934665603
FNV_PRIME = 1099511628211
FNV_MASK = 0xffffffffffffffff
DESCRIPTOR_BYTES = 656
DESCRIPTOR_WORDS = 164
MAX_INPUTS = 32
MIN_DXBC = 32
MAX_DXBC = 4 * 1024 * 1024
MAX_VS_SOURCE = 262144
MAX_PS_SOURCE = 131072
MAX_ROOT_BLOB = 64 * 1024
VS_TARGET = b'vs_5_0'
PS_TARGET = b'ps_5_0'
KEY_PREFIX = b'gt5p-pso-v1'
ROOT_TAG = b'rs'
INPUT_SEMANTIC = b'ATTR\0'
HEX16 = re.compile(r'[0-9a-f]{16}')
# Same slots native_state rejects: pointers, unused stages, stream-output
# pointers and the cached-blob pointer/size.
POINTER_Q_OFFSETS = (0, 8, 24, 40, 48, 56, 64, 72, 80, 88, 104, 552, 632, 640)
# guest_pso_hash_ex clears these on its descriptor copy before hashing.
HASH_CLEAR_Q = (0, 8, 24, 552, 632, 640)
STREAM_WORDS = (24, 25, 28, 29)
FLT_MAX_BITS = b'\xff\xff\x7f\x7f'

FILTER_POINT = 0
FILTER_LINEAR_MIP_POINT = 0x14
FILTER_LINEAR = 0x15
FILTER_ANISOTROPIC = 0x55
ADDRESS_WRAP = 1
ADDRESS_CLAMP = 3
VISIBILITY_VERTEX = 1
VISIBILITY_PIXEL = 5
PARAMETER_TABLE = 0
PARAMETER_CBV = 2
PARAMETER_SRV = 3
RANGE_SRV = 0
RANGE_OFFSET_APPEND = 0xffffffff
ROOT_FLAG_INPUT_LAYOUT = 0x1
ROOT_SIGNATURE_VERSION = 1
ANISOTROPY = 16
LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x800

_d3d12_library = None


def rs_bytes_hash(data, seed=FNV_OFFSET):
    """Renderer FNV-1a-64. A seed continues a running hash and is not hashed."""
    if type(data) not in (bytes, bytearray):
        raise TypeError('Hash input must be bytes')
    if type(seed) is not int or seed < 0 or seed > FNV_MASK:
        raise ValueError('Invalid hash seed')
    value = seed
    for byte in data:
        value = ((value ^ byte) * FNV_PRIME) & FNV_MASK
    return value


def source_key(source, target):
    """Renderer source key: FXC flags 0; DXC includes IEEE strictness (-Gis)."""
    if type(source) is not bytes or type(target) is not bytes or not target or b'\x00' in target:
        raise ValueError('Invalid shader source key input')
    if b'\x00' in source:
        raise ValueError('Invalid shader source key input')
    flags = 0x2000 if target in (b'vs_6_0', b'ps_6_0') else 0
    return ((fnv64(source + target) ^ flags) * FNV_PRIME) & FNV_MASK


def _as_u32(value, message):
    if type(value) is not int or value < 0 or value > 0xffffffff:
        raise ValueError(message)
    return value


def _root_hash(value):
    # Zero is the runtime sentinel for an unknown root signature.
    if type(value) is not int or not 0 < value <= FNV_MASK:
        raise ValueError('Root signature hash required')
    return value


def _u64(words, index):
    return words[index] | (words[index + 1] << 32)


def _store_u64(words, index, value):
    words[index] = value & 0xffffffff
    words[index + 1] = (value >> 32) & 0xffffffff


def _dxbc(data):
    if type(data) is not bytes or len(data) < MIN_DXBC or len(data) > MAX_DXBC or not data.startswith(b'DXBC'):
        raise ValueError('Invalid DXBC bytecode')
    return data


def _source(data, limit, label):
    if type(data) is not bytes or not data or len(data) > limit or b'\x00' in data:
        raise ValueError(f'Invalid {label} source')
    return data


def _native(record):
    if type(record) is not dict or type(record.get('native')) is not dict:
        raise ValueError('Invalid native state layout')
    native = record['native']
    words = native.get('words')
    inputs = native.get('inputs')
    if type(words) is not list or len(words) != DESCRIPTOR_WORDS or type(inputs) is not list:
        raise ValueError('Invalid native state layout')
    for value in words:
        _as_u32(value, 'Invalid native state word')
    if len(inputs) > MAX_INPUTS or words[140] != len(inputs):
        raise ValueError('Unsupported input count')
    if any(words[index] for index in STREAM_WORDS):
        raise ValueError('Unsupported stream output')
    if words[144] > 8:
        raise ValueError('Unsupported render-target count')
    for offset in POINTER_Q_OFFSETS:
        if _u64(words, offset // 4):
            raise ValueError('Unsupported pointer/stage in numeric descriptor')
    checked = []
    for item in inputs:
        if type(item) is not list or len(item) != 6:
            raise ValueError('Invalid native input')
        checked.append([_as_u32(value, 'Invalid native input') for value in item])
    return words, checked


def _descriptor_bytes(words):
    data = bytearray(struct.pack('<164I', *words))
    if len(data) != DESCRIPTOR_BYTES:
        raise ValueError('Descriptor is not 656 bytes')
    for offset in HASH_CLEAR_Q:
        data[offset:offset + 8] = b'\x00' * 8
    return data


def _input_bytes(fields):
    element = bytearray(32)
    struct.pack_into('<6I', element, 8, *fields)
    return element


def native_key(record, vs, ps, root_hash, check_lengths=True):
    """16-hex guest_pso_hash_ex of one numeric record and its DXBC bytes."""
    if type(check_lengths) is not bool:
        raise TypeError('check_lengths must be a bool')
    root_hash = _root_hash(root_hash)
    vs = _dxbc(vs)
    ps = _dxbc(ps)
    words, inputs = _native(record)
    declared_vs = _u64(words, 4)
    declared_ps = _u64(words, 8)
    if declared_vs > MAX_DXBC or declared_ps > MAX_DXBC:
        raise ValueError('Bytecode length exceeds its bound')
    if check_lengths and (declared_vs != len(vs) or declared_ps != len(ps)):
        raise ValueError('Rebuilt shader length differs from template')
    chunks = [KEY_PREFIX, _descriptor_bytes(words), ROOT_TAG, struct.pack('<Q', root_hash), vs, ps]
    for fields in inputs:
        chunks.extend((_input_bytes(fields), INPUT_SEMANTIC))
    # One bounded concatenation lets the existing verified native checksum DLL
    # hash the stream; its Python fallback has identical byte order and seed.
    digest = fnv64(b''.join(chunks))
    if digest == 0:
        raise ValueError('Pipeline key is zero')
    return f'{digest:016x}'


def derive_record(record, vs_source, vs, ps_source, ps, root_hash):
    """Deep-copy record and replace only its key, shader ids and length words.

    Length words 4/5 and 8/9 are the VS and PS bytecode sizes. The original
    record is not modified. Source ids use vs_5_0 and ps_5_0 with flags 0.
    """
    root_hash = _root_hash(root_hash)
    vs_source = _source(vs_source, MAX_VS_SOURCE, 'vertex')
    ps_source = _source(ps_source, MAX_PS_SOURCE, 'fragment')
    import shader_compiler
    vs_target, ps_target = shader_compiler.targets()  # Phase 231: vs_6_0/ps_6_0 with DXC
    return derive_record_from_ids(record, f'{source_key(vs_source, vs_target):016x}', vs,
                                  f'{source_key(ps_source, ps_target):016x}', ps, root_hash)


def derive_record_from_ids(record, vs_source_id, vs, ps_source_id, ps, root_hash):
    """Derive from source ids verified by the production shader worker/result path.

    Caller supplies verified local source identities, never guessed template ids
    for changed shaders. No source text is fabricated or reconstructed here.
    """
    root_hash = _root_hash(root_hash)
    for identity in (vs_source_id, ps_source_id):
        if type(identity) is not str or not HEX16.fullmatch(identity) or not int(identity, 16):
            raise ValueError('Invalid verified shader source identity')
    vs = _dxbc(vs)
    ps = _dxbc(ps)
    out = copy.deepcopy(record)
    words, _inputs = _native(out)
    _store_u64(words, 4, len(vs))
    _store_u64(words, 8, len(ps))
    code_vs = fnv64(vs)
    code_ps = fnv64(ps)
    if 0 in (code_vs, code_ps):
        raise ValueError('Shader identifier is zero')
    out['vs'] = f'{code_vs:016x}'
    out['ps'] = f'{code_ps:016x}'
    out['vp_source'] = vs_source_id
    out['fp_source'] = ps_source_id
    out['key'] = native_key(out, vs, ps, root_hash, True)
    return out


def _label(record, index):
    if type(record) is dict and type(record.get('key')) is str and HEX16.fullmatch(record['key']):
        return record['key']
    return f'record {index}'


def _identity(record, index, found):
    words, _inputs = _native(record)
    for source_name, code_name, slot in (('vp_source', 'vs', 4), ('fp_source', 'ps', 8)):
        source = record.get(source_name)
        code = record.get(code_name)
        if (type(source) is not str or type(code) is not str or not HEX16.fullmatch(source) or
                not HEX16.fullmatch(code) or int(source, 16) == 0 or int(code, 16) == 0):
            raise ValueError(f'Selected default shader identity is malformed for {_label(record, index)}')
        identity = (code, _u64(words, slot))
        previous = found.get(source)
        if previous is not None and previous != identity:
            raise ValueError('Template source/bytecode mapping conflicts')
        found[source] = identity


def _cached_shader(shaders, source, identity):
    if type(shaders) is not dict or source not in shaders:
        raise ValueError(f'Selected default shader bytes are missing for {source}')
    blob = shaders[source]
    code, length = identity
    if type(blob) is not bytes:
        raise ValueError(f'Selected default shader bytes are invalid for {source}')
    if len(blob) != length or len(blob) < MIN_DXBC or len(blob) > MAX_DXBC or not blob.startswith(b'DXBC'):
        raise ValueError(f'Selected default shader length mismatch for {source}')
    if f'{fnv64(blob):016x}' != code:
        raise ValueError(f'Selected default shader identity mismatch for {source}')
    return blob


def calibrate(records, shaders, root_hash):
    """Fail if any selected default record disagrees with its cached DXBC.

    shaders maps 16-hex source ids to verified bytecode. Every record is
    checked. A missing blob, a length or bytecode-id conflict, or a pipeline
    key that guest_pso_hash_ex would not produce raises ValueError.
    """
    root_hash = _root_hash(root_hash)
    if type(records) not in (list, tuple) or not records:
        raise ValueError('No selected default pipeline records')
    if type(shaders) is not dict:
        raise TypeError('Cached source-key bytes must be a dict')
    found = {}
    for index, record in enumerate(records):
        _identity(record, index, found)
    blobs = {source: _cached_shader(shaders, source, identity) for source, identity in found.items()}
    for index, record in enumerate(records):
        label = _label(record, index)
        if type(record.get('key')) is not str or not HEX16.fullmatch(record['key']) or int(record['key'], 16) == 0:
            raise ValueError(f'Selected default pipeline key is malformed for {label}')
        try:
            expected = native_key(record, blobs[record['vp_source']], blobs[record['fp_source']], root_hash, True)
        except ValueError as exc:
            raise ValueError(f'Selected default pipeline is malformed for {label}: {exc}') from exc
        if expected != record['key']:
            raise ValueError(f'Selected default pipeline key mismatch for {label}')
    return {'records': len(records), 'matched': len(records), 'root_hash': root_hash}


class _DescriptorRange(ctypes.Structure):
    _fields_ = (
        ('RangeType', ctypes.c_uint),
        ('NumDescriptors', ctypes.c_uint),
        ('BaseShaderRegister', ctypes.c_uint),
        ('RegisterSpace', ctypes.c_uint),
        ('OffsetInDescriptorsFromTableStart', ctypes.c_uint),
    )


class _RootDescriptor(ctypes.Structure):
    _fields_ = (
        ('ShaderRegister', ctypes.c_uint),
        ('RegisterSpace', ctypes.c_uint),
    )


class _RootConstants(ctypes.Structure):
    _fields_ = (
        ('ShaderRegister', ctypes.c_uint),
        ('RegisterSpace', ctypes.c_uint),
        ('Num32BitValues', ctypes.c_uint),
    )


class _RootDescriptorTable(ctypes.Structure):
    _fields_ = (
        ('NumDescriptorRanges', ctypes.c_uint),
        ('pDescriptorRanges', ctypes.c_void_p),
    )


class _RootParameterUnion(ctypes.Union):
    _fields_ = (
        ('DescriptorTable', _RootDescriptorTable),
        ('Constants', _RootConstants),
        ('Descriptor', _RootDescriptor),
    )


class _RootParameter(ctypes.Structure):
    _fields_ = (
        ('ParameterType', ctypes.c_uint),
        ('u', _RootParameterUnion),
        ('ShaderVisibility', ctypes.c_uint),
    )


class _StaticSampler(ctypes.Structure):
    _fields_ = (
        ('Filter', ctypes.c_uint),
        ('AddressU', ctypes.c_uint),
        ('AddressV', ctypes.c_uint),
        ('AddressW', ctypes.c_uint),
        ('MipLODBias', ctypes.c_float),
        ('MaxAnisotropy', ctypes.c_uint),
        ('ComparisonFunc', ctypes.c_uint),
        ('BorderColor', ctypes.c_uint),
        ('MinLOD', ctypes.c_float),
        ('MaxLOD', ctypes.c_float),
        ('ShaderRegister', ctypes.c_uint),
        ('RegisterSpace', ctypes.c_uint),
        ('ShaderVisibility', ctypes.c_uint),
    )


class _RootSignatureDesc(ctypes.Structure):
    _fields_ = (
        ('NumParameters', ctypes.c_uint),
        ('pParameters', ctypes.c_void_p),
        ('NumStaticSamplers', ctypes.c_uint),
        ('pStaticSamplers', ctypes.c_void_p),
        ('Flags', ctypes.c_uint),
    )


_QueryInterface = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
_AddRef = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
_Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
_GetBufferPointer = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
_GetBufferSize = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)


class ID3DBlobVtbl(ctypes.Structure):
    _fields_ = (
        ('QueryInterface', _QueryInterface),
        ('AddRef', _AddRef),
        ('Release', _Release),
        ('GetBufferPointer', _GetBufferPointer),
        ('GetBufferSize', _GetBufferSize),
    )


class ID3DBlob(ctypes.Structure):
    _fields_ = (('lpVtbl', ctypes.POINTER(ID3DBlobVtbl)),)


def _field_offset(cls, name):
    return getattr(cls, name).offset


def validate_layouts():
    """Reject a ctypes layout that is not the Windows x64 MSVC layout.

    This does not load d3d12.dll. Call it from tests with a fake serializer.
    """
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError('Windows x64 ctypes layout required')
    expected = (
        (_DescriptorRange, 20),
        (_RootDescriptor, 8),
        (_RootConstants, 12),
        (_RootDescriptorTable, 16),
        (_RootParameterUnion, 16),
        (_RootParameter, 32),
        (_StaticSampler, 52),
        (_RootSignatureDesc, 40),
        (ID3DBlob, 8),
    )
    for cls, size in expected:
        if ctypes.sizeof(cls) != size:
            raise RuntimeError(f'Windows x64 layout mismatch: {cls.__name__} is {ctypes.sizeof(cls)} bytes')
    offsets = (
        (_RootParameter, 'u', 8),
        (_RootParameter, 'ShaderVisibility', 24),
        (_RootDescriptorTable, 'pDescriptorRanges', 8),
        (_StaticSampler, 'MaxLOD', 36),
        (_StaticSampler, 'ShaderRegister', 40),
        (_StaticSampler, 'ShaderVisibility', 48),
        (_RootSignatureDesc, 'pParameters', 8),
        (_RootSignatureDesc, 'pStaticSamplers', 24),
        (_RootSignatureDesc, 'Flags', 32),
        (_DescriptorRange, 'OffsetInDescriptorsFromTableStart', 16),
        (ID3DBlobVtbl, 'Release', 16),
        (ID3DBlobVtbl, 'GetBufferPointer', 24),
        (ID3DBlobVtbl, 'GetBufferSize', 32),
    )
    for cls, name, offset in offsets:
        if _field_offset(cls, name) != offset:
            raise RuntimeError(f'Windows x64 layout mismatch: {cls.__name__}.{name}')
    if ctypes.sizeof(ID3DBlobVtbl) != 40:
        raise RuntimeError('Windows x64 layout mismatch: ID3DBlob vtable')


def _sampler(register, filt, address_u, address_v, address_w, anisotropy=0):
    item = _StaticSampler()
    item.Filter = filt
    item.AddressU = address_u
    item.AddressV = address_v
    item.AddressW = address_w
    item.MaxAnisotropy = anisotropy
    item.MaxLOD = struct.unpack('<f', FLT_MAX_BITS)[0]
    item.ShaderRegister = register
    item.ShaderVisibility = VISIBILITY_PIXEL
    return item


def _production_samplers():
    """The backend's 16 samplers with RSX_ANISO fixed at the template default."""
    samplers = (_StaticSampler * 16)()
    for index in range(16):
        samplers[index] = _sampler(index, FILTER_LINEAR, ADDRESS_WRAP, ADDRESS_WRAP, ADDRESS_WRAP)
    samplers[0] = _sampler(0, FILTER_POINT, ADDRESS_CLAMP, ADDRESS_CLAMP, ADDRESS_CLAMP)
    filters = (FILTER_POINT, FILTER_LINEAR_MIP_POINT, FILTER_LINEAR)
    for key in range(12):
        wrap = key & 3
        filt = filters[key >> 2]
        anisotropy = 0
        if (key >> 2) >= 1:
            filt = FILTER_ANISOTROPIC
            anisotropy = ANISOTROPY
        address_u = ADDRESS_CLAMP if wrap in (1, 3) else ADDRESS_WRAP
        address_v = ADDRESS_CLAMP if wrap in (1, 2) else ADDRESS_WRAP
        samplers[4 + key] = _sampler(4 + key, filt, address_u, address_v, ADDRESS_CLAMP, anisotropy)
    return samplers


def _parameter(kind, visibility, register=0, ranges=None):
    item = _RootParameter()
    item.ParameterType = kind
    item.ShaderVisibility = visibility
    if kind == PARAMETER_TABLE:
        item.u.DescriptorTable.NumDescriptorRanges = 1
        item.u.DescriptorTable.pDescriptorRanges = ctypes.addressof(ranges)
    else:
        item.u.Descriptor.ShaderRegister = register
        item.u.Descriptor.RegisterSpace = 0
    return item


def _build_root_signature():
    ranges = _DescriptorRange()
    ranges.RangeType = RANGE_SRV
    ranges.NumDescriptors = 16
    ranges.BaseShaderRegister = 0
    ranges.RegisterSpace = 0
    ranges.OffsetInDescriptorsFromTableStart = RANGE_OFFSET_APPEND
    parameters = (_RootParameter * 5)()
    parameters[0] = _parameter(PARAMETER_CBV, VISIBILITY_VERTEX, 0)
    parameters[1] = _parameter(PARAMETER_TABLE, VISIBILITY_PIXEL, ranges=ranges)
    parameters[2] = _parameter(PARAMETER_CBV, VISIBILITY_PIXEL, 1)
    parameters[3] = _parameter(PARAMETER_SRV, VISIBILITY_VERTEX, 20)
    parameters[4] = _parameter(PARAMETER_CBV, VISIBILITY_VERTEX, 2)
    samplers = _production_samplers()
    desc = _RootSignatureDesc()
    desc.NumParameters = 5
    desc.pParameters = ctypes.addressof(parameters)
    desc.NumStaticSamplers = 16
    desc.pStaticSamplers = ctypes.addressof(samplers)
    desc.Flags = ROOT_FLAG_INPUT_LAYOUT
    desc._keepalive = (ranges, parameters, samplers)
    return desc


def _release(blob):
    if not blob:
        return
    table = blob.contents.lpVtbl
    if not table or not table.contents.Release:
        return
    table.contents.Release(ctypes.cast(blob, ctypes.c_void_p))


def _release_pair(signature, error):
    first = None
    for blob in (signature, error):
        try:
            _release(blob)
        except Exception as exc:
            if first is None:
                first = exc
    if first is not None:
        raise first


def _read_blob(blob, limit, reject_oversize):
    if not blob:
        raise RuntimeError('COM blob is null')
    table = blob.contents.lpVtbl
    if not table or not table.contents.GetBufferSize or not table.contents.GetBufferPointer:
        raise RuntimeError('COM blob vtable is incomplete')
    this = ctypes.cast(blob, ctypes.c_void_p)
    size = int(table.contents.GetBufferSize(this))
    if size <= 0:
        raise RuntimeError('COM blob is empty')
    if size > limit:
        if reject_oversize:
            raise RuntimeError('COM blob exceeds its bound')
        size = limit
    pointer = table.contents.GetBufferPointer(this)
    if not pointer:
        raise RuntimeError('COM blob pointer is null')
    return ctypes.string_at(pointer, size)


def _error_text(blob):
    if not blob:
        return ''
    try:
        text = _read_blob(blob, 512, False)
    except Exception:
        return ''
    message = text.split(b'\x00', 1)[0].decode('utf-8', 'replace')[:200]
    return ': ' + message if message else ''


def _failed(hr):
    return (int(hr) & 0xffffffff) >= 0x80000000


def _load_d3d12():
    if os.name != 'nt' or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError('Production root signature serialization requires Windows x64')
    return ctypes.WinDLL('d3d12.dll', winmode=LOAD_LIBRARY_SEARCH_SYSTEM32)


def _invoke_serialize(desc):
    """Call D3D12SerializeRootSignature. Tests replace this; import does not."""
    global _d3d12_library
    library = _load_d3d12()
    function = library.D3D12SerializeRootSignature
    function.argtypes = (
        ctypes.POINTER(_RootSignatureDesc), ctypes.c_uint,
        ctypes.POINTER(ctypes.POINTER(ID3DBlob)), ctypes.POINTER(ctypes.POINTER(ID3DBlob)))
    function.restype = ctypes.c_long
    signature = ctypes.POINTER(ID3DBlob)()
    error = ctypes.POINTER(ID3DBlob)()
    result = function(ctypes.byref(desc), ROOT_SIGNATURE_VERSION, ctypes.byref(signature), ctypes.byref(error))
    _d3d12_library = library
    return result, signature, error


def root_signature_hash():
    """Hash the serialized production root signature. Loads d3d12.dll on use."""
    validate_layouts()
    desc = _build_root_signature()
    result, signature, error = _invoke_serialize(desc)
    try:
        if _failed(result):
            raise RuntimeError(f'D3D12SerializeRootSignature failed: 0x{int(result) & 0xffffffff:08X}{_error_text(error)}')
        data = _read_blob(signature, MAX_ROOT_BLOB, True)
        return rs_bytes_hash(data)
    finally:
        _release_pair(signature, error)
