# Fragment sample-count sharing

`RSX_FP_DUAL_SHAPE=1` makes a one-sample fragment profile and a multisample
profile of the same program compile to one pixel shader. Unset, or any value
other than `1`, leaves the compiled text as it is today. The pipeline sample
count is unchanged either way.

This is the specialization behind starter `state.cube` bits 17 and 18. Those
bits are a sample count, not a cube-versus-2D texture shape. A second SRV for
every varying unit was not required for this split, and it is not in the
overlay.

## What the cube word stores

`cube_units16` in `libs/video/rsx_d3d12_backend.c` unpacks texture units as
`(key & 0xF) | ((key >> 16) & 0xFFF0)`. Units 0–3 are bits 0–3. Units 4–15 are
bits 20–31. Bits 16–19 are the sample count the draw ORs in
(`dr_cube_mask(dr) | (off_rt.ms ? ms_n << 16 : 0)`). The pipeline uses that
nibble as `SampleDesc.Count`.

On the 5,669-record starter (`assets/pipeline-templates/gt5p-disc-v2`):

| Cube bit | Records | Meaning |
| --- | ---: | --- |
| 1, 2, 3 | 29, 19, 3 | Cube on texture units 1, 2, 3 |
| 8–11 | 3,493 down to 302 | sRGB read on units 0–3 |
| 12 | 5,640 | sRGB encode on write |
| 17 (`0x20000`) | 2,121 | 2 samples |
| 18 (`0x40000`) | 662 | 4 samples |
| 30 (`0x40000000`) | 2,624 | Cube on unit 14 |

Unit 14 is the environment map (`envMapSampler`, kind `0x901`). Its cube flag
is constant for each fragment program: 669 programs always cube, 735 never,
and 0 of 1,404 are both. `cube_units16(0x20000)` and `cube_units16(0x40000)`
are both 0. Volume units live in `ghi`, not in this word.

Inside one program, the bits that vary are 8 (6 programs), 9 (1), 12 (2),
17 (1,103), and 18 (353). No program varies its unpacked cube-unit mask.

## The 1,741 pairs

Of 1,404 fragment programs, 1,373 have more than one `ps` value, and those
form 3,724 pairs of `ps` values. For each pair the nearest state difference
was taken across records. 1,749 pairs differ only in `cube`. Their XOR values:

| XOR | Pairs |
| --- | ---: |
| `0x20000` (1 sample vs 2) | 1,460 |
| `0x40000` (1 sample vs 4) | 281 |
| gamma bits, sometimes together with a sample bit | 8 |

`0x20000` and `0x40000` are the 1,741 pairs. A 2-vs-4 pair (`0x60000`) does
not appear: those records already share `ps` and `fp_source`. Collapsing the
nibble only to "more than one sample" therefore does not merge any current
shader. The starter has 5,308 full states, 3,609 `fp_source` values, and
3,585 `ps` values (3,605 `(fp, ps)` pairs).

The only fragment-text change is in `vp_get_fp_pso`. When `RSX_SSAA` is on
(the default) and the nibble is greater than 1, interpolants are rewritten to
`sample float4`. Counts 2 and 4 take the same path. Count 1 does not. The
library compiler returns before the pipeline object is created, so the batch
key is the HLSL source hash (`fp_source`). `ps` is the FNV-1a of the DXBC.

## What the switch does

`patches/ps3recomp-fp-dual-shape.patch` adds `fp_sample_qualifier`. With
`RSX_FP_DUAL_SHAPE=1` the `sample` rewrite runs for every count, including
one sample, still gated by `RSX_SSAA`. `SampleDesc.Count` still follows bits
16–19. The root signature, sampler registers `s0`–`s15`, and texture
declarations are untouched.

Emitting that qualifier for one sample as well makes the 1-sample HLSL equal
the multisample HLSL. A union of current `fp_source` values across records
that differ only by bits 16–19 predicts 3,609 sources become 1,865, and 3,585
bytecode keys become 1,854.

A dual `Texture2D` plus `TextureCube` declaration would not merge these
pairs. Unit 14 does not change shape inside a program in this starter, and
the sample-count bits are not a unit index. That design would also add SRVs,
a null descriptor of the unused dimension, and a uniform branch around every
`Sample` / `SampleCmp` / `SampleBias` / `SampleGrad` / `SampleLevel` rewrite
(derivatives, projection, shadow compare, gamma, unnormalized coordinates).
It stays future work for a capture where one unit is actually both shapes.

## Offline compile

Private engine: current `patches/ps3recomp-4e8f3ca8-local.patch`, then the
overlay, with only `rsx_d3d12_backend.c` relinked ahead of the v0.2.3 runtime
archive (`scripts/test/fp_dual_shape_build.py`). Starter programs come from
`player-map.json` offsets in the original volume. Catalogue filenames are the
raw SHA-256; the starter stores `fp_identity()`, and 215 of the 1,404
identities are absent from `shadercache/library-v1/all`.

