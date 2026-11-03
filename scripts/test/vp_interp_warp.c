/* Original synthetic NV40 programs, compared against our decompiler on WARP.
 * Compute wrappers call the real vertex bodies and compare all 14 outputs.
 * No captured program or generated decompiler source is written to disk. */
#define WIN32_LEAN_AND_MEAN
#define CINTERFACE
#define COBJMACROS
#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "rsx_vp_decompiler.h"
#define RSX_VP_INTERP_EMBED_HLSL
#include "rsx_vp_interp.h"

#define CHECK(x) do { HRESULT hr_ = (x); if (FAILED(hr_)) { fprintf(stderr,"line %d hr=%08lx\n", __LINE__, (unsigned long)hr_); exit(2); } } while(0)
static ID3D11Device *dev;
static ID3D11DeviceContext *ctx;
static ID3D11Buffer *readback, *output;
static ID3D11UnorderedAccessView *uav;

static ID3D11Buffer *buffer(const void *p, UINT bytes, UINT bind, UINT misc)
{
    ID3D11Buffer *b = NULL;
    D3D11_BUFFER_DESC d = {0}; D3D11_SUBRESOURCE_DATA data = {0};
    d.ByteWidth=bytes; d.Usage=D3D11_USAGE_DEFAULT; d.BindFlags=bind; d.MiscFlags=misc;
    data.pSysMem=p;
    CHECK(dev->lpVtbl->CreateBuffer(dev,&d,p?&data:NULL,&b));
    return b;
}
static ID3D11ShaderResourceView *raw(const void *p, UINT n)
{
    ID3D11Buffer *b=buffer(p,n,D3D11_BIND_SHADER_RESOURCE,D3D11_RESOURCE_MISC_BUFFER_ALLOW_RAW_VIEWS);
    D3D11_SHADER_RESOURCE_VIEW_DESC d={0}; ID3D11ShaderResourceView *v=NULL;
    d.Format=DXGI_FORMAT_R32_TYPELESS; d.ViewDimension=D3D11_SRV_DIMENSION_BUFFEREX;
    d.BufferEx.NumElements=n/4; d.BufferEx.Flags=D3D11_BUFFEREX_SRV_FLAG_RAW;
    CHECK(dev->lpVtbl->CreateShaderResourceView(dev,(ID3D11Resource*)b,&d,&v));
    b->lpVtbl->Release(b); return v;
}
static const char *tail =
    "\nRWByteAddressBuffer result:register(u0);\n"
    "[numthreads(1,1,1)] void test(uint3 tid:SV_DispatchThreadID) { VSInput i;\n"
    "#if RSX_VP_INTERP_FETCH\n i.vid=tid.x;\n#else\n"
    "i.a0=float4(-0.75,0.25,0.5,1); i.a1=float4(0.5,-0.25,0.75,1);\n"
    "i.a2=i.a0; i.a3=i.a1; i.a4=i.a0; i.a5=i.a1; i.a6=i.a0; i.a7=i.a1;\n"
    "i.a8=i.a0; i.a9=i.a1; i.a10=i.a0; i.a11=i.a1; i.a12=i.a0; i.a13=i.a1; i.a14=i.a0; i.a15=i.a1;\n#endif\n"
    "VSOutput o=main(i); uint at=tid.x*224;\n"
    "result.Store4(at,asuint(o.pos)); result.Store4(at+16,asuint(o.col0)); result.Store4(at+32,asuint(o.col1)); result.Store4(at+48,asuint(o.fog));\n"
    "result.Store4(at+64,asuint(o.t0)); result.Store4(at+80,asuint(o.t1)); result.Store4(at+96,asuint(o.t2)); result.Store4(at+112,asuint(o.t3));\n"
    "result.Store4(at+128,asuint(o.t4)); result.Store4(at+144,asuint(o.t5)); result.Store4(at+160,asuint(o.t6)); result.Store4(at+176,asuint(o.t7));\n"
    "result.Store4(at+192,asuint(o.t8)); result.Store4(at+208,asuint(o.t9)); }\n";

