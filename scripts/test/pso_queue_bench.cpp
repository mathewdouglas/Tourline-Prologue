/* Time CreateGraphicsPipelineState alone, then several threads at once.

   Each pipeline has its own pixel shader, so a later pass is not a repeat of a
   descriptor the driver already compiled. Fresh rows use disjoint shaders.
   Cached-blob rows recreate the one-thread set after those pipelines were
   released. A pipeline-library load of that same set is timed beside them.

   Build: cl /O2 /EHsc /std:c++17 pso_queue_bench.cpp d3d12.lib d3dcompiler.lib dxgi.lib
*/
#define WIN32_LEAN_AND_MEAN
#include <d3d12.h>
#include <d3dcompiler.h>
#include <dxgi.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <vector>

#pragma comment(lib, "d3d12.lib")
#pragma comment(lib, "d3dcompiler.lib")
#pragma comment(lib, "dxgi.lib")

static const char* kVS =
    "struct V { float4 p : SV_Position; };\n"
    "V main(uint id : SV_VertexID) { V o; o.p = float4((float)id, 0, 0, 1); return o; }\n";

struct Job {
    D3D12_GRAPHICS_PIPELINE_STATE_DESC desc;
    std::vector<uint8_t> ps;
    std::vector<uint8_t> blob;
};

static double qpc_ms(LARGE_INTEGER a, LARGE_INTEGER b, LARGE_INTEGER f) {
    return (double)(b.QuadPart - a.QuadPart) * 1000.0 / (double)f.QuadPart;
}

struct Pool {
    const std::vector<Job>* jobs;
    ID3D12Device* device;
    ID3D12RootSignature* root;
    volatile LONG next;
    int use_blob;
    volatile LONG ok, fail;
};

static DWORD WINAPI worker(LPVOID p) {
    Pool* pool = (Pool*)p;
    for (;;) {
        LONG i = InterlockedIncrement(&pool->next) - 1;
        if (i < 0 || (size_t)i >= pool->jobs->size()) break;
        const Job& job = (*pool->jobs)[(size_t)i];
        D3D12_GRAPHICS_PIPELINE_STATE_DESC desc = job.desc;
        desc.pRootSignature = pool->root;
        desc.PS.pShaderBytecode = job.ps.data();
        desc.PS.BytecodeLength = job.ps.size();
        if (pool->use_blob && !job.blob.empty()) {
            desc.CachedPSO.pCachedBlob = job.blob.data();
            desc.CachedPSO.CachedBlobSizeInBytes = job.blob.size();
        } else {
            desc.CachedPSO.pCachedBlob = NULL;
            desc.CachedPSO.CachedBlobSizeInBytes = 0;
        }
        ID3D12PipelineState* pso = NULL;
        HRESULT hr = pool->device->CreateGraphicsPipelineState(&desc, __uuidof(ID3D12PipelineState), (void**)&pso);
        if (SUCCEEDED(hr) && pso) { pso->Release(); InterlockedIncrement(&pool->ok); }
        else InterlockedIncrement(&pool->fail);
    }
    return 0;
}

static double run_pool(const std::vector<Job>& jobs, ID3D12Device* device, ID3D12RootSignature* root,
                        int threads, int use_blob, int* ok, int* fail) {
    Pool pool = {};
    pool.jobs = &jobs;
    pool.device = device;
    pool.root = root;
    pool.use_blob = use_blob;
    LARGE_INTEGER f, a, b;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&a);
    if (threads < 2) {
        worker(&pool);
    } else {
        HANDLE th[8];
        for (int i = 0; i < threads; i++) th[i] = CreateThread(NULL, 0, worker, &pool, 0, NULL);
        WaitForMultipleObjects(threads, th, TRUE, INFINITE);
        for (int i = 0; i < threads; i++) CloseHandle(th[i]);
    }
    QueryPerformanceCounter(&b);
    *ok = (int)pool.ok;
    *fail = (int)pool.fail;
    return qpc_ms(a, b, f);
}

