# DXC preparation and packaging

DXC is the default for gameplay and preparation in 0.2.5. Set
`RSX_SHADER_COMPILER=fxc` to restore FXC, or `=dxc` to select DXC explicitly.
Use the same choice for the launcher and helper. The interpreter remains
default-off; enabling either `RSX_SHADER_INTERP` or `RSX_SHADER_INTERP_VP`
with `1` or `force` keeps guest shaders on FXC because its
generic FXC stages cannot share a pipeline with DXIL stages.

The user accepted the in-game visual checks and requested this default in
Phase 232. The synthetic GPU harness's numeric differences, fixed game-frame
comparison and other GPU vendors remain documented limits of the evidence.

## Existing FXC caches

Preparing DXC shaders does **not** clear FXC caches. Compiler choice, the engine
and compiler DLL identity distinguish preparation generations. Reusable files
are verified and copied into the new generation; their source stays intact.
The selected-cache pointer changes only after preparation succeeds. Cancel or
failure keeps the prior selection. An older FXC cache cannot satisfy DXC shader
keys, but remains available for rollback or later reuse. No cache deletion was
added as part of branch/worktree cleanup; player storage is separate.

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
as follow-up rendering coverage.

See progress Phase 231 for preparation, frozen-worker and packaging validation.
The earlier Phase 227 compile timings are retained as historical measurements;
they predate the strictness flag and are not a new full-preparation speed claim.


## Combined race prewarm

The 0.2.5 helper also writes the race-pipeline bundle after its membership lists
are final. The reader accepts startup reordering of the same members, verifies
the pack's internal checksum and exact membership, and follows the live priority
order. Changes in membership still fall back to the individual files.
`RSX_RACE_PREWARM_PACK=0` restores that per-file path. This is independent of the
compiler selection and does not remove either compiler's shader caches.

## Upgrade notice and optional cleanup

Configured players get one DXC migration offer before the game starts, even with
background preparation enabled. It explains that FXC shaders cannot serve DXC,
offers **Prepare now** or **Skip and play**, and keeps the old cache. A current
preparation suppresses the offer; answering or closing it records
`prepare-offer-dxc-v1.done` in player storage. Fresh setup uses its existing flow.
`GT5P_PREPARE_DXC_OFFER=0` disables this migration offer; `GT5P_PREPARE_OFFER=0`
continues to disable all preparation offers/background preparation. Explicit FXC
and interpreter users keep the existing preparation flow.

After full preparation succeeds and selects its new cache, the launcher offers to
remove older **completed preparation generations**, displaying their approximate
total size in GB. **No** is the default. It warns that deletion removes their
learned shaders and that FXC/older-renderer rollback will require preparation again.
The selected generation, unfinished work, ordinary `shadercache`, saves and
settings are kept. This includes older DXC settings generations, not just FXC.
No cleanup is scheduled on failure, cancellation or interpreter-only preparation.

Foreground preparation offers cleanup after its progress window closes.
Background preparation schedules it for the next normal launch, before gameplay;
it never opens a cleanup dialog during play. The answer is recorded once per
selected generation (`prepare-cleanup-<generation>.done`). A pending offer lives
in `prepare-cleanup-pending.txt`; it must match the completed current selection.
`GT5P_PREPARE_CLEANUP=0` disables scheduling and showing cleanup offers.

Cleanup requires the launcher's storage lease and no running game. It checks
bounded storage-relative generation names, complete checkpoints, regular files,
hard links and junctions, and acquires each old generation's preparation lock
before deleting. Locked/incomplete/unknown generations are not offered; unsafe
trees abort cleanup. It rechecks selection and targets after the user answers.
Cleanup failure leaves the selected preparation usable and reports a notice.
