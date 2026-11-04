# Shader-first enumeration

`scripts/shader_enumerate.py` compiles fragment and vertex programs found in
the game assets across a small set of global contexts learned from the
observed starter. The goal is a DXBC cache that does not depend on someone
playing every car. Native pipeline objects stay with the runtime background
worker and the observed templates.

The CLI is a maintainer tool. Development player preparation now consumes a
metadata-only plan generated with it; see the player integration section below.
`GT5P_ENUM_STOP=<file>` stops a compile between chunks when that file exists.
Outputs are game-derived and stay in gitignored storage. This note records
the method and the measurements; it does not ship a cache.

The profile tuple is exactly `prepare_material_shaders.fragment_profile`:
exposure, the packed cube word, stencil, unnormalized units, sampler nibbles,
the gamma/volume word, the shadow word, high-unit texel flags, the used-unit
mask, and the final dither flag. A profile splits into a program-local vector
and a global context. The local vector is the state of the units a material
binds itself (shape, gamma, volume, texel addressing, sampler nibble). The
global context is a handful of scalars plus the state of the global samplers
the program actually samples.

Bits 16–19 of `state.cube` are the MSAA sample-count nibble (0, 2, or 4 in
this starter: 1×, 2×, 4×). The environment cube is texture unit 14, cube bit
30, and it does not vary within a program here. Sample count is a global
setting axis. Passing `--msaa 2,4` replicates every observed multisampled
context at those counts and keeps every 1× context as it was learned. An
empty `--msaa` keeps the learned counts only.

Material tables supply the local vector when the material parses and its
used-unit mask matches the program. Programs with no usable material borrow
up to four donor local vectors observed on the same local-unit mask
(`--fallback-locals 4`). Global sampler identifiers follow the material when
it has them, and otherwise the observed convention (dither 103, shadow 87,
environment cube 71, and the rarer 96, 104, and 115). Shadow flags are
dropped when no sampled unit is a shadow map, matching the production trim.
The catalogue stores many raw payloads per program because inline constants
differ. The identity hash collapses those, and the compile uses the first
payload of each identity in sorted order.

## Sample count and the production key

The offline compiler writes the same 16-hex HLSL source key the runtime
stores as `RSX_SHADER_CACHE/%016llx.dxbc`. Across the finished catalogue
compile, every identical program body (same identity, same unit state, same
scalars apart from the sample nibble) was compared:

| pair | both compiled | same key | different key |
| --- | ---: | ---: | ---: |
| 1× vs 2× | 12,031 | 0 | 12,031 |
| 2× vs 4× | 12,031 | 12,031 | 0 |

No identity produced two different keys for one body at the same sample
count. The 1× shader differs by the per-sample interpolant qualifier. 2× and
4× compile to one DXBC. Enumerating both sample counts repeats that work.
One nonzero sample count is enough for shaders. Native pipeline state still
depends on the sample count, and that stays on the observed-template path.

Of 3,034 distinct observed (identity, profile) pairs that exist in the
catalogue, 2,976 compiled to the template's recorded `fp_source`, none
compiled to a different key, and 58 had no successful compile in the memo.

## Held-out recall

The starter provenance is the template history, labeled by record key:

| label | commit | records |
| --- | --- | ---: |
| earlier | `273f1df` | 3,102 |
| phase 201 dealership | `24e501f` | 1,348 |
| phase 206 collection | `9254369` | 1,219 |

The current bundle has 5,669 records and 1,404 fragment programs. 1,189 of
those programs (4,683 records) occur in the asset catalogue. The other 215
programs (986 records) have no asset payload and stay on the observed path.

Recall asks whether contexts learned from a training split, crossed with each
program's local vectors, reproduce the held-out profiles and their production
keys. The candidate generator sees only the training split. The key of a
candidate is read from the finished catalogue compile (one payload of every
identity, contexts learned from the whole starter). A hit is an exact source
key. A candidate the catalogue compile did not produce is unresolved and
counts as a miss. The seed for the random split is `0x47543550`.

