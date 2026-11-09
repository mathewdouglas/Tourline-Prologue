/* Boot opening movie: link game.skip_movie to the game's own flag.

 * The boot movie starts in phase 9 of boot.ad when opening_after_autoload is
 * truthy, the TV content exists, and the "top" stage is not already prepared.
 * 1 plays, 0 skips. Misc > Other > Opening Movie is that flag (index 0 plays).
 * The Demo page's visible_demo_opening checkbox skips only the attract movie.
 *
 * mAttributeEval, mAttributePush, and mAssignPop are reached only through
 * bctrl, so host wrappers registered after ppu_recomp_register see them.
 * The instruction's symbol vector is at this+8 (begin at +12, end at +16).
 * The last symbol is a long string: capacity at +0x1C, characters at +8, or a
 * heap pointer there when the capacity is above 15.
 *
 * The script's read is ATTRIBUTE_EVAL. Its result is an hByte; the value is
 * the byte at object+0x14 (a word store would land in the wrong byte). Every
 * eval result is overwritten with the live setting. The script writes with
 * ATTRIBUTE_PUSH then ASSIGN_POP. Push leaves the parent on the stack, not the
 * value, so the value is rewritten on the assign that follows that push.
 * Assigns before the first eval are the initial value and boot's force-to-1,
 * and are forced back to the setting. Assigns after that are the in-game
 * option and update the file. GT5P_NATIVE_OPENING=0 does not install wrappers.
 *
 * Addresses are execute() in this title's EMAIN.ELF (RTTI slot 20). A re-lift
 * moves them.
 */
#include "gt5p_settings.h"

#include "ppu_context.h"

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>

extern "C" {
typedef struct { uint64_t addr; void (*func)(ppu_context*); const char* name; } gt5p_func_entry;
extern const gt5p_func_entry function_table[];
extern const uint64_t function_table_count;
void ppu_register_function(uint64_t addr, void (*fn)(ppu_context*));
uint32_t vm_read32(uint64_t addr);
void vm_write32(uint64_t addr, uint32_t val);
uint8_t vm_read8(uint64_t addr);
void vm_write8(uint64_t addr, uint8_t val);
}

