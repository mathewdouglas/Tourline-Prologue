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

Since Phase 213 the renderer's offline default enables `RSX_FP_SAMPLE_SHARE`,
so `GT5P_PREPARE_ENUMERATE_SAMPLE_SHARE` now defaults to `1`: the stage clears the
sample nibble and deduplicates (identity, profile), reducing fragment jobs to
22,282. `=0` restores compiling both sample classes (34,355 jobs); use it only
with an engine that lacks sharing. An engine without the `RSX_FP_SAMPLE_SHARE`
switch rejects the collapsed mode. This flag does not enable renderer source
sharing itself. Changing the flag changes both the generation token and
checkpoint contract.

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
binary lacks the `RSX_FP_SAMPLE_SHARE` switch. Phase 213 made sample sharing the
renderer's default, re-keyed the starter, and this flag is now default-on in
`preparation_enumeration.sample_share()` (`=0` rolls back).

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

## Enumeration speed work

Branch `t3/enumeration-speed` (development, unfinished; see "Not done"). Goal: the full
**Enumerating shaders** list in about five minutes on the 6-core / 12-thread i5-12400F, with the same
bytecode, no dropped jobs, and no time budget: every job still runs before the stage reports complete.
All numbers are single runs on this machine. The stage is measured in isolation
(`scripts/test/enumeration_speed.py stage`: the real `preparation_enumeration.stage()` against the original
GT.VOL/ELF, a private engine built from the reference objects, and a cache seeded with the DXBC files of a
template-only generation, so jobs the template stage already produced are real disk hits), not through the
frozen player helper.

### Measured: full list, before and after

| | baseline (`GT5P_PREPARE_COMPILER_WORKERS=legacy`, `GT5P_PREPARE_ENUMERATE_BATCH=256`) | new defaults (10 workers, 4096-job launches) |
| --- | ---: | ---: |
| stage wall time | **1,028.5 s (17.1 min)** | **493.8 s (8.2 min)** |
| fragment (22,282 requests, 16,019 real compiles) | 708.7 s | 271.4 s |
| fragment engine launches | 175 | 12 |
| fragment launch overhead (process wall minus in-engine batch time) | 341 s | 27 s |
| vertex (2,240 jobs) | 293.4 s, nine pools of 4 workers | 198.1 s, one pool of 10 workers |
| volume lookup (19 s) and the rest | ~25 s | ~24 s |
| prepared / failed jobs | 24,434 / 88 | 24,434 / 88 |

The results are identical: all 97 checkpoint chunks have the same (source key, DXBC SHA-256, size) rows and
the two caches hold the same 21,779 `.dxbc` names. The 88 failures are fragment jobs whose compile failed
(the same class as the earlier 122). A 2,319-request fixed subset (first 3,200 plan fragment jobs, 256
vertex jobs): 121.2 s legacy/256, 104.6 s with 1024-job launches at 4 workers, 79.8 s with 10 workers and
1024-job launches.

Where the time went in the baseline: engine process start-up and shutdown cost about 2 s per launch, and the
fragment stage launched 175 times (256-job chunks, two dither classes each), which was 48% of its wall time.
Within a launch the single submitting thread needs 1-2 ms per job to translate, so with 10 workers the
4,096-job batch is compile-bound, not submit-bound (`translate_submit` 33 s for all jobs, overlapped with the
workers). Vertex peak commit: 60 MiB per worker, 479 MiB aggregate with ten workers. The 12 launches still
carry roughly 2.2 s of fixed cost each.

### Changes (all helper-side; no engine or starter change)

| Switch | Default | Rollback |
| --- | --- | --- |
| `GT5P_PREPARE_COMPILER_WORKERS` | `auto`: logical processors minus two, 2..10, and no more than free RAM allows (256 MiB per worker after a 1 GiB reserve); resolved once per process | `legacy` (4 on 8+ logical processors, else 2), or an explicit 2..12 |
| `GT5P_PREPARE_ENUMERATE_BATCH` | 4096 jobs per fragment engine launch; the vertex pool takes every remaining chunk at once and writes each 256-job checkpoint when it completes | `256` (previous), 512, 1024 or 2048 |

