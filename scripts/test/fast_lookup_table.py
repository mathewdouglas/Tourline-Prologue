"""Phase 221 fast lookup table: the Python mirror must match the renderer.

1. rsx_fp_structural_hash: compiles the runtime's rsx_fp_decompiler.c (patched tree) with a tiny harness and
   compares it with fast_lookup_table.structural_hash on fragment programs from a local catalogue (read-only;
   only hashes are printed) plus synthetic edge cases (no END, too many constants).
2. Key/tag/file round trip, order independence of the translation environment, and mode separation.
Usage: fast_lookup_table.py --runtime <patched tree> [--catalog <dir of .fp files>] [--limit 400]
"""
import argparse
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import fast_lookup_table as f  # noqa: E402


def native_hashes(runtime, programs):
    work = ROOT / 'scratch' / ('fast-lookup-test-' + uuid.uuid4().hex)
    work.mkdir(parents=True)
    for i, p in enumerate(programs):
        (work / f'{i:05d}.fp').write_bytes(p)
    (work / 'h.c').write_text(r'''
#include <stdio.h>
#include <stdlib.h>
#include "rsx_fp_decompiler.h"
int main(int argc, char** argv) {
    for (int i = 1; i < argc; i++) {
        FILE* f = fopen(argv[i], "rb"); if (!f) return 2;
        static unsigned char buf[1 << 16]; size_t n = fread(buf, 1, sizeof buf, f); fclose(f);
        printf("%016llx\n", (unsigned long long)rsx_fp_structural_hash(buf, (unsigned)n, 0));
    }
    return 0;
}
''', encoding='ascii')
    video = runtime / 'libs' / 'video'
    cmd = work / 'build.cmd'
    cmd.write_text(f'''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
"C:\\Program Files\\LLVM\\bin\\clang-cl.exe" /nologo /TC /O1 /MD /W0 /D_CRT_SECURE_NO_WARNINGS /I"{video}" /I"{runtime / 'include'}" /Fe"{work}/h.exe" /Fo"{work}/" "{work}/h.c" "{video / 'rsx_fp_decompiler.c'}"
exit /b %errorlevel%
''')
    subprocess.run(['cmd', '/c', str(cmd)], check=True, capture_output=True)
    files = [str(work / f'{i:05d}.fp') for i in range(len(programs))]
    out = []
    for i in range(0, len(files), 200):
        out += subprocess.run([str(work / 'h.exe')] + files[i:i + 200], check=True, capture_output=True,
                              text=True).stdout.split()
    return [int(x, 16) for x in out]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime', type=Path, required=True)
    ap.add_argument('--catalog', type=Path, default=Path(r'C:\Users\GGPC\Dev\Recomps\GT5P\shadercache\library-v1\all'))
    ap.add_argument('--limit', type=int, default=400)
    a = ap.parse_args()
    programs = []
    if a.catalog.is_dir():
        paths = sorted(a.catalog.glob('*.fp'))
        random.Random(221).shuffle(paths)
        programs = [p.read_bytes() for p in paths[:a.limit]]
    # Synthetic: END on the first instruction; a constant-bearing instruction; no END at all; truncated constant.
    end = bytes.fromhex('00000001' + '00000000' * 3)          # half-word swapped: w0 bit 0 set -> 0x0001 in high half
    programs += [end, bytes(16), bytes(15), b'\x00\x02\x00\x00' * 4]
    expected = native_hashes(a.runtime, programs)
    got = [f.structural_hash(p) for p in programs]
    bad = sum(1 for x, y in zip(expected, got) if x != y)
    print(f'structural hash: {len(programs)} programs ({len(programs) - 4} catalogue), mismatches {bad}')
    assert bad == 0 and len(expected) == len(programs)

    state = dict(blend=19278219, nrt=1, rtfmt=11, exp32=0, cmask=15, cull=0, stencil=0xF0000000, unnorm=0,
                 cube=0x20000, vmask=265, samplers='0000000000000009', ghi=0, shd=0, unhi=0)
    k1 = f.key(0x1234, 0x5678, state)
    assert k1 == f.key(0x1234, 0x5678, dict(state)) and k1 != f.key(0x1234, 0x5679, state)
    assert k1 != f.key(0x1234, 0x5678, dict(state, samplers='000000000000000a'))
    with tempfile.TemporaryDirectory() as d:
        exe = Path(d) / 'gt5p.exe'
        exe.write_bytes(b'x' * 100)
        t = {m: f.tag(exe, m) for m in f.MODES}
        assert len(set(t.values())) == 3, 'translation modes must not share a tag'
        assert f.tag(exe, 'default', translation_env={'RSX_FP_REG_SIZE': '0', 'RSX_VFETCH_LOOP': '1'}) == \
            f.tag(exe, 'default', translation_env={'rsx_vfetch_loop': '1', 'RSX_FP_REG_SIZE': '0'})
        assert f.tag(exe, 'default', translation_env={'RSX_PSO_TIMING': '1'}) == t['default'], 'non-translation env ignored'
        assert f.tag(exe, 'default', high_precision=False) != t['default']
        path = Path(d) / 'table.bin'
        f.write(path, t['default'], {k1: 0xABCDEF})
        assert f.read(path) == (t['default'], {k1: 0xABCDEF})
        exe.write_bytes(b'y' * 101)
        assert f.tag(exe, 'default') != t['default'], 'engine identity enters the tag'
    print('fast lookup table: key, tag, file checks passed')


if __name__ == '__main__':
    main()
