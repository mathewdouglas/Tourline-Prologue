/* Offline WARP compare: interpreter pixel shader vs rsx_fp_decompile_buffered.
 * Catalogue bytecode is read only to classify and to draw. Results written by
 * the caller are counts and error magnitudes, never the programs. */
#define CINTERFACE
#define COBJMACROS
#define WIN32_LEAN_AND_MEAN
#define RSX_FP_INTERP_IMPLEMENTATION
#define RSX_FP_INTERP_EMBED_HLSL
#include <windows.h>
#include <initguid.h>
#include <d3d12.h>
#include <d3d12sdklayers.h>
#include <dxgi1_4.h>
#include <d3dcompiler.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "rsx_fp_interp.h"

#define RT 8
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #c); exit(1); } } while (0)

static void enable_d3d_debug(void)
{
    ID3D12Debug* dbg = NULL;
    HRESULT hr = D3D12GetDebugInterface(&IID_ID3D12Debug, (void**)&dbg);
    if (SUCCEEDED(hr) && dbg) {
        dbg->lpVtbl->EnableDebugLayer(dbg);
        dbg->lpVtbl->Release(dbg);
        fprintf(stderr, "d3d12 debug layer on\n");
    } else {
        fprintf(stderr, "d3d12 debug layer unavailable hr=0x%08lx\n", (unsigned long)hr);
    }
}

static void dump_d3d_queue(ID3D12Device* dev)
{
    ID3D12InfoQueue* q = NULL;
    UINT64 n, i, begin;
    if (FAILED(dev->lpVtbl->QueryInterface(dev, &IID_ID3D12InfoQueue, (void**)&q)) || !q) {
        fprintf(stderr, "no info queue\n");
        return;
    }
    n = q->lpVtbl->GetNumStoredMessages(q);
    begin = n > 12 ? n - 12 : 0;
    fprintf(stderr, "info messages %llu\n", (unsigned long long)n);
    for (i = begin; i < n; i++) {
        SIZE_T sz = 0;
        q->lpVtbl->GetMessage(q, i, NULL, &sz);
        if (!sz) continue;
        {
            D3D12_MESSAGE* m = (D3D12_MESSAGE*)malloc(sz);
            if (m && SUCCEEDED(q->lpVtbl->GetMessage(q, i, m, &sz)) && m->pDescription)
                fprintf(stderr, "D3D12[%llu]: %s\n", (unsigned long long)i, m->pDescription);
            free(m);
        }
    }
    q->lpVtbl->Release(q);
}

static void create_pso_or_die(ID3D12Device* dev, D3D12_GRAPHICS_PIPELINE_STATE_DESC* desc,
                              ID3D12PipelineState** out, const char* tag)
{
    HRESULT hr = dev->lpVtbl->CreateGraphicsPipelineState(dev, desc, &IID_ID3D12PipelineState, (void**)out);
    if (FAILED(hr)) {
        fprintf(stderr, "PSO %s hr=0x%08lx bytes=%llu\n", tag, (unsigned long)hr,
                (unsigned long long)desc->PS.BytecodeLength);
        dump_d3d_queue(dev);
        exit(1);
    }
}

static const char* WIDE_CB =
    "cbuffer PSConstants : register(b1) {\n"
    "    float4 rsx_texscale[4];\n"
    "    float4 rsx_alphatest;\n"
    "    float4 fp_constants[256];\n"
    "    float4 rsx_fogstate;\n"
    "    float4 rsx_texexpand[4];\n"
    "    float4 rsx_texscale_hi[6];\n"
    "};\n";

static const char* VS_HLSL =
    "struct VI {\n"
    "  float4 pos:POSITION; float4 col0:COLOR0; float4 col1:COLOR1; float4 fog:FOG;\n"
    "  float4 tc0:TEXCOORD0; float4 tc1:TEXCOORD1; float4 tc2:TEXCOORD2; float4 tc3:TEXCOORD3;\n"
    "  float4 tc4:TEXCOORD4; float4 tc5:TEXCOORD5; float4 tc6:TEXCOORD6; float4 tc7:TEXCOORD7;\n"
    "  float4 tc8:TEXCOORD8; float4 tc9:TEXCOORD9;\n"
    "};\n"
    "struct VO {\n"
    "  float4 pos:SV_Position; float4 col0:COLOR0; float4 col1:COLOR1; float4 fog:FOG;\n"
    "  float4 tc0:TEXCOORD0; float4 tc1:TEXCOORD1; float4 tc2:TEXCOORD2; float4 tc3:TEXCOORD3;\n"
    "  float4 tc4:TEXCOORD4; float4 tc5:TEXCOORD5; float4 tc6:TEXCOORD6; float4 tc7:TEXCOORD7;\n"
    "  float4 tc8:TEXCOORD8; float4 tc9:TEXCOORD9;\n"
    "};\n"
    "VO main(VI i){ VO o; o.pos=i.pos; o.col0=i.col0; o.col1=i.col1; o.fog=i.fog;\n"
    "  o.tc0=i.tc0; o.tc1=i.tc1; o.tc2=i.tc2; o.tc3=i.tc3; o.tc4=i.tc4;\n"
    "  o.tc5=i.tc5; o.tc6=i.tc6; o.tc7=i.tc7; o.tc8=i.tc8; o.tc9=i.tc9; return o; }\n";

static void put_guest(u8* p, u32 w)
{
    u32 be = (w << 16) | (w >> 16);
    p[0] = (u8)(be >> 24); p[1] = (u8)(be >> 16); p[2] = (u8)(be >> 8); p[3] = (u8)be;
}

static u32 fbits(float f) { u32 u; memcpy(&u, &f, 4); return u; }

static int patch_hlsl(char* hlsl, u32 cap)
{
    char* cb = strstr(hlsl, "cbuffer PSConstants");
    char* end;
    char* wp;
    if (!cb) return 0;
    end = strstr(cb, "};");
    if (!end) return 0;
    end += 2;
    if (*end == '\n') end++;
    {
        u32 head = (u32)(cb - hlsl);
        u32 tail = (u32)strlen(end);
        u32 wide = (u32)strlen(WIDE_CB);
        if (head + wide + tail + 1 > cap) return 0;
        memmove(cb + wide, end, tail + 1);
        memcpy(cb, WIDE_CB, wide);
    }
    wp = strstr(hlsl, "#define _rsx_wpos");
    if (wp) {
        char* nl = strchr(wp, '\n');
        const char* rep = "#define _rsx_wpos(p) (p)\n";
        u32 repn = (u32)strlen(rep);
        if (!nl) return 0;
        nl++;
        {
            u32 head = (u32)(wp - hlsl);
            u32 tail = (u32)strlen(nl);
            if (head + repn + tail + 1 > cap) return 0;
            memmove(wp + repn, nl, tail + 1);
            memcpy(wp, rep, repn);
        }
    }
    return strstr(hlsl, "fp_alpha") == NULL;
}

static ID3DBlob* compile_text(const char* text, u32 len, const char* profile, UINT flags, int loud)
{
    ID3DBlob* blob = NULL;
    ID3DBlob* err = NULL;
    HRESULT hr = D3DCompile(text, len ? len : strlen(text), "fp", NULL, NULL, "main", profile, flags, 0, &blob, &err);
    if (FAILED(hr)) {
        if (loud && err)
            fwrite(err->lpVtbl->GetBufferPointer(err), 1, err->lpVtbl->GetBufferSize(err), stderr);
        if (err) err->lpVtbl->Release(err);
        return NULL;
    }
    if (err) err->lpVtbl->Release(err);
    return blob;
}