Fragment threads are the engine's `RSX_SHADER_WORKERS`; vertex workers are processes whose per-process cap
stays 512 MiB, with the aggregate job cap 1 GiB up to four workers and 256 MiB per worker beyond that
(`MAX_WORKERS` 4 -> 12). Normal game worker policy is unchanged. The worker setting applies to the whole
offline preparation (template stage included); only the enumeration stage was re-measured. Checkpoints
remain per 256-job chunk, so a cancelled fragment launch loses at most one 4,096-job batch (about 35 s here).
The report gains `compiler_workers`, `batch_jobs`, per-launch `batches` and `vertex_batches` (with
`GT5P_PREPARE_SHADER_PROFILE=1` they carry the engine and worker timings).

### Measured: jobs that could be skipped (step 3)

Nothing worth skipping was found, and no job was dropped. In a 2,061-row sample, 288 jobs (14%) already had
their source key from the template stage, and a further 276 shared a key with another job in the same run;
the engine already compiles each distinct missing key exactly once (1,515 compiles for 1,785 distinct keys,
270 of them on disk), and a skipped job would save only its translation (about 1.3 ms). Vertex GPU-fetch
mode 0 variants were kept: their source differs from the mode 1 source, so they are not provably redundant.
Priority ordering was not implemented: with tails of a second or two per launch it would not change wall time.

### Measured: cheaper generated code (step 5, nothing defaulted)

Single-thread `D3DCompile` over real generated sources (`scripts/test/hlsl_compile_bench.py`; sources from
`RSX_SHADER_SRC_DUMP`, ignored storage only). Every rewrite changes the shader source key.

| Fragment (200-300 sampled sources, mean 64-69 ms) | speed-up | output |
| --- | ---: | --- |
| compile flags: skip validation / opt level 0 / level 3 | 1.00 / 0.94 / 0.92 | bytes differ for all |
| register arrays sized to the highest literal index | 1.18-1.27 | byte-identical for 199/200 and 245/250 |
| explicit init of referenced registers only | 1.25 | 245/250 identical |
| registers as scalar `float4` variables | 1.32 | 245/250 identical |
| unused texture declarations removed | 1.00 | identical |
| no zero-init at all (not semantics-preserving; bound only) | 2.00 | differs |

| Vertex GPU fetch (78 real sources, mean 671 ms) | speed-up | DXBC mean |
| --- | ---: | ---: |
| default | 1.00 | 58.7 KB |
| `RSX_VFETCH_LOOP=1` (4-component loop is a real loop) | 2.39 | 29.5 KB |
| `RSX_VFETCH_LOOP=2` (plus one loop over the attribute mask) | 4.83 | 13.3 KB |

CPU-fetch (mode 0) vertex sources average 65 ms and gain nothing from it. `patches/ps3recomp-shader-source-dump.patch`
(`RSX_SHADER_SRC_DUMP`, passed through by `GT5P_PREPARE_SHADER_SRC_DUMP`) is the diagnostic that produced the
fragment sources. The table above was a projection when written. Phase 215 below made the vertex switch and the
register sizing defaults (the standalone `patches/ps3recomp-vertex-fetch-loop.patch` was folded into the main runtime
patch and removed) and measured them end to end.

### De-specialized shader text (Phase 215, now default)

Four generator changes make the same shaders cheaper to compile. None changes what a shader computes, and each
has a renderer switch (default on, `0` restores the previous text) and a helper-side rollback. The helper switch must
be set for the game run as well, because the text is the cache key (`scripts/shader_source_policy.py`):

| Change | Renderer switch | Helper rollback | What it does |
| --- | --- | --- | --- |
| Looped GPU vertex fetch | `RSX_VFETCH_LOOP` (2 default; 1, 0) | `GT5P_PREPARE_VFETCH_LOOP=0`/`1`/`2` | one loop over the program's attribute mask replaces the inlined per-attribute fetch |
| Sized fragment registers | `RSX_FP_REG_SIZE=0` | `GT5P_PREPARE_FP_REG_SIZE=0` | `r[]`/`h[]` are declared to the highest literal index the body uses (48 if any index is not a literal) |
| Lazy sRGB helpers | `RSX_FP_GAMMA_LAZY=0` | `GT5P_PREPARE_FP_GAMMA_LAZY=0` | the encode/decode helper functions are added only when a call site was wrapped |
| No encode of a forced constant | `RSX_FP_MASK_ENCODE=0` | `GT5P_PREPARE_FP_MASK_ENCODE=0` | a redirected stencil-mask pass (its colour is replaced by `(1.0).xxxx` after the sRGB step) no longer gets the single-target output encode |

