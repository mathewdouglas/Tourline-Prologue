/* Exercise the actual runtime pack-index helper, extracted by race_pack_order.py. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint64_t u64;
typedef uint32_t u32;
#define PSO_RACE_SEEN 4
/* Non-hash bytes must follow their item through the ordering operation. */
typedef struct { u64 hash; unsigned payload; } PsoPackItem;
static u64 pso_hash_bytes(u64 h, const void* bytes, size_t n) {
    const unsigned char* p = (const unsigned char*)bytes;
    while (n--) { h ^= *p++; h *= 1099511628211ull; }
    return h;
}
#include "race_pack_order_impl.h"
static u64 checksum(const PsoPackItem* p, u32 n) {
    u64 h = 1469598103934665603ull;
    for (u32 i=0; i<n; ++i) h=pso_hash_bytes(h,&p[i].hash,sizeof(u64));
    return h;
}
int main(void) {
    const PsoPackItem original[] = {{30,300},{10,100},{20,200}};
    const u64 same[] = {30,10,20}, reordered[] = {20,30,10};
    const u64 changed[] = {20,30,40}, duplicate[] = {20,20,30};
    PsoPackItem items[3]; u64 hash=checksum(original,3);
    memcpy(items,original,sizeof items);
    assert(pso_pack_match_and_order(items,3,same,hash));
    assert(items[0].payload==300 && items[1].payload==100 && items[2].payload==200);
    memcpy(items,original,sizeof items);
    assert(pso_pack_match_and_order(items,3,reordered,hash));
    assert(items[0].hash==20 && items[0].payload==200 && items[1].payload==300 && items[2].payload==100);
    memcpy(items,original,sizeof items); assert(!pso_pack_match_and_order(items,3,changed,hash));
    memcpy(items,original,sizeof items); assert(!pso_pack_match_and_order(items,3,duplicate,hash));
    memcpy(items,original,sizeof items); assert(!pso_pack_match_and_order(items,3,same,hash^1));
    memcpy(items,original,sizeof items); items[2]=items[1];
    assert(!pso_pack_match_and_order(items,3,same,checksum(items,3)));
    memcpy(items,original,sizeof items); items[0].hash=0;
    assert(!pso_pack_match_and_order(items,3,same,checksum(items,3)));
    assert(!pso_pack_match_and_order(items,0,same,hash));
    assert(!pso_pack_match_and_order(items,PSO_RACE_SEEN+1,same,hash));
    assert(!pso_pack_match_and_order(NULL,3,same,hash));
    assert(!pso_pack_match_and_order(items,3,NULL,hash));
    puts("Native pack membership, priority reordering, payload preservation and rejection checks passed");
    return 0;
}
