"""Developer measurement: single-thread D3DCompile timing of dumped HLSL (never tracked data).

Usage: hlsl_compile_bench.py <dir-of-*.hlsl> [--sample N] [--seed S] [--flags F] [--transform NAME ...]
Sources come from the RSX_SHADER_SRC_DUMP engine overlay; they are game-derived and stay in ignored storage.
Run through run_locked.py. Prints per-sample totals and the slowest sources; with --transform, compiles each
sample source also after a textual rewrite and reports the speed-up (this changes the source key; it is a
measurement of potential only).
"""
import argparse
import ctypes
from ctypes import wintypes
import random
import re
import statistics
import sys
import time
from pathlib import Path

d3d = ctypes.WinDLL('d3dcompiler_47.dll')
D3DCompile = d3d.D3DCompile
D3DCompile.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint,
                       ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
D3DCompile.restype = ctypes.c_long


def blob_size(blob):
    vtbl = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    getsize = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(vtbl[4])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
    return getsize(blob), release


def blob_bytes(blob):
    vtbl = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    getptr = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(vtbl[3])
    size, _ = blob_size(blob)
    return ctypes.string_at(getptr(blob), size)


def compile_source(text, target, flags):
    out, err = ctypes.c_void_p(), ctypes.c_void_p()
    begin = time.perf_counter()
    hr = D3DCompile(text, len(text), b'bench', None, None, b'main', target, flags, 0, ctypes.byref(out), ctypes.byref(err))
    elapsed = time.perf_counter()-begin
    size, data = 0, b''
    if out:
        data = blob_bytes(out); size = len(data); _, release = blob_size(out); release(out)
    if err:
        _, release = blob_size(err); release(err)
    return elapsed, hr, size, data


DECL = 'float4 r[48]; float4 h[48];'
INIT = '[unroll] for (int _i = 0; _i < 48; _i++) { r[_i] = (float4)0; h[_i] = (float4)0; }'


def shrink_regs(text):
    """Register arrays sized to the highest literal index used. Unchanged when any index is not a literal."""
    if DECL not in text or INIT not in text:
        return text
    body = text.replace(INIT, '').replace(DECL, '')
    if re.search(r'\b[rh]\[(?!\d+\])', body):
        return text
    n = {name: max([int(m) for m in re.findall(r'\b%s\[(\d+)\]' % name, body)] or [0]) + 1 for name in 'rh'}
    text = text.replace(DECL, f'float4 r[{n["r"]}]; float4 h[{n["h"]}];')
    return text.replace(INIT, f'[unroll] for (int _i = 0; _i < {n["r"]}; _i++) r[_i] = (float4)0; '
                              f'[unroll] for (int _i = 0; _i < {n["h"]}; _i++) h[_i] = (float4)0;')


def no_init(text):
    """Measurement only: not semantics-preserving."""
    return text.replace(INIT, '')


def strip_decls(text):
    """Drop texture declarations the body never samples (not the sampler array)."""
    for name in re.findall(r'^Texture\w+\s+(rsx_tex\d+)\s*:\s*register\(t\d+\);\r?\n', text, re.M):
        if len(re.findall(r'\b%s\b' % name, text)) == 1:
            text = re.sub(r'^Texture\w+\s+%s\s*:\s*register\(t\d+\);\r?\n' % name, '', text, flags=re.M)
    return text


def _literal_regs(text):
    if DECL not in text or INIT not in text:
        return None
    body = text.replace(INIT, '').replace(DECL, '')
    if re.search(r'\b[rh]\[(?!\d+\])', body):
        return None
    return body, {name: sorted({int(m) for m in re.findall(r'\b%s\[(\d+)\]' % name, body)}) for name in 'rh'}


def explicit_init(text):
    """Same zero initialisation, but one plain statement per referenced register (no 48-entry loop)."""
    parsed = _literal_regs(text)
    if not parsed:
        return text
    body, used = parsed
    lines = ' '.join(f'{name}[{k}] = (float4)0;' for name in 'rh' for k in used[name])
    n = {name: used[name][-1] + 1 if used[name] else 1 for name in 'rh'}
    return text.replace(DECL, f'float4 r[{n["r"]}]; float4 h[{n["h"]}];').replace(INIT, lines)


def scalarize(text):
    """Registers as separate float4 variables (every index is a literal), zero-initialised, referenced only."""
    parsed = _literal_regs(text)
    if not parsed:
        return text
    body, used = parsed
    names = {'r': '_R', 'h': '_H'}
    body = re.sub(r'\b([rh])\[(\d+)\]', lambda m: names[m[1]] + m[2], body)
    decl = ''.join(f'float4 {names[name]}{k} = (float4)0; ' for name in 'rh' for k in used[name])
    return text.replace(DECL, '').replace(INIT, decl) if False else _scalar_join(text, body, decl)


def _scalar_join(text, body, decl):
    # Rebuild the text: the body (with DECL/INIT removed) has had the registers renamed; put the declarations
    # where the original INIT stood.
    i = text.index(INIT) if INIT in text else -1
    before = text[:i].replace(DECL, '')
    after = text[i + len(INIT):]
    after = re.sub(r'\b([rh])\[(\d+)\]', lambda m: {'r': '_R', 'h': '_H'}[m[1]] + m[2], after)
    before = re.sub(r'\b([rh])\[(\d+)\]', lambda m: {'r': '_R', 'h': '_H'}[m[1]] + m[2], before)
    return before + decl + after