The generation token mixes any helper rollback, so a rollback never reuses a default generation. The starter
templates (format 3, inputs only) are unchanged: nothing under `assets/` or `config/` differs from Phase 214
(`git diff d7d38dc -- assets config` is empty), so no re-key was needed.

**Equivalence.**

- Vertex: all 1,120 enumerated vertex programs, original and looped text, run on the RTX 4060 with random constants,
  fetch descriptors and vertex data (2 x 1,024 vertices x 14 float4 outputs): 128,450,560 values, 0 bit differences
  (`scripts/test/vertex_fetch_equiv.cpp`).
- Fragment registers: `RSX_FP_REG_SIZE=0` text is identical to the unpatched decoder for 7,929 of 7,929 translatable
  catalogue programs. For the default, 2,963 programs (cube mask 0) and 1,178 (cube mask 0x10001) were compiled both ways
  (`scripts/test/fp_reg_size_check.py --disasm`): 0 compile-status differences; 94.6% and 95.0% byte-identical bytecode;
  **every other pair has an identical instruction stream** after renumbering temporaries and ignoring the declared size
  of `dcl_indexableTemp`, which is the only difference. Total DXBC size is equal. This is a stronger statement than
  sampled GPU outputs, since the same instructions run. D3DCompile is about 1.8x faster for the new text.
- Whole enumeration, 22,194 prepared (program, profile) jobs: the DXBC with the lazy-helper change equals the DXBC without
  it for all 22,194, and adding the mask-encode change again changes none. The first two changes against the full rollback
  give identical bytecode for 21,414 jobs (96.5%); the other 780 were not disassembled one by one (hypothesis: the
  declared-size differences found in the catalogue samples).
- Frozen helper on the full 12,669-record starter with all four rollbacks set: the output equals the format-2 reference
  exactly (so every helper switch reaches the engine).

**Measured (this machine, RTX 4060, application-cache cold, consecutive runs through the lock).**

| | rollback | default |
| --- | ---: | ---: |
| Enumeration stage, 24,522 plan jobs, seeded (`enumeration_speed.py stage`) | 504.3 s | 262.0 s |
| Full starter preparation (frozen helper), until native input is published (vertex + fragment) | 249.9 s | 158.6 s |
| ... then the resumed run (native pipelines, verification, packs) | 204.9 s | 176.9 s |
| `preparation_stage_times.py`, vertex / fragment stage | 104-107 / about 150 s | 19-20 / 126-141 s |
| Distinct fragment sources / bytecodes in the enumeration | 19,094 / 17,907 | 18,856 / 17,907 |

The earlier stage-times pairs (rollback 485 and 507 s, defaults 414 and 315 s in total) and the first frozen default run
(299 s to native input, then 320 s) were taken when the machine was probably busier; the frozen numbers in the table are
the consecutive pair. Source counts are exact; wall times vary from run to run (compiler workers, driver and OS caches).
The lazy-helper and mask-encode changes remove 238 distinct sources (1.2%) and are within timing noise: the time comes
from the first two changes.

**In-game.** The same prepared cache seeds, the engine with and without the text changes; GPU time is the mean of the
engine's five-second `[present-prof]` GPU averages (first dropped); frame statistics from `race.ps1 -FrameTest` (60 s).
There was no PSO failure and no device removal in any run, and only 4-6 shaders were compiled after the cache copy.

| Scene | rollback GPU ms | default GPU ms | frame result, rollback -> default |
| --- | ---: | ---: | --- |
| Dealership 720p, 1x | 5.26 | 4.81, 4.67 | 30 FPS (title cap) both |
| Dealership 1080p, 2x MSAA | 6.78 | 6.92, 6.36 | 30 FPS both |
| High Speed Ring 720p | 5.64, 5.66 | 5.61, 5.66, 5.73 | 59.7, 59.1 -> 59.7, 59.9, 59.6 FPS; p99 18.1, 21.5 -> 18.2, 18.1, 18.7 ms |
| High Speed Ring 1080p, 2x | 5.94, 6.00 | 5.61, 6.03, 6.02 | 59.7, 59.8 -> 59.5, 59.7, 59.5 FPS; p99 18.2, 18.1 -> 18.5, 18.6, 18.2 ms |
| Daytona 1080p, 2x | 5.93 | 5.53 | 59.2 -> 59.4 FPS; p99 22.1 -> 19.4 ms |