static ID3D11ComputeShader *compile(const char *body, int fetch)
{
    static char src[400000]; ID3DBlob *b=NULL,*e=NULL; ID3D11ComputeShader *s=NULL;
    snprintf(src,sizeof src,"#define RSX_VP_INTERP_FETCH %d\n%s\n%s",fetch,body,tail);
    HRESULT hr=D3DCompile(src,strlen(src),"vp-warp",NULL,NULL,"test","cs_5_0",0,0,&b,&e);
    if (FAILED(hr)) { fprintf(stderr,"compile: %s\n",e?(char*)e->lpVtbl->GetBufferPointer(e):"failed"); exit(2); }
    if(e)e->lpVtbl->Release(e);
    CHECK(dev->lpVtbl->CreateComputeShader(dev,b->lpVtbl->GetBufferPointer(b),b->lpVtbl->GetBufferSize(b),NULL,&s));
    b->lpVtbl->Release(b); return s;
}
static void run(ID3D11ComputeShader *s, float *out)
{
    D3D11_MAPPED_SUBRESOURCE m;
    ctx->lpVtbl->CSSetShader(ctx,s,NULL,0);
    ctx->lpVtbl->CSSetUnorderedAccessViews(ctx,0,1,&uav,NULL);
    ctx->lpVtbl->Dispatch(ctx,4,1,1);
    ID3D11UnorderedAccessView *none=NULL;
    ctx->lpVtbl->CSSetUnorderedAccessViews(ctx,0,1,&none,NULL);
    ctx->lpVtbl->CopyResource(ctx,(ID3D11Resource*)readback,(ID3D11Resource*)output);
    CHECK(ctx->lpVtbl->Map(ctx,(ID3D11Resource*)readback,0,D3D11_MAP_READ,0,&m));
    memcpy(out,m.pData,4*224);
    ctx->lpVtbl->Unmap(ctx,(ID3D11Resource*)readback,0);
}
/* All sources use identity swizzle; input src0, constant src1, temp0 src2. */
static void ins(unsigned *w,unsigned v,unsigned s,unsigned dst,unsigned input,unsigned constant,int end)
{
    unsigned a=2u|0x1B00u, b=3u|0x1B00u, c=1u|0x1B00u;
    w[0]=(1u<<30)|(63u<<15)|(7u<<10);
    w[1]=(s<<27)|(v<<22)|(constant<<12)|(input<<8)|(a>>9);
    w[2]=((a&511u)<<23)|(b<<6)|(c>>11);
    w[3]=((c&2047u)<<21)|(15u<<13)|(63u<<7)|(dst<<2)|(end?1u:0u);
    if(s) { w[0]&=~(1u<<30); w[3]=(w[3]&~(15u<<13))|(15u<<17); }
}