static int load_file_cap(const char* path, u8** out, u32* out_n, long cap)
{
    FILE* f = fopen(path, "rb");
    long n;
    u8* b;
    if (!f) return 0;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return 0; }
    n = ftell(f);
    if (n <= 0 || n > cap) { fclose(f); return 0; }
    rewind(f);
    b = (u8*)malloc((size_t)n);
    if (!b || fread(b, 1, (size_t)n, f) != (size_t)n) { free(b); fclose(f); return 0; }
    fclose(f);
    *out = b;
    *out_n = (u32)n;
    return 1;
}

static int load_file(const char* path, u8** out, u32* out_n)
{
    return load_file_cap(path, out, out_n, 256 * 1024);
}

static void status_name(u32 bit, char* dst, u32 n)
{
    const char* s = "ok";
    if (bit & RSX_FP_INTERP_BAD_ARGS) s = "bad-args";
    else if (bit & RSX_FP_INTERP_UNTERMINATED) s = "unterminated";
    else if (bit & RSX_FP_INTERP_TOO_LONG) s = "too-long";
    else if (bit & RSX_FP_INTERP_TOO_MANY_CONST) s = "too-many-const";
    else if (bit & RSX_FP_INTERP_NESTING) s = "nesting";
    else if (bit & RSX_FP_INTERP_OVERFLOW) s = "overflow";
    else if (bit & RSX_FP_INTERP_TEMP) s = "temp";
    strncpy(dst, s, n - 1);
    dst[n - 1] = 0;
}

static int cmd_encode(const char* dir)
{
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    u32 files = 0, ok = 0, read_fail = 0;
    u32 bits[8] = {0};
    u32 max_ins = 0, max_const = 0, max_nest = 0;
    u32 nest_gt8 = 0, with_br = 0, with_tex = 0, with_pred = 0;
    u32 half = 0, mrt = 0;
    snprintf(pattern, sizeof pattern, "%s\\*.fp", dir);
    h = FindFirstFileA(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) { fprintf(stderr, "no fp files\n"); return 1; }
    do {
        char path[MAX_PATH];
        u8* b = NULL;
        u32 n = 0;
        rsx_fp_interp_info info;
        u32 mask;
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        snprintf(path, sizeof path, "%s\\%s", dir, fd.cFileName);
        files++;
        if (!load_file(path, &b, &n)) { read_fail++; continue; }
        rsx_fp_interp_encode(b, n, RSX_FP_CTRL_AUTO, NULL, 0, &info);
        free(b);
        if (info.instructions > max_ins) max_ins = info.instructions;
        if (info.constants > max_const) max_const = info.constants;
        if (info.max_nest > max_nest) max_nest = info.max_nest;
        if (info.max_nest > 8) nest_gt8++;
        if (info.branches) with_br++;
        if (info.textured) with_tex++;
        if (info.predicated) with_pred++;
        if (info.half) half++;
        if (info.targets > 1) mrt++;
        if (info.status == 0) ok++;
        for (mask = 1; mask <= RSX_FP_INTERP_TEMP; mask <<= 1)
            if (info.status & mask) bits[0]++; /* filled below */
        if (info.status & RSX_FP_INTERP_UNTERMINATED) bits[1]++;
        if (info.status & RSX_FP_INTERP_TOO_LONG) bits[2]++;
        if (info.status & RSX_FP_INTERP_TOO_MANY_CONST) bits[3]++;
        if (info.status & RSX_FP_INTERP_NESTING) bits[4]++;
        if (info.status & RSX_FP_INTERP_TEMP) bits[5]++;
        if (info.status & RSX_FP_INTERP_OVERFLOW) bits[6]++;
        if (info.status & RSX_FP_INTERP_BAD_ARGS) bits[7]++;
    } while (FindNextFileA(h, &fd));
    FindClose(h);
    printf("encode files=%u ok=%u read_fail=%u max_ins=%u max_const=%u max_nest=%u nest_gt8=%u\n",
           files, ok, read_fail, max_ins, max_const, max_nest, nest_gt8);
    printf("encode branched=%u textured=%u predicated=%u half=%u mrt=%u\n",
           with_br, with_tex, with_pred, half, mrt);
    printf("encode reject unterminated=%u too_long=%u const=%u nesting=%u temp=%u overflow=%u bad=%u\n",
           bits[1], bits[2], bits[3], bits[4], bits[5], bits[6], bits[7]);
    return files ? 0 : 1;
}

static int cmd_compile(const char* dir_out)
{
    /* ps_5_1 so the 16 texture units and samplers are arrays. A ps_5_0 literal
     * switch compiled to ~460KB and heap-corrupted pipeline creation. */
    UINT flags = 0;
    ULONGLONG t0;
    ID3DBlob* a;
    ID3DBlob* b;
    char path[MAX_PATH];
    FILE* f;
    int loud_fail = 1;
    t0 = GetTickCount64();
    a = compile_text(rsx_fp_interp_hlsl, (u32)strlen(rsx_fp_interp_hlsl), "ps_5_1", flags, loud_fail);
    if (!a) return 1;
    printf("compile single ms=%llu bytes=%u flags=%u\n",
           (unsigned long long)(GetTickCount64() - t0), (unsigned)a->lpVtbl->GetBufferSize(a), flags);
    {
        char* mrt = (char*)malloc(32u + strlen(rsx_fp_interp_hlsl) + 1u);
        ID3DBlob* m;
        ULONGLONG t1;
        CHECK(mrt);
        strcpy(mrt, "#define RSX_INTERP_MRT 1\n");
        strcat(mrt, rsx_fp_interp_hlsl);
        t1 = GetTickCount64();
        m = compile_text(mrt, (u32)strlen(mrt), "ps_5_1", flags, loud_fail);
        free(mrt);
        if (!m) { a->lpVtbl->Release(a); return 1; }
        printf("compile mrt ms=%llu bytes=%u\n",
               (unsigned long long)(GetTickCount64() - t1), (unsigned)m->lpVtbl->GetBufferSize(m));
        b = m;
    }
    snprintf(path, sizeof path, "%s\\ps_single.cso", dir_out);
    f = fopen(path, "wb");
    CHECK(f);
    CHECK(fwrite(a->lpVtbl->GetBufferPointer(a), 1, a->lpVtbl->GetBufferSize(a), f) == a->lpVtbl->GetBufferSize(a));
    fclose(f);
    snprintf(path, sizeof path, "%s\\ps_mrt.cso", dir_out);
    f = fopen(path, "wb");
    CHECK(f);
    CHECK(fwrite(b->lpVtbl->GetBufferPointer(b), 1, b->lpVtbl->GetBufferSize(b), f) == b->lpVtbl->GetBufferSize(b));
    fclose(f);
    snprintf(path, sizeof path, "%s\\ps_flags.txt", dir_out);
    f = fopen(path, "wb");
    CHECK(f);
    fprintf(f, "%u\n", flags);
    fclose(f);
    a->lpVtbl->Release(a);
    b->lpVtbl->Release(b);
    return 0;
}

/* ---- GPU compare ---- */