Test programs are disjoint from the training programs in the random split.
Content splits overlap where one program appears in more than one phase, so
"new" counts only programs absent from the training labels.

| split | MSAA axis | programs (new) | profile recall | key recall | candidates / program | wasted keys / program | unresolved | fully covered |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| random 50% | learned | 594 (594) | 1,455/1,499 (97.1%) | 1,407/1,449 (97.1%) | 6.76 | 2.86 | 73 | 576/594 |
| random 50% | 2× and 4× | 594 (594) | 1,456/1,499 (97.1%) | 1,407/1,449 (97.1%) | 7.86 | 2.86 | 86 | 576/594 |
| phase 206 vs earlier+201 | learned | 353 (266) | 308/678 (45.4%) | 674/678 (99.4%) | 4.79 | 2.85 | 0 | 350/353 |
| phase 206 vs earlier+201 | 2× and 4× | 353 (266) | 674/678 (99.4%) | 674/678 (99.4%) | 7.03 | 2.85 | 0 | 350/353 |
| phase 201 vs earlier | learned | 348 (329) | 715/718 (99.6%) | 715/718 (99.6%) | 4.89 | 2.80 | 0 | 346/348 |
| phase 201 vs earlier | 2× and 4× | 348 (329) | 715/718 (99.6%) | 715/718 (99.6%) | 7.15 | 2.80 | 0 | 346/348 |
| phase 201 vs the rest | learned | 348 (284) | 715/718 (99.6%) | 715/718 (99.6%) | 6.11 | 2.81 | 0 | 346/348 |
| phase 201 vs the rest | 2× and 4× | 348 (284) | 715/718 (99.6%) | 715/718 (99.6%) | 7.16 | 2.81 | 0 | 346/348 |

Phase 206 introduced every 4× record in the starter. With learned sample
counts, 366 of its profile misses are `scalar:msaa=4`. Those profiles still
match a production key, because the generated 2× candidate compiles to the
recorded 4× key. Expanding the axis removes that profile gap and does not
change the wasted-key count: the extra 4× candidates are duplicate keys.

Misses that remain after expanding sample count:

| split | misses |
| --- | --- |
| random 50% | `local(fallback)` 19, `cap/combination` 17, `local` 5, `scalar:other` 2 |
| phase 206 vs the rest | `local` 3, `scalar:other` 1 |
| phase 201 vs earlier, and vs the rest | `cap/combination` 1, `local` 2 |

`local` means the observed local vector is not among the material's parsed
locals. `local(fallback)` means the program had no usable material and the
donor locals for its unit mask did not include the observed vector.
`scalar:other` means output gamma, shadow flags, dither, or stencil differed
from every projected context. `cap/combination` means the observed global
context was in the projected set, so the miss is the combination with the
local vectors rather than a missing scalar or sampler type. No context cap
was applied. No miss in these splits was charged to a missing global sampler
type.

New-program key recall is 675/677 for the dealership against the earlier
starter, and 548/551 for the collection against everything before it.

Vertex programs are compiled as the catalogue inventory at GPU modes 0 and 1
(1,120 programs, 2,240 variants), not as a context product. Against the
starter, 478 of 482 observed (program, GPU mode) variants have their source
key in that set: 14/18 at mode 0 and 464/464 at mode 1. The four misses are
mode 0 variants that are not in the asset inventory, so the compile never
selected them. All 2,240 inventory compiles succeeded.

## Catalogue compile

The fragment catalogue is `shadercache/library-v1/all`: 8,142 payload files,
8,069 accepted, 5,864 identities, plus 1,120 vertex programs. Material tables
cover 5,319 programs, 5,249 of them with a complete local vector. The other
615 use donor locals.

