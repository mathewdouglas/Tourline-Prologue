/* Cache integrity only. Keep the renderer's deliberately nonstandard FNV seed. */
#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

EXPORT uint32_t gt5p_cache_hash_abi(void) { return 1; }

EXPORT uint64_t gt5p_cache_fnv64(const unsigned char* data, size_t size) {
    uint64_t value = UINT64_C(1469598103934665603);
    for (size_t i = 0; i < size; ++i)
        value = (value ^ data[i]) * UINT64_C(1099511628211);
    return value;
}