typedef struct Gpu {
    ID3D12Device* dev;
    ID3D12CommandQueue* q;
    ID3D12CommandAllocator* alloc;
    ID3D12GraphicsCommandList* cl;
    ID3D12Fence* fence;
    UINT64 fv;
    HANDLE fe;
    ID3D12RootSignature* sig_spec;
    ID3D12RootSignature* sig_ip;
    ID3D12PipelineState* pso_single;
    ID3D12PipelineState* pso_mrt;
    ID3D12DescriptorHeap* srv_heap;
    ID3D12DescriptorHeap* rtv_heap;
    UINT srv_inc, rtv_inc;
    ID3D12Resource* rt[8];
    ID3D12Resource* readback;
    UINT64 rb_stride;
    ID3D12Resource* upload;
    u8* upload_map;
    ID3D12Resource* cb;
    ID3D12Resource* prog;
    ID3D12Resource* prog_gpu;
    D3D12_RESOURCE_STATES prog_state;
    ID3D12Resource* vb;
    ID3DBlob* vs;
    D3D12_INPUT_ELEMENT_DESC layout[14];
    char sem[14][16];
} Gpu;

static D3D12_RESOURCE_DESC res_desc(ID3D12Resource* r)
{
    D3D12_RESOURCE_DESC d;
    r->lpVtbl->GetDesc(r, &d);
    return d;
}

static D3D12_CPU_DESCRIPTOR_HANDLE cpu_start(ID3D12DescriptorHeap* h)
{
    D3D12_CPU_DESCRIPTOR_HANDLE o;
    h->lpVtbl->GetCPUDescriptorHandleForHeapStart(h, &o);
    return o;
}

static D3D12_GPU_DESCRIPTOR_HANDLE gpu_start(ID3D12DescriptorHeap* h)
{
    D3D12_GPU_DESCRIPTOR_HANDLE o;
    h->lpVtbl->GetGPUDescriptorHandleForHeapStart(h, &o);
    return o;
}

static void gpu_wait(Gpu* g)
{
    g->fv++;
    CHECK(SUCCEEDED(g->q->lpVtbl->Signal(g->q, g->fence, g->fv)));
    if (g->fence->lpVtbl->GetCompletedValue(g->fence) < g->fv) {
        CHECK(SUCCEEDED(g->fence->lpVtbl->SetEventOnCompletion(g->fence, g->fv, g->fe)));
        CHECK(WaitForSingleObject(g->fe, 20000) == WAIT_OBJECT_0);
    }
}

static void gpu_begin(Gpu* g)
{
    CHECK(SUCCEEDED(g->alloc->lpVtbl->Reset(g->alloc)));
    CHECK(SUCCEEDED(g->cl->lpVtbl->Reset(g->cl, g->alloc, NULL)));
}

static void gpu_end(Gpu* g)
{
    ID3D12CommandList* lists[1];
    CHECK(SUCCEEDED(g->cl->lpVtbl->Close(g->cl)));
    lists[0] = (ID3D12CommandList*)g->cl;
    g->q->lpVtbl->ExecuteCommandLists(g->q, 1, lists);
    gpu_wait(g);
}

static D3D12_RESOURCE_DESC tex_desc(UINT w, UINT h, UINT depth, UINT array, DXGI_FORMAT fmt, int cube, int rt)
{
    D3D12_RESOURCE_DESC d;
    memset(&d, 0, sizeof d);
    d.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    if (depth > 1) d.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE3D;
    d.Width = w; d.Height = h;
    d.DepthOrArraySize = depth > 1 ? (UINT16)depth : (UINT16)array;
    d.MipLevels = 1;
    d.Format = fmt;
    d.SampleDesc.Count = 1;
    if (cube) d.Flags = 0;
    if (rt) d.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
    return d;
}

static ID3D12Resource* make_res(ID3D12Device* dev, const D3D12_RESOURCE_DESC* d, D3D12_HEAP_TYPE heap, D3D12_RESOURCE_STATES st)
{
    D3D12_HEAP_PROPERTIES hp;
    ID3D12Resource* r = NULL;
    memset(&hp, 0, sizeof hp);
    hp.Type = heap;
    CHECK(SUCCEEDED(dev->lpVtbl->CreateCommittedResource(
        dev, &hp, D3D12_HEAP_FLAG_NONE, d, st, NULL, &IID_ID3D12Resource, (void**)&r)));
    return r;
}

static void fill_sampler(D3D12_STATIC_SAMPLER_DESC* s, UINT reg)
{
    memset(s, 0, sizeof *s);
    s->Filter = D3D12_FILTER_MIN_MAG_MIP_POINT;
    s->AddressU = s->AddressV = s->AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
    s->MaxLOD = 0;
    s->ShaderRegister = reg;
    s->ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    s->ComparisonFunc = D3D12_COMPARISON_FUNC_NEVER;
}

