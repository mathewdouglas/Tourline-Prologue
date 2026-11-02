"""Optional native cache checksums with an identical portable Python fallback.

Load only the bundled absolute DLL path, or an explicitly selected developer
library. A version/known-vector self-test gates native use. No integrity check
or shader/pipeline identifier changes when the backend changes.
"""
import ctypes
import hashlib
import os
from pathlib import Path
import sys
import time
import threading

_native = None
_configured = False
_backend = dict(backend='python', reason='not-configured')
_counts = dict(calls=0, bytes=0, native_calls=0, python_calls=0, seconds=0.0)
_counts_lock = threading.Lock()


def python_fnv64(data):
    value = 1469598103934665603  # Renderer seed, not the standard FNV offset.
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return value


def configure(path=None):
    global _native, _configured, _backend
    _native = None
    _configured = True
    _backend = dict(backend='python', reason='not-installed')
    if os.environ.get('GT5P_PREPARE_NATIVE_HASH') == '0':
        _backend['reason'] = 'disabled'
        return _backend.copy()
    if path is None:
        if getattr(sys, 'frozen', False):
            path = Path(sys.executable).parent/'cache_hash.dll'
        else:
            path = os.environ.get('GT5P_PREPARE_HASH_LIBRARY')
    if not path:
        return _backend.copy()
    path = Path(path).absolute()
    try:
        for item in (path, *path.parents):
            if item.is_symlink() or getattr(item.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('redirected-library')
        if not path.is_file() or path.stat().st_nlink > 1 or path.stat().st_size > 1024**2:
            raise ValueError('invalid-library-file')
        # No PATH/current-directory DLL search. The helper is statically linked;
        # only Windows dependencies are allowed when loading its absolute path.
        library = ctypes.CDLL(str(path), **({'winmode': 0x100 | 0x800} if os.name == 'nt' else {}))
        abi = library.gt5p_cache_hash_abi
        abi.argtypes = []; abi.restype = ctypes.c_uint32
        if abi() != 1:
            raise ValueError('incompatible-abi')
        function = library.gt5p_cache_fnv64
        function.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        function.restype = ctypes.c_uint64
        for payload in (b'', b'\0', b'\xff', bytes(range(256)), bytes(range(251))*17):
            if function(ctypes.c_char_p(payload), len(payload)) != python_fnv64(payload):
                raise ValueError('self-test-failed')
        _native = function  # ctypes keeps its owning library alive.
        _backend = dict(backend='native', abi=1, library_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    except (OSError, AttributeError, ValueError) as exc:
        _backend = dict(backend='python', reason=str(exc)[:200])
    return _backend.copy()


def fnv64(data):
    if not _configured:
        configure()
    begin = time.perf_counter()
    byte_payload = isinstance(data, (bytes, bytearray)) or (
        isinstance(data, memoryview) and data.ndim == 1 and data.format == 'B')
    if _native is not None and byte_payload:
        payload = data if isinstance(data, bytes) else bytes(data)
        result = _native(ctypes.c_char_p(payload), len(payload))
        kind='native_calls'
    else:
        result = python_fnv64(data)
        kind='python_calls'
    with _counts_lock:
        _counts[kind] += 1
        _counts['calls'] += 1
        _counts['bytes'] += len(data) if hasattr(data, '__len__') else 0
        _counts['seconds'] += time.perf_counter() - begin
    return result


def statistics(before=None):
    if not _configured:
        configure()
    with _counts_lock:values = _counts.copy()
    if before is not None:
        values = {key:value-before[key] for key,value in values.items()}
    return dict(_backend, **values)