def vf_loop(text):
    """GPU-fetch helper: the 4-component loop as a real loop (was [unroll])."""
    return text.replace('[unroll] for (uint i = 0; i < 4u; i++) {', '[loop] for (uint i = 0; i < 4u; i++) {')


def vf_maskloop(text):
    """GPU-fetch helper loop plus one loop over the literal attribute mask instead of one inlined fetch each."""
    text = vf_loop(text)
    found = re.findall(r'^    v\[(\d+)\]=rsx_vfetch\(\1u, input\.vid\);\r?\n', text, re.M)
    if not found:
        return text
    mask = sum(1 << int(k) for k in found)
    text = re.sub(r'^    v\[(\d+)\]=rsx_vfetch\(\1u, input\.vid\);\r?\n', '', text, flags=re.M)
    marker = '    [unroll] for (int _k=0;_k<16;_k++) v[_k]=float4(0,0,0,1);\n'
    loop = f'    [loop] for (uint _a = 0; _a < 16u; _a++) if ((({mask}u >> _a) & 1u) != 0u) v[_a] = rsx_vfetch(_a, input.vid);\n'
    return text.replace(marker, marker + loop, 1)


VDECL = 'float4 r[32];'
VINIT = '[unroll] for (int _i=0;_i<32;_i++) r[_i]=(float4)0;'


def vshrink(text):
    """Temporary register array sized to the highest literal index (unchanged when any index is dynamic)."""
    if VINIT not in text:
        return text
    body = text.replace(VINIT, '')
    if re.search(r'\br\[(?!\d+\])', body):
        return text
    n = max([int(m) for m in re.findall(r'\br\[(\d+)\]', body)] or [0]) + 1
    text = text.replace(VINIT, f'[unroll] for (int _i=0;_i<{n};_i++) r[_i]=(float4)0;')
    return re.sub(r'float4 r\[32\];', f'float4 r[{n}];', text, count=1)


TRANSFORMS = {
    # Fragment source experiments (measurements of potential only; each changes the shader source key).
    'none': lambda text: text,
    'shrink_regs': shrink_regs,
    'no_init': no_init,
    'strip_decls': strip_decls,
    'explicit_init': explicit_init,
    'scalarize': scalarize,
    'vf_loop': vf_loop,
    'vf_maskloop': vf_maskloop,
    'vshrink': vshrink,
    'vf_all': lambda text: vshrink(vf_maskloop(text)),
    'shrink_and_strip': lambda text: strip_decls(shrink_regs(text)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder', type=Path)
    ap.add_argument('--target', default='ps_5_0')
    ap.add_argument('--sample', type=int, default=200)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--flags', type=lambda v: int(v, 0), default=0)
    ap.add_argument('--transform', action='append', default=[])
    ap.add_argument('--compare-flags', type=lambda v: int(v, 0), action='append', default=[], help='Also compile with these flags; report time and byte-identity')
    ap.add_argument('--only', default='', help='Substring the file name must contain (e.g. gpu1)')
    ap.add_argument('--top', type=int, default=8)
    a = ap.parse_args()
    files = sorted(p for p in a.folder.glob(f'*.{a.target}.hlsl') if a.only in p.name)
    random.Random(a.seed).shuffle(files)
    files = files[:a.sample]
    target = a.target.encode()
    rows = []
    reference = {}
    for path in files:
        text = path.read_bytes()
        elapsed, hr, size, data = compile_source(text, target, a.flags)
        rows.append((elapsed, len(text), size, path.name, hr))
        reference[path.name] = data
    times = [r[0] for r in rows]
    print(f'{len(rows)} sources: total {sum(times):.2f} s, mean {statistics.mean(times)*1e3:.1f} ms, '
          f'median {statistics.median(times)*1e3:.1f} ms, p90 {sorted(times)[int(.9*len(times))]*1e3:.1f} ms, '
          f'failed {sum(1 for r in rows if r[4] < 0)}')
    print('source bytes mean', int(statistics.mean(r[1] for r in rows)), 'dxbc bytes mean', int(statistics.mean(r[2] for r in rows)))
    for r in sorted(rows, reverse=True)[:a.top]:
        print(f'  {r[0]*1e3:7.1f} ms  src {r[1]:7d}  dxbc {r[2]:7d}  {r[3]}')
    for flags in a.compare_flags:
        total = 0.0; identical = 0; failed = 0
        for path in files:
            elapsed, hr, size, data = compile_source(path.read_bytes(), target, flags)
            total += elapsed; failed += hr < 0; identical += data == reference[path.name]
        print(f'flags {flags:#x}: total {total:.2f} s vs {sum(times):.2f} s (x{sum(times)/total:.2f}); byte-identical {identical}/{len(rows)}; failed {failed}')
    for name in a.transform:
        fn = TRANSFORMS[name]
        total = 0.0
        same = 0
        for path in files:
            text = fn(path.read_bytes().decode('utf-8', 'replace')).encode()
            elapsed, hr, size, data = compile_source(text, target, a.flags)
            total += elapsed
            same += data == reference[path.name]
        print(f'transform {name}: total {total:.2f} s vs {sum(times):.2f} s (x{sum(times)/total:.2f}); same-size outputs {same}/{len(rows)}')


if __name__ == '__main__':
    main()
