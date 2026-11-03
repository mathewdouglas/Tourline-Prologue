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
screenshots are below. `RSX_SHADER_INTERP=1` and the vertex interpreter
are not run yet.

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

An interpreter pipeline key is native state only:

- blend state and write mask (`blend`, `cmask`)
- render-target count and DXGI format
- depth format and whether a depth buffer is bound
- cull
- stencil state
- sample count (the MSAA class already stored in the cube-mask high bits)
- depth-export on or off (changes `SV_Depth`)

It does not include the fragment program, cube mask, unnormalized mask,
sampler bank, shadow, gamma, expand, or constant values. The starter
observation is about 57 distinct blend/RT/cull/stencil classes. Sample count
and depth-export multiply that by a small factor. The implementation records
the distinct interpreter keys it actually creates (`RSX_SHADER_INTERP_LOG=1`)
and precreates the ones seen, rather than the full cartesian product.

Those pipelines are created at device init for the classes observed on the
starter, and on first use for any class that was not listed. First use of an
unlisted class can still hitch once, by about 4 ms, not by a shader compile.
Stage 3 measures whether that residual hitch shows up. If it does, the
missing class is added to the precreate list. The list is data in the
runtime, not a capture.

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

Stage 3 wires `=1` into the pending-draw path. With an empty private shader
cache, a first dealership visit and an HSR race are compared with today's
async policy: missing draws, frame times (`scripts/test/race.ps1 -FrameTest`),
and F3 logs. Interpreter pipelines for the observed native classes are
created ahead of that run if the stage 1 log says that is what removes the
hitch.

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
  8-14 ms with the switch unset (`RSX_SSAA=0`). `=1` is implemented in the
  replay hook and is not measured.