The catalogue plan at `--msaa 2,4` is 39,937 fragment jobs (6.81 per
identity). 82 identities produced no job: the projection found no global
context for their sampler-type set, or a fallback program had no donor local
for its unit mask. Four locked stages, 40 chunks of 1,024 jobs (the last
chunk is one job), compiled 39,803 jobs and failed 134, across 34 identities,
in 963.2 seconds of stage time (299.6 + 300.9 + 287.0 + 75.7). About 41
successful fragment jobs per second on this machine. The stage reports'
failure counters disagree with each other because a resumed chunk is not
counted again; the 134 is a scan of the chunk rows. The compiler's reason
for each failure was discarded with the work log and was not re-run.

Vertex compilation was one locked run: 9 chunks, 2,240 compiled, 0 failed,
307.0 seconds.

The private cache holds 27,151 DXBC files, 292,693,484 bytes. That is 24,911
distinct fragment source keys plus the 2,240 vertex source keys.

## Runtime

The reference engine (180,406,784 bytes, the v0.2.3 binary) contains
`RSX_SHADER_CACHE` and the pipeline metric switches. It does not contain
`RSX_PSO_COVERAGE`, so the Phase 192 coverage log is not available without a
separate patched engine. `shader_pending` is a per-frame flag and this binary
does not print a pending-draw count. What it does print, with
`RSX_PIPELINE_METRICS=1`, is `shader_compiles` (incremented on D3DCompile).
`RSX_PSO_TIMING=1` prints `[pso-time]` pipeline misses for each 5 second
window and the same compile total as "compiled so far". A draw skipped
because a shader was still compiling is not in that line.

The route is High Speed Ring through `scripts/test/race.ps1` at the script's
720p and `RSX_MSAA=2`, sampling for 20 seconds from the moment the grid
appears, with `RSX_SHADER_ASYNC=1` and `RSX_SHADER_WARMUP_SCAN=0`. The game
root and both caches are private copies under scratch. The empty cache ran
first. The enumerated cache is a copy of the 27,151 DXBC files, so the
compile directory itself is not what the game writes. Disk lookup is the
runtime's HLSL source-key file name (`%016llx.dxbc`), which is what the
offline compiler wrote. A hit reads that file and does not call D3DCompile.
`shader_compiles` counts D3DCompile calls. `[dxbc-mem]` misses count the
times that bytecode was not already in the process memory cache, including
both disk hits and compiles. Native pipeline blobs (`pso_*.bin`) are a
separate cache; enumeration does not write them.

Both runs reached the grid about 65 seconds after launch and then sampled
20 seconds. The window shot 10 seconds into that sample shows the same HUD
on both (position 8/16, lap 1/2, about 120 km/h, race clock still at
0:00.000). The empty-cache shot shows that HUD over a black view. The
enumerated-cache shot shows High Speed Ring.

| run | last `shader_compiles` | DXBC files after | dxbc-mem hits / misses | pso-disk hits / misses / saved | median fps |
| --- | ---: | ---: | --- | --- | ---: |
| empty private cache | 375, with further compile lines after that sample | 0 → 399 | 3 / 366 | 0 / 285 / 285 | 20 |
| enumerated private cache | 205, and that sample is the end of the log | 27,151 → 27,360 | 7 / 1,154 | 377 / 1,066 / 1,066 | 29 |

The empty run's last pipeline-metrics line is `shader_compiles=365`; the
later pso-time line says 375, and 19 more fragment-compile lines follow
before the process was stopped. The 399 files are the disk result. The
enumerated run's last metrics line and last pso-time line both say 205, and
the cache grew by 209 DXBC files. Memory misses (1,154) minus compiles (205)
are reads of a DXBC file that was already there: about 950 shaders served
from the enumerated cache. The empty run's misses and compiles stay in step,
and it started with no files.