`scripts/test/fp_dual_shape_native.py` compiles the three helpers with no
GPU. `cube_units16(1<<30)` is unit 14. `cube_units16(0x20000)` and
`cube_units16(0x40000)` are 0. The qualifier follows "nibble > 1" for an
unset value, `0`, `2`, and an empty string. `RSX_FP_DUAL_SHAPE=1` is true
for every tested mask, including a count of 1 and unit 14's cube bit.

`scripts/test/fp_dual_shape_batch.py` compiled all 3,696 unique fragment
profiles (5,669 records, 1,404 programs), each into its own shader cache:

| | Switch off | Switch on |
| --- | ---: | ---: |
| Compiled / failed | 3,696 / 0 | 3,696 / 0 |
| Distinct source keys | 3,609 | 1,865 |
| Distinct bytecode keys | 3,585 | 1,854 |
| Profiles whose key matches the starter | 3,696 source, 3,696 bytecode | 1,831 source, 1,838 bytecode |
| Wall time, including the volume read | 142.2 s | 85.3 s |

Off matches the shipped starter on every profile. On lands on the predicted
1,865 and 1,854. The 1,831 profiles that still match are the ones whose text
did not change (already multisample, or no interpolant rewrite). The faster
on-run is the shared source key: a second profile hits DXBC already compiled
in that process. Both runs were locked, one at a time, with private
`RSX_SHADER_CACHE` directories under `scratch/fp-dual-shape/`.

## In-game pictures

1080p, private caches, `PS3_VERBOSE=0`, PrintWindow. The 2× runs set
`RSX_MSAA=2`. No pixel-shader compile failure and no device-removed line in
any of these logs.

Dealership, switch off, then a warm retry of switch on (the first on launch
stayed on the top menu and never reached `DealerTopRoot`; the warm retry did,
at 32 s, the same as off). Both pages were 1920×1080 at 30 fps, 2,164 draws
off and 2,167 on. The showroom turntable moves. Two frames two seconds apart
in one run differ by mean absolute channel sum 27.7 (off) and 29.7 (on).
The off-versus-on pair differs by 18.2 and 20.4, which is inside that motion.
Both frames are the Acura NSX showroom: red and black paint, glass, and floor
reflections. They are not a phase-locked pair, so this is not a pixel-identity
result.

High Speed Ring, 30 s sampled after 25 s, a shot every 15 s. Median frame
rate 8.87 fps off and 12.81 fps on. The two end frames are different corners
(pit straight versus the start gantry). Almost every pixel differs (mean
absolute channel sum 194.6 and 111.9). Both frames show the track, cars,
shadows, and sky with no missing surfaces. The frame-rate gap is not a clean
GPU comparison: the cold caches hitch, and the cars are not at the same place.

GPU time is the `gpu N ms avg` field of `[present-prof]`, first sample
dropped:

| Run | Kept samples | Mean of the averages |
| --- | ---: | ---: |
| Dealer 2× off | 9 | 5.27 ms |
| Dealer 2× on, warm retry | 8 | 4.63 ms |
| Dealer 1× off | 7 | 4.59 ms |
| Dealer 1× on | 7 | 4.31 ms |
| Race 2× off, last 6 | 6 | 19.61 ms |
| Race 2× on, last 6 | 6 | 13.58 ms |

The dealer means sit together. The race means do not describe the same
workload.

An extra 1080p 1× pair (`RSX_MSAA=1`) is the path the switch actually
changes. Both reached the showroom at 32 s, 30 fps, 2,182 and 2,183 draws.
The 1× on log has no pipeline or compile failure. Paint, glass, and the floor
reflection are present. The right-hand car had cycled from Berlina Black to
Sebring Silver, so the frames are not pixel-equal (mean absolute channel sum
13.5, still below the two-second turntable delta above). One-sample
`sample` interpolation producing the same shading as the old 1× shader is
supported by that picture and by the matching draw count. It is not proven by
a locked pixel diff.

## If this became the default

Do not regenerate `gt5p-disc-v2`. Turning the switch on changes `fp_source`
and `ps` for the one-sample rows. Multisample rows keep their keys (1,831 of
3,696 profiles still matched). Any pipeline key that includes the bytecode
changes with those rows. The sample-count nibble, `SampleDesc.Count`, and
`root_signature_keyed` stay. The renderer contract hashes
`patches/ps3recomp-4e8f3ca8-local.patch` only; this overlay is a separate
file, so the shipped contract does not move until the behaviour is folded
into that patch.

Preparation would then treat one-sample and multisample profiles of one
program as one fragment compile. The cube word stored on the template can
keep the real sample count for the pipeline object.

## What is left

A dual `Texture2D` / `TextureCube` binding, selected by a root constant, for
a unit whose shape really varies. Nothing in this starter needs it. The
per-sample qualifier at one sample has no phase-locked pixel proof against
the old 1× shader. `RSX_SSAA=0` still disables the qualifier on every count;
that combination was checked in the helper, not in a frame.
