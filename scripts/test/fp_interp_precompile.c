/* Write the 16 fragment-interpreter DXBC variants into a private cache.
 * The filename is shader_source_key from rsx_d3d12_backend.c: FNV-1a over the
 * exact source bytes, then the target string, then the flag word. The entry
 * name is not part of the key. Flags default to 0, matching
 * RSX_SHADER_INTERP_OPT unset. The HLSL bytes come from rsx_fp_interp.h so
 * this tool and the engine cannot drift.
 *
 * Usage: fp_interp_precompile <cache-dir> [flags]
 */
#define WIN32_LEAN_AND_MEAN
#define CINTERFACE
#define COBJMACROS
#include <windows.h>
#include <d3dcompiler.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define RSX_FP_INTERP_EMBED_HLSL
#include "rsx_fp_interp.h"

static unsigned long long source_key(const char* src, size_t len, const char* target, unsigned flags)
{
    unsigned long long h = 1469598103934665603ull;
    size_t i;
    const char* t;
    for (i = 0; i < len; i++) { h ^= (unsigned char)src[i]; h *= 1099511628211ull; }
    for (t = target; *t; t++) { h ^= (unsigned char)*t; h *= 1099511628211ull; }
    h ^= flags; h *= 1099511628211ull;
    return h;
}

int main(int argc, char** argv)
{
    const char* dir = argc > 1 ? argv[1] : NULL;
    unsigned flags = 0;
    char src[65536];
    int full, sample, targets, wrote = 0;
    if (!dir || !dir[0]) {
        fprintf(stderr, "usage: fp_interp_precompile <cache-dir> [flags]\n");
        return 2;
    }
    if (argc > 2) flags = (unsigned)strtoul(argv[2], NULL, 0);
    if (!CreateDirectoryA(dir, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        fprintf(stderr, "cache dir %s: %lu\n", dir, GetLastError());
        return 1;
    }
    for (full = 0; full < 2; full++)
        for (sample = 0; sample < 2; sample++)
            for (targets = 1; targets <= 4; targets++) {
                int n = rsx_fp_interp_variant_prefix(src, sizeof src, full, sample, targets);
                size_t hl = strlen(rsx_fp_interp_hlsl);
                ID3DBlob* blob = NULL;
                ID3DBlob* err = NULL;
                unsigned long long h;
                char path[1024];
                HRESULT hr;
                ULONGLONG t0;
                FILE* f;
                size_t nb;
                if (n < 0 || (size_t)n + hl + 1 > sizeof src) {
                    fprintf(stderr, "source buffer overflow\n");
                    return 1;
                }
                memcpy(src + n, rsx_fp_interp_hlsl, hl + 1);
                h = source_key(src, (size_t)n + hl, "ps_5_1", flags);
                snprintf(path, sizeof path, "%s/%016llx.dxbc", dir, h);
                t0 = GetTickCount64();
                hr = D3DCompile(src, (size_t)n + hl, "rsx_fp_interp", NULL, NULL,
                                "main", "ps_5_1", flags, 0, &blob, &err);
                fprintf(stderr, "[precompile] full=%d sample=%d targets=%d hr=0x%08lx %llu ms %u bytes %s\n",
                        full, sample, targets, (unsigned long)hr,
                        (unsigned long long)(GetTickCount64() - t0),
                        blob ? (unsigned)blob->lpVtbl->GetBufferSize(blob) : 0u, path);
                if (FAILED(hr) || !blob) {
                    if (err) fprintf(stderr, "%s\n", (const char*)err->lpVtbl->GetBufferPointer(err));
                    if (err) err->lpVtbl->Release(err);
                    return 1;
                }
                f = fopen(path, "wb");
                if (!f) { fprintf(stderr, "open %s failed\n", path); return 1; }
                nb = blob->lpVtbl->GetBufferSize(blob);
                if (fwrite(blob->lpVtbl->GetBufferPointer(blob), 1, nb, f) != nb) {
                    fclose(f);
                    return 1;
                }
                fclose(f);
                blob->lpVtbl->Release(blob);
                if (err) err->lpVtbl->Release(err);
                wrote++;
            }
    fprintf(stderr, "[precompile] wrote %d variants flags 0x%X\n", wrote, flags);
    return wrote == 16 ? 0 : 1;
}