Pipeline creation was not removed. The empty run finished the sample at 284
driver pipeline calls and 0 cached calls. The enumerated run reached 1,442
driver calls and 376 cached calls, and wrote 1,173 `pso_*.bin` files beside
the DXBC. Those cached calls are pipeline blobs created and then reused
inside that one process. The enumerated run also drew more (the present
thread's last pipeline-cache size is 949, against 284), which is why its
median over the same 20 seconds is 29 fps rather than 20. The on-screen
"compiling" badge counts shaders and pipelines together. Its longest showing
was 12.2 seconds on the empty run and 14.5 seconds on the enumerated run;
the long enumerated showing lines up with the pipeline burst, not with a
larger shader-compile count.

## Limits

This is one prologue catalogue, one GPU, and one settings pair on one route.
It is not whole-game coverage and it is not a first-draw guarantee. Programs
with no asset payload (215 fragment identities) are invisible to enumeration.
One payload per identity leaves other constant variants uncompiled. 82
programs had no candidate. 134 fragment jobs failed, and their compiler
errors were not kept. Donor locals and projected contexts can emit keys the
held-out route never uses (about 2.8 wasted keys per test program). 2× and
4× duplicate DXBC when both are enumerated. Native pipelines are not
enumerated.

A GT5 catalogue would need that game's own executable, volume, material
tables, and extracted programs, and the context set would have to be
re-measured from GT5 play. The prologue starter does not establish those
contexts. At the rate above, a few tens of thousands of fragment jobs are a
quarter-hour of chunked offline compile; a much larger car list is hours of
the same kind of run, on that game's own assets, rather than a claim that
this cache covers it.

## Default player enumeration (development, 2026-11-04)

The first-run offer, **Prepare shaders.cmd** and F1 **Debug > Prepare shaders**
all enter the same helper. Enumeration is enabled inside that optional operation
by default. `GT5P_PREPARE_ENUMERATE=0` restores the previous template-only path,
including its previous generation identity. This changes no published release.
The developer `pipeline_template.prepare()` API remains opt-in via its
`enumeration` argument.

After the existing template, additional-translation and pack stages succeed,
**Enumerating shaders** compiles asset fragment/vertex DXBC in the new generation's
cache. It creates no native PSOs, recipes, membership or packs. Native preparation
remains the 12,669-record template path; other native pipelines remain with the
runtime background worker. Enumeration currently uses the default translation;
the template's existing settings-aware additional translation remains separate.

`assets/shader-enumeration/gt5p-disc-v1/` contains only identifiers, numeric
profiles and offsets. Its five files total 2,750,681 bytes:

| file | bytes |
| --- | ---: |
| plan.json | 1,014,093 |
| programs-0000.json | 719,650 |
| programs-0001.json | 719,599 |
| programs-0002.json | 235,711 |
| volume.json | 61,628 |

The location map covers 5,864 fragment and 1,120 vertex identities. Its 371
archive containers are a subset of the previously verified numeric search map;
no additional archive locations were needed. The maintainer generator matches
catalogue payloads to their indexed original containers and checks their full
SHA-256, then the bounded packed reader independently verifies every container
and program against GT.VOL/ELF before publishing metadata. Players need only
their original supported volume and ELF, without a catalogue or extraction.

The plan is generated by the `shader_enumerate` candidate machinery from all
starter contexts with `msaa=[2]`, four fallback locals and no local/context cap.
It has 1,540 interned numeric profiles, 34,355 fragment jobs and 2,240 vertex
jobs (GPU-fetch modes 0/1), 36,595 total. It retains 1x and 2x and never repeats
the equivalent 4x shader. The 69 fragment identities with no projected candidate
remain without a job; runtime demand is still necessary.

`GT5P_PREPARE_ENUMERATE_SAMPLE_SHARE=1` is an explicit integration option for a
renderer whose **offline default** enables `RSX_FP_SAMPLE_SHARE`. It clears the
sample nibble and deduplicates (identity, profile), reducing fragment jobs to
22,282. The historical renderer rejects this option because it lacks the switch.
This flag does not enable renderer source sharing itself. Keep it unset/0 with
the current engine, or when renderer sample sharing is disabled. Changing the
flag changes both the generation token and checkpoint contract.

Loading checks schema/version, exact fields, numeric widths, duplicate jobs,
program/profile indices, program/container bounds, file SHA-256 pins, the ELF,
volume and starter digest. The plan is capped at 8 MiB / 65,536 fragment jobs /
8,192 vertex jobs; program shards are each under 1,000,000 bytes. Resolved raw
programs are capped at 128 MiB. The existing packed reader retains its decoded
container, time and full-volume hash guards.

The helper owns the existing preparation checkpoint throughout enumeration.
Sequential 256-job chunks use the production exact fragment batch and bounded
vertex derive workers, retaining their process, bytecode and memory limits.
Each successful result records its source-key filename, DXBC SHA-256 and size;
resume verifies those files before skipping a completed chunk. Private transient
inputs are removed after owned compilers exit. Per-job compiler rejections are
counted and retained as bounded error text; they do not fail the optional stage.
Failed fragment processes (including a missing offline guard or malformed batch
results) and conflicting vertex cache writes abort the stage; they are not
converted into completed best-effort chunks. Cancellation, metadata/cache
rejection or other stage failure leaves the old
cache selection intact. Selection changes only after the complete helper succeeds.
The report adds `enumeration` counts, verified lookup, timings and failure examples.

Packaging explicitly validates and includes these five metadata files. PyInstaller
discovers the new Python module through its normal import graph; the metadata
lives beside the player assets and needs no extra embedded build data. Focused
older frozen fixtures explicitly disable enumeration to retain their original
small template/translation scope.

The earlier held-out recall and HSR result above remain evidence for the enumeration
method; the acceptance run below measures this player integration.

### Packed-player acceptance (2026-11-04, 12,669-record starter)

One frozen helper, private storage, original GT.VOL/ELF, clean PATH, default
translation, four vertex workers; every step ran through the machine test lock.
The run was split by the driver's chunk budget (cancel through the real player
marker): run 0 (budget 8) and run 1 (budget 40) ended with exit 2, the previous
selected cache untouched and the generation `interrupted`; run 2 resumed and
completed with exit 0.