static ID3D12RootSignature* make_sig(ID3D12Device* dev, int interp)
{
    D3D12_STATIC_SAMPLER_DESC sam[16];
    D3D12_DESCRIPTOR_RANGE range[3];
    D3D12_ROOT_PARAMETER param[4];
    D3D12_ROOT_SIGNATURE_DESC desc;
    ID3DBlob* ser = NULL;
    ID3DBlob* err = NULL;
    ID3D12RootSignature* sig = NULL;
    UINT i, nparam = interp ? 4u : 2u;
    for (i = 0; i < 16; i++) fill_sampler(&sam[i], i);
    memset(range, 0, sizeof range);
    memset(param, 0, sizeof param);
    range[0].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
    range[0].NumDescriptors = 16;
    range[0].BaseShaderRegister = 0;
    range[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
    range[1].NumDescriptors = 16;
    range[1].BaseShaderRegister = 32;
    range[1].OffsetInDescriptorsFromTableStart = 16;
    range[2].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
    range[2].NumDescriptors = 16;
    range[2].BaseShaderRegister = 48;
    range[2].OffsetInDescriptorsFromTableStart = 32;
    param[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV;
    param[0].Descriptor.ShaderRegister = 1;
    param[0].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    param[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    param[1].DescriptorTable.NumDescriptorRanges = interp ? 3u : 1u;
    param[1].DescriptorTable.pDescriptorRanges = range;
    param[1].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    if (interp) {
        param[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_SRV;
        param[2].Descriptor.ShaderRegister = 16;
        param[2].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
        param[3].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
        param[3].Constants.ShaderRegister = 3;
        param[3].Constants.Num32BitValues = 4;
        param[3].ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    }
    memset(&desc, 0, sizeof desc);
    desc.NumParameters = nparam;
    desc.pParameters = param;
    desc.NumStaticSamplers = 16;
    desc.pStaticSamplers = sam;
    desc.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
    if (FAILED(D3D12SerializeRootSignature(&desc, D3D_ROOT_SIGNATURE_VERSION_1, &ser, &err))) {
        if (err) fwrite(err->lpVtbl->GetBufferPointer(err), 1, err->lpVtbl->GetBufferSize(err), stderr);
        return NULL;
    }
    CHECK(SUCCEEDED(dev->lpVtbl->CreateRootSignature(
        dev, 0, ser->lpVtbl->GetBufferPointer(ser), ser->lpVtbl->GetBufferSize(ser),
        &IID_ID3D12RootSignature, (void**)&sig)));
    ser->lpVtbl->Release(ser);
    if (err) err->lpVtbl->Release(err);
    return sig;
}

static void barrier(Gpu* g, ID3D12Resource* r, D3D12_RESOURCE_STATES a, D3D12_RESOURCE_STATES b)
{
    D3D12_RESOURCE_BARRIER br;
    memset(&br, 0, sizeof br);
    br.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    br.Transition.pResource = r;
    br.Transition.StateBefore = a;
    br.Transition.StateAfter = b;
    br.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    g->cl->lpVtbl->ResourceBarrier(g->cl, 1, &br);
}

static void upload_tex(Gpu* g, ID3D12Resource* tex, const u8* pixels, UINT w, UINT h, UINT subresources, UINT pixel_bytes)
{
    D3D12_RESOURCE_DESC d = res_desc(tex);
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT fp[16];
    UINT rows[16];
    UINT64 row_size[16];
    UINT64 total = 0;
    UINT i;
    D3D12_TEXTURE_COPY_LOCATION dst, src;
    g->dev->lpVtbl->GetCopyableFootprints(g->dev, &d, 0, subresources, 0, fp, rows, row_size, &total);
    CHECK(total < 1024 * 1024);
    for (i = 0; i < subresources; i++) {
        u8* dstp = g->upload_map + fp[i].Offset;
        UINT y, z;
        UINT depth = fp[i].Footprint.Depth;
        UINT height = fp[i].Footprint.Height;
        UINT pitch = fp[i].Footprint.RowPitch;
        for (z = 0; z < depth; z++) {
            for (y = 0; y < height; y++) {
                memcpy(dstp + ((size_t)z * height + y) * pitch,
                       pixels + ((size_t)i * depth * h + (size_t)z * h + y) * w * pixel_bytes,
                       (size_t)w * pixel_bytes);
            }
        }
        (void)row_size;
    }
    gpu_begin(g);
    barrier(g, tex, D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_DEST);
    for (i = 0; i < subresources; i++) {
        memset(&dst, 0, sizeof dst);
        memset(&src, 0, sizeof src);
        dst.pResource = tex;
        dst.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        dst.SubresourceIndex = i;
        src.pResource = g->upload;
        src.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
        src.PlacedFootprint = fp[i];
        g->cl->lpVtbl->CopyTextureRegion(g->cl, &dst, 0, 0, 0, &src, NULL);
    }
    barrier(g, tex, D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
    gpu_end(g);
}

static void srv_tex(Gpu* g, ID3D12Resource* res, D3D12_SRV_DIMENSION dim, UINT slot)
{
    D3D12_SHADER_RESOURCE_VIEW_DESC s;
    D3D12_CPU_DESCRIPTOR_HANDLE h = cpu_start(g->srv_heap);
    memset(&s, 0, sizeof s);
    s.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    s.ViewDimension = dim;
    s.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    if (dim == D3D12_SRV_DIMENSION_TEXTURE2D) s.Texture2D.MipLevels = 1;
    if (dim == D3D12_SRV_DIMENSION_TEXTURECUBE) s.TextureCube.MipLevels = 1;
    if (dim == D3D12_SRV_DIMENSION_TEXTURE3D) s.Texture3D.MipLevels = 1;
    h.ptr += (SIZE_T)slot * g->srv_inc;
    g->dev->lpVtbl->CreateShaderResourceView(g->dev, res, &s, h);
}

static ID3DBlob* load_cso(const char* path)
{
    u8* b = NULL;
    u32 n = 0;
    ID3DBlob* blob = NULL;
    if (!load_file_cap(path, &b, &n, 4 * 1024 * 1024)) return NULL;
    CHECK(SUCCEEDED(D3DCreateBlob(n, &blob)));
    memcpy(blob->lpVtbl->GetBufferPointer(blob), b, n);
    free(b);
    return blob;
}

static void build_vertices(float* v)
{
    int i, a;
    float pos[3][4] = {{-2, -2, 0.5f, 2}, {6, -2, 0.5f, 2}, {-2, 6, 0.5f, 2}};
    for (i = 0; i < 3; i++) {
        float* o = v + i * 14 * 4;
        memcpy(o, pos[i], sizeof pos[i]);
        o[4] = (i == 0) ? -0.5f : (i == 1) ? 1.5f : 0.25f;
        o[5] = 0.5f; o[6] = (float)i; o[7] = 1;
        o[8] = 0.2f * (float)(i + 1); o[9] = -0.3f; o[10] = 0.7f; o[11] = 1;
        o[12] = 0.1f * (float)(i + 1); o[13] = 0; o[14] = 0; o[15] = 0;
        for (a = 0; a < 10; a++) {
            o[16 + a * 4 + 0] = (float)i * 0.4f + (float)a * 0.05f;
            o[16 + a * 4 + 1] = 1.0f - (float)i * 0.3f;
            o[16 + a * 4 + 2] = (a == 0 && i == 1) ? 1.0f : 0.25f;
            o[16 + a * 4 + 3] = 1.0f;
        }
    }
}

static int gpu_init(Gpu* g, const char* cso_dir)
{
    IDXGIFactory4* factory = NULL;
    IDXGIAdapter* adapter = NULL;
    D3D12_COMMAND_QUEUE_DESC qd;
    D3D12_DESCRIPTOR_HEAP_DESC hd;
    D3D12_RESOURCE_DESC bd;
    ID3D12Resource *tex2d, *texcu, *tex3d;
    u8 pix2d[4 * 4 * 4];
    u8 pixcu[6 * 4 * 4 * 4];
    u8 pix3d[4 * 4 * 4 * 4];
    char path[MAX_PATH];
    ID3DBlob *ps_s, *ps_m;
    D3D12_GRAPHICS_PIPELINE_STATE_DESC pso;
    int i, x, y, z, f;
    const char* sem_names[14] = {
        "POSITION", "COLOR", "COLOR", "FOG",
        "TEXCOORD", "TEXCOORD", "TEXCOORD", "TEXCOORD",
        "TEXCOORD", "TEXCOORD", "TEXCOORD", "TEXCOORD",
        "TEXCOORD", "TEXCOORD"
    };
    const UINT sem_index[14] = {
        0, 0, 1, 0,
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9
    };
    memset(g, 0, sizeof *g);
    if (getenv("RSX_FP_INTERP_DEBUG")) enable_d3d_debug();
    CHECK(SUCCEEDED(CreateDXGIFactory1(&IID_IDXGIFactory4, (void**)&factory)));
    CHECK(SUCCEEDED(factory->lpVtbl->EnumWarpAdapter(factory, &IID_IDXGIAdapter, (void**)&adapter)));
    CHECK(SUCCEEDED(D3D12CreateDevice((IUnknown*)adapter, D3D_FEATURE_LEVEL_11_0, &IID_ID3D12Device, (void**)&g->dev)));
    adapter->lpVtbl->Release(adapter);
    factory->lpVtbl->Release(factory);
    memset(&qd, 0, sizeof qd);
    qd.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    CHECK(SUCCEEDED(g->dev->lpVtbl->CreateCommandQueue(g->dev, &qd, &IID_ID3D12CommandQueue, (void**)&g->q)));
    CHECK(SUCCEEDED(g->dev->lpVtbl->CreateCommandAllocator(g->dev, D3D12_COMMAND_LIST_TYPE_DIRECT, &IID_ID3D12CommandAllocator, (void**)&g->alloc)));
    CHECK(SUCCEEDED(g->dev->lpVtbl->CreateCommandList(g->dev, 0, D3D12_COMMAND_LIST_TYPE_DIRECT, g->alloc, NULL, &IID_ID3D12GraphicsCommandList, (void**)&g->cl)));
    CHECK(SUCCEEDED(g->cl->lpVtbl->Close(g->cl)));
    CHECK(SUCCEEDED(g->dev->lpVtbl->CreateFence(g->dev, 0, D3D12_FENCE_FLAG_NONE, &IID_ID3D12Fence, (void**)&g->fence)));
    g->fe = CreateEventA(NULL, FALSE, FALSE, NULL);
    CHECK(g->fe);
    g->sig_spec = make_sig(g->dev, 0);
    g->sig_ip = make_sig(g->dev, 1);
    CHECK(g->sig_spec && g->sig_ip);
    memset(&hd, 0, sizeof hd);
    hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    hd.NumDescriptors = 256;
    hd.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    CHECK(SUCCEEDED(g->dev->lpVtbl->CreateDescriptorHeap(g->dev, &hd, &IID_ID3D12DescriptorHeap, (void**)&g->srv_heap)));
    hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    hd.NumDescriptors = 8;
    hd.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_NONE;
    CHECK(SUCCEEDED(g->dev->lpVtbl->CreateDescriptorHeap(g->dev, &hd, &IID_ID3D12DescriptorHeap, (void**)&g->rtv_heap)));
    g->srv_inc = g->dev->lpVtbl->GetDescriptorHandleIncrementSize(g->dev, D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    g->rtv_inc = g->dev->lpVtbl->GetDescriptorHandleIncrementSize(g->dev, D3D12_DESCRIPTOR_HEAP_TYPE_RTV);
    for (i = 0; i < 8; i++) {
        D3D12_RESOURCE_DESC rd = tex_desc(RT, RT, 1, 1, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 1);
        D3D12_CPU_DESCRIPTOR_HANDLE rh = cpu_start(g->rtv_heap);
        g->rt[i] = make_res(g->dev, &rd, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_RENDER_TARGET);
        rh.ptr += (SIZE_T)i * g->rtv_inc;
        g->dev->lpVtbl->CreateRenderTargetView(g->dev, g->rt[i], NULL, rh);
    }
    {
        D3D12_RESOURCE_DESC rd0 = res_desc(g->rt[0]);
        D3D12_PLACED_SUBRESOURCE_FOOTPRINT fp;
        UINT64 total = 0;
        g->dev->lpVtbl->GetCopyableFootprints(g->dev, &rd0, 0, 1, 0, &fp, NULL, NULL, &total);
        g->rb_stride = (total + 255ull) & ~255ull;
        memset(&bd, 0, sizeof bd);
        bd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
        bd.Width = g->rb_stride * 8;
        bd.Height = 1; bd.DepthOrArraySize = 1; bd.MipLevels = 1; bd.SampleDesc.Count = 1;
        bd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        g->readback = make_res(g->dev, &bd, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    }
    memset(&bd, 0, sizeof bd);
    bd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    bd.Width = 1024 * 1024;
    bd.Height = 1; bd.DepthOrArraySize = 1; bd.MipLevels = 1; bd.SampleDesc.Count = 1;
    bd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    g->upload = make_res(g->dev, &bd, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    CHECK(SUCCEEDED(g->upload->lpVtbl->Map(g->upload, 0, NULL, (void**)&g->upload_map)));
    bd.Width = 4352;
    g->cb = make_res(g->dev, &bd, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    bd.Width = 64 + RSX_FP_INTERP_MAX_INSNS * 16;
    g->prog = make_res(g->dev, &bd, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    g->prog_gpu = make_res(g->dev, &bd, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON);
    g->prog_state = D3D12_RESOURCE_STATE_COMMON;
    for (y = 0; y < 4; y++) for (x = 0; x < 4; x++) {
        u8* p = pix2d + (y * 4 + x) * 4;
        p[0] = (u8)(x * 80); p[1] = (u8)(y * 80); p[2] = (u8)(40 + x * 20 + y * 10); p[3] = 255;
    }
    for (f = 0; f < 6; f++) for (y = 0; y < 4; y++) for (x = 0; x < 4; x++) {
        u8* p = pixcu + ((f * 4 + y) * 4 + x) * 4;
        p[0] = (u8)(30 + f * 30); p[1] = (u8)(x * 60); p[2] = (u8)(y * 60); p[3] = 255;
    }
    for (z = 0; z < 4; z++) for (y = 0; y < 4; y++) for (x = 0; x < 4; x++) {
        u8* p = pix3d + ((z * 4 + y) * 4 + x) * 4;
        p[0] = (u8)(z * 60); p[1] = (u8)(y * 60); p[2] = (u8)(x * 60); p[3] = 255;
    }
    {
        D3D12_RESOURCE_DESC d2 = tex_desc(4, 4, 1, 1, DXGI_FORMAT_R8G8B8A8_UNORM, 0, 0);
        D3D12_RESOURCE_DESC dc = tex_desc(4, 4, 1, 6, DXGI_FORMAT_R8G8B8A8_UNORM, 1, 0);
        D3D12_RESOURCE_DESC d3 = tex_desc(4, 4, 4, 1, DXGI_FORMAT_R8G8B8A8_UNORM, 0, 0);
        tex2d = make_res(g->dev, &d2, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON);
        texcu = make_res(g->dev, &dc, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON);
        tex3d = make_res(g->dev, &d3, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON);
    }
    upload_tex(g, tex2d, pix2d, 4, 4, 1, 4);
    upload_tex(g, texcu, pixcu, 4, 4, 6, 4);
    upload_tex(g, tex3d, pix3d, 4, 4, 1, 4);
    /* Heap layout: 0 spec 2D, 16 spec cube (t0 cube), 32 spec volume (t0 3D),
     * 48 interpreter 2D/cube/3D (48 descriptors). */
    for (i = 0; i < 16; i++) srv_tex(g, tex2d, D3D12_SRV_DIMENSION_TEXTURE2D, (UINT)i);
    srv_tex(g, texcu, D3D12_SRV_DIMENSION_TEXTURECUBE, 16);
    for (i = 1; i < 16; i++) srv_tex(g, tex2d, D3D12_SRV_DIMENSION_TEXTURE2D, 16u + (UINT)i);
    srv_tex(g, tex3d, D3D12_SRV_DIMENSION_TEXTURE3D, 32);
    for (i = 1; i < 16; i++) srv_tex(g, tex2d, D3D12_SRV_DIMENSION_TEXTURE2D, 32u + (UINT)i);
    for (i = 0; i < 16; i++) {
        srv_tex(g, tex2d, D3D12_SRV_DIMENSION_TEXTURE2D, 48u + (UINT)i);
        srv_tex(g, texcu, D3D12_SRV_DIMENSION_TEXTURECUBE, 64u + (UINT)i);
        srv_tex(g, tex3d, D3D12_SRV_DIMENSION_TEXTURE3D, 80u + (UINT)i);
    }
    g->vs = compile_text(VS_HLSL, 0, "vs_5_0", 0, 1);
    CHECK(g->vs);
    snprintf(path, sizeof path, "%s\\ps_single.cso", cso_dir);
    ps_s = load_cso(path);
    snprintf(path, sizeof path, "%s\\ps_mrt.cso", cso_dir);
    ps_m = load_cso(path);
    CHECK(ps_s && ps_m);
    for (i = 0; i < 14; i++) {
        strncpy(g->sem[i], sem_names[i], sizeof g->sem[i] - 1);
        memset(&g->layout[i], 0, sizeof g->layout[i]);
        g->layout[i].SemanticName = g->sem[i];
        g->layout[i].SemanticIndex = sem_index[i];
        g->layout[i].Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
        g->layout[i].AlignedByteOffset = (UINT)(i * 16);
        g->layout[i].InputSlotClass = D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA;
    }
    memset(&pso, 0, sizeof pso);
    pso.pRootSignature = g->sig_ip;
    pso.VS.pShaderBytecode = g->vs->lpVtbl->GetBufferPointer(g->vs);
    pso.VS.BytecodeLength = g->vs->lpVtbl->GetBufferSize(g->vs);
    pso.PS.pShaderBytecode = ps_s->lpVtbl->GetBufferPointer(ps_s);
    pso.PS.BytecodeLength = ps_s->lpVtbl->GetBufferSize(ps_s);
    pso.BlendState.RenderTarget[0].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
    pso.SampleMask = ~0u;
    pso.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
    pso.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
    pso.RasterizerState.DepthClipEnable = TRUE;
    pso.InputLayout.pInputElementDescs = g->layout;
    pso.InputLayout.NumElements = 14;
    pso.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
    pso.NumRenderTargets = 1;
    pso.RTVFormats[0] = DXGI_FORMAT_R32G32B32A32_FLOAT;
    pso.SampleDesc.Count = 1;
    fprintf(stderr, "creating pso single (%llu bytes)\n", (unsigned long long)pso.PS.BytecodeLength);
    fflush(stderr);
    create_pso_or_die(g->dev, &pso, &g->pso_single, "single");
    fprintf(stderr, "pso single ok\n");
    fflush(stderr);
    pso.PS.pShaderBytecode = ps_m->lpVtbl->GetBufferPointer(ps_m);
    pso.PS.BytecodeLength = ps_m->lpVtbl->GetBufferSize(ps_m);
    pso.NumRenderTargets = 4;
    for (i = 0; i < 4; i++) {
        pso.RTVFormats[i] = DXGI_FORMAT_R32G32B32A32_FLOAT;
        pso.BlendState.RenderTarget[i].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
    }
    create_pso_or_die(g->dev, &pso, &g->pso_mrt, "mrt");
    ps_s->lpVtbl->Release(ps_s);
    ps_m->lpVtbl->Release(ps_m);
    {
        float verts[3 * 14 * 4];
        void* mapped = NULL;
        D3D12_RESOURCE_DESC vd;
        build_vertices(verts);
        memset(&vd, 0, sizeof vd);
        vd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
        vd.Width = sizeof verts;
        vd.Height = 1; vd.DepthOrArraySize = 1; vd.MipLevels = 1; vd.SampleDesc.Count = 1;
        vd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        g->vb = make_res(g->dev, &vd, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
        CHECK(SUCCEEDED(g->vb->lpVtbl->Map(g->vb, 0, NULL, &mapped)));
        memcpy(mapped, verts, sizeof verts);
        g->vb->lpVtbl->Unmap(g->vb, 0, NULL);
    }
    return 0;
}

static void fill_cb(Gpu* g, const u8* ucode, u32 n)
{
    float consts[256][4];
    float* mapped = NULL;
    int count;
    u8* raw = NULL;
    memset(consts, 0, sizeof consts);
    count = rsx_fp_collect_constants_to(ucode, n, consts, 256);
    CHECK(count >= 0 && count <= 256);
    CHECK(SUCCEEDED(g->cb->lpVtbl->Map(g->cb, 0, NULL, (void**)&mapped)));
    memset(mapped, 0, 4352);
    if (count > 0) memcpy(mapped + 5 * 16, consts, (size_t)count * 16);
    g->cb->lpVtbl->Unmap(g->cb, 0, NULL);
    (void)raw;
}

static void fill_prog(Gpu* g, const u32* image, const rsx_fp_interp_info* info, u32 shape)
{
    u32 hdr[16];
    u8* mapped = NULL;
    u32 bytes = info->instructions * 16u;
    memset(hdr, 0, sizeof hdr);
    hdr[0] = 64;
    hdr[1] = info->instructions;
    hdr[2] = (info->half ? 1u : 0u) | 256u; /* lg2 abs on, other epilogues off */
    hdr[3] = shape;
    hdr[7] = 0x76543210u;
    hdr[8] = 0xFEDCBA98u;
    CHECK(SUCCEEDED(g->prog->lpVtbl->Map(g->prog, 0, NULL, (void**)&mapped)));
    memset(mapped, 0, 64 + bytes);
    memcpy(mapped, hdr, 64);
    memcpy(mapped + 64, image, bytes);
    g->prog->lpVtbl->Unmap(g->prog, 0, NULL);
}

static void draw_one(Gpu* g, ID3D12PipelineState* pso, ID3D12RootSignature* sig, int interp,
                     UINT spec_table, UINT nrt, UINT rt_base)
{
    D3D12_CPU_DESCRIPTOR_HANDLE rtvs[4];
    D3D12_GPU_DESCRIPTOR_HANDLE gpu;
    D3D12_VERTEX_BUFFER_VIEW vbv;
    D3D12_VIEWPORT vp;
    D3D12_RECT sc;
    float clear[4] = {3.f, -5.f, 7.f, 11.f};
    UINT i;
    ID3D12DescriptorHeap* heaps[1];
    u32 root_c[4] = {0, 0, 0, 0};
    gpu_begin(g);
    heaps[0] = g->srv_heap;
    g->cl->lpVtbl->SetDescriptorHeaps(g->cl, 1, heaps);
    g->cl->lpVtbl->SetGraphicsRootSignature(g->cl, sig);
    g->cl->lpVtbl->SetPipelineState(g->cl, pso);
    g->cl->lpVtbl->SetGraphicsRootConstantBufferView(g->cl, 0, g->cb->lpVtbl->GetGPUVirtualAddress(g->cb));
    gpu = gpu_start(g->srv_heap);
    gpu.ptr += (UINT64)spec_table * g->srv_inc;
    g->cl->lpVtbl->SetGraphicsRootDescriptorTable(g->cl, 1, gpu);
    if (interp) {
        barrier(g, g->prog_gpu, g->prog_state, D3D12_RESOURCE_STATE_COPY_DEST);
        g->cl->lpVtbl->CopyBufferRegion(g->cl, g->prog_gpu, 0, g->prog, 0, 64 + RSX_FP_INTERP_MAX_INSNS * 16);
        barrier(g, g->prog_gpu, D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
        g->prog_state = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
        g->cl->lpVtbl->SetGraphicsRootShaderResourceView(g->cl, 2, g->prog_gpu->lpVtbl->GetGPUVirtualAddress(g->prog_gpu));
        g->cl->lpVtbl->SetGraphicsRoot32BitConstants(g->cl, 3, 4, root_c, 0);
    }
    for (i = 0; i < nrt; i++) {
        rtvs[i] = cpu_start(g->rtv_heap);
        rtvs[i].ptr += (SIZE_T)(rt_base + i) * g->rtv_inc;
        g->cl->lpVtbl->ClearRenderTargetView(g->cl, rtvs[i], clear, 0, NULL);
    }
    g->cl->lpVtbl->OMSetRenderTargets(g->cl, nrt, rtvs, FALSE, NULL);
    vp.TopLeftX = 0; vp.TopLeftY = 0; vp.Width = RT; vp.Height = RT; vp.MinDepth = 0; vp.MaxDepth = 1;
    sc.left = 0; sc.top = 0; sc.right = RT; sc.bottom = RT;
    g->cl->lpVtbl->RSSetViewports(g->cl, 1, &vp);
    g->cl->lpVtbl->RSSetScissorRects(g->cl, 1, &sc);
    vbv.BufferLocation = g->vb->lpVtbl->GetGPUVirtualAddress(g->vb);
    vbv.SizeInBytes = 3 * 14 * 16;
    vbv.StrideInBytes = 14 * 16;
    g->cl->lpVtbl->IASetPrimitiveTopology(g->cl, D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    g->cl->lpVtbl->IASetVertexBuffers(g->cl, 0, 1, &vbv);
    g->cl->lpVtbl->DrawInstanced(g->cl, 3, 1, 0, 0);
    for (i = 0; i < nrt; i++)
        barrier(g, g->rt[rt_base + i], D3D12_RESOURCE_STATE_RENDER_TARGET, D3D12_RESOURCE_STATE_COPY_SOURCE);
    for (i = 0; i < nrt; i++) {
        D3D12_TEXTURE_COPY_LOCATION dst, src;
        D3D12_RESOURCE_DESC rd = res_desc(g->rt[rt_base + i]);
        D3D12_PLACED_SUBRESOURCE_FOOTPRINT fp;
        memset(&dst, 0, sizeof dst);
        memset(&src, 0, sizeof src);
        g->dev->lpVtbl->GetCopyableFootprints(g->dev, &rd, 0, 1, g->rb_stride * (rt_base + i), &fp, NULL, NULL, NULL);
        dst.pResource = g->readback;
        dst.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
        dst.PlacedFootprint = fp;
        src.pResource = g->rt[rt_base + i];
        src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        g->cl->lpVtbl->CopyTextureRegion(g->cl, &dst, 0, 0, 0, &src, NULL);
    }
    for (i = 0; i < nrt; i++)
        barrier(g, g->rt[rt_base + i], D3D12_RESOURCE_STATE_COPY_SOURCE, D3D12_RESOURCE_STATE_RENDER_TARGET);
    gpu_end(g);
}

static int compare_readback(Gpu* g, UINT nrt, float* worst)
{
    u8* map = NULL;
    UINT t, y, x, c;
    int bad = 0;
    D3D12_RANGE range;
    range.Begin = 0; range.End = (SIZE_T)(g->rb_stride * 8);
    CHECK(SUCCEEDED(g->readback->lpVtbl->Map(g->readback, 0, &range, (void**)&map)));
    for (t = 0; t < nrt; t++) {
        D3D12_RESOURCE_DESC rd = res_desc(g->rt[t]);
        D3D12_PLACED_SUBRESOURCE_FOOTPRINT fp_a, fp_b;
        g->dev->lpVtbl->GetCopyableFootprints(g->dev, &rd, 0, 1, g->rb_stride * t, &fp_a, NULL, NULL, NULL);
        g->dev->lpVtbl->GetCopyableFootprints(g->dev, &rd, 0, 1, g->rb_stride * (4u + t), &fp_b, NULL, NULL, NULL);
        for (y = 0; y < RT; y++) for (x = 0; x < RT; x++) {
            float* a = (float*)(map + fp_a.Offset + (size_t)y * fp_a.Footprint.RowPitch + (size_t)x * 16);
            float* b = (float*)(map + fp_b.Offset + (size_t)y * fp_b.Footprint.RowPitch + (size_t)x * 16);
            for (c = 0; c < 4; c++) {
                float d;
                if (a[c] != a[c] || b[c] != b[c]) {
                    static int nan_logged;
                    if (nan_logged < 24) { nan_logged++; printf("NaN rt=%u x=%u y=%u c=%u spec=%g interp=%g\n", t, x, y, c, (double)a[c], (double)b[c]); }
                    bad = 1; *worst = 1e9f; continue;
                }
                d = a[c] - b[c];
                if (d < 0) d = -d;
                if (d > *worst) *worst = d;
                if (d > 1e-4f) bad = 1;
            }
        }
    }
    g->readback->lpVtbl->Unmap(g->readback, 0, NULL);
    return bad;
}

static ID3D12PipelineState* compile_spec_pso(Gpu* g, const char* hlsl, UINT nrt)
{
    ID3DBlob* ps = compile_text(hlsl, 0, "ps_5_0", 0, 0);
    D3D12_GRAPHICS_PIPELINE_STATE_DESC pso;
    ID3D12PipelineState* out = NULL;
    UINT i;
    if (!ps) return NULL;
    memset(&pso, 0, sizeof pso);
    pso.pRootSignature = g->sig_spec;
    pso.VS.pShaderBytecode = g->vs->lpVtbl->GetBufferPointer(g->vs);
    pso.VS.BytecodeLength = g->vs->lpVtbl->GetBufferSize(g->vs);
    pso.PS.pShaderBytecode = ps->lpVtbl->GetBufferPointer(ps);
    pso.PS.BytecodeLength = ps->lpVtbl->GetBufferSize(ps);
    pso.SampleMask = ~0u;
    pso.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
    pso.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
    pso.RasterizerState.DepthClipEnable = TRUE;
    pso.InputLayout.pInputElementDescs = g->layout;
    pso.InputLayout.NumElements = 14;
    pso.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
    pso.NumRenderTargets = nrt;
    pso.SampleDesc.Count = 1;
    for (i = 0; i < nrt; i++) {
        pso.RTVFormats[i] = DXGI_FORMAT_R32G32B32A32_FLOAT;
        pso.BlendState.RenderTarget[i].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
    }
    if (FAILED(g->dev->lpVtbl->CreateGraphicsPipelineState(g->dev, &pso, &IID_ID3D12PipelineState, (void**)&out)))
        out = NULL;
    ps->lpVtbl->Release(ps);
    return out;
}

static int run_program(Gpu* g, const u8* ucode, u32 n, u32 cube_mask, u32 shape, UINT spec_table, int loud, float* worst)
{
    rsx_fp_interp_info info;
    u32 image[RSX_FP_INTERP_MAX_INSNS * 4];
    char* hlsl;
    int rc;
    ID3D12PipelineState* spec;
    UINT nrt;
    *worst = 0;
    if (rsx_fp_interp_encode(ucode, n, RSX_FP_CTRL_AUTO, image, RSX_FP_INTERP_MAX_INSNS * 4, &info) != 0)
        return -1;
    if (info.depth_export) return -2;
    hlsl = (char*)malloc(RSX_FP_HLSL_BUFFER_SIZE);
    if (!hlsl) return -3;
    rc = rsx_fp_decompile_buffered_ex(ucode, n, RSX_FP_CTRL_AUTO, cube_mask, hlsl, RSX_FP_HLSL_BUFFER_SIZE, NULL);
    if (rc < 0 || !patch_hlsl(hlsl, RSX_FP_HLSL_BUFFER_SIZE)) {
        if (loud) fprintf(stderr, "decompile/patch failed rc=%d\n", rc);
        free(hlsl);
        return -4;
    }
    nrt = info.targets > 4 ? 4 : info.targets;
    if (nrt < 1) nrt = 1;
    spec = compile_spec_pso(g, hlsl, nrt);
    free(hlsl);
    if (!spec) return -5;
    fill_cb(g, ucode, n);
    fill_prog(g, image, &info, shape);
    /* Spec draws into RT 0..nrt-1. Interpreter draws into RT 4.. */
    draw_one(g, spec, g->sig_spec, 0, spec_table, nrt, 0);
    draw_one(g, nrt == 1 ? g->pso_single : g->pso_mrt, g->sig_ip, 1, 48, nrt == 1 ? 1u : 4u, 4);
    spec->lpVtbl->Release(spec);
    return compare_readback(g, nrt, worst) ? 1 : 0;
}

static void guest_const(u8* p, float a, float b, float c, float d)
{
    put_guest(p + 0, fbits(a));
    put_guest(p + 4, fbits(b));
    put_guest(p + 8, fbits(c));
    put_guest(p + 12, fbits(d));
}

static u32 swizzle_xyzw(void)
{
    return (0u << 9) | (1u << 11) | (2u << 13) | (3u << 15);
}

static int synth_math(u8* p)
{
    /* MUL r0, c0, c1; ADD r0, r0, c0; RCP r0, r0; END on the RCP. */
    u32 w0, w1, exec = 7u << 18;
    int n = 0;
    w0 = (0xFu << 9) | (0x02u << 24);
    w1 = 2u | swizzle_xyzw() | exec;
    put_guest(p + n, w0); put_guest(p + n + 4, w1);
    put_guest(p + n + 8, 2u | swizzle_xyzw());
    put_guest(p + n + 12, 0);
    n += 16; guest_const(p + n, 0.5f, 0.25f, 0.125f, 1.f); n += 16;
    w0 = (0xFu << 9) | (0x03u << 24);
    w1 = 0u | swizzle_xyzw() | exec; /* temp r0 */
    put_guest(p + n, w0); put_guest(p + n + 4, w1);
    put_guest(p + n + 8, 2u | swizzle_xyzw()); /* src1 const */
    put_guest(p + n + 12, 0);
    n += 16; guest_const(p + n, 0.5f, 0.25f, 0.125f, 1.f); n += 16;
    w0 = 1u | (0xFu << 9) | (0x1Au << 24); /* END RCP */
    w1 = 0u | swizzle_xyzw() | exec;
    put_guest(p + n, w0); put_guest(p + n + 4, w1); put_guest(p + n + 8, 0); put_guest(p + n + 12, 0);
    n += 16;
    return n;
}

static int synth_col(u8* p)
{
    u32 exec = 7u << 18;
    u32 w0 = 1u | (0xFu << 9) | (1u << 13) | (0x01u << 24); /* END MOV, input COL0 */
    u32 w1 = 1u | swizzle_xyzw() | exec; /* INPUT */
    put_guest(p, w0); put_guest(p + 4, w1); put_guest(p + 8, 0); put_guest(p + 12, 0);
    return 16;
}

static int synth_tex(u8* p)
{
    u32 exec = 7u << 18;
    u32 w0 = 1u | (0xFu << 9) | (4u << 13) | (0x17u << 24); /* END TEX unit 0, input TC0 */
    u32 w1 = 1u | swizzle_xyzw() | exec;
    put_guest(p, w0); put_guest(p + 4, w1); put_guest(p + 8, 0); put_guest(p + 12, 0);
    return 16;
}

static int cmd_compare(const char* dir, const char* cso_dir, const char* summary)
{
    Gpu g;
    float worst = 0;
    int rc;
    u8 code[256];
    int n;
    FILE* out;
    u32 spec_fail = 0, skip = 0, fail = 0, pass = 0, cube_fail = 0, cube_pass = 0;
    float cat_worst = 0;
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    enum { WANT_ALU = 30, WANT_BR = 20, WANT_TEX = 20, WANT_PRED = 10 };
    char* picked[80];
    int kind[80];
    int np = 0, nalu = 0, nbr = 0, ntex = 0, npred = 0;
    int pi;
    const char* env_note = NULL;
    if (getenv("RSX_FP_SAT_PROG") || getenv("RSX_FP_SAT_OPS") || getenv("RSX_FP_SAT_VIS"))
        env_note = "diagnostic saturation env is set; interpreter does not honor it";
    CHECK(gpu_init(&g, cso_dir) == 0);
    n = synth_math(code);
    rc = run_program(&g, code, (u32)n, 0, 0, 0, 1, &worst);
    printf("synthetic math rc=%d worst=%g\n", rc, worst);
    if (rc != 0) { printf("synthetic math failed; catalogue skipped\n"); return 2; }
    n = synth_col(code);
    rc = run_program(&g, code, (u32)n, 0, 0, 0, 1, &worst);
    printf("synthetic col rc=%d worst=%g\n", rc, worst);
    if (rc != 0) return 2;
    n = synth_tex(code);
    rc = run_program(&g, code, (u32)n, 0, 0, 0, 1, &worst);
    printf("synthetic tex rc=%d worst=%g\n", rc, worst);
    if (rc != 0) return 2;

    snprintf(pattern, sizeof pattern, "%s\\*.fp", dir);
    h = FindFirstFileA(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) { fprintf(stderr, "no catalogue\n"); return 1; }
    do {
        char path[MAX_PATH];
        u8* b = NULL;
        u32 nb = 0;
        rsx_fp_interp_info info;
        int k;
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        if (np >= 80 && nalu >= WANT_ALU && nbr >= WANT_BR && ntex >= WANT_TEX && npred >= WANT_PRED)
            break;
        snprintf(path, sizeof path, "%s\\%s", dir, fd.cFileName);
        if (!load_file(path, &b, &nb)) continue;
        if (rsx_fp_interp_encode(b, nb, RSX_FP_CTRL_AUTO, NULL, 0, &info) != 0) { free(b); continue; }
        free(b);
        k = -1;
        if (info.predicated && npred < WANT_PRED) k = 3;
        else if (info.branches && nbr < WANT_BR) k = 1;
        else if (info.textured && ntex < WANT_TEX) k = 2;
        else if (!info.branches && !info.textured && !info.predicated && nalu < WANT_ALU) k = 0;
        if (k < 0) continue;
        picked[np] = _strdup(path);
        kind[np] = k;
        np++;
        if (k == 0) nalu++;
        else if (k == 1) nbr++;
        else if (k == 2) ntex++;
        else npred++;
    } while (FindNextFileA(h, &fd));
    FindClose(h);
    printf("catalogue selected alu=%d branch=%d tex=%d pred=%d\n", nalu, nbr, ntex, npred);
    for (pi = 0; pi < np; pi++) {
        u8* b = NULL;
        u32 nb = 0;
        float w = 0;
        int r;
        if (!load_file(picked[pi], &b, &nb)) { skip++; continue; }
        r = run_program(&g, b, nb, 0, 0, 0, 0, &w);
        if (r == -5) spec_fail++;
        else if (r < 0) skip++;
        else if (r > 0) { fail++; if (w > cat_worst) cat_worst = w; printf("catalogue FAIL kind=%d worst=%g %s\n", kind[pi], w, picked[pi]); }
        else pass++;
        if (kind[pi] == 2 && cube_pass + cube_fail < 5 && r >= 0) {
            float cw = 0;
            int cr = run_program(&g, b, nb, 1u, 1u, 16u, 0, &cw);
            if (cr == 0) cube_pass++;
            else cube_fail++;
            if (cw > cat_worst) cat_worst = cw;
        }
        free(b);
        free(picked[pi]);
    }
    printf("catalogue pass=%u fail=%u skip=%u spec_compile_fail=%u worst=%g cube_pass=%u cube_fail=%u\n",
           pass, fail, skip, spec_fail, cat_worst, cube_pass, cube_fail);
    if (env_note) printf("note %s\n", env_note);
    out = fopen(summary, "wb");
    if (out) {
        fprintf(out, "pass=%u fail=%u skip=%u spec_compile_fail=%u worst=%g cube_pass=%u cube_fail=%u\n",
                pass, fail, skip, spec_fail, cat_worst, cube_pass, cube_fail);
        fprintf(out, "selected alu=%d branch=%d tex=%d pred=%d\n", nalu, nbr, ntex, npred);
        if (env_note) fprintf(out, "note %s\n", env_note);
        fclose(out);
    }
    return (fail || cube_fail) ? 3 : 0;
}

int main(int argc, char** argv)
{
    const char* cmd;
    if (argc < 2) {
        fprintf(stderr, "usage: fp_interp_harness compile|encode|compare ...\n");
        return 2;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    cmd = argv[1];
    if (!strcmp(cmd, "encode")) return cmd_encode(argc > 2 ? argv[2] : "");
    if (!strcmp(cmd, "compile")) return cmd_compile(argc > 2 ? argv[2] : ".");
    if (!strcmp(cmd, "compare")) {
        if (argc < 5) { fprintf(stderr, "compare <catalogue> <cso-dir> <summary>\n"); return 2; }
        return cmd_compare(argv[2], argv[3], argv[4]);
    }
    fprintf(stderr, "unknown command\n");
    return 2;
}