static int compile_ps(int id, std::vector<uint8_t>* out) {
    char src[512];
    sprintf_s(src, sizeof src,
              "float4 main(float4 p : SV_Position) : SV_Target {\n"
              "  float x = p.x + %d.0001;\n"
              "  [loop] for (int k = 0; k < 80; ++k) x = sin(x) * 1.0001 + p.y;\n"
              "  return float4(x, %d.0, x, 1);\n"
              "}\n",
              id + 1, id + 3);
    ID3DBlob* ps = NULL;
    ID3DBlob* err = NULL;
    HRESULT hr = D3DCompile(src, strlen(src), NULL, NULL, NULL, "main", "ps_5_0", 0, 0, &ps, &err);
    if (FAILED(hr) || !ps) {
        fprintf(stderr, "ps compile %d failed\n%s\n", id, err ? (char*)err->GetBufferPointer() : "");
        if (err) err->Release();
        return 0;
    }
    out->assign((uint8_t*)ps->GetBufferPointer(), (uint8_t*)ps->GetBufferPointer() + ps->GetBufferSize());
    ps->Release();
    if (err) err->Release();
    return 1;
}

static void fill_desc(D3D12_GRAPHICS_PIPELINE_STATE_DESC* d, ID3D12RootSignature* root,
                      ID3DBlob* vs, const std::vector<uint8_t>* ps) {
    memset(d, 0, sizeof *d);
    d->pRootSignature = root;
    d->VS.pShaderBytecode = vs->GetBufferPointer();
    d->VS.BytecodeLength = vs->GetBufferSize();
    d->PS.pShaderBytecode = ps->data();
    d->PS.BytecodeLength = ps->size();
    d->BlendState.RenderTarget[0].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
    d->SampleMask = 0xFFFFFFFFu;
    d->RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
    d->RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
    d->RasterizerState.DepthClipEnable = TRUE;
    d->PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
    d->NumRenderTargets = 1;
    d->RTVFormats[0] = DXGI_FORMAT_R8G8B8A8_UNORM;
    d->SampleDesc.Count = 1;
}

/* Create once with no blob and keep GetCachedBlob. The pipeline is released. */
static int seed_blobs(std::vector<Job>* jobs, ID3D12Device* device) {
    for (size_t i = 0; i < jobs->size(); i++) {
        ID3D12PipelineState* pso = NULL;
        HRESULT hr = device->CreateGraphicsPipelineState(&(*jobs)[i].desc, __uuidof(ID3D12PipelineState), (void**)&pso);
        if (FAILED(hr) || !pso) {
            fprintf(stderr, "seed create %zu failed %08lX\n", i, (unsigned long)hr);
            return 0;
        }
        ID3DBlob* blob = NULL;
        if (FAILED(pso->GetCachedBlob(&blob)) || !blob) {
            pso->Release();
            fprintf(stderr, "no cached blob %zu\n", i);
            return 0;
        }
        (*jobs)[i].blob.assign((uint8_t*)blob->GetBufferPointer(),
                               (uint8_t*)blob->GetBufferPointer() + blob->GetBufferSize());
        blob->Release();
        pso->Release();
    }
    return 1;
}

static void write_u32(FILE* f, uint32_t v) { fwrite(&v, 4, 1, f); }

static int save_cache(const char* path, ID3DBlob* vs, const std::vector<Job>& jobs, const std::vector<uint8_t>& library) {
    FILE* f = NULL;
    if (fopen_s(&f, path, "wb") || !f) return 0;
    uint32_t magic = 0x424F5350u;
    uint32_t count = (uint32_t)jobs.size();
    fwrite(&magic, 4, 1, f);
    fwrite(&count, 4, 1, f);
    uint32_t vs_len = (uint32_t)vs->GetBufferSize();
    write_u32(f, vs_len);
    fwrite(vs->GetBufferPointer(), 1, vs_len, f);
    for (const Job& job : jobs) {
        write_u32(f, (uint32_t)job.ps.size());
        if (!job.ps.empty()) fwrite(job.ps.data(), 1, job.ps.size(), f);
        write_u32(f, (uint32_t)job.blob.size());
        if (!job.blob.empty()) fwrite(job.blob.data(), 1, job.blob.size(), f);
    }
    write_u32(f, (uint32_t)library.size());
    if (!library.empty()) fwrite(library.data(), 1, library.size(), f);
    fclose(f);
    return 1;
}

static int read_exact(FILE* f, void* dst, size_t n) { return n == 0 || fread(dst, 1, n, f) == n; }