| quantity | measured |
| --- | ---: |
| fresh template stage (12,669 native pipelines, 4,096-record chunks) | 630 s |
| template revalidation on each resume | 265-286 s |
| enumeration jobs requested | 36,595 (34,355 fragment + 2,240 vertex) |
| prepared / failed | 36,473 / 122 (0.33%) |
| failed vertex jobs | 0 |
| failures | all fragment jobs with no bytecode produced by the offline compiler; reported, left to demand compilation |
| sum of chunk compile time (fragment 1,128 s + vertex 286 s) | 1,414 s (23.6 min) |
| lookup of 6,984 programs from GT.VOL/ELF (2.05 GB hashed) | 19.6 s |
| final resumed stage, 96 new chunks + checking 48 retained | 1,070 s |
| new DXBC files / bytes added to the generation cache | 25,847 / 228,983,256 |
| whole cache after enumeration | 33,464 files, 334,776,240 bytes |
| enumeration checkpoints | 144 files, 4,780,344 bytes |

Added preparation time on this machine is about 24 minutes of compile plus
about 20 s of lookup and resume verification, on top of a fresh 10.5 minute
template stage. Disk adds roughly 219 MiB of bytecode. A repeat preparation with
nothing changed re-verifies the retained results instead of recompiling.

Correctness against the starter: of 12,669 template records, 11,439 fragment and
12,639 vertex source keys reappear among the enumerated results, with 0
mismatches. This is a consistency check on programs the enumeration covers, not
a hit-rate claim for unseen play; the remaining records have a program with no
asset match or a profile outside the learned contexts. All 12,669 native
pipelines were verified in the final selected cache.

