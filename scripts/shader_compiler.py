"""Which HLSL compiler guest shaders use, for preparation (Phase 231). Mirrors the engine's shader_dxc_on().

RSX_SHADER_COMPILER: `dxc` = DXC to shader model 6.0 (vs_6_0/ps_6_0, `-HV 2018`); unset or `fxc` = FXC to 5.0
(d3dcompiler_47 from the Windows system directory, as before). The target string is part of every shader source
key, so FXC and DXC caches never mix. RSX_SHADER_INTERP=1 keeps FXC in the engine (the interpreter's own shaders
are FXC), and here too.

DXC is the dxcompiler.dll beside the game engine: GT5P_PREPARE_DXC_LIBRARY names it (the player helper sets it to
install/runtime/dxcompiler.dll; developer tools default to third_party/dxc/dxcompiler.dll). The arguments are the
engine's (-E main -T <target> -HV 2018 -Gis), so both produce the same bytes from the same text.
"""
import ctypes
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = ('fxc', 'dxc')
TARGETS = {'fxc': (b'vs_5_0', b'ps_5_0'), 'dxc': (b'vs_6_0', b'ps_6_0')}
_CLSID_COMPILER = (0x73e22d93, 0xe6ce, 0x47f3, (0xb5, 0xbf, 0xf0, 0x66, 0x4f, 0x39, 0xc1, 0xb0))
_IID_COMPILER3 = (0x228b4687, 0x5a6a, 0x4730, (0x90, 0x0c, 0x97, 0x02, 0xb2, 0x20, 0x3f, 0x54))
_IID_OP_RESULT = (0xcedb484a, 0xd4e9, 0x445a, (0xb9, 0x91, 0xca, 0x21, 0xca, 0x15, 0x7d, 0xc2))


def mode(environ=None):
    environ = os.environ if environ is None else environ
    value = environ.get('RSX_SHADER_COMPILER', 'fxc')
    if value not in MODES:
        raise ValueError('RSX_SHADER_COMPILER must be unset, fxc or dxc')
    if environ.get('RSX_SHADER_INTERP') == '1':
        return 'fxc'
    return value


def targets(environ=None):
    """(vertex target, pixel target) as bytes, for source keys."""
    return TARGETS[mode(environ)]


def library(environ=None):
    environ = os.environ if environ is None else environ
    value = environ.get('GT5P_PREPARE_DXC_LIBRARY')
    return Path(value) if value else ROOT / 'third_party/dxc/dxcompiler.dll'


class _GUID(ctypes.Structure):
    _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte * 8)]


def _guid(t):
    return _GUID(t[0], t[1], t[2], (ctypes.c_ubyte * 8)(*t[3]))


class _Buffer(ctypes.Structure):
    _fields_ = [('ptr', ctypes.c_void_p), ('size', ctypes.c_size_t), ('encoding', ctypes.c_uint32)]


def _method(obj, index, restype, *argtypes):
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(table[index])


def _blob_bytes(blob):
    pointer = _method(blob, 3, ctypes.c_void_p)(blob)
    size = _method(blob, 4, ctypes.c_size_t)(blob)
    return ctypes.string_at(pointer, size) if size else b''


def _release(obj):
    if obj:
        _method(obj, 2, ctypes.c_ulong)(obj)


class Dxc:
    """One DXC compiler object (not thread-safe; one per thread or process)."""

    def __init__(self, path=None):
        path = Path(path or library())
        if not path.is_file():
            raise ValueError(f'DXC compiler not found: {path} (scripts/get_dxc.py), or set RSX_SHADER_COMPILER=fxc')
        # LOAD_WITH_ALTERED_SEARCH_PATH: dxil.dll (the signer) from the same folder.
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
        kernel.LoadLibraryExW.restype = ctypes.c_void_p
        handle = kernel.LoadLibraryExW(str(path.resolve()), None, 0x8)
        if not handle:
            raise ValueError(f'DXC compiler could not be loaded: {path}')
        self.dll = ctypes.WinDLL(str(path.resolve()), handle=handle)
        create = self.dll.DxcCreateInstance
        create.argtypes = [ctypes.POINTER(_GUID), ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
        create.restype = ctypes.c_long
        self.compiler = ctypes.c_void_p()
        if create(ctypes.byref(_guid(_CLSID_COMPILER)), ctypes.byref(_guid(_IID_COMPILER3)),
                  ctypes.byref(self.compiler)) < 0:
            raise ValueError('DXC compiler object could not be created')
        self.iid_result = _guid(_IID_OP_RESULT)

    def close(self):
        compiler = getattr(self, 'compiler', None)
        self.compiler = None
        _release(compiler)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass  # ctypes may already be torn down during interpreter shutdown.

    def compile(self, source, target):
        """(bytecode, error text) for HLSL bytes; bytecode is b'' on failure."""
        if b'rsx_samp[' in source or b'rsx_tex[' in source:
            # The engine rewrites these arrays for DXC (shader_dxc_scalarize); only fragment programs have them
            # and the offline engine compiles those. Refuse rather than produce different bytes.
            raise ValueError('Resource arrays in a shader compiled outside the engine')
        args = ['-E', 'main', '-T', target.decode('ascii'), '-HV', '2018', '-Gis']  # as the engine (Phase 231)
        argv = (ctypes.c_wchar_p * len(args))(*args)
        text = ctypes.create_string_buffer(source, len(source))
        buffer = _Buffer(ctypes.cast(text, ctypes.c_void_p), len(source), 65001)
        result = ctypes.c_void_p()
        compile_ = _method(self.compiler, 3, ctypes.c_long, ctypes.POINTER(_Buffer), ctypes.c_void_p, ctypes.c_uint32,
                           ctypes.c_void_p, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))
        hr = compile_(self.compiler, ctypes.byref(buffer), argv, len(args), None, ctypes.byref(self.iid_result),
                      ctypes.byref(result))
        if hr < 0 or not result:
            return b'', f'DXC call failed (0x{hr & 0xffffffff:08x})'
        try:
            status = ctypes.c_long(-1)
            _method(result, 3, ctypes.c_long, ctypes.POINTER(ctypes.c_long))(result, ctypes.byref(status))
            blob = ctypes.c_void_p()
            if status.value >= 0:
                _method(result, 4, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(result, ctypes.byref(blob))
                try:
                    return _blob_bytes(blob), ''
                finally:
                    _release(blob)
            _method(result, 5, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(result, ctypes.byref(blob))
            try:
                return b'', _blob_bytes(blob).decode('utf-8', 'replace') if blob else 'DXC failed'
            finally:
                _release(blob)
        finally:
            _release(result)
