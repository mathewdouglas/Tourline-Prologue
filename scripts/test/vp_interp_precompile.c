/* Write the two vertex-interpreter DXBC variants into a private cache.
 * The filename is shader_source_key from rsx_d3d12_backend.c: FNV-1a over the
 * exact source bytes, then the target string, then the flag word. The entry
 * name is not part of the key. Flags default to 0, matching
 * RSX_SHADER_INTERP_VP_OPT unset. Usage: vp_interp_precompile <cache-dir> [flags]
 */
#define WIN32_LEAN_AND_MEAN
#define CINTERFACE
#define COBJMACROS
#include <windows.h>
#include <d3dcompiler.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define RSX_VP_INTERP_EMBED_HLSL
#include "rsx_vp_interp.h"

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
    char src[131072];
    int fetch, wrote = 0;
    if (!dir || !dir[0]) {
        fprintf(stderr, "usage: vp_interp_precompile <cache-dir> [flags]\n");
        return 2;
    }
    if (argc > 2) flags = (unsigned)strtoul(argv[2], NULL, 0);
    if (!CreateDirectoryA(dir, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        fprintf(stderr, "cache dir %s: %lu\n", dir, GetLastError());
        return 1;
    }
    for (fetch = 0; fetch < 2; fetch++) {
        int n = rsx_vp_interp_variant_prefix(src, sizeof src, fetch);
        size_t hl = strlen(rsx_vp_interp_hlsl);
        ID3DBlob* blob = NULL;
        ID3DBlob* err = NULL;
        unsigned long long h;
        char path[1024];
        HRESULT hr;
        ULONGLONG t0;
        FILE* f;
        if (n < 0 || (size_t)n + hl + 1 > sizeof src) {
            fprintf(stderr, "source buffer overflow\n");
            return 1;
        }
        memcpy(src + n, rsx_vp_interp_hlsl, hl + 1);
        h = source_key(src, (size_t)n + hl, "vs_5_0", flags);
        snprintf(path, sizeof path, "%s/%016llx.dxbc", dir, h);
        t0 = GetTickCount64();
        hr = D3DCompile(src, (size_t)n + hl, "rsx_vp_interp", NULL, NULL,
                        "main", "vs_5_0", flags, 0, &blob, &err);
        fprintf(stderr, "[precompile-vp] fetch=%d hr=0x%08lx %llu ms %u bytes %s\n",
                fetch, (unsigned long)hr, (unsigned long long)(GetTickCount64() - t0),
                blob ? (unsigned)blob->lpVtbl->GetBufferSize(blob) : 0u, path);
        if (FAILED(hr) || !blob) {
            if (err) fprintf(stderr, "%s\n", (const char*)err->lpVtbl->GetBufferPointer(err));
            if (err) err->lpVtbl->Release(err);
            return 1;
        }
        if (err) err->lpVtbl->Release(err);
        f = fopen(path, "wb");
        if (!f) { fprintf(stderr, "open %s failed\n", path); return 1; }
        if (fwrite(blob->lpVtbl->GetBufferPointer(blob), 1, blob->lpVtbl->GetBufferSize(blob), f)
            != blob->lpVtbl->GetBufferSize(blob)) {
            fprintf(stderr, "short write %s\n", path);
            fclose(f);
            return 1;
        }
        fclose(f);
        blob->lpVtbl->Release(blob);
        wrote++;
    }
    fprintf(stderr, "[precompile-vp] wrote %d\n", wrote);
    return wrote == 2 ? 0 : 1;
}
