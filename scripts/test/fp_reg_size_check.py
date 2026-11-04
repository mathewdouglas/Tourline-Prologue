"""Developer check for RSX_FP_REG_SIZE: fragment register files sized to what the program uses.

    fp_reg_size_check.py --a <old decoder dll> --b <new decoder dll> --catalog <dir of *.fp> [--sample N]
                         [--seed S] [--rollback] [--cube-mask M]

The DLLs export rsx_fp_decompile_buffered_ex (build them from the runtime's rsx_fp_decompiler.c with and
without the change). Programs are the raw .fp files of the local asset catalogue (game data: read only, never
tracked). Without --rollback the new text is compiled with D3DCompile next to the old one and the check
reports compile time and how many bytecodes are identical. With --rollback the new decoder runs under
RSX_FP_REG_SIZE=0 and its text must equal the old text for every program. Run through run_locked.py.
"""
import argparse
import ctypes
import os
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))


def load(path):
    lib = ctypes.CDLL(str(path))
    fn = lib.rsx_fp_decompile_buffered_ex
    fn.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p,
                   ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    fn.restype = ctypes.c_int
    return fn


def translate(fn, data, cube):
    out = ctypes.create_string_buffer(1 << 20)
    count = ctypes.c_uint32(0)
    rc = fn(data, len(data), 0xFFFFFFFF, cube, out, len(out), ctypes.byref(count))
    return out.value if rc >= 0 else None


def disasm_key(blob):
    """Disassembly with the comment header dropped and r# temporaries renumbered by first appearance."""
    import re
    d3d = ctypes.WinDLL('d3dcompiler_47.dll')
    fn = d3d.D3DDisassemble
    fn.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
    fn.restype = ctypes.c_long
    out = ctypes.c_void_p()
    if fn(blob, len(blob), 0, None, ctypes.byref(out)) < 0:
        return None
    import hlsl_compile_bench as bench
    text = bench.blob_bytes(out).decode('latin1')
    bench.blob_size(out)[1](out)
    lines = [l for l in text.splitlines() if not l.startswith('//') and l.strip() and not l.startswith('dcl_temps')]
    seen = {}
    def rename(m):
        return 'r%d' % seen.setdefault(m.group(1), len(seen))
    return [re.sub(r'\br(\d+)\b', rename, l) for l in lines]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--a', type=Path, required=True)
    ap.add_argument('--b', type=Path, required=True)
    ap.add_argument('--catalog', type=Path, required=True)
    ap.add_argument('--sample', type=int, default=300)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--cube-mask', type=lambda v: int(v, 0), default=0)
    ap.add_argument('--rollback', action='store_true')
    ap.add_argument('--disasm', action='store_true',
                    help='for pairs whose bytecode differs, compare the disassembly after renumbering temporaries')
    a = ap.parse_args()
    if a.rollback:
        os.environ['RSX_FP_REG_SIZE'] = '0'
    else:
        os.environ.pop('RSX_FP_REG_SIZE', None)
    old, new = load(a.a), load(a.b)
    files = sorted(a.catalog.glob('*.fp'))
    random.Random(a.seed).shuffle(files)
    files = files[:a.sample]
    translated = failed = same_text = 0
    totals = [0.0, 0.0]
    identical = ok_pairs = status_mismatch = 0
    renamed = unequal = 0
    sizes = [0, 0]
    if not a.rollback:
        import hlsl_compile_bench as bench
    for path in files:
        data = path.read_bytes()
        ta, tb = translate(old, data, a.cube_mask), translate(new, data, a.cube_mask)
        if ta is None or tb is None:
            failed += ta is None or tb is None
            if (ta is None) != (tb is None):
                status_mismatch += 1
            continue
        translated += 1
        same_text += ta == tb
        if a.rollback:
            continue
        ea, ha, sa, da = bench.compile_source(ta, b'ps_5_0', 0)
        eb, hb, sb, db = bench.compile_source(tb, b'ps_5_0', 0)
        totals[0] += ea
        totals[1] += eb
        if (ha < 0) != (hb < 0):
            status_mismatch += 1
        elif ha >= 0:
            ok_pairs += 1
            identical += da == db
            if a.disasm and da != db:
                if disasm_key(da) == disasm_key(db):
                    renamed += 1
                else:
                    unequal += 1
                    print('instruction streams differ:', path.name)
            sizes[0] += sa
            sizes[1] += sb
    print(f'programs {len(files)}: translated {translated}, translate failed {failed}, '
          f'identical text {same_text}, compile-status mismatches {status_mismatch}')
    if a.rollback:
        ok = same_text == translated and not status_mismatch
        print('rollback text identical for every program' if ok else 'ROLLBACK DIFFERS')
        return 0 if ok else 1
    if a.disasm:
        print(f'bytecode differs but identical after temporary renumbering {renamed}; instruction streams differ {unequal}')
    print(f'compiled pairs {ok_pairs}: old {totals[0]:.2f} s, new {totals[1]:.2f} s (x{totals[0] / max(totals[1], 1e-9):.2f}); '
          f'bytecode identical {identical}/{ok_pairs}; dxbc bytes old {sizes[0]} new {sizes[1]}')
    return 0 if not status_mismatch else 1


if __name__ == '__main__':
    sys.exit(main())