namespace {

constexpr uint32_t kEval = 0x00988210u;
constexpr uint32_t kPush = 0x0099C440u;
constexpr uint32_t kAssign = 0x0097F0C0u;
constexpr uint32_t kHintA = 0x010E1CF4u;
constexpr uint32_t kHintB = 0x01247100u;
constexpr uint32_t kHByte = 0x01262898u;
const char kName[] = "opening_after_autoload";

void (*g_eval)(ppu_context*) = nullptr;
void (*g_push)(ppu_context*) = nullptr;
void (*g_assign)(ppu_context*) = nullptr;
std::atomic<int> g_seen{0};
std::atomic<uint32_t> g_hit[8];
thread_local int g_depth = 0;
thread_local int g_opening_push = 0;

bool guest_ptr(uint32_t p)
{
    return p >= 0x10000u && p < 0xF0000000u;
}

void (*lookup(uint32_t guest))(ppu_context*)
{
    uint64_t lo = 0, hi = function_table_count;
    while (lo < hi) {
        uint64_t mid = lo + (hi - lo) / 2;
        uint32_t a = (uint32_t)function_table[mid].addr;
        if (a == guest) return function_table[mid].func;
        if (a < guest) lo = mid + 1; else hi = mid;
    }
    return nullptr;
}

bool named(uint32_t sym)
{
    uint32_t cap = vm_read32(sym + 0x1C);
    uint32_t ptr;
    if (cap <= 15) ptr = sym + 8;
    else if (cap < 1000000u) {
        ptr = vm_read32(sym + 8);
        if (!guest_ptr(ptr)) return false;
    } else return false;
    char buf[32];
    for (int i = 0; i < (int)sizeof buf - 1; i++) {
        unsigned c = vm_read8((uint64_t)ptr + (uint32_t)i);
        buf[i] = (char)c;
        if (c == 0) return strcmp(buf, kName) == 0;
        if (c < 32 || c > 126) return false;
    }
    return false;
}

void remember(uint32_t sym)
{
    for (auto& slot : g_hit) {
        uint32_t cur = slot.load(std::memory_order_relaxed);
        if (cur == sym) return;
        if (cur == 0 && slot.compare_exchange_strong(cur, sym)) return;
    }
}

bool is_opening(uint32_t self)
{
    if (!guest_ptr(self)) return false;
    uint32_t begin = vm_read32(self + 12);
    uint32_t end = vm_read32(self + 16);
    if (!guest_ptr(end) || end < begin + 4 || end - begin > 64 || (end & 3)) return false;
    uint32_t sym = vm_read32(end - 4);
    if (!guest_ptr(sym)) return false;
    thread_local uint32_t hit = 0, miss = 0;
    if (sym == hit) return true;
    if (sym == miss) return false;
    for (auto& slot : g_hit)
        if (slot.load(std::memory_order_relaxed) == sym) { hit = sym; return true; }
    if (!named(sym)) { miss = sym; return false; }
    hit = sym;
    remember(sym);
    return true;
}

uint32_t frame_of(ppu_context* ctx)
{
    uint32_t vm = (uint32_t)ctx->gpr[4];
    if (!guest_ptr(vm)) return 0;
    uint32_t frame = vm_read32(vm + 0x40);
    return guest_ptr(frame) ? frame : 0;
}

uint32_t top_index(uint32_t frame)
{
    if (!frame) return 0;
    uint32_t top = vm_read32(frame + 0x24);
    return top > 0 && top <= 65536u ? top : 0;
}

bool object_at_index(uint32_t frame, uint32_t index, uint32_t* obj)
{
    if (!frame) return false;
    uint32_t base = vm_read32(frame + 4);
    if (!guest_ptr(base)) return false;
    uint32_t slot = base + index * 4;
    if (slot < base || !guest_ptr(slot)) return false;
    uint32_t o = vm_read32(slot);
    if (!guest_ptr(o) || !guest_ptr(o + 0x14)) return false;
    *obj = o;
    return true;
}

/* hInt is a big-endian word at +0x14. hByte is one byte there; a word store
 * would write the other end of that word. */
enum class Width : int { None = 0, Word = 1, Byte = 2 };

struct Num { Width width; uint32_t value; };

Num read_num(uint32_t obj)
{
    uint32_t vt = vm_read32(obj);
    if (vt == kHintA || vt == kHintB)
        return {Width::Word, vm_read32(obj + 0x14)};
    if (vt == kHByte)
        return {Width::Byte, vm_read8((uint64_t)obj + 0x14)};
    return {Width::None, 0};
}

void write_num(uint32_t obj, Width width, uint32_t value)
{
    if (width == Width::Word) vm_write32(obj + 0x14, value);
    else if (width == Width::Byte) vm_write8((uint64_t)obj + 0x14, (uint8_t)value);
}

uint32_t desired()
{
    return gt5p_skip_movie_now() ? 0u : 1u;
}

void note(const char* op, int before, int after, uint32_t frame, uint32_t top, uint32_t obj)
{
    static std::atomic<int> seq{0};
    static int trace = -1;
    if (trace < 0) {
        const char* e = getenv("GT5P_OPENING_TRACE");
        trace = e && e[0] == '1';
    }
    int i = seq.fetch_add(1, std::memory_order_relaxed);
    if (i >= 12 && !(trace && i < 48)) return;
    uint32_t vt = obj ? vm_read32(obj) : 0;
    uint32_t w14 = obj ? vm_read32(obj + 0x14) : 0;
    printf("[opening] %s #%d %d -> %d skip=%d frame=%08X top=%u obj=%08X vt=%08X w14=%08X\n",
           op, i, before, after, gt5p_skip_movie_now() ? 1 : 0, frame, top, obj, vt, w14);
}

void hook_push(ppu_context* ctx)
{
    if (g_depth || !is_opening((uint32_t)ctx->gpr[3])) { g_push(ctx); return; }
    uint32_t frame = frame_of(ctx);
    uint32_t top = top_index(frame);
    uint32_t obj = 0;
    if (top) object_at_index(frame, top - 1, &obj);
    note("push", -1, -1, frame, top, obj);
    g_depth++;
    g_push(ctx);
    g_depth--;
    /* The value sits under this attribute. The next ASSIGN_POP writes it. */
    g_opening_push = 1;
}

void hook_assign(ppu_context* ctx)
{
    if (!g_opening_push) { g_assign(ctx); return; }
    g_opening_push = 0;
    if (g_depth) { g_assign(ctx); return; }
    uint32_t frame = frame_of(ctx);
    uint32_t top = top_index(frame);
    uint32_t obj = 0;
    Num num{Width::None, 0};
    if (top >= 2 && object_at_index(frame, top - 2, &obj)) num = read_num(obj);
    int before = num.width == Width::None ? -1 : (int)num.value;
    int after = before;
    bool early = g_seen.load(std::memory_order_acquire) == 0;
    if (early && num.width != Width::None) {
        after = (int)desired();
        write_num(obj, num.width, (uint32_t)after);
    } else if (!early && num.width != Width::None && num.value <= 1u) {
        gt5p_skip_movie_from_game(num.value == 0u);
        after = (int)num.value;
    }
    note(early ? "assign" : "assign-menu", before, after, frame, top, obj);
    g_depth++;
    g_assign(ctx);
    g_depth--;
}

void hook_eval(ppu_context* ctx)
{
    if (g_depth || !is_opening((uint32_t)ctx->gpr[3])) { g_eval(ctx); return; }
    uint32_t frame = frame_of(ctx);
    g_depth++;
    g_eval(ctx);
    g_depth--;
    g_seen.store(1, std::memory_order_release);
    uint32_t top = top_index(frame);
    uint32_t obj = 0;
    Num num{Width::None, 0};
    if (top && object_at_index(frame, top - 1, &obj)) num = read_num(obj);
    int before = num.width == Width::None ? -1 : (int)num.value;
    int after = before;
    if (num.width != Width::None) {
        after = (int)desired();
        write_num(obj, num.width, (uint32_t)after);
    }
    note("eval", before, after, frame, top, obj);
}

}  // namespace

void gt5p_opening_install()
{
    if (!gt5p_native_opening()) {
        printf("[opening] GT5P_NATIVE_OPENING=0: skip still presses Cross (PAD_SKIP_MOVIE)\n");
        return;
    }
    g_eval = lookup(kEval);
    g_push = lookup(kPush);
    g_assign = lookup(kAssign);
    if (!g_eval || !g_push) {
        fprintf(stderr, "[opening] attribute execute functions are not in this build; "
                        "the movie link is off and Cross is not pressed either\n");
        return;
    }
    ppu_register_function(kEval, hook_eval);
    ppu_register_function(kPush, hook_push);
    if (g_assign)
        ppu_register_function(kAssign, hook_assign);
    else
        fprintf(stderr, "[opening] assign is not in this build; in-game changes will not update the setting\n");
    printf("[opening] boot movie uses Opening Movie (skip=%d). GT5P_NATIVE_OPENING=0 presses Cross\n",
           gt5p_skip_movie_now() ? 1 : 0);
}
