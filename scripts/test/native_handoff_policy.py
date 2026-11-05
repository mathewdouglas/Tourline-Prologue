"""Compile the actual offline header with synthetic loaders; no GPU/game assets.

Run under isolated_validation.ps1 in an x64 VS environment. Test code/build
outputs live in a TemporaryDirectory and are removed; only JSON evidence remains.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if os.environ.get('VSCMD_ARG_TGT_ARCH','').lower()!='x64':raise ValueError('Use x64 VS environment')
    patch=(ROOT/'patches/ps3recomp-4e8f3ca8-local.patch').read_text(encoding='utf-8')
    section=patch.split('diff --git a/libs/video/rsx_offline_batch.h b/libs/video/rsx_offline_batch.h\n',1)[1]
    header='\n'.join(line[1:] for line in section.splitlines() if line.startswith('+') and not line.startswith('+++'))+'\n'
    with tempfile.TemporaryDirectory(prefix='p210-policy-',dir=ROOT/'scratch') as directory:
        work=Path(directory);(work/'offline.h').write_bytes(header.encode())
        (work/'test.c').write_text(r'''
#include <windows.h>
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef uint64_t u64;typedef uint32_t u32;
#define PSO_WARM_CODE_MAX (4u*1024u*1024u)
static u64 pso_hash_bytes(u64 hash,const void* ptr,size_t n) {
    const unsigned char* p=(const unsigned char*)ptr;
    for(size_t i=0;i<n;i++){hash^=p[i];hash*=1099511628211ull;}return hash;
}
typedef struct { unsigned char data[2760]; } PsoWarmRecipe;
static int pso_warm_recipe_valid(const PsoWarmRecipe* r){return r->data[0]==42;}
static unsigned loaded,freed,ticks;
static void* pso_warm_read_code(const char* dir,u64 hash,u32 bytes) {
    (void)dir;loaded++;if(hash==99)return NULL;return calloc(1,bytes);
}
static void tracked_free(void* p){if(p)freed++;free(p);}
static BOOL fake_counter(LARGE_INTEGER* value){ticks++;value->QuadPart=1000000;return TRUE;}
static BOOL fake_frequency(LARGE_INTEGER* value){value->QuadPart=1000000;return TRUE;}
#define free tracked_free
#define QueryPerformanceCounter fake_counter
#define QueryPerformanceFrequency fake_frequency
#include "offline.h"
#undef free
int main(void) {
    assert(pso_offline_clock()==0 && ticks==0);
    s_offline.active=1;s_offline.shared="pool";
    int owned=1;void* a=pso_offline_code("legacy",1,8,&owned);
    assert(a && !owned && loaded==1 && s_offline.codes==1 && s_offline.bytes==8);
    void* b=pso_offline_code("legacy",1,8,&owned);
    assert(a==b && !owned && loaded==1 && s_offline.hits==1);
    assert(!pso_offline_code("legacy",1,9,&owned) && loaded==1);
    assert(!pso_offline_code("legacy",99,8,&owned) && owned && s_offline.codes==1);
    s_offline.bytes=PSO_OFFLINE_CODE_BYTES;
    b=pso_offline_code("legacy",2,8,&owned);
    assert(b && owned && s_offline.codes==1 && s_offline.bytes==PSO_OFFLINE_CODE_BYTES);tracked_free(b);
    s_offline.codes=PSO_OFFLINE_CODE_SLOTS;
    b=pso_offline_code("legacy",3,8,&owned);
    assert(b && owned && s_offline.codes==PSO_OFFLINE_CODE_SLOTS);tracked_free(b);
    pso_offline_clear();assert(freed==3 && !s_offline.codes && !s_offline.bytes);
    s_offline.shared="ignored-outside-offline";
    b=pso_offline_code("legacy",1,8,&owned);assert(b && owned && !s_offline.codes);tracked_free(b);
    assert(pso_offline_clock()==0 && ticks==0);
    s_offline.profile=1;assert(pso_offline_clock()==1000000 && ticks==1);pso_offline_clear();
    char names[2][65];memset(names[0],'a',64);memset(names[1],'b',64);names[0][64]=names[1][64]=0;
    unsigned char header[16]="GT5PPRQ2";u32 rows=2,size=2760;
    memcpy(header+8,&rows,4);memcpy(header+12,&size,4);
    FILE* f=fopen("requests.bin","wb");assert(f);fwrite(header,1,16,f);
    PsoWarmRecipe recipe={0};recipe.data[0]=42;
    for(unsigned i=0;i<2;i++){fwrite(names[i],1,64,f);fwrite(&recipe,1,sizeof recipe,f);}fclose(f);
    assert(!pso_offline_requests("requests.bin",names,0));
    assert(!pso_offline_requests("requests.bin",names,4097));
    assert(pso_offline_requests("requests.bin",names,2) && s_offline.requests);pso_offline_clear();
    names[0][0]='f';assert(!pso_offline_requests("requests.bin",names,2) && !s_offline.requests);
    names[0][0]='a';f=fopen("requests.bin","ab");fputc(0,f);fclose(f);
    assert(!pso_offline_requests("requests.bin",names,2) && !s_offline.requests);
    unsigned char data[16+16+8]={0};memcpy(data,"GT5PCOD1",8);
    u32 one=1,eight=8,at=32;u64 hash=pso_hash_bytes(1469598103934665603ull,"DXBCtest",8);
    memcpy(data+8,&one,4);memcpy(data+12,&eight,4);memcpy(data+16,&hash,8);
    memcpy(data+24,&eight,4);memcpy(data+28,&at,4);memcpy(data+32,"DXBCtest",8);
    f=fopen("code.bin","wb");fwrite(data,1,sizeof data,f);fclose(f);
    s_offline.active=1;s_offline.shared="pool";
    assert(pso_offline_code_bundle("code.bin") && s_offline.arena && s_offline.codes==1);
    b=pso_offline_code("unused",hash,8,&owned);assert(b&&!owned&&!memcmp(b,"DXBCtest",8));
    assert(!pso_offline_code("unused",hash+1,8,&owned));
    assert(!pso_offline_code_persisted("pool",hash,8,0));
    pso_offline_code_persisted("pool",hash,8,1);assert(pso_offline_code_persisted("pool",hash,8,0));
    assert(pso_offline_code_persisted("POOL",hash,8,0));
    assert(!pso_offline_code_persisted("other",hash,8,0));pso_offline_clear();
    for(int damage=0;damage<4;damage++) {
        unsigned char broken[sizeof data];memcpy(broken,data,sizeof data);
        if(damage==0)broken[39]^=1;
        if(damage==1)broken[28]=33;
        if(damage==2)memset(broken+12,255,4);
        f=fopen("code.bin","wb");fwrite(broken,1,sizeof broken-(damage==3),f);fclose(f);
        s_offline.active=1;s_offline.shared="pool";
        assert(!pso_offline_code_bundle("code.bin")&&!s_offline.arena&&!s_offline.codes);pso_offline_clear();
    }
    puts("native bounded cache, uncached fallback, default-off clock and bundle guards passed");return 0;
}
''')
        subprocess.run(['C:/Program Files/LLVM/bin/clang-cl.exe','/nologo','/O2','/MT',
            '/Fo'+str(work/'test.obj'),'/Fe'+str(work/'test.exe'),str(work/'test.c'),'/link','kernel32.lib'],cwd=work,check=True)
        subprocess.run([str(work/'test.exe')],cwd=work,check=True)
    assert not work.exists()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(dict(passed=True,private_build_removed=True,
        code_cache_bytes=128*1024*1024,code_slots=8192,request_chunk_records=4096,
        default_off_clock=True,cache_hit_conflict_budget_and_slot_fallback=True,
        limitation='Actual header with synthetic code loader/recipe validator; real native rejection is a separate proof.'),indent=2)+'\n')


if __name__=='__main__':main()