int main(int argc, char **argv)
{
    D3D_FEATURE_LEVEL fl;
    CHECK(D3D11CreateDevice(NULL,D3D_DRIVER_TYPE_WARP,NULL,0,NULL,0,D3D11_SDK_VERSION,&dev,&fl,&ctx));
    output=buffer(NULL,4*224,D3D11_BIND_UNORDERED_ACCESS,D3D11_RESOURCE_MISC_BUFFER_ALLOW_RAW_VIEWS);
    D3D11_UNORDERED_ACCESS_VIEW_DESC ud={0}; ud.Format=DXGI_FORMAT_R32_TYPELESS;
    ud.ViewDimension=D3D11_UAV_DIMENSION_BUFFER; ud.Buffer.NumElements=4*224/4; ud.Buffer.Flags=D3D11_BUFFER_UAV_FLAG_RAW;
    CHECK(dev->lpVtbl->CreateUnorderedAccessView(dev,(ID3D11Resource*)output,&ud,&uav));
    D3D11_BUFFER_DESC rd={0}; rd.ByteWidth=4*224; rd.Usage=D3D11_USAGE_STAGING; rd.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
    CHECK(dev->lpVtbl->CreateBuffer(dev,&rd,NULL,&readback));
    float constants[514][4];
    for(int i=0;i<514;i++)for(int c=0;c<4;c++)constants[i][c]=(float)((i*3+c)%17+1)/16.0f;
    for(int c=0;c<4;c++){constants[512][c]=1;constants[513][c]=0;}
    ID3D11Buffer *cb=buffer(constants,sizeof constants,D3D11_BIND_CONSTANT_BUFFER,0);
    ctx->lpVtbl->CSSetConstantBuffers(ctx,0,1,&cb);
    unsigned desc[128]={0}, bytes[256];
    for(int i=0;i<256;i++)bytes[i]=_byteswap_ulong(0x3F000000u+(i%4)*0x80000u);
    for(int i=0;i<16;i++){desc[4*i]=i*16;desc[4*i+1]=0;desc[4*i+2]=0x142;}
    ID3D11Buffer *vf=buffer(desc,sizeof desc,D3D11_BIND_CONSTANT_BUFFER,0);
    ctx->lpVtbl->CSSetConstantBuffers(ctx,2,1,&vf);
    ID3D11ShaderResourceView *vb=raw(bytes,sizeof bytes);
    ctx->lpVtbl->CSSetShaderResources(ctx,20,1,&vb);
    int pass=0,fail=0; float worst=0;
    for(int fetch=0;fetch<2;fetch++) {
        ID3D11ComputeShader *interp=compile(rsx_vp_interp_hlsl,fetch);
        for(unsigned test=0;test<54;test++) {
            unsigned image[64]={0},*w=image+16;
            image[0]=64;image[1]=3;image[5]=0xFFFF;
            /* Initialize temp0 before scalar/ADD/MAD operations. */
            ins(w,1,0,1,0,0,0); w[0]=(w[0]&~(63u<<15));
            unsigned op=test<22?test+1:1, sca=test<22?0:test-21;
            if(op==0x0D)op=0x19;
            if(sca>=8)sca+=5;
            ins(w+4,op,sca,1,1,3,0);
            ins(w+8,1,0,0,0,0,1);
            if(test>=33 && test<42) {
                ins(w+4,1,0,1,1,3,0);
                for(int i=0;i<16;i++) {
                    desc[4*i]=i*16+(test==41?1:0);
                    desc[4*i+2]=test==40?0:0x140u+((test-33)%7+1);
                }
                ctx->lpVtbl->UpdateSubresource(ctx,(ID3D11Resource*)vf,0,NULL,desc,0,0);
            } else {
                for(int i=0;i<16;i++){desc[4*i]=i*16;desc[4*i+2]=0x142;}
                ctx->lpVtbl->UpdateSubresource(ctx,(ID3D11Resource*)vf,0,NULL,desc,0,0);
            }
            if(test>=42 && test<49) {
                /* Predication against initially-zero condition codes. */
                ins(w+4,1,0,1,1,3,0);
                w[4]=(w[4]&~(7u<<10))|((test-42)<<10)|(1u<<13);
            }
            if(test>=49) {
                /* Branch over a different colour write, including boolean
                 * taken/not-taken and one call/return. */
                unsigned flow=test==49?8:test==50?9:test==51?17:test==52?18:10;
                image[1]=flow==10 || flow==18 ? 7:5;
                ins(w+4,1,0,1,1,3,0);
                ins(w+8,0,flow,0,0,0,0);
                w[10]&=~63u;
                w[11]=(w[11]&~((15u<<17)|(7u<<29)))|(4u<<29); /* target slot 4 */
                ins(w+12,1,0,0,0,0,0);
                ins(w+16,1,0,1,0,0,flow==10 || flow==18?0:1);
                if(image[1]==7) {
                    ins(w+12,0,9,0,0,0,0); w[14]&=~63u;
                    w[15]=(w[15]&~((15u<<17)|(7u<<29)))|(6u<<29);
                    ins(w+20,0,12,0,0,0,0); w[23]&=~(15u<<17);
                    ins(w+24,1,0,0,0,0,1);
                }
            }
            ID3D11ShaderResourceView *prog=raw(image,sizeof image);
            ctx->lpVtbl->CSSetShaderResources(ctx,21,1,&prog);
            unsigned head[4]={0}; ID3D11Buffer *hb=buffer(head,sizeof head,D3D11_BIND_CONSTANT_BUFFER,0);
            ctx->lpVtbl->CSSetConstantBuffers(ctx,4,1,&hb);
            static char hlsl[300000];
            int n=fetch?rsx_vp_decompile_gpufetch((u8*)w,image[1]*16,hlsl,sizeof hlsl):rsx_vp_decompile((u8*)w,image[1]*16,hlsl,sizeof hlsl);
            if(n<0)return 2;
            ID3D11ComputeShader *spec=compile(hlsl,fetch);
            float a[224],b[224];run(spec,a);run(interp,b);
            int bad=0;
            for(int i=0;i<224;i++) {
                float e=fabsf(a[i]-b[i]);
                if(isnan(a[i])&&isnan(b[i]))continue;
                if(a[i]==b[i])continue;
                if(!isfinite(e)||e>0.0001f*fmaxf(1,fabsf(a[i])))bad=1;
                if(e>worst)worst=e;
            }
            if(bad){fail++;fprintf(stderr,"FAIL fetch=%d test=%u vec=%u sca=%u\n",fetch,test,op,sca);}else pass++;
            spec->lpVtbl->Release(spec); prog->lpVtbl->Release(prog); hb->lpVtbl->Release(hb);
        }
        if(argc>1) {
            char pattern[1024],path[1024]; WIN32_FIND_DATAA fd;
            snprintf(pattern,sizeof pattern,"%s/*.vp",argv[1]);
            HANDLE find=FindFirstFileA(pattern,&fd);
            if(find==INVALID_HANDLE_VALUE)return 2;
            unsigned tested=0;
            do {
                unsigned image[16+544*4]={0};
                snprintf(path,sizeof path,"%s/%s",argv[1],fd.cFileName);
                FILE *f=fopen(path,"rb"); if(!f)return 2;
                size_t bytes=fread(image+16,1,544*16,f); int extra=fgetc(f); fclose(f);
                if(extra!=EOF||!bytes||bytes%16)return 2;
                unsigned nins=rsx_vp_program_size_instrs((u8*)(image+16),(u32)bytes);
                if(!nins)return 2;
                image[0]=64;image[1]=nins;image[5]=0xFFFF;
                ID3D11ShaderResourceView *prog=raw(image,sizeof image);
                ctx->lpVtbl->CSSetShaderResources(ctx,21,1,&prog);
                unsigned head[4]={0}; ID3D11Buffer *hb=buffer(head,sizeof head,D3D11_BIND_CONSTANT_BUFFER,0);
                ctx->lpVtbl->CSSetConstantBuffers(ctx,4,1,&hb);
                static char hlsl[300000];
                int n=fetch?rsx_vp_decompile_gpufetch((u8*)(image+16),nins*16,hlsl,sizeof hlsl)
                           :rsx_vp_decompile((u8*)(image+16),nins*16,hlsl,sizeof hlsl);
                if(n<0)return 2;
                ID3D11ComputeShader *spec=compile(hlsl,fetch);
                float a[224],b[224];run(spec,a);run(interp,b);
                int bad=0;
                for(int i=0;i<224;i++) {
                    float e=fabsf(a[i]-b[i]);
                    if((isnan(a[i])&&isnan(b[i]))||a[i]==b[i])continue;
                    if(!isfinite(e)||e>0.0001f*fmaxf(1,fabsf(a[i])))bad=1;
                    if(e>worst)worst=e;
                }
                if(bad){fail++;fprintf(stderr,"FAIL catalogue fetch=%d file=%s\n",fetch,fd.cFileName);}else pass++;
                spec->lpVtbl->Release(spec); prog->lpVtbl->Release(prog); hb->lpVtbl->Release(hb);
                if(++tested%50==0)fprintf(stderr,"catalogue fetch=%d tested=%u fail=%d\n",fetch,tested,fail);
            } while(FindNextFileA(find,&fd));
            FindClose(find);
            fprintf(stderr,"catalogue fetch=%d tested=%u\n",fetch,tested);
        }
        interp->lpVtbl->Release(interp);
    }
    fprintf(stderr,"vertex WARP pass=%d fail=%d worst=%.9g (IA + GPU fetch, all outputs)\n",pass,fail,worst);
    return fail?1:0;
}
