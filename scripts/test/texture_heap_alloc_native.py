"""Exercise the backend's placed-texture range allocator (texh_take / texh_give) with fake heaps.

Compiles the production functions from a patched runtime tree (no GPU, no game) and runs randomized
allocate/free sequences against an independent byte-map reference: no overlap, alignment honoured,
free bytes conserved, full coalescing after everything is freed.
Usage: texture_heap_alloc_native.py --runtime <tree with the main patch applied>
"""
import argparse
from pathlib import Path
import subprocess
import uuid


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime', type=Path, required=True)
    a = ap.parse_args()
    src = (a.runtime / 'libs/video/rsx_d3d12_backend.c').read_text(encoding='utf-8')
    begin = src.index('typedef struct { u64 off, size; } TexFree;')
    take = src.index('static int texh_take(')
    give_end = src.index('/* A texture resource for td (COPY_DEST)')
    types = src[begin:src.index('static TexHeap s_texh[TEXH_MAX];')]
    funcs = src[take:give_end]
    root = Path(__file__).resolve().parents[2]
    work = root / 'scratch' / ('texture-heap-' + uuid.uuid4().hex)
    work.mkdir(parents=True)
    test = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint64_t u64; typedef uint32_t u32; typedef uint8_t u8;
typedef struct ID3D12Heap ID3D12Heap;
#define TEXH_MAX 64
''' + types + r'''
static TexHeap s_texh[TEXH_MAX];
static u32 s_texh_n;
''' + funcs + r'''
#define HEAPS 3
#define HB (1u << 20)
static u8 owner[HEAPS][HB];
typedef struct { int live; u32 heap; u64 off, size; } Al;
static u32 rng = 12345;
static u32 rnd(void) { rng = rng * 1664525u + 1013904223u; return rng >> 8; }
int main(void)
{
    for (int i = 0; i < HEAPS; i++) {
        s_texh[i].cap = 4; s_texh[i].fr = (TexFree*)malloc(4 * sizeof(TexFree));
        s_texh[i].fr[0].off = 0; s_texh[i].fr[0].size = HB; s_texh[i].nfr = 1; s_texh[i].free_bytes = HB;
    }
    s_texh_n = HEAPS;
    static Al al[4096]; int nal = 0, ops = 0, fails = 0;
    for (int step = 0; step < 200000; step++) {
        int do_alloc = nal < 4096 && (rnd() % 100) < 55;
        if (do_alloc) {
            u64 align = (rnd() & 1) ? 4096 : 65536;
            u64 size = ((rnd() % 64) + 1) * 4096;
            u32 h; u64 off;
            if (texh_take(size, align, &h, &off)) {
                if (off % align) { printf("FAIL alignment\n"); return 1; }
                if (off + size > HB) { printf("FAIL range\n"); return 1; }
                for (u64 b = off; b < off + size; b++) if (owner[h][b]) { printf("FAIL overlap\n"); return 1; }
                memset(&owner[h][off], 1, size);
                al[nal].live = 1; al[nal].heap = h; al[nal].off = off; al[nal].size = size; nal++; ops++;
            } else fails++;
        } else if (nal) {
            int k = rnd() % nal;
            texh_give(al[k].heap, al[k].off, al[k].size);
            memset(&owner[al[k].heap][al[k].off], 0, al[k].size);
            al[k] = al[--nal]; ops++;
        }
        if ((step % 997) == 0) {
            for (int i = 0; i < HEAPS; i++) {
                u64 used = 0; for (u32 b = 0; b < HB; b++) used += owner[i][b];
                if (used + s_texh[i].free_bytes != HB) { printf("FAIL accounting heap %d\n", i); return 1; }
                for (u32 f = 0; f < s_texh[i].nfr; f++) {
                    if (f && s_texh[i].fr[f - 1].off + s_texh[i].fr[f - 1].size >= s_texh[i].fr[f].off) { printf("FAIL order/merge\n"); return 1; }
                    for (u64 b = s_texh[i].fr[f].off; b < s_texh[i].fr[f].off + s_texh[i].fr[f].size; b++)
                        if (owner[i][b]) { printf("FAIL free range in use\n"); return 1; }
                }
            }
        }
    }
    while (nal) { nal--; texh_give(al[nal].heap, al[nal].off, al[nal].size); }
    for (int i = 0; i < HEAPS; i++)
        if (s_texh[i].nfr != 1 || s_texh[i].fr[0].off != 0 || s_texh[i].fr[0].size != HB || s_texh[i].free_bytes != HB) {
            printf("FAIL final coalescing heap %d (%u ranges)\n", i, s_texh[i].nfr); return 1; }
    printf("texture heap allocator: %d operations, %d full-heap refusals, all checks passed\n", ops, fails);
    return 0;
}
'''
    (work / 'test.c').write_text(test, encoding='utf-8')
    cmd = work / 'build.cmd'
    cmd.write_text(f'''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
"C:\\Program Files\\LLVM\\bin\\clang-cl.exe" /nologo /TC /O2 /MD /W3 /D_CRT_SECURE_NO_WARNINGS /Fo"{work}/test.obj" /Fe"{work}/test.exe" "{work}/test.c"
exit /b %errorlevel%
''')
    subprocess.run(['cmd', '/c', str(cmd)], check=True)
    r = subprocess.run([str(work / 'test.exe')], capture_output=True, text=True)
    print(r.stdout, end='')
    raise SystemExit(r.returncode)


if __name__ == '__main__':
    main()