/* First creates in this process. --only blob times cached blobs. --only library times a library load. */
static int cold_from_file(const char* path, const char* only, ID3D12Device* device, ID3D12Device1* device1, ID3D12RootSignature* root) {
    FILE* f = NULL;
    if (fopen_s(&f, path, "rb") || !f) { fprintf(stderr, "cannot open %s\n", path); return 1; }
    uint32_t magic = 0, count = 0, vs_len = 0;
    if (!read_exact(f, &magic, 4) || !read_exact(f, &count, 4) || magic != 0x424F5350u || !count || count > 128 || !read_exact(f, &vs_len, 4) || vs_len > 1u << 20) {
        fclose(f); fprintf(stderr, "bad cache header\n"); return 1;
    }
    std::vector<uint8_t> vs(vs_len);
    if (!read_exact(f, vs.data(), vs_len)) { fclose(f); return 1; }
    std::vector<Job> jobs(count);
    for (uint32_t i = 0; i < count; i++) {
        uint32_t ps_len = 0, blob_len = 0;
        if (!read_exact(f, &ps_len, 4) || ps_len > 1u << 20) { fclose(f); return 1; }
        jobs[i].ps.resize(ps_len);
        if (!read_exact(f, jobs[i].ps.data(), ps_len)) { fclose(f); return 1; }
        if (!read_exact(f, &blob_len, 4) || blob_len > 16u << 20) { fclose(f); return 1; }
        jobs[i].blob.resize(blob_len);
        if (!read_exact(f, jobs[i].blob.data(), blob_len)) { fclose(f); return 1; }
        memset(&jobs[i].desc, 0, sizeof jobs[i].desc);
        jobs[i].desc.pRootSignature = root;
        jobs[i].desc.VS.pShaderBytecode = vs.data();
        jobs[i].desc.VS.BytecodeLength = vs.size();
        jobs[i].desc.PS.pShaderBytecode = jobs[i].ps.data();
        jobs[i].desc.PS.BytecodeLength = jobs[i].ps.size();
        jobs[i].desc.BlendState.RenderTarget[0].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
        jobs[i].desc.SampleMask = 0xFFFFFFFFu;
        jobs[i].desc.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
        jobs[i].desc.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
        jobs[i].desc.RasterizerState.DepthClipEnable = TRUE;
        jobs[i].desc.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
        jobs[i].desc.NumRenderTargets = 1;
        jobs[i].desc.RTVFormats[0] = DXGI_FORMAT_R8G8B8A8_UNORM;
        jobs[i].desc.SampleDesc.Count = 1;
    }
    uint32_t lib_len = 0;
    if (!read_exact(f, &lib_len, 4) || lib_len > 64u << 20) { fclose(f); return 1; }
    std::vector<uint8_t> library(lib_len);
    if (!read_exact(f, library.data(), lib_len)) { fclose(f); return 1; }
    fclose(f);
    printf("cold_load count=%u library_bytes=%u\n", count, lib_len);
    fflush(stdout);
    int do_blob = !only || !strcmp(only, "blob");
    int do_lib = only && !strcmp(only, "library");
    if (do_blob) {
        /* One thread only: a second pass would be a driver cache hit, not a cold blob load. */
        int ok = 0, fail = 0;
        double ms = run_pool(jobs, device, root, 1, 1, &ok, &fail);
        printf("cold_cached_blob threads=1 ok=%d fail=%d ms=%.1f per=%.2f\n", ok, fail, ms, ms / count);
        fflush(stdout);
    }
    if (do_lib) {
        if (!device1 || library.empty()) { printf("cold_library_unavailable\n"); return 1; }
        ID3D12PipelineLibrary* lib = NULL;
        HRESULT hr = device1->CreatePipelineLibrary(library.data(), library.size(), __uuidof(ID3D12PipelineLibrary), (void**)&lib);
        int loaded = 0;
        LARGE_INTEGER freq, a, b;
        QueryPerformanceFrequency(&freq);
        QueryPerformanceCounter(&a);
        if (SUCCEEDED(hr) && lib) {
            for (uint32_t i = 0; i < count; i++) {
                wchar_t name[32];
                swprintf_s(name, 32, L"p%d", i);
                D3D12_GRAPHICS_PIPELINE_STATE_DESC desc = jobs[i].desc;
                desc.pRootSignature = root;
                desc.PS.pShaderBytecode = jobs[i].ps.data();
                desc.PS.BytecodeLength = jobs[i].ps.size();
                ID3D12PipelineState* pso = NULL;
                if (SUCCEEDED(lib->LoadGraphicsPipeline(name, &desc, __uuidof(ID3D12PipelineState), (void**)&pso)) && pso) {
                    pso->Release();
                    loaded++;
                }
            }
            lib->Release();
        }
        QueryPerformanceCounter(&b);
        printf("cold_library_load=%d hr=%08lX ms=%.1f per=%.2f\n", loaded, (unsigned long)hr, qpc_ms(a, b, freq), qpc_ms(a, b, freq) / count);
    }
    return 0;
}

