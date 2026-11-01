/* Fixed-width byte rotations. All per-game parameters come from the user's ELF. */
#include <stddef.h>
#include <stdint.h>

__declspec(dllexport) uint32_t gt5p_volume_abi(void) { return 1; }

__declspec(dllexport) void gt5p_volume_xor(unsigned char* data, size_t size,
                                         const uint32_t* initial, uint64_t offset) {
    const unsigned widths[4] = {17, 19, 23, 29};
    uint32_t state[4];
    for (unsigned j = 0; j < 4; ++j) {
        unsigned width = widths[j], shift = (unsigned)((offset % width) * 8 % width);
        uint32_t mask = (UINT32_C(1) << width) - 1;
        state[j] = initial[j] & mask;
        if (shift) state[j] = ((state[j] >> shift) | (state[j] << (width - shift))) & mask;
    }
    for (size_t i = 0; i < size; ++i) {
        data[i] ^= (unsigned char)(state[0] ^ state[1] ^ state[2] ^ state[3]);
        for (unsigned j = 0; j < 4; ++j)
            state[j] = (state[j] >> 8) | ((state[j] & 255) << (widths[j] - 8));
    }
}
