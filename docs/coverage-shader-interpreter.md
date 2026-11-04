# RSX shader interpreter (ubershader) fallback

Design for a generic, precompiled fragment (then vertex) shader that runs an
RSX program from a GPU buffer. A draw whose specialized DXBC is still
compiling renders immediately. The specialized shader keeps compiling on the
existing background workers and replaces the interpreter on a later frame.

This is the Dolphin "ubershader" idea and the same shape as RPCS3's "async
with shader interpreter" mode. RPCS3 is GPLv2: the semantics below were read
from this tree's decoder and from public NV40 field descriptions. No RPCS3
source was copied.

Default is off. `RSX_SHADER_INTERP=0` (unset) must leave pipeline keys, HLSL,
DXBC and pixels unchanged. Unvalidated behaviour stays on an environment
switch.

## Status (Phase 216, 2026-11-05)

Phase 216 closed four of the five gaps that kept `RSX_SHADER_INTERP=1` from being a player default and
measured it against the async baseline on cold and warm caches. Everything stays default-off; the sections
below that describe the earlier state are kept as the record and are corrected here.

What was wrong and what changed (all in `patches/ps3recomp-shader-interp.patch`, the overlay):

1. **ACURA wordmark (was red 13 vs 39): fixed. The cause was a missing behaviour, not gamma.** A stencil mask
   pass that the renderer redirects to a colour target (`stencil` bit 26, the title's glyph/shape mask) computes
   its pass operation as a blend from a source of exactly 1, so the specialized shader's colour output is forced
   to `(1,1,1,1)` (the `FP_ONE` block in `vp_get_fp_pso`). The interpreter wrote the program's own colour into the
   mask instead. It now sets header flag bit 11 (`2048`) for a single-target draw with that stencil bit and the
   epilogue forces `o0 = 1` before the alpha test, as the specialized path does. Evidence: the same
   `RSX_SHADER_INTERP_AB` alternating-frame capture, `force` fragment interpreter, same save, same warm cache,
   crop 1015,110-1215,145 (the wordmark), per-channel maximum: Phase 215 overlay engine, interpreted frames
   red 13, green 24-28, blue 53-60 against specialized frames red 39, green 48-51, blue 71-76; Phase 216 engine,
   interpreted red 39-40, green 49-51, blue 71-76 against specialized red 39, green 48-50, blue 70-75 (the one-level
   differences follow the fade, which advances between adjacent frames; the specialized frames step the same way).
   The whole-frame mean absolute difference of adjacent pairs is 0.8-1.04 / 255 (motion included),
   unchanged from before, and the title crop differs by at most 2. `RSX_SHADER_INTERP_MASK_ONE=0` is the rollback (by construction restores the Phase 215 behaviour; not re-run) -- the
   earlier gamma-read and export-count experiments were looking in the wrong
   place and stay reverted.
2. **`tex_dz` (depth-copy) and `tex_mip` (stacked-mip) draws: interpreted.** Two header words carry the depth
   units and crossbar (`hdr[9]`: bits 0-3 units, 8-19 crossbar selectors) and the mip units (`hdr[10]`). The
   shader reproduces the specialized `rsx_dz<u>` byte unpacking (`rsx_i_dz`) and the `rsx_mip<u>` stacked-level
   fetch for TXL (`rsx_i_mip`, `rsx_i_mipuv`: clamp, per-level origin/scale from `rsx_texscale`, two-level blend,
   gamma per tap). Depth-copy units keep sRGB decode off, as in the specialized shader. Evidence: the gap counter
   (`[interp] ... gap`) that was 780 (dealership) and 3,141 (High Speed Ring) in Phase 215 is 0 in every run
   below. There is no offline equivalence proof for these two paths (the WARP harness compares the decompiler
   alone, which does not emit them); validation is the in-game alternating captures. `RSX_SHADER_INTERP_DZMIP=0`
   restores the skip.
3. **Replay vertex omissions rising 713 -> 2,028 with the vertex interpreter: explained, gone.** The Phase 215
   High Speed Ring run had `fallback = gap = 3,141`, and 2,028 + 1,113 (replay vertex + replay fragment
   omissions) is exactly 3,141: they were the `tex_dz`/`tex_mip` gap draws, whose vertex shader was also pending,
   so neither interpreter could take them. With gap 2 closed the interpreter-only synchronous run has 0 replay
   vertex, 0 replay fragment and 0 recording-time vertex omissions. (The baseline's own replay vertex count is
   681; the raise was not a vertex-interpreter defect.) New diagnostics split `vp_interp_stage` misses into
   `nohash`/`unseen`/`not_vp`/`lost` in the `[interp-vp]` line; they were all zero.
4. **Interpreter pipelines were created on first use on the replay thread and never saved (gap 1): persisted
   and moved off the replay thread, behind two switches.** `RSX_SHADER_INTERP_PSO_DISK=1` stores each driver
   blob as `ipso_<hash>.bin` (separate prefix, so tools that enumerate `pso_*.bin` do not see them) under the
   same size/checksum validation as the guest blobs; the key hashes both shaders, all native state and the
   interpreter root signature's serialized bytes (`interp_rs_hash`, so a layout change cannot reuse a blob).
   `RSX_SHADER_INTERP_PSO_ASYNC=1` queues a missing pipeline to one below-normal worker (ring of 512
   descriptor copies; shader blobs are held by the slot, the root signatures live to shutdown) and treats the
   draw as pending until it is ready, exactly like a specialized pipeline still compiling. New counters on the
   `[interp-pso]` line: replay-thread time inside `CreateGraphicsPipelineState` (`block_ms`, `block_max_ms`),
   queued, queue-full, draws that found their pipeline pending, disk hits/saves/rejects.
   **Not done:** observed pipelines are not recorded for startup creation in the background. The existing
   `RSX_SHADER_INTERP_PREWARM=1` still precreates only the generic-vertex-shader pairs (133 classes) and
   therefore only helps paired mode; in fragment-only `=1` the vertex shader is the specialized one and is
   unknown at startup. Persisted blobs make the second launch cheap (see the disk-hit counts), but the first
   launch still pays each pipeline once, on the worker, not on the replay thread. Creating the interpreter
   pipelines during preparation (the starter has the vertex programs and native state) is the remaining step.
5. **p99 on the cold race: not fixed (gap 5, open).** See the measurements.

### Phase 216 measurements

Private engine built by `scripts/test/interp_private_build.py` from the overlay at this commit (Phase 215 main
patch underneath; the specialized decompiler objects are the v0.2.3 reference objects, so specialized shader
text is the older, not the Phase 215, text), 720p, MSAA default, `RSX_SSAA=0`, private empty or reused caches,
one locked run per cell, same save seed (`9161393d2439d610`), `GT5P_PRESENT_PROF=1`. "off" is the new engine with
both switches 0 (the async baseline). "interp" is `RSX_SHADER_INTERP=1 RSX_SHADER_INTERP_VP=1`; "interp+pso" adds
`RSX_SHADER_INTERP_PSO_DISK=1 RSX_SHADER_INTERP_PSO_ASYNC=1`. FrameTest is `race.ps1 -FrameTest` (60 s after a
45 s delay, foreground required). Single runs on a shared workstation: differences of a few percent are within
run-to-run variation (the Phase 215 note recorded 23.1% late and p99 151.8 ms for what is the same cold-HSR
baseline; this session's baseline was 11.5% and 91.8 ms), so compare mechanisms and counters, not decimals.

| Route / cache | Mode | FPS | p99 ms | max ms | >20 ms | Replay omissions (fp / vp), recording vp |
| --- | --- | --- | --- | --- | --- | --- |
| HSR cold | off | 50.8 | 91.8 | 288 | 11.5% | 812,595 / 681, 829,624 |
| HSR cold | interp | 51.3 | 88.4 | 955 | 9.3% | 0 / 0, 0 |
| HSR cold | interp+pso | 52.4 | 86.7 | 235 | 9.2% | 3,873 / 6,730, 0 |
| HSR warm | off | 59.8 | 18.0 | 54.0 | 0.3% | 42,734 / 6 |
| HSR warm | interp+pso | 59.9 | 18.0 | 20.3 | 0.1% | 3,203 / 1 |
| Daytona cold | off | 52.3 | 83.1 | 166 | 8.3% | 1,035,919 / 378, 542,898 |
| Daytona cold | interp+pso | 51.3 | 100.2 | 184 | 7.5% | 4,296 / 1,562, 0 |
| Daytona warm | off | 56.0 | 40.0 | 193 | 10.2% | 57,882 / 0, 45 |
| Daytona warm | interp+pso | 59.5 | 22.2 | 71.3 | 1.2% | 3,844 / 4, 0 |

Interpreter pipeline creation (cold HSR): synchronous `interp` blocked the replay thread for 1,926 ms in total
(461 pipelines, 900 ms the largest, the 955 ms frame in the table); with PSO async the replay thread blocked for
0 ms (462 pipelines, 2,817 ms on the worker, 688 ms the largest, max frame 235 ms). Warm HSR: 143 of 168
requested pipelines loaded from `ipso_*.bin` (25 new, saved); warm Daytona 139 of 183; warm dealership 102
of 104; no rejected blob in any run. The omissions that remain with PSO async are draw attempts left out
while their interpreter pipeline was queued (`wait_draws`: 10,638 cold HSR, 4,048 cold dealership), about
0.5-2% of the draw attempts the baseline leaves out.

Dealership (cold, 12 shots, inspected): the off run's shots show missing materials and background for the first
seconds (cars as dark grey slabs, no blue backdrop; replay omissions 258,009 / 648 plus 555,867 recording-time);
the interp+pso run's shots at the same moments show both cars with paint, glass, reflections, backdrop and text
(omissions 2,713 / 1,320, recording-time 0). Frame cost: the cold dealership windows at the page's first
appearance are GPU-bound while many programs are interpreted (60-63 presents per 5 s, GPU 17-27 ms, against
98-128 presents and 5.6 ms for the baseline, which simply leaves the draws out); settled windows are equal
(150 presents, 4.9-7 ms, in both). Warm dealership omissions 23,347 (off) against 1,881 (interp+pso).

What the table says honestly: warm caches, `=1` with PSO persistence is equal or better in every cell
(Daytona warm clearly: p99 40.0 -> 22.2 ms, 10.2% -> 1.2% late, mostly because the baseline's pending native
pipelines left draws out and interpreted draws kept the frame filled while a pipeline finished). Cold caches: the
share of late frames is lower, the pictures are complete instead of missing most materials, and the worst single
frame is no longer a driver call; p99 is not reduced beyond noise (HSR 91.8 -> 86.7, Daytona 83.1 -> 100.2).

Why p99 stays high on cold caches (gap 5): the per-5-second `[present-prof]` windows show two different cold
costs. The baseline's late frames come from compile completions and first-time pipeline/texture work with many
draws missing. With the interpreter the late frames are GPU-bound windows (34-60 presents per 5 s, GPU 36-54 ms)
at the moments when many unseen programs are on screen at once, for example the first seconds after the race
starts; the interpreter's per-pixel cost, about 20x the specialized shader's in `force` (see below), is the
price of drawing those pixels at all. Removing it needs a cheaper interpreter (below), not another switch.

### Remaining work, in priority order

1. **Cheaper interpreter pixel shader.** Candidates, all untested: size the `r[48]`/`h[48]` register files by the
   program's highest used index (the Phase 215 specialized change, here as shader variants: 16/32/48), skip the
   96-register zero fill, and replace the per-instruction 22-bit source decode by a pre-decoded form. Each
   variant multiplies the embedded generic bytecode (about 20-27 s of D3DCompile per variant today).
2. **Interpreter pipelines at preparation time** (starter vertex programs x native classes), so even the first
   launch loads blobs instead of building them on the worker.
3. A foreground-held, repeated cold HSR/Daytona series (three or more pairs) to put an interval on the p99
   difference; this session has one pair per cell and the Phase 215 baseline varied by 60 ms.
4. Epilogue pixel equivalence for the rest of the epilogue flags (WPOS host-pixel noise sample on small
   dither textures differs in form from the specialized shader's and was not examined) and `tex_dz`/`tex_mip`
   equivalence beyond the inspected captures.

### Proposed default change (not applied)

Not applied by this phase. If accepted, the change touches exactly:

- `fp_interp_cfg()` and `vp_interp_cfg()` (`rsx_fp_interp_backend.inc`, `rsx_vp_interp_backend.inc`): treat an
  unset `RSX_SHADER_INTERP` / `RSX_SHADER_INTERP_VP` as `1` (keep `0` as the rollback).
- `interp_pso_disk()` and `interp_pso_async()`: unset means on (keep `0` as the rollback).
- `src/main.cpp`, which sets the other renderer defaults (`RSX_SHADER_ASYNC`), is where a player default would be
  set instead if the engine default should stay off for development.
- The interpreter generic DXBC (embedded, 1.2 MB with these variants) must be linked in the release engine:
  `scripts/test/interp_private_build.py` is a private-build recipe only; the CI build would need the same
  embed step (or the 20+ s per variant D3DCompile at first run would block startup).
- The F1 settings page and `gt5p_settings.toml` have no interpreter entry; one is needed if it becomes a player
  choice.
- No pipeline key, shader text, cache format or starter change; the interpreter adds `ipso_*.bin` files beside
  the existing cache entries, which the cache-size/cleanup code does not yet count.

Recommendation: the data supports making `=1` with persisted, background pipelines the default only for
warm-cache play (equal or better in all three routes, with far fewer left-out draws). Cold-cache play trades
missing materials for GPU-bound windows and does not lower p99 beyond noise in this single-run set; accept that
trade explicitly (or wait for the cheaper pixel shader) before shipping it.

## Status (2026-11-04, superseded where Phase 216 says so)

The fallback works in game and stays off. `=1` draws with the interpreter
only while a specialized shader or its driver pipeline is pending, then the
specialized pipeline replaces it. `force` runs the interpreter for every
accepted draw. That mode is about 20x slower on the GPU: dealership about
77 ms against 3.3 ms, High Speed Ring about 45-88 ms against 8-14 ms
(`RSX_SSAA=0`, earlier locked runs). Only `=1` is a sensible play switch.

What the cold measurements show:

- Dealership, empty private cache, both stages `=1` (locked
  `interp-cold-dealer-pair-r2`, not re-run here). Replay fragment omissions
  fell from 408,704 to 91. Replay vertex omissions fell from 837 to 42.
  Recording-time GPU-fetch vertex omissions fell from 788,510 to 0.
- High Speed Ring FrameTest, separate empty private caches, same save seed
  `9161393d2439d610`, 720p, MSAA 2, SSAA off. Foreground activation was
  accepted (the run was not rejected). The route and settings match; the
  camera and traffic do not, so this is not a matched-frame speedup.
  - Baseline, both switches `0` (`interp-hsr-ft-base-b`): 2,723 frames over
    62.9 s, 43.3 FPS, interval median 17.0 ms, p99 151.8 ms, max 549.3 ms,
    23.1% of intervals over 20 ms. The once-per-second title sample median
    was 51.23 fps. Final omissions: replay vertex 713, replay fragment
    686,163, recording vertex 730,573. The last intro shot is sky, HUD and
    a few floating tires. Later on-track shots show the circuit, cars and HUD.
  - `RSX_SHADER_INTERP=1` and `RSX_SHADER_INTERP_VP=1`
    (`interp-hsr-ft-interp`): 3,046 frames over 62.4 s, 48.8 FPS, median
    16.7 ms, p99 123.0 ms, max 524.7 ms, 11.5% over 20 ms. Title-sample
    median 59 fps. Omissions: replay vertex 2,028, replay fragment 1,113,
    recording vertex 0. Interpreter counters: 269,880 draws, fallback = gap
    = 3,141, reject 0, arena 0, PSO failures 0, 444 PSOs, 27,831 ms total
    driver creation, 837 ms maximum. Settled GPU windows were about
    4.3-5.0 ms mean, in the same band as the baseline's settled windows.
    The rolling-start shot shows the bridge, cars, Bridgestone banners and
    grandstand. On-track shots show cars, the mirror, barriers and HUD.
- `RSX_SHADER_INTERP_PAIR` was not part of this race pair. The dealership
  paired-prewarm run already showed it is not a frame-time win. The
  checkpoint's race comparison is independent `=1`.

It is not fit to become a default. Cold `=1` removes most missing fragment
draws and the sky-only rolling start, and it cuts the share of late frames,
but p99 is still 123 ms, one interpreter PSO took 837 ms, and those PSOs are
not written to the disk cache. Known `tex_dz` / `tex_mip` draws still keep
the specialized shader (the 3,141 gaps). Replay vertex omissions were not
eliminated. The dealership ACURA wordmark is still red 13 on interpreted
frames and 39 on specialized frames; gamma-read off and an uncommitted MRT
export-count change did not fix it, and that MRT change was reverted.
Epilogue pixel equivalence is unproven. Best-lap and last-lap fields are
dashes in both HSR runs, so that is not an interpreter-only defect.

Switches. Unset leaves the new draw paths off. `EMBED` defaults to the
embedded bytecode, and gamma decode stays on unless `GAMMA_READ=0`.

| Switch | Effect |
| --- | --- |
| `RSX_SHADER_INTERP=0` / `1` / `force` | Fragment interpreter off, pending-only, or every accepted draw |
| `RSX_SHADER_INTERP_VP=0` / `1` / `force` | Same three modes for the vertex interpreter |
| `RSX_SHADER_INTERP_PAIR=1` | While either stage or driver pipeline is pending, interpret both. Requires both stage switches |
| `RSX_SHADER_INTERP_PREWARM=1` | Create the starter native-class pipelines at device init. Requires the embedded class list |
| `RSX_SHADER_INTERP_EMBED=0` | Compile the generic shaders from the private cache instead of the embedded DXBC |
| `RSX_SHADER_INTERP_STATS=1` | Print `[interp-pending]` every five seconds |
| `RSX_SHADER_INTERP_LOG=1` | Log interpreter pipeline keys as they are created |
| `RSX_SHADER_INTERP_AB=1` | Alternate specialized and interpreted frames for captures |
| `RSX_SHADER_INTERP_GAMMA_READ=0` | Diagnostic: skip interpreter texture gamma decode. Does not restore the wordmark |
| `RSX_SHADER_INTERP_ARENA_KB`, `RSX_SHADER_INTERP_VP_ARENA_KB` | Raise the program arena (256..16384) |
| `RSX_SHADER_INTERP_OPT`, `RSX_SHADER_INTERP_VP_OPT` | D3DCompile optimization level for a non-embedded build |
| `RSX_SHADER_INTERP_VP_BASE=1` | Subtract the vertex program's start slot. Default matches the specialized shader |
| `RSX_SHADER_INTERP_PSO_DISK=1` | Phase 216: persist each interpreter pipeline's driver blob as `ipso_<hash>.bin` in the shader cache and reuse it when it validates. Default off |
| `RSX_SHADER_INTERP_PSO_ASYNC=1` | Phase 216: create interpreter pipelines on one below-normal worker; the draw is left out (pending) until its pipeline is ready, so the replay thread never blocks in the driver. Default off |
| `RSX_SHADER_INTERP_DZMIP=0` | Phase 216: restore the old skip of depth-copy (`tex_dz`) and stacked-mip (`tex_mip`) draws (they then keep the specialized shader and count as gaps). Default is to interpret them |
| `RSX_SHADER_INTERP_MASK_ONE=0` | Phase 216 diagnostic: stop forcing a redirected stencil-mask pass's colour to 1.0 (restores the ACURA wordmark defect) |

Build-only: `INTERP_EMBED_DXBC=0` links without the embedded payload.
`INTERP_SKIP_PRECOMPILE=1` reuses generic bytecode whose source key still matches.

Stage 1 offline status (2026-11-03): the fragment encoder and the ps_5_1
interpreter match `rsx_fp_decompile_buffered` on WARP. Three synthetic
programs and 80 catalogue programs (30 ALU, 20 branch, 20 textured, 10
predicated) plus 5 of those textured programs resampled as cube unit 0 all
compared equal (max abs error 0, tolerance 1e-4). Epilogues were off for
that compare. The instruction image and register file below are the ones
that comparison used. An earlier draft of this section described a
different packing and a 64-wide register file; that draft was not what ran.

Stage 1b (2026-11-04) wires that interpreter into the D3D12 replay path.
The overlay is `patches/ps3recomp-shader-interp.patch`, applied after
`patches/ps3recomp-4e8f3ca8-local.patch`. The private build is
`scripts/test/interp_private_build.py`. The 16 input/sample/target
variants are compiled once by `scripts/test/fp_interp_precompile.c`
(D3DCompile flags 0) into the private shader cache. In-game `force`
screenshots are below. Later vertex and pending-only results, including
failed acceptance checks, are recorded below.

Runtime facts below are from a private copy of ps3recomp `4e8f3ca8` plus
`patches/ps3recomp-4e8f3ca8-local.patch` (`libs/video/rsx_fp_decompiler.c`,
`rsx_vp_decompiler.c`, `rsx_d3d12_backend.c`). The asset-catalogue counts are
from a read-only walk of `shadercache/library-v1/all` on 2026-11-03 (8,142
raw `.fp` payloads, each named by its SHA-256). No program bytes are stored
here.

## Why a draw disappears today

`RSX_SHADER_ASYNC=1` (GT5P's "Precompile shaders", on from `src/main.cpp`)
compiles a missing DXBC on a worker pool. `d3d_compile_async_h` returns
`E_PENDING` until `shadercache/<hash>.dxbc` appears. `vp_get_fp_pso` then
sets `s_fp_pending` and returns NULL. The replay loop records that draw as
left out (`FR->shader_pending = 1`) and continues. The same happens when the
vertex shader's `vs_idx` is `VS_PENDING`, and when `RSX_PSO_ASYNC` has the
driver pipeline queued (`pso_queue_pending`).

`RSX_SHADER_ASYNC_HOLD` is off by default, so the frame is presented with
those draws missing (pop-in). `=1` holds the last complete picture for at
most 3 seconds and is known to reintroduce the Phase 63 ring-space deadlock.
`RSX_PSO_ASYNC` follows shader async unless set to `0`. Driver PSO creation
is about 4 ms; a fragment compile is about 50 ms and a GPU-fetch vertex
compile about 0.3 s (measured on the 5,669-record starter, 2026-11-03).

The interpreter removes the fragment-compile wait. It does not remove a
missing vertex shader (stage 2) or an unseen *interpreter* pipeline. Those
interpreter pipelines depend only on native output state, so they can be
created before the first draw.

## Fragment instruction encoding

Each instruction is 16 bytes, four big-endian words whose 16-bit halves are
swapped (`rsx_fp_read_word`). A source whose register type is CONST (2) is
followed by one inline float4; every CONST operand in that instruction
shares the slot. `PROGRAM_END` (word 0 bit 0) terminates the program.
`rsx_fp_program_size` is the length the cache hashes.

Word 0 (OPDEST):

| Field | Bits | Decoder macro |
| --- | --- | --- |
| end | 0 | `FP_END` |
| dest index | 1..6 | `FP_OUT_REG_*` (0..63) |
| dest is H file | 7 | `FP_OUT_HALF` |
| condition write | 8 | `FP_COND_WRITE` |
| write mask X Y Z W | 9..12 | `FP_OUT_MASK_SHIFT` |
| input source | 13..16 | `FP_INPUT_SRC_*` |
| texture unit | 17..20 | `FP_TEX_UNIT_*` |
| `_bx2` / EXP_TEX | 21 | `FP_TEX_EXPAND` |
| opcode | 24..29 | `FP_OPCODE_*` (6 bits) |
| no dest write | 30 | `FP_OUT_NONE` |
| saturate result | 31 | `FP_OUT_SAT` |

An empty write mask is treated as `xyzw`.

Words 1, 2, 3 are sources 0, 1, 2:

| Field | Bits |
| --- | --- |
| register type | 0..1 (0 temp, 1 input, 2 const) |
| register index | 2..7 |
| source from H file | 8 |
| swizzle X Y Z W | 9..16, 2 bits each, 0=x .. 3=w |
| negate | 17 |

Absolute value is outside the source word: source 0 in word 1 bit 29, source
1 in word 2 bit 18. Source 2 has no absolute bit in this decoder.

Other fields this decoder reads:

- Execution predicate, word 1 bits 18..20 (`exec_if_lt/eq/gr`). All three set
  means unconditional. None set means the instruction never writes. Otherwise
  the result is selected per component against the condition register.
- Condition swizzle, word 1 bits 21..28. Condition register read is word 1
  bit 31; the register written by `set_cond` is word 1 bit 30. There are two
  condition registers.
- Branch marker, word 2 bit 31. When set, the opcode field is a flow op, not
  an ALU op.
- Result scale, word 2 bits 28..30. 1/2/3 multiply by 2/4/8, 5/6/7 divide by
  2/4/8, applied before saturate.
- Source-range modifiers, word 2 bits 19..27, three independent 3-bit fields.
  See "what the translator specializes on".
- Perspective correction, word 3 bit 31, and only when the instruction is not
  a branch. A texcoord input (TC0..TC9) is multiplied by `1/w`.
- IFE else address is word 2 bits 0..30, shifted left 2 (a byte offset).
  LOOP/REP end count, init and increment are word 2 bits 2..9, 10..17 and
  19..26. The block end address is word 3 bits 0..30, shifted left 2.

Inline constants are sanitized: a non-finite word becomes 0 and
`g_rsx_fp_nonfinite_constants` increments. The buffered path keeps the
host-order bits in `fp_constants[slot]`.

### Opcodes the emitter implements

The name table lists every NV40 opcode the decoder recognises. The HLSL
emitter writes a result only for the EMIT set. Anything else becomes a
comment and does not write the destination (the previous register value
stays). The interpreter must do the same, or a pixel comparison against the
specialized shader will fail.

| Opcode | Code | Emitter |
| --- | --- | --- |
| NOP | 0x00 | no write |
| MOV MUL ADD MAD | 0x01..0x04 | yes |
| DP3 DP4 | 0x05 0x06 | dot3 / dot4, replicates |
| DST | 0x07 | no write |
| MIN MAX | 0x08 0x09 | yes |
| SLT SGE SLE SGT SNE SEQ | 0x0A..0x0F | component compare, 0 or 1 |
| FRC FLR | 0x10 0x11 | `frac` / `floor` |
| KIL | 0x12 | `discard` under the same predicate; no dest |
| PK4B UP4B | 0x13 0x14 | pack helpers |
| DDX DDY | 0x15 0x16 | no write |
| TEX TXP | 0x17 0x18 | `Sample`, shape-dependent coordinates |
| TXD | 0x19 | no write (and translation *fails* if that unit has gamma or sign-expand) |
| RCP RSQ EX2 LG2 | 0x1A..0x1D | scalar `.x`, broadcast. RSQ is `rsqrt(abs(x))`. LG2 is `log2(abs(x))` unless `RSX_LG2_ABS=0` |
| LIT | 0x1E | no write |
| LRP | 0x1F | `lerp(src2, src1, src0)` |
| STR SFL | 0x20 0x21 | no write |
| COS SIN POW | 0x22 0x23 0x26 | scalar `.x` |
| PK2H UP2H PK4UB UP4UB PK2US UP2US PKG UPG | 0x24..0x2A, 0x2C 0x2D | pack helpers |
| DP2A | 0x2E | no write |
| TXL TXB | 0x2F 0x31 | `SampleLevel` / `SampleBias`, LOD or bias is source 1 `.x` |
| TEXBEM TXPBEM | 0x33 0x34 | no write (translation fails if gamma or sign-expand is requested) |
| RFL | 0x36 | no write |
| DP2 NRM DIV DIVSQ LIF | 0x38..0x3C | yes. DIVSQ is 0 where the numerator component is 0, else `num/sqrt(abs(den.x))`. LIF is `(1, y, y>0 ? exp2(w) : 0, 1)` |
| FENCT FENCB | 0x3D 0x3E | no write |

Pack helpers match the decompiler: UNORM8, SNORM8, UNORM16 pairs, fp16 pairs,
and the sRGB pack/unpack used by PKG/UPG. A packed word is a scalar that
replicates through the write mask, carried in a float's bits (`asfloat` /
`asuint`).

Scalar results (RCP, RSQ, EX2, LG2, SIN, COS, POW, DP2, DP3, DP4) are
broadcast with `(float4)`. The write mask then selects components of that
vector, so `dst.w = rhs.w`, not HLSL's scalar truncation.

Flow, when word 2 bit 31 is set (opcode field, not the ALU table):

| Code | Op | Emitter |
| --- | --- | --- |
| 0x00 | BRK | `break` if a loop is open and the condition is true |
| 0x01 | CAL | comment only, no call |
| 0x02 | IFE | `if (cond)`; else address opens the other side |
| 0x03 | LOOP | counted `for`, condition gates entry |
| 0x04 | REP | same shape as LOOP |
| 0x05 | RET | comment only |
| other | — | comment only |

The condition is the first component of the condition swizzle compared with
0, or `true` / `false` for the unconditional and never predicates. A malformed
block (nesting overflow, end address not after the instruction) is skipped.
CAL and RET are not implemented in the specialized shader either, so matching
it means not calling. Programs that need a real call stay on today's path
only if a later stage starts rejecting them; stage 1 matches the skip.

### Catalogue, measured 2026-11-03

8,142 `.fp` files, 0 rejected as unaligned. Instruction counts: median 39,
mean 55.4, maximum 433. None exceed 512. Inline constant slots: mean 20.3,
maximum 142 (the per-draw `fp_constants[256]` slot holds that).

Files that contain at least one of: a branch-marked instruction 1,195;
a non-trivial predicate 5,679; an H-file destination 7,291; `OUT_SAT` 7,083;
a non-zero result scale 7,376; perspective correction 7,129. Files whose
ALU opcode is outside the EMIT set: 187. CAL or RET opcodes under the branch
bit: 32 instructions in the whole catalogue.

The common ALU and texture opcodes are all in the EMIT set (MUL, MOV, MAD,
DP3, ADD, TEX, NRM, LG2, EX2, DIV, DIVSQ, TXP, RCP, RSQ, compares). The
no-write opcodes are rare (RFL 44, TXD 21, DDX 17, DDY 15, DST 15, STR 15,
TEXBEM 13, DP2A 11, TXPBEM 7, SFL 4, plus a handful of unknown opcode
numbers). An interpreter that implements EMIT and treats the rest as a
no-write covers every catalogue program the specialized translator covers,
except programs the translator already rejects (unsupported shadow or gamma
fetch). Those rejections stay rejections.

## Vertex instruction encoding

Four little-endian words, 16 bytes, no inline constants. The program ends at
word 3 bit 0. Constants live in a 512-wide `vp_c` bank. Branch targets are
absolute slots in a 544-slot transform-program memory; `rsx_vp_set_branch_base`
makes them relative to the ucode pointer.

Word layout the decompiler uses (D0..D3):

- D0: condition swizzle [2:9], condition [10:12], condition-test enable [13],
  condition update [14] and [29], vector temp dest [15:20], source absolute
  [21:23], address-register select [24], condition-register select [25],
  saturate [26], vector result goes to an output [30].
- D1: source 0 high, input index [8:11], constant index [12:21], vector
  opcode [22:26], scalar opcode [27:31].
- D2 / D3 pack source 0 low, source 1, source 2, the end bit, indexed-constant
  bit, output dest, scalar temp dest, and the two write masks.
- A 17-bit source is type (1 temp, 2 input, 3 constant), temp index, swizzle,
  negate. Inputs use the instruction's input index, not the source index.
  Constants use `const_src`, or `const_src + a[addr].component` when
  `index_const` is set, masked to 511.

Each instruction co-issues one vector op and one scalar op. Vector ADD reads
source 0 + source 2. The vector result is written to `o[dst]` when the
vector-result bit is set (dst 0x1F means none) and to `r[dst_tmp]` (0x3F
means none). Otherwise the scalar result is written to the output, else to
`r[sca_dst_tmp]`. Temps are `r[32]`. Address registers are `a0` and `a1`.

Vector opcodes the emitter implements: MOV, MUL, ADD, MAD, DP3, DPH, DP4,
DST, MIN, MAX, SLT, SGE, ARL, FRC, FLR, SEQ, SFL, SGT, SLE, SNE, STR, SSG,
TXL (vertex texture, units 0..3). Unknown vector opcodes emit a comment and
do not write.

Scalar opcodes: MOV, RCP, RCC (clamped reciprocal), RSQ, EXP, LOG, LIT is
named but not in the scalar result switch below LG2, LG2, EX2, SIN, COS, and
the flow ops. Flow is BRA, BRI, CAL, CLI, RET, BRB, CLB. A branching program
is a block state machine inside a loop capped by `RSX_VP_LOOP_MAX` (default
16384). BRB/CLB test one bit of `SET_TRANSFORM_BRANCH_BITS`, which the
decompiler bakes in, so those programs are keyed on the bits
(`rsx_vp_uses_branch_bits`).

Output map: o0 HPOS, o1 COL0, o2 COL1, o5.x fog, o6 TEX9 (also point size),
o7..o14 TEX0..7, o15 TEX8. Unwritten outputs default to (0,0,0,1).

GPU vertex fetch (`rsx_vp_decompile_gpufetch`, `k_vfetch_hlsl`): the vertex
shader reads raw guest bytes from root SRV `t20` and per-attribute
descriptors from `b2`, instead of a pre-expanded vertex buffer. 464 of 482
compiled vertex variants in the starter use this path. The fetch formats in
the helper cover the types the backend uploads (f32, s16n, u8n, s16, u8, and
the half path). Stage 2's interpreter calls the same helper, then runs the
vertex program. It does not invent a second fetch format table.

Epilogue, after the program:

- `pos = p.xyz * vp_posscale + p.w * vp_posoffset`, with `w` kept. That is
  the RSX viewport mapped into D3D clip space. The backend fills both vectors
  per draw.
- Ultrawide (`RSX_ULTRAWIDE` non-zero): if `vp_posoffset.w > 0`, vertices that
  sit on the title's 16:9 clip edge are moved to the screen edge. If it is
  negative, a full-screen edge is pulled back to 16:9. Emitted only in that
  mode, so other runs keep their cached vertex shaders.
- User clip (`rsx_vp_apply_user_clip`): planes live in o5.yzw and o6.yzw.
  `NV4097_SET_USER_CLIP_PLANE_CONTROL` is two bits per plane (off, keep
  `d <= 0`, keep `d >= 0`). The helper adds `SV_ClipDistance`. It is state,
  not program text, but it is baked into the HLSL, so it is part of the
  vertex-shader key today. An interpreter passes the six ops as constants
  and writes clip distance in the epilogue.

On the starter, vertex programs are essentially 1:1 with compiled variants
(477 programs, 482 variants). The fragment stage is where specialization
multiplies (1,404 programs, 3,605 variants).

## What the fragment translator specializes on

These are baked into HLSL or into the pipeline key today. An interpreter
passes them as constants, or reads them from the program buffer, so one
pixel shader serves every program.

Texture shape. `tex_cube_mask` bits 0..15 are cube units; the volume mask
(passed beside it, and stored in the high half of `s_pso_ghi` by the
backend) names 3D units. Other units are `Texture2D`. A cube or volume sample
uses `.xyz`. TXP divides by `.w` for 2D and 3D and does not divide a cube.
With no cube and no volume the emitter declares `Texture2D rsx_tex[16]` at
`t0`. Otherwise each unit is its own `tN` declaration. On the starter,
template `state.cube` bits 17 and 18 alone separate most variant pairs.
Global context combos of those bits with shadow and upper-unnormalized flags
are about 15, of which about 6 are common.

Gamma. `rsx_fp_texture_gamma_units` walks fetches. A per-unit RGBA lane mask
is applied after the sample, unless the fetch has EXP_TEX (word 0 bit 21).
TXD, TEXBEM and TXPBEM with a gamma mask fail translation. The helper is
`_rsx_gamma_input`.

Sign expand. `UNSIGNED_REMAP_BIASED` recentres lanes named by
`expand_masks[unit]`, after gamma and not on gamma lanes:
`(round(x*255)-128)/127`, or `/32767` when bit 4 is set. EXP_TEX (`_bx2`)
returns `x*2-1` on every lane and skips gamma. Comparison fetches are not
expanded. The backend can also rewrite expand to use `rsx_texexpand` in `b1`
so the mask stays dynamic. Units that expand are part of the pipeline
identity today (`rsx_fp_texture_expand_units`, `rsx_fp_texture_bx2_units`).

Shadow compare. `rsx_fp_shadow_desc` is enabled, compare func, linear, and
unnormalized. Supported fetches are 2D TEX and TXP, one mip, a decoded
D24_D8 or D16, and a nearest or linear min/mag filter. Float depth, cubes,
3D, extra mips and other fetch opcodes reject the program (`return -1`).
The compare is reference-against-depth in the order this decompiler emits
(`_rsx_shadow_cmp`), not ARB_shadow's order. Four-tap softening is
`RSX_SHADOW_SOFT` in the backend, not a second program. The interpreter
rejects the same layouts on the CPU and falls back to today's compile.

Unnormalized coordinates. `rsx_fp_apply_unnorm_scale` divides texel-space
coordinates by width, height, and depth for volume units. Cube units are
skipped. The backend keys `unnorm` from `dr_unnorm` / `dr_unnorm_hi` and
uploads the reciprocal sizes (`rsx_texscale`, and `rsx_texscale_hi` for the
upper units). The interpreter multiplies by those existing vectors instead
of patching HLSL.

Sampler bank. `rsx_fp_apply_sampler_map` rewrites `rsx_sampN` to one of the
16 static samplers. The key is `samp_key` (4 bits per unit). The root
signature's samplers are the bank: s0 is point/clamp, s1..s3 are linear/wrap
in the original slots, s4..s15 are the point/linear/aniso by wrap/clamp
combinations (`RSX_ANISO`, default 16). The interpreter uses the same
`rsx_samp[bank]` index. No new sampler objects.

Constants embedded in the fragment program. `FP_CONSTBUF` defaults on. Inline
slots become `fp_constants[n]` in `b1` and are uploaded every draw, so a
program patched each frame (showroom brightness) is not frozen into DXBC.
More than `FP_CB_CONSTS` (256) slots falls back to literals. The structural
hash skips constant payload bytes; the legacy hash included them
(`FP_CONSTBUF=0`). The interpreter always reads constants from the buffer.
142 is the catalogue maximum, under 256.

Source-range modifiers. Default `RSX_FP_SOURCE_RANGE=2`: only code 4
(saturate) is applied, and never to an input operand. `=0` applies nothing.
`=1` also applies the signed clamps (1 → ±65504, 2 → ±2, 3 → ±1), saturation
before absolute value, absolute value before the clamp, negation last.
`=3` is saturation but not on texture fetches. The CPU encoder bakes the
effective modifier into the uploaded instruction, using the same rules, so
the GPU does not read the environment variable.

Alpha test. D3D12 has no fixed-function alpha test. The compare
(`CELL_GCM` funcs 0x200..0x207) is patched in front of the colour return
against `rsx_alphatest`. ALWAYS is a no-op. The reference is decoded from
the surface format (`rsx_fp_alpha_ref`: UNORM8, fp16, or fp32). The
interpreter discards in the epilogue from the same constant.

Export precision. `NV4097_SET_SHADER_CONTROL` bit 0x40 selects the colour
file: set means fp32 `r0`, clear means fp16 `h0`. The backend passes that
bit from the draw (`fp_exp32`) unless `FP_CTRL_AUTO=1`, which uses the old
"whichever of r0/h0 was written" heuristic. Extra targets are `r2/r3/r4` or
`h4/h6/h8`. Depth export (control bits 1..3) writes `r1.z`, saturated, to
`SV_Depth`. A NaN colour becomes 0. H registers are stored as full float4
in the specialized shader; the interpreter does the same. Half rounding is
not modelled by either path.

sRGB packer. `rsx_fp_srgb_output_enabled` is the integer-framebuffer packer
(`NV4097_SET_SHADER_PACKER`). Any non-zero packer enables linear-to-sRGB on
half exports. Floating surfaces and 32-bit exports skip it. RGB only; alpha
and depth stay. The interpreter applies it in the epilogue when the profile
bit is set.

Dither. `RSX_FINAL_DITHER` defaults on, and only when high precision is on,
the target is one `R8G8B8A8_UNORM` with a colour write mask. It adds a
triangular ±1/255 noise from a hash of the host pixel, then the NaN guard.
The interpreter runs that same hash in the epilogue when the profile bit is
set. `RSX_FINAL_DITHER=0` leaves both paths alone.

WPOS and MSAA. Window position is `SV_POSITION` with the origin and
half-pixel bias from `fp_alpha` (`_rsx_wpos`): y flips when the RSX window
origin is bottom, and `.z` is the integer-centre bias. On an antialiased
surface kept at sample resolution, `rsx_fp_apply_wpos_grid` rewrites WPOS to
the pixel centre `floor(pos/grid)+0.5` before that flip. The grid is the
target's sample count. Sample shading itself is pipeline state
(`SampleDesc`), which is native state, not program text. The interpreter
PSO varies by sample count; the grid is a constant. `RSX_MSAA` / 
`RSX_MSAA_FORCE` are unchanged.

Perspective `1/w`. Under FXC, `SV_POSITION.w` is clip w, so the factor is
`1/w`. The Vulkan and Metal paths define `RSX_FRAGCOORD_W_IS_RCP` because
their position is already reciprocal. The D3D12 interpreter uses `1/w`.

Inputs. `PSInput` is `SV_POSITION`, `COLOR0`, `COLOR1`, `FOG`,
`TEXCOORD0..7`, plus `TEXCOORD8/9` and `SV_IsFrontFace` only when the
program reads them. Colour inputs are saturated before swizzle, absolute
value and negate. Texcoords are not. Input indices: 0 WPOS, 1 COL0, 2 COL1,
3 FOG, 4..11 TC0..7, 0xC TC8, 0xD TC9, 0xE FACING (+1 front, −1 back).
Anything else reads zero. The specialized vertex shader already writes this
layout, including the optional outputs. Stage 1 keeps that vertex shader, so
the interpreter pixel shader declares the full set. A vertex shader that
omits TC8/TC9 still links if the pixel shader does not read them; the
interpreter declares them as optional interpolants with a default of 0 when
the program does not use them, matching the link rule. Programs that read
them require a vertex shader that writes them, which the specialized path
already does for those draws.

Vertex-side specializations that stay in the specialized vertex shader for
stage 1, and move into the vertex interpreter in stage 2: GPU fetch versus
expanded inputs, the input mask (`RSX_VTX_MASK`), vertex texture units
(`vtex_mask`, `Texture2D` at `t(16+N)`), branch-bit baking, user clip,
`vp_posscale` / `vp_posoffset`, and the ultrawide epilogue.

## Root signature and constant buffers

The guest-program root signature (`s_d3d.vp_root_sig`, five parameters) is:

| Slot | Register | Visibility | Contents |
| --- | --- | --- | --- |
| 0 | CBV b0 | vertex | `vp_c[512]`, `vp_posscale`, `vp_posoffset` |
| 1 | SRV table t0..t15 | pixel | fragment textures, one descriptor per unit |
| 2 | CBV b1 | pixel | fragment constants, below |
| 3 | SRV t20 | vertex | raw guest vertex bytes (GPU fetch) |
| 4 | CBV b2 | vertex | attribute descriptors for that fetch |

Sixteen static samplers s0..s15, pixel visibility. The serialized bytes are
hashed into the native pipeline key (`s_vp_rs_hash`) because a blob saved
under an older sampler bank drew the road with the wrong sampler.

`b1` as the backend rewrites it (`decl_unhi`, the wide form):

```
float4 rsx_texscale[4];
float4 rsx_alphatest;
float4 fp_constants[256];
float4 rsx_fogstate;
float4 rsx_texexpand[4];
float4 rsx_texscale_hi[6];
```

That is the 4352-byte slot. Smaller programs omit the tail in the HLSL
declaration; the upload stride still matches the wide layout when those
features are on. `rsx_alphatest` also carries the WPOS window height and
the pixel-centre bias. Fog state is in the same slot.

`b0` is one draw's vertex-constant block (`rsx_vertex_constant_ring_plan`).
`b1` is a 256-byte-aligned allocation in a fence-retired fragment ring
(`rsx_fp_constant_ring_plan`). Dropping a draw because the ring is full is
not allowed; the caller submits and retries.

The interpreter pixel shader cannot put 2D, cube and 3D views on the same
`tN`. It also cannot put the program next to the textures without a new
binding. Stage 1 therefore adds a second root signature, created only when
`RSX_SHADER_INTERP` is `1` or `force`, and used only by interpreter
pipelines:

- Parameters 0..4 are identical to `vp_root_sig`, so the specialized vertex
  shader binds unchanged.
- Parameter 5 is a pixel-visible root SRV at `t16`: a `ByteAddressBuffer`
  holding the per-frame program arena. It is not part of the descriptor
  table, so it does not alias a texture unit.
- The pixel descriptor table is three ranges: `t0..t15` 2D, `t32..t47`
  cube, `t48..t63` 3D. Cube and 3D views are null when that unit is not
  that shape. Sampling a null view returns 0, and the profile's shape id
  never samples it.

`b1` for an interpreter draw is the same wide layout the backend already
uploads (4352 bytes). Named `fp_constants[N]` is float4 index `5 + N`.
Profile bits do not go in `b1`. They go in a 64-byte header in the program
arena. Parameter 6 is four pixel root constants at `b3`: the byte offset of
that header, then three zeros. A one-dword root constant does not match the
16-byte cbuffer slot and `CreateGraphicsPipelineState` returns
`E_INVALIDARG`.

```
cbuffer PSConstants : register(b1) { /* wide layout above */ };
cbuffer RSXInterpRoot : register(b3) {
    uint rsx_ip_hdr; uint pad0; uint pad1; uint pad2;
};
ByteAddressBuffer rsx_iprog : register(t16);
```

Header dwords at `rsx_ip_hdr`: instruction byte offset, instruction count,
flags, shape (2 bits x 16), unnormalized mask, sRGB read mask, shadow
word, sampler nibbles 0-7, sampler nibbles 8-15. Flag bits: 0 half, 4
alpha test, 5 fog, 6 WPOS scale, 7 final dither, 8 log2-of-abs (default
on), 9 game dither, 10 sRGB write. The harness sets only bit 8, puts
instructions at byte 64, and passes root constant 0.

Textures are ps_5_1 arrays: `Texture2D[16]` at t0, `TextureCube[16]` at
t32, `Texture3D[16]` at t48. ps_5_0 cannot dynamically index them, and a
literal switch of 16 units by 16 samplers by 3 shapes compiled to about
460KB unoptimized and heap-corrupted pipeline creation
(`0xC0000374`). Samplers stay the sixteen static samplers. A sampler
array asks for a descriptor range the static-sampler signature does not
bind. The shader switches on the sampler index and indexes the texture
array. Optimized bytecode is about 72KB (single target) and 74KB (MRT).

Specialized draws keep today's `b1` layout and today's root signature. The
replay loop binds the interpreter signature only for an interpreter draw and
binds the guest signature again afterwards. `RSX_SHADER_INTERP=0` does not
create the second signature and does not touch a root binding. That replay
hook is not in the backend yet.

## Interpreter program image

The CPU decodes the guest program once per distinct ucode (cached beside the
shader cache, in memory only) into a fixed 16-byte instruction the pixel
shader can switch on. The image is not NV40 bitfields and it is not HLSL.

Each instruction is one `uint4`, little-endian, loaded with `Load4`.

`u0`: opcode 6, dest 6, dest-half, no-write, mask 4, saturate, scale 3,
predicate 2 (0 unconditional, 1 never, 2 conditional), compare 3, cc-read,
set-cond, cc-write, perspective, FLOW.

ALU `u1`: source0 22, input index 4, texture unit 4, bx2. ALU `u2`:
source1 22, condition swizzle 8. ALU `u3`: source2 22, constant slot 8.
Each source is 22 bits: type 2, index 6, half, negate, absolute, precision
3, swizzle 8. Swizzle xyzw is `0xE4`.

FLOW `u1`: else PC 16, end PC 16 (else `0xFFFF` means none). FLOW `u2`:
init 8, end count 8, step 8. FLOW condition swizzle is `u3` bits 0-7.
Malformed flow, CAL, and RET occupy a PC slot and do nothing. An ALU
opcode the emitter does not handle is the same kind of slot, with
set-cond cleared. KIL stays opcode `0x12` and discards after the loop.

Constants stay in `fp_constants`, not in the instruction. The per-draw
header is the 64-byte record above, not a prefix of the instruction
stream. The encoder rejects a program that is unterminated, longer than
512 instructions, has more than 256 constants, nests flow deeper than 8,
overflows the destination buffer, or uses a temp or dest index at or
above 48 on an opcode it actually executes. It does not reject cube, 3D,
shadow, gamma, bx2, or an unhandled opcode. Of 8,142 catalogue programs,
8,021 encode: 73 unterminated (the decompiler also rejects those), 49
temp-index, max instructions 433, max constants 142, max nest 4. Depth-copy
unnorm bits, mip-stack bits, and stencil bit 26 are draw-time skips, not
encoder rejects. A rejected program keeps today's async path.

Upload is a per-frame arena, not a buffer per draw. One upload buffer of
2 MiB (about 4,000 draws at the catalogue mean of ~55 instructions, and the
showroom is about 4,300 draws with heavy reuse) is reset at frame start.
Each distinct program is copied once; later draws of it reuse the offset.
The offset and length go in `profile[0]`. A frame that would exceed the
arena falls those extra draws back to today's path and counts them. The
default 2 MiB held the measured frames: dealership peak 217 KB, High Speed
Ring peak 389 KB, and the arena-overflow counter stayed 0. The switch
`RSX_SHADER_INTERP_ARENA_KB` (256..16384) raises it without a rebuild.

Loop and branch limits. The pixel shader runs a counted loop of at most
`RSX_FP_INTERP_STEPS` steps (default 2048). Catalogue programs are at most
433 instructions and the LOOP/REP counts in the encoding are 8-bit, so 2048
covers a single pass plus the small loops those programs use. A step that
does not reach `END` writes black and sets a debug counter rather than
looping until the GPU times out. CAL/RET do not push a stack; they are
skipped, matching the translator. IFE nesting is encoded as explicit else
and end instruction indices, walked with a small stack of 8 in the shader.
Deeper nesting is a CPU rejection.

Register file. The decompiler's files are `float4 r[48]` and `float4 h[48]`,
plus two condition registers. The interpreter uses those sizes. A used
index at or above 48 is an encoder reject (49 catalogue programs). Both
files start at 0. Dynamic indexing lands in indexable temporary memory.
That is the expensive part. A catalogue-mean program of 55 instructions
costs several times a specialized shader when every draw takes the
interpreter. Measured with `GT5P_PRESENT_PROF=1` and `RSX_SSAA=0` (pixel
rate), the dealership's last 5 s window was gpu 77.05 ms (avg 80.52) against
3.32 ms (avg 8.53) with the switch unset. High Speed Ring on-track windows
were about 45-88 ms against about 8-14 ms. That is the steady cost of
`force`, which never returns to the specialized pixel shader. `=1` pays it
only while a specialized shader is pending. The offline WARP run did not
measure GPU time. Default D3DCompile optimisation of the ps_5_1 shader
takes about 15 s (single target) and 25 s (MRT). The runs below used flags
0 and loaded the cached DXBC (`warmup 0 ms`, `compile 0 ms`, 71440-74284
bytes). The earlier ps_5_0 literal texture switch was still optimising
after 8 minutes and was not used.

Texture shape in the shader. Two profile bits per unit are 0 = 2D, 1 = cube,
2 = 3D. The sample indexes the matching ps_5_1 texture array and switches
the static sampler. Unnormalized units multiply
the coordinate by `rsx_texscale` first. Gamma and expand run on the fetched
value using the lane masks in `profile` and `rsx_texexpand`. Shadow units
that passed the CPU check use the same compare helper as the translator,
with the func and the linear flag in the profile. The CPU rejects a program
whose shadow descriptor would make `rsx_fp_decompile_buffered_shadow_*`
return −1.

## Pipeline identity

The target key for a pipeline interpreting both stages is native state only:

- blend state and write mask (`blend`, `cmask`)
- render-target count and DXGI format
- depth format and whether a depth buffer is bound
- cull
- stencil state
- sample count (the MSAA class already stored in the cube-mask high bits)
- depth-export on or off (changes `SV_Depth`)

For the interpreted stages it does not include the program, cube mask, unnormalized mask,
sampler bank, shadow, gamma, expand, or constant values. The starter
observation is about 57 distinct blend/RT/cull/stencil classes. Sample count
and depth-export multiply that by a small factor. The implementation records
the distinct interpreter keys it actually creates (`RSX_SHADER_INTERP_LOG=1`)
but does not yet precreate the ones seen.

Without opt-in prewarming, replay pipelines are created on first use. Fragment-only interpretation
also keys on the specialized vertex bytecode; vertex-only interpretation keys
on the specialized pixel bytecode. Only combined interpretation removes both
program identities. First-use driver work can still hitch. The paired prewarm
experiment below adds a bounded device-init list. The roughly 4 ms driver cost above is
earlier preparation evidence, not a bound measured for these generic pipelines.
Stage 3 must measure it before claiming that compilation stalls are removed.

`RSX_SHADER_INTERP=force` uses the interpreter pixel shader for every draw
that the encoder accepts, with the normal specialized vertex shader.
`=1` uses it only when the specialized fragment shader or its driver
pipeline is pending (`s_fp_pending` or a NULL pipeline for that reason).
A draw the encoder rejects, or whose vertex shader is pending, keeps today's
behaviour. `=0` does not consult the encoder.

## Stages

Stage 0 is this document.

Stage 1 is the fragment interpreter, the second root signature, the arena,
the CPU encoder, and `RSX_SHADER_INTERP`. Validation is offline first: a
WARP harness compiles the specialized shader from `rsx_fp_decompile_*` and
the interpreter, draws an 8x8 grid with synthetic interpolants and the
program's own constants, and compares pixels. Texture programs get a
deterministic 2D or cube texture. Programs the encoder rejects are counted,
not compared. The harness reads the catalogue in place and writes only under
`scratch/`. Nothing from the catalogue is committed.

The offline pieces are `scripts/test/gen_fp_interp_hlsl.py` (the HLSL),
`scripts/test/fp_interp_harness.c`, and `scripts/test/fp_interp_warp.py`.
The encoder and the embedded HLSL ship in
`patches/ps3recomp-shader-interp.patch`. On 2026-11-03 the locked WARP
compare (`fp-interp-warp`) reported synthetic math, colour, and texture
worst error 0, then `pass=80 fail=0 skip=0 spec_compile_fail=0 worst=0
cube_pass=5 cube_fail=0`. Epilogue flags (alpha test, fog, WPOS scale,
dither, sRGB write) were off, so that compare matches the decompiler.
The backend epilogues are constant bits in the arena header and were on
for the game runs below. The WARP compare was not re-run after the
input-variant ifdefs.

### Stage 1b game runs (2026-11-04)

Private `gt5p.exe` from `interp_private_build.py`, private
`RSX_SHADER_CACHE`, lock, `PS3_VERBOSE=0`. `RSX_GPU_TIME` is the
`[present-prof]` gpu field (`GT5P_PRESENT_PROF=1`). Counters are
cumulative.

Switch unset (mode 0), `RSX_SSAA=0`: DealerTopRoot at 30.3 s. No `[interp]`
line. Last window gpu 3.32 ms avg 8.53. The same binary with default SSAA
also reached the dealership and logged no `[interp]` line. This is the
patched exe with the switch off, not a pixel compare against an unpatched
exe.

`RSX_SHADER_INTERP=force`, default SSAA (sample-rate variant, dealership
MSAA 4): the interpreter loaded (`warmup 0 ms`, `pso_fail 0`) but the top
menu settled near gpu 130 ms, about 6 fps. `winshot.ps1`'s 100 ms pad taps
are shorter than a frame, so DealerTopRoot was not reached. That run is a
navigation failure, not a crash.

`force` with `RSX_SSAA=0` (pixel rate) did reach DealerTopRoot, at 31.8 s.
Last window gpu 77.05 ms avg 80.52. Final counter line: `draws 314670
fallback 940 reject 0 gap 940 arena 0 pso_fail 0 pso 118 peak 217KB
compile 0ms`. The shot is the Acura studio: two NSX, floor reflections,
readable "GRAN TURISMO 5 Prologue" and "ACURA" text. It is a different
turntable moment from the mode-0 shot (about 6 fps against 30 fps over the
settle), so a whole-frame diff was not taken. Nothing in the frame reads
as a missing material.

High Speed Ring, `race.ps1 -RaceShots 12 -Seconds 35 -SampleDelay 12`,
`RSX_SSAA=0`, 720p MSAA 2. Mode 0: the script printed median 14 fps; the
last on-track window was gpu 12.48 ms avg 42.73; `race024` is a broadcast
view (blue car, HUD 8/16, 120 km/h). Force: the script printed median
6.79 fps. On-track windows sat around gpu 45-88 ms (one late window
45.43 ms avg 55.95, an earlier one 79.97 ms avg 80.40). Final counter
line: `draws 780648 fallback 11279 reject 0 gap 11279 arena 0 pso_fail 0
pso 345 peak 389KB compile 0ms`. `race000` is still the starting grid
(readable car names). `race024` and the closing window are a chase view:
the car ahead, Bridgestone and brembo banners, crowd, HUD, and speedo.
Different camera from the mode-0 shot, so again no whole-frame diff.
Draw counts on track stayed in the same band as the mode-0 race (about
1,000-2,600). Replay CPU was also high (about 55-70 ms per frame in the
present-thread log), so the fps drop is not the GPU alone.

On every force log line, `fallback` equalled `gap`. Those are the known
`tex_dz` / `tex_mip` skips, which keep the specialized shader. `reject`,
`arena`, and `pso_fail` stayed 0. Interpreter pipelines are created on
first use and are not written to the disk PSO cache: 118 by the end of
the dealership, 345 by the end of the race. That first-use create is the
hitch stage 3 should precreate. `RSX_SHADER_INTERP=1` was not launched.

Stage 2 is the vertex interpreter, including GPU fetch, under
`RSX_SHADER_INTERP_VP` with the same 0 / 1 / `force` meanings. The vertex
interpreter's pipeline still depends on the fragment shader in `force` mode
only when the fragment side is the specialized one; the key adds the vertex
input layout the fetch path already uses. Validation matches stage 1.

Stage 2 implementation checkpoint (2026-11-04): the separate overlay now
contains the generic vertex body, per-frame program arena, recorded-program
lookup, GPU-fetch and IA variants, and combined vertex/fragment root bindings.
`scripts/test/vp_interp.hlsl` is original generic interpreter source, not
game-derived HLSL. `gen_vp_interp_hlsl.py` embeds it in the overlay;
`interp_make_patch.py` regenerates the overlay from the private scratch tree.
The private build also precompiles the two vertex variants. The prior locked
`interp-s2-build` succeeded; live vertex interpretation is still unverified at
this checkpoint. Review added frame-start signature-state reset and retained
bytecode references in the shared interpreter pipeline cache. A fresh locked
build and the new synthetic IA/GPU-fetch WARP output comparison are pending.
The synthetic comparison is not a catalogue or rasterization proof.

### Stage 2 first acceptance (2026-11-04)

Locked `interp-vp-warp-valid-end` passes 108/108 synthetic comparisons over
all 14 vertex outputs (four invocations per case), using both IA and GPU-fetch
variants. Worst absolute error is 4.76837158e-7; the acceptance tolerance is
1e-4 times max(1, abs(reference)). Cases include vector/scalar arithmetic,
predication, branches/calls, all seven attribute formats, disabled attributes
and unaligned fetch. Three failures in the first draft were invalid fixtures
with END before their branch target; the corrected programs pass. No runtime
shader change was needed for those failures.

The first live force-VP dealership shot was almost black. The new path had
selected fetch/IA from `dr->gpu_fetch`, a stale byte in reused CPU records.
Both interpreter combinations now use the renderer's authoritative `gf_slot`
generation marker. Locked `interp-vp-slotfix` rebuilds and reaches DealerTopRoot
in 34.5 s; its inspected PrintWindow shot has both NSX cars, reflections,
manufacturer/title/car text and the blue studio background. Last GPU window:
8.68 ms mean / 9.18 ms maximum, title 30.00 fps. Final vertex counters:
1,351,168 draws, fallback/miss/arena/PSO-failure all zero, 74 seen programs,
183 KiB peak arena, 16 ms cached bytecode loading. These are cumulative attempts,
not distinct draw or pipeline counts. Specialized fragment work still omitted
3,061 replay attempts in this warm-cache vertex-only run.

The earlier failed visual run also exposed first-use generic driver PSO cost:
3,688 ms total, 751 ms maximum. The corrected run's 170 pipelines cost 26 ms
total / 4 ms maximum with the driver already warmed. This is not evidence that
cold first-use hitches are gone. HSR, a starter-program WARP comparison and
pending-only empty-cache runs remain to be validated.

Locked `interp-vp-catalogue-hsr` subsequently resolves all 477 starter VPs
through the verified original ELF/GT.VOL maps, without an unpacked catalogue.
All 477 pass in both IA and GPU-fetch form. Together with the synthetic suite:
1,062 passes, zero failures, worst absolute error 4.76837158e-7. This uses
synthetic attributes/constants and compares vertex outputs, not actual game
draw state or raster pixels. The raw inputs and generated shader bodies stay
private; only the resolver and test harness are tracked.

That locked run then exercises HSR with vertex force / fragment off, 720p,
MSAA 2, SSAA off, 35 s sampling after a 12 s delay. Script median is 30 fps;
last GPU window 5.27 ms mean / 7.85 ms maximum. Final counters: 3,341,152
interpreted vertex draw attempts; fallback/miss/arena/PSO failure all zero;
211 seen programs, 211 KiB peak arena, zero bytecode compilation milliseconds.
803 interpreter PSOs cost 17,390 ms total / 771 ms maximum in synchronous
driver calls. This is elapsed call time, not an isolated driver-compiler cost.
The race024 shot visibly contains track, cars, mirror, signage and HUD. The
race000 shot is black and 10,168 fragment-pending replay attempts were omitted:
vertex-only interpretation does not fix pending fragment work. HUD underlayers
also appear incomplete in the later shot. This is a vertex-route rendering
proof with fragment omissions, not a complete race acceptance or speed win;
it was not the standard foreground FrameTest or a matched baseline pair.

`RSX_SHADER_INTERP_STATS=1` is an independent, default-off diagnostic for the
async baseline and the interpreter paths. Every five seconds `[interp-pending]`
reports cumulative replay vertex/fragment omissions, recording-time GPU-fetch
vertex omissions, and interpreter PSO count/creation milliseconds. These are
draw attempts over time, not distinct pipelines or visible missing objects.
The recorder/replay sites are separate; their totals must be reported separately.
`scripts/test/interp_game_probe.py` runs the existing screenshot/race scripts with
a scratch copy of the ELF/save, an absolute read-only game-folder mapping, and
an explicit private scratch shader cache. `--cold` rejects nonempty caches,
including caches containing only the generic interpreter bytecode. `winshot.ps1`
now accepts an explicit private engine/root/timeout and cleans up only its owned
process. The original game/save paths are never used as writable storage by this
probe. These new diagnostics/probes await the validation below.

Stage 3 wires `=1` into the pending-draw path. With an empty private shader
cache, a first dealership visit and an HSR race are compared with today's
async policy: missing draws, frame times (`scripts/test/race.ps1 -FrameTest`),
and F3 logs. Interpreter pipelines for the observed native classes are
created ahead of that run if the stage 1 log says that is what removes the
hitch.

### Stage 3 development checkpoint (2026-11-04)

The private builder embeds 18 original generic shaders (1,241,616 bytes), keyed
by exact HLSL/target/flags, through `scripts/test/interp_embed.py`. The generated
header and DXBC remain under scratch and are never tracked. This makes an empty
`RSX_SHADER_CACHE` test genuinely empty, without an eight-minute generic compile
at each launch. `INTERP_EMBED_DXBC=0` builds without this payload;
`RSX_SHADER_INTERP_EMBED=0` uses the existing cache/compiler path instead.
`INTERP_SKIP_PRECOMPILE=1` reuses existing generic build inputs, with mandatory
source-key/size checks; otherwise the builder compiles them before linking.
An embedded load's elapsed time is still included in the legacy `compile` log
field; that field alone does not establish a D3DCompile call.

Locked `interp-cold-dealer-pair-r2`: separate caches initially contain zero
entries, copied-save hashes match, 720p/default dealership MSAA, SSAA off.
Both routes delay menu navigation by 30 seconds so first-use hitches do not
lose short pad taps; first DealerTopRoot is reached in 63.9 / 64.4 seconds.
Twelve shots follow at nominal one-second gaps. Baseline cumulative omissions:
837 replay VP, 408,704 replay FP, 788,510 recording-time GPU VP. Independent
`RSX_SHADER_INTERP=1 RSX_SHADER_INTERP_VP=1`: 42 replay VP, 91 replay FP,
zero recording VP; 67,196 interpreted FP and 28,404 interpreted VP attempts.
Reject/arena/PSO-failure counters stay zero; 133 fragment gap attempts retain the
specialized path. 166 interpreter PSOs take 5,867 ms total / 689 ms maximum in
driver calls. The first baseline images visibly lack materials; the fallback
images retain more of the cars/background during their logo transition. Their
animations and random car colours differ, so these are not equal-input pixel
comparisons or unique-object counts. The earlier `interp-embedded-cold-dealer-pair`
is rejected: the fallback lost navigation taps and never reached the dealer.

Opt-in `RSX_SHADER_INTERP_PAIR=1`, requiring both stage switches, interprets both
stages together while either shader/driver pipeline is pending. It explicitly
overrides independent-stage selection to permit a program-independent native
pipeline. Known fragment gaps can still use a specialized fragment stage.
`RSX_SHADER_INTERP_PREWARM=1` precreates both input signatures for the 133
native/input classes derived from the verified starter metadata (266 PSOs).
It requires the private build's embedded metadata; unknown classes retain the
bounded first-use path. Both options default off; independent `=1` is unchanged.

Locked `interp-paired-prewarm-dealer-ab` compiles the private engine and runs
a third empty-cache dealership visit with the same save hash. Prewarm creates
266 pipelines without failure: 31 ms wall, 14 ms aggregate driver, 9 ms maximum
on this already-warm driver cache. After startup: eight additional PSOs, 1 ms
aggregate / 1 ms maximum driver work; 155,813 FP and 155,814 VP interpreted
attempts; recording VP omissions zero, replay VP/FP omissions 53/110, 164 known
fragment gaps. Encoder/arena/PSO failures stay zero. Shader load fields are zero.
This removes observed generic PSO calls from these draws by moving known classes
to startup; it is not a first-ever GPU-driver-cache-cold result or a universal
frame-time/stutter win. The late GPU window is still 36.85 ms mean / 52.68 ms
maximum while substantial interpretation remains active.

The subsequent both-force alternating-frame capture exposes an unresolved
fragment correctness gap: the ACURA wordmark reaches red 13 on interpreted
frames versus 39 on specialized frames. Fragment-only A/B reproduces it;
vertex-only A/B holds 39 on both paths. Eleven adjacent-pair whole-frame mean
absolute differences are 0.91-1.20 / 255 (motion included), maximum 184; the
fixed title crop differs by at most 2 / 255. These numbers do not establish
pixel equivalence. `interp_compare_frames.py` uses only the standard library
to read the renderer's 24-bit BMPs. The first analysis attempt failed because
Pillow was unavailable; the dependency is removed.

Locked `interp-fp-gamma-isolate-ab` repeats the fragment-force alternating
capture with `RSX_SHADER_INTERP_GAMMA_READ=0`. The specialized wordmark stays
at red 39. Interpreted text-like pixels in the same crop stay near red 12-14.
Other pixels in that crop reach the 70s, so the bypass changes colour and
does not close the gap. The switch stays a default-on decode with an off
diagnostic.

An uncommitted follow-up compiled the interpreter pixel shader for the
program's exported colour-target count instead of the bound attachment count,
and pre-created one pipeline per smaller count. `RSX_SHADER_INTERP_MRT_OUTPUTS=0`
would have restored the attachment count. Locked `interp-fp-mrt-exports-ab`
rebuilt that binary and repeated the fragment-force capture. It logged no
`[interp-mrt]` line, so the export count never differed from the attachment
count in that scene, and the wordmark stayed at red 13 against 39. That edit
was reverted. It is not a validated fix.

The first cold HSR FrameTest, and two launches at the start of this session,
were rejected at the grid because another window stayed in front. They supply
no timing result. `scripts/test/race.ps1 -RequireForeground` now resolves the
titled game window again at the grid and joins only the current foreground
input queue while calling `SetForegroundWindow`. A console or IME owned by
the same process does not pass. The accepted pair is the status section
above. Exact epilogue equivalence and the wordmark correction remain open.

## What stays out

- No change to specialized HLSL, DXBC keys, or the async worker policy when
  the switches are off.
- No copy of RPCS3 interpreter code.
- No game programs, DXBC, or generated HLSL in the repository.
- Half-precision rounding, DDX/DDY, TXD, subroutine calls, and the opcodes
  the translator already ignores stay matched to the translator, not
  "fixed", until a separate change does both paths.
- The interpreter is not a claim that unseen shaders are free. It is a claim
  that they can draw, at a higher GPU cost, while the specialized shader
  compiles. In `force` that cost is the whole frame: about 77 ms GPU on the
  dealership and about 45-88 ms on High Speed Ring, against about 3.3 ms and
  8-14 ms with the switch unset (`RSX_SSAA=0`). `=1` is the pending-only path
  measured in the status section. Settled frames there are back in the
  specialized GPU band; the remaining stalls are first-use interpreter PSOs,
  which are not stored in the disk cache.
