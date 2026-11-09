# DXC preparation and packaging

`RSX_SHADER_COMPILER=dxc` selects DXC for both gameplay and preparation. Leave it
unset, or set `RSX_SHADER_COMPILER=fxc`, for the existing FXC path. Set the same
choice in the environment that starts the launcher and helper. The interpreter
remains default-off; `RSX_SHADER_INTERP=1` keeps guest shaders on FXC because its
generic FXC stages cannot share a pipeline with DXIL stages.

DXC is still opt-in. The developer GPU harness found numeric differences beyond
its threshold, and fixed in-game frame parity and other GPU vendors remain open.
Compilation success and a visually plausible race do not establish parity.

## Compiler and cache identity

The pinned compiler is Microsoft's DirectX Shader Compiler v1.8.2502. Run
`python scripts/get_dxc.py` before building. It verifies the release archive,
x64 compiler and signer DLLs, and all three license files by SHA-256. CI invokes
it automatically. CMake copies both DLLs beside `gt5p.exe`; the strict player
packager checks those copies against the pinned distribution and includes its
LLVM/NCSA, MIT and Microsoft notices plus the version/source manifest.

The game loads DXC from its own directory. The player helper uses that same
`runtime/dxcompiler.dll`; source developer tools can select a DLL with
`GT5P_PREPARE_DXC_LIBRARY`. Offline engine processes and vertex workers inherit
an explicit compiler choice, even after renderer environment sanitization.

DXC uses `vs_6_0`/`ps_6_0`, `-HV 2018` and `-Gis`. Strict floating-point rules
preserve the output NaN scrub that DXC otherwise optimized away. Both helper and
renderer source keys include the shader target and the IEEE strictness flag
(`0x2000`), so neither FXC nor the older non-strict Phase 227 DXC bytecode can be
mistaken for current DXC output. Native keys continue to hash actual bytecode.
Preparation identities also include the chosen compiler and compiler DLL hash.
A different choice creates a separate generation and preserves prior caches.

Missing DLLs make an explicitly requested DXC preparation fail early; gameplay
falls back to FXC with a diagnostic. The port's own helper shaders stay on FXC.
For DXC, guest resource arrays are split into individual declarations in the
engine before compilation, matching the existing root signature's bindings.

## Rendering check and limits

`scripts/test/compiler_parity.cpp` compiles locally captured HLSL with both
compilers and runs it on the hardware D3D12 device with identical synthetic
inputs. It checks vertex outputs and pixel target/depth values, including
coverage. Captured HLSL and all resulting bytecode belong under ignored scratch
storage. Build and invoke the harness through the machine-wide test lock.

The recovered November 6 run covers 264 GPU-fetch vertex shaders and 1,073 pixel
shaders from High Speed Ring and a dealership, with two trials. Eighteen
CPU-fetch vertex shaders were not run. Both sides compile successfully and
pixel coverage agrees. Among 74,579,968 pixel values, 9,736 exceed the harness's
1/1024 relative threshold (maximum relative difference 1.32); 53 pixel shaders
are flagged. Vertex comparisons flag 40 shaders, including 343 one-sided NaNs,
32 infinities, and one finite value over the threshold. These random inputs
include extreme values and do not reproduce a real game draw.

An FXC-versus-FXC skip-optimization control also differs, but less: 1,282 pixel
values exceed the threshold and 17 pixel shaders are flagged. This control does
not prove the additional DXC differences harmless. Both harness runs return 1
because their threshold was exceeded; neither is a parity pass. Fixed game
frames, CPU-fetch inputs and AMD/Intel/other drivers need separate acceptance
before changing the compiler default.

See progress Phase 231 for preparation, frozen-worker and packaging validation.
The earlier Phase 227 compile timings are retained as historical measurements;
they predate the strictness flag and are not a new full-preparation speed claim.