Other checks: `reject` (a checkpoint whose plan pin is altered) exits 1 with
"Enumeration checkpoint mismatch", keeps the cache selection and the checkpoint
bytes are restored; `rollback` (`GT5P_PREPARE_ENUMERATE=0`) selects a template-only
generation with no `enumeration` report entry or folder, byte-identical packs,
and leaves the enumeration generation intact (218 s, 7,617 DXBC files, 105,792,984 bytes, zero shader compiles). Focused synthetic tests
(`preparation_enumeration`, `preparation_checkpoint`, `preparation_shader_pack`,
`shader_enumerate`, `pipeline_template`, `player_package`) pass. One machine,
one GPU, one settings pair; no live hitch, whole-game, other-settings or
sample-sharing claim.

### Re-pinning after any starter change

The plan pins the starter's digest (`template_sha256`) and learns its contexts
from the starter's records, so any change to `assets/pipeline-templates/gt5p-disc-v2/`
(new records, re-keyed records, a changed source contract) must be followed by a
re-pin. One command, from the repository root with the Python virtual environment
(about 4 minutes, dominated by hashing the 2 GB volume and reading the catalogue):

```
set GT5P_PREPARE_VOLUME_LIBRARY=<path-to>/volume_reader.dll
python scripts/release/build_enumeration.py --catalog <shadercache>/library-v1/all ^
    --volume <GT.VOL> --elf <EMAIN.ELF>
```

`--template` defaults to the shipped starter and `--volume-map` to its
`search-map.json`. With no `--output` the generator writes a private
`scratch/enumeration-repin` folder, runs the player loader on it (schema, pins,
container and program checks against the starter), and only then replaces
`assets/shader-enumeration/gt5p-disc-v1/*.json`. The location files are
byte-identical across re-pins unless the volume map changes. Commit the changed
`plan.json` (the `.json` files there carry a 2 MB allowance in
`scripts/check_no_game_files.py`; they hold identifiers and numbers only).
Re-run `scripts/test/preparation_enumeration.py` and `scripts/test/player_package.py`.

Re-pinned for the 12,669-record starter (Phase 212): fragment jobs rose from
27,872 (5,669-record contexts) to 34,355 and profiles from 1,239 to 1,540; the
location files did not change.

### Collapsing to one sample class

The plan carries 1x and 2x fragment classes (profile sample nibble 0 / 2). When
the renderer's offline default is `RSX_FP_SAMPLE_SHARE=1` (1x and multisampled
sources identical), set `GT5P_PREPARE_ENUMERATE_SAMPLE_SHARE=1`. The stage then
clears the nibble and deduplicates, with no regeneration: 34,355 -> 22,282
fragment jobs. The flag is refused (cache selection preserved) if the engine
binary lacks the `RSX_FP_SAMPLE_SHARE` switch. When sample sharing becomes the
renderer's default, make this flag default-on in `preparation_enumeration.sample_share()`
in the same change, and re-key/re-pin the starter first (its source keys change).

Reproducible checks use `scripts/test/preparation_enumeration.py`,
`scripts/test/player_package.py`, `scripts/test/preparation_shader_pack.py`,
`scripts/test/preparation_checkpoint.py` and `scripts/test/shader_enumerate.py`.
The frozen acceptance driver is `scripts/test/player_enumeration_native.py`:
`verify`, `build` (in an x64 VS environment), `run --budget N`, `reject`, and
`rollback`, all with `--output scratch/<private-directory>`. Its private
`inputs.json` names `reference_root`, `reference_helper`, `runtime`, `game`
(PS3_GAME root) and `elf`; machine paths stay outside tracked files. Run each
through `run_locked.py` and check tasklist first. A budget cancels through the
real player marker after N newly published chunks; it is a validation control,
not a player preparation limit.

Completed chunks resume within the same generation. Cross-generation verified
reuse remains template-scoped: a changed plan or a fork after learned pack changes
can compile enumeration again. No old generation is deleted automatically.