(The third default value in each row is the engine with all four changes against a cache prepared by the engine with
the first two; its text changes were compiled on demand.) GPU time is the same within run-to-run noise (about 5%); the
looped fetch has no measurable GPU cost here, so the less aggressive `RSX_VFETCH_LOOP=1` was not needed. The window shots
(PrintWindow) of every scene were inspected: the dealership, the race introduction and the race pictures look the same.
The dealership changes its car colours per visit and its camera moves between shots, so a pixel comparison is not
meaningful there. This is one GPU, one save and a few routes: not a whole-game, other-GPU or stutter claim.

**Which axes still split fragment shaders** (`scripts/test/enumeration_axes.py`). An upper bound: the prepared jobs are
grouped by (program, profile with the axis removed), and the saving is how many sources would merge if the axis were
a run-time value instead of text.

| Axis removed | sources saved (of 19,094) |
| --- | ---: |
| sampler lanes (`samplers`) | 2,482 (13.0%) |
| sRGB read bits 8-11 and output bit 12 of the cube word | 1,810 (9.5%) |
| stencil-mask flag | 475 (2.5%) |
| dither | 238 (1.2%) |
| unnorm, shadow flag, `unhi`, `ghi`, `exp32`, `used` | 0 to 6 |
| gamma bits + samplers | 4,360 (22.8%) |
| everything but `used` | 14,055 (73.6%) |

Cube and shape bits are left out (they change which texture type is declared). The sampler lanes and gamma bits are
literals in the text (`_rsx_gamma_input(v, mask)`, the `rsx_s2l` wrappers, the sampler selection). Turning them into
values read from a constant buffer needs uniform plumbing in the renderer and a per-draw upload, and moves compile-time
constants into run time, where the compiler can no longer fold them. That is not provably identical, so it was not
implemented. Design note: a per-unit mask uniform next to `rsx_texscale` in `b1`, with each decode written as a
branch-free `lerp(v, srgb_to_linear(v), flag)`; the source key would drop the axis and the profile's `samplers` and gamma
fields would collapse in `fragment_jobs(collapse=True)` the way the 0xf0000 sample bits do. The price is shader
arithmetic for every unit on every pixel, so GPU time must be measured before any default.

A direct finding: 1,293 of the 19,094 sources (6.8%) compile to the same bytecode as another source of the same program
and differ only in the cube word (1,093, of which 1,001 in bit 12) or the sampler lanes
(`enumeration_axes.py` prints this). The 1,001 were stencil-mask passes: `rsx_d3d12_backend.c` adds the output encode
first and then replaces the colour with `(1.0).xxxx`, and the compiler folds the encoded constant. The mask-encode change
removes that text, but only 235 sources merge (the pairs were already deduplicated in most cases). 817 pairs that differ
only in the cube word and 94 in the cube word plus samplers remain; their cause was not investigated (hypothesis:
other programs whose output is dead code, where a decoded sample feeds nothing). Equal DXBC for every job is a
check the enumeration comparison can make, so these are the next provably identical candidates.

### Not done

- (Done in Phase 215: cancellation/resume and the four rollback switches together through the frozen helper.)
  `reject`, and each switch on its own through the frozen helper, were not repeated.
- The template stage's time with the new worker default (it applies there too; not measured).
- 2048-job launches, 12 workers, overlapping the vertex pool with the fragment launches, and overlapping the
  19 s volume lookup were not tried.
- (Done in Phase 215: stage-level runs and the generator defaults for step 5; the starter needed no change.)
- `docs/player-setup.md` states only the measured stage time; the full first preparation (template stage plus
  enumeration) with the new defaults has not been measured.

Focused tests passing at the final commit: `shader_vertex_batch`, `preparation_enumeration`,
`shader_reconstruct`, `preparation_checkpoint`, `shader_fragment_batch`, `player_package`, `shader_enumerate`.
Tools: `scripts/test/enumeration_speed.py` (`build`, `helper`, `stage`; `--overlay`, `--decoder`),
`hlsl_compile_bench.py`, `vertex_hlsl_dump.py`.