int main(int argc, char** argv) {
    int count = 64;
    const char* save_path = NULL;
    const char* load_path = NULL;
    const char* only = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--count") && i + 1 < argc) count = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--save") && i + 1 < argc) save_path = argv[++i];
        else if (!strcmp(argv[i], "--load") && i + 1 < argc) load_path = argv[++i];
        else if (!strcmp(argv[i], "--only") && i + 1 < argc) only = argv[++i];
    }
    if (count < 1) count = 1;
    if (count > 128) count = 128;

    ID3D12Device* device = NULL;
    HRESULT hr = D3D12CreateDevice(NULL, D3D_FEATURE_LEVEL_11_0, __uuidof(ID3D12Device), (void**)&device);
    if (FAILED(hr) || !device) {
        fprintf(stderr, "no D3D12 device %08lX\n", (unsigned long)hr);
        return 1;
    }
    ID3D12Device1* device1 = NULL;
    device->QueryInterface(__uuidof(ID3D12Device1), (void**)&device1);

    ID3DBlob* vs = NULL;
    ID3DBlob* err = NULL;
    if (FAILED(D3DCompile(kVS, strlen(kVS), NULL, NULL, NULL, "main", "vs_5_0", 0, 0, &vs, &err)) || !vs) {
        fprintf(stderr, "vs compile failed\n%s\n", err ? (char*)err->GetBufferPointer() : "");
        return 1;
    }
    ID3DBlob* serialized = NULL;
    D3D12_ROOT_SIGNATURE_DESC rs = {};
    rs.Flags = D3D12_ROOT_SIGNATURE_FLAG_ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT;
    if (FAILED(D3D12SerializeRootSignature(&rs, D3D_ROOT_SIGNATURE_VERSION_1, &serialized, &err)) || !serialized) {
        fprintf(stderr, "root signature failed\n");
        return 1;
    }
    ID3D12RootSignature* root = NULL;
    hr = device->CreateRootSignature(0, serialized->GetBufferPointer(), serialized->GetBufferSize(),
                                     __uuidof(ID3D12RootSignature), (void**)&root);
    if (FAILED(hr) || !root) {
        fprintf(stderr, "CreateRootSignature %08lX\n", (unsigned long)hr);
        return 1;
    }
    if (load_path) {
        int code = cold_from_file(load_path, only, device, device1, root);
        root->Release();
        serialized->Release();
        if (device1) device1->Release();
        device->Release();
        return code;
    }

    /* Three disjoint fresh sets, then the cached-blob replays use the first set. */
    const int groups = 3;
    std::vector<std::vector<Job>> fresh(groups);
    LARGE_INTEGER freq, t0, t1;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&t0);
    for (int g = 0; g < groups; g++) {
        fresh[g].resize(count);
        for (int i = 0; i < count; i++) {
            int id = g * count + i;
            if (!compile_ps(id, &fresh[g][i].ps)) return 1;
            fill_desc(&fresh[g][i].desc, root, vs, &fresh[g][i].ps);
        }
    }
    QueryPerformanceCounter(&t1);
    printf("shader_compile count=%d groups=%d ms=%.1f\n", count, groups, qpc_ms(t0, t1, freq));
    fflush(stdout);
    {
        /* One discarded create so the timed rows are not paying for driver startup. */
        std::vector<uint8_t> warm_ps;
        if (!compile_ps(100000, &warm_ps)) return 1;
        D3D12_GRAPHICS_PIPELINE_STATE_DESC warm_desc;
        fill_desc(&warm_desc, root, vs, &warm_ps);
        ID3D12PipelineState* warm_pso = NULL;
        device->CreateGraphicsPipelineState(&warm_desc, __uuidof(ID3D12PipelineState), (void**)&warm_pso);
        if (warm_pso) warm_pso->Release();
    }

    const int threads[] = {1, 2, 4};
    for (int g = 0; g < groups; g++) {
        int ok = 0, fail = 0;
        double ms = run_pool(fresh[g], device, root, threads[g], 0, &ok, &fail);
        printf("fresh threads=%d ok=%d fail=%d ms=%.1f per=%.2f\n", threads[g], ok, fail, ms, ms / count);
        fflush(stdout);
    }
    if (!seed_blobs(&fresh[0], device)) return 1;
    {
        /* Same shaders again, still with no blob, so a warm driver cache is visible beside the blob rows. */
        int ok = 0, fail = 0;
        double ms = run_pool(fresh[0], device, root, 1, 0, &ok, &fail);
        printf("replay_noblob threads=1 ok=%d fail=%d ms=%.1f per=%.2f\n", ok, fail, ms, ms / count);
        fflush(stdout);
    }

    for (int t : threads) {
        int ok = 0, fail = 0;
        double ms = run_pool(fresh[0], device, root, t, 1, &ok, &fail);
        printf("cached_blob threads=%d ok=%d fail=%d ms=%.1f per=%.2f\n", t, ok, fail, ms, ms / count);
        fflush(stdout);
    }

    std::vector<uint8_t> library_serial;
    if (device1) {
        ID3D12PipelineLibrary* lib = NULL;
        hr = device1->CreatePipelineLibrary(NULL, 0, __uuidof(ID3D12PipelineLibrary), (void**)&lib);
        int stored = 0;
        if (SUCCEEDED(hr) && lib) {
            for (int i = 0; i < count; i++) {
                ID3D12PipelineState* pso = NULL;
                D3D12_GRAPHICS_PIPELINE_STATE_DESC desc = fresh[0][i].desc;
                desc.pRootSignature = root;
                desc.PS.pShaderBytecode = fresh[0][i].ps.data();
                desc.PS.BytecodeLength = fresh[0][i].ps.size();
                desc.CachedPSO.pCachedBlob = fresh[0][i].blob.data();
                desc.CachedPSO.CachedBlobSizeInBytes = fresh[0][i].blob.size();
                if (FAILED(device->CreateGraphicsPipelineState(&desc, __uuidof(ID3D12PipelineState), (void**)&pso)) || !pso)
                    continue;
                wchar_t name[32];
                swprintf_s(name, 32, L"p%d", i);
                if (SUCCEEDED(lib->StorePipeline(name, pso))) stored++;
                pso->Release();
            }
            size_t bytes = lib->GetSerializedSize();
            std::vector<uint8_t> serial(bytes ? bytes : 1);
            QueryPerformanceCounter(&t0);
            hr = bytes ? lib->Serialize(serial.data(), bytes) : E_FAIL;
            QueryPerformanceCounter(&t1);
            printf("library_store=%d serialize_bytes=%zu serialize_ms=%.1f\n", stored, bytes, qpc_ms(t0, t1, freq));
            if (SUCCEEDED(hr) && bytes) library_serial = serial;
            lib->Release();
            lib = NULL;
            if (SUCCEEDED(hr) && bytes) {
                hr = device1->CreatePipelineLibrary(serial.data(), bytes, __uuidof(ID3D12PipelineLibrary), (void**)&lib);
                int loaded = 0;
                QueryPerformanceCounter(&t0);
                if (SUCCEEDED(hr) && lib) {
                    for (int i = 0; i < count; i++) {
                        wchar_t name[32];
                        swprintf_s(name, 32, L"p%d", i);
                        D3D12_GRAPHICS_PIPELINE_STATE_DESC desc = fresh[0][i].desc;
                        desc.pRootSignature = root;
                        desc.PS.pShaderBytecode = fresh[0][i].ps.data();
                        desc.PS.BytecodeLength = fresh[0][i].ps.size();
                        ID3D12PipelineState* pso = NULL;
                        if (SUCCEEDED(lib->LoadGraphicsPipeline(name, &desc, __uuidof(ID3D12PipelineState), (void**)&pso)) && pso) {
                            pso->Release();
                            loaded++;
                        }
                    }
                }
                QueryPerformanceCounter(&t1);
                printf("library_load=%d ms=%.1f per=%.2f\n", loaded, qpc_ms(t0, t1, freq), qpc_ms(t0, t1, freq) / count);
                if (lib) lib->Release();
            } else {
                printf("library_serialize_failed %08lX\n", (unsigned long)hr);
            }
        } else {
            printf("pipeline_library_unavailable %08lX\n", (unsigned long)hr);
        }
        device1->Release();
    } else {
        printf("device1_unavailable\n");
    }
    fflush(stdout);
    if (save_path) {
        int saved = save_cache(save_path, vs, fresh[0], library_serial);
        printf("saved=%d path=%s\n", saved, save_path);
    }
    root->Release();
    serialized->Release();
    vs->Release();
    device->Release();
    return 0;
}
