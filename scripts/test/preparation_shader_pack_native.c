/* Exercise the existing production pack reader with verified prepared packs.
 * This creates no device, shader compiler, game process or pipeline queue. */
#define CINTERFACE
#define COBJMACROS
#include <windows.h>
#include <d3dcompiler.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint8_t u8;
#include "pack.inc"

static u64 hash_bytes(const void* data, size_t size) {
    const u8* p = data;
    u64 h = 1469598103934665603ull;
    for (size_t i = 0; i < size; i++) { h ^= p[i]; h *= 1099511628211ull; }
    return h;
}
int main(int argc, char** argv) {
    assert(argc == 3);
    assert(_putenv_s("RSX_SHADER_CACHE", argv[1]) == 0);
    if (!spack_on()) {
        spack_begin(0);
        assert(!s_spack_active && !s_spack_n);
        puts("PASS disabled pack reader");
        return 0;
    }
    FILE* f = fopen(argv[2], "rb");
    assert(f);
    unsigned counts[2] = {0};
    int scope, previous = -1;
    unsigned long long key, expected;
    unsigned bytes;
    ID3DBlob* retained = NULL;
    while (fscanf(f, "%d %llx %llx %u", &scope, &key, &expected, &bytes) == 4) {
        assert(scope == 0 || scope == 1);
        if (scope != previous) {
            spack_begin(scope);
            assert(s_spack_scope == scope && s_spack_active);
            if (retained) {  /* caller's AddRef survives scope release */
                assert(retained->lpVtbl->GetBufferSize(retained) > 0);
                retained->lpVtbl->Release(retained);
                retained = NULL;
            }
            previous = scope;
        }
        ID3DBlob* blob = NULL;
        assert(spack_get((u64)key, &blob) && blob);
        assert(blob->lpVtbl->GetBufferSize(blob) == bytes);
        assert(hash_bytes(blob->lpVtbl->GetBufferPointer(blob), bytes) == (u64)expected);
        if (!retained) { retained = blob; retained->lpVtbl->AddRef(retained); }
        blob->lpVtbl->Release(blob);
        counts[scope]++;
    }
    fclose(f);
    ID3DBlob* missing = NULL;
    assert(!spack_get(0x123456789abcdef0ull, &missing) && !missing);
    spack_end_ex(1);
    assert(!s_spack_active && !s_spack_n && !s_spack_bytes);
    if (retained) retained->lpVtbl->Release(retained);
    printf("PASS production pack lookups: menu=%u race=%u; bytecode identities, miss fallback and blob ownership\n", counts[0], counts[1]);
    return 0;
}
