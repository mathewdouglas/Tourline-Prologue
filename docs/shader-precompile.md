# Offline game shader preparation

For measured asset/raw-program coverage, recipe dependency checks and the
remaining provenance gap, see [shader coverage audit](shader-coverage.md).

## Road to the finished precompiler

The core mechanism works: a portable template identifies programs and numeric
pipeline state, and preparation reconstructs/verifies both shaders and native
pipelines from the user's own assets. Remaining work is breadth, performance and
player integration; retained-route coverage is not whole-game coverage.

v0.2 added an optional standalone player entry point. See
[player setup](player-setup.md#optional-shader-preparation-in-v02) and
[release notes](release-v0.2.md). It uses a complete hash/offset map for this
starter, rather than requiring a developer SHDS catalogue. v0.2.1 includes Phase 178
reading the user's original packed GT.VOL directly, using the configured game folder;
the older v0.2 package retains its earlier unpacked-asset selection.
Broader coverage, settings/GPU validation
and a consistent live stutter benefit remain separate requirements.

Current development builds already provide direct packed-game reads, both-stage
reconstruction and native-key verification, bounded default batching, cancellation/
resume, verified incremental reuse, first-run Prepare/Skip, progress UI and settings
restart. Phase 188 makes supported settings selection automatic inside optional
preparation. The published v0.2.1 release predates these latest development changes.

The remaining work is:

1. **Prove live use and reduce stutters.** Check that the selected translation's
   prepared files are found at runtime and that useful pipelines become resident
   before their first draw. Separate shader compiles from driver pipeline creation,
   file reads and unrelated game work. Measure preparation hits, demand builds,
   frame-time hitches, loading time and memory on repeatable routes, and inspect
   screenshots. Existing trials have not established a consistent stutter benefit;
   blanket startup scanning must not become a default on assumption alone.
   Phase 192 measures 99.7% prepared-key coverage on one HSR route; native
   first-use readiness, early rendering transients and consistent stutter
   reduction remain open.
   Phase 193 feeds observed phase membership to the existing worker: one
   same-cache HSR pair reduces demand jobs from 2,336 to 169, with a smaller
   early p99 improvement and no later p99 improvement. Keep it experimental;
   repeat acceptance and the reported mirror reflection/LOD hitch remain open.
2. **Broaden representative coverage.** Add useful missing tracks, cars,
   dealerships, menus, cameras and effects. Rank observed misses/shared programs
   so collection targets gaps rather than every car-track combination. The starter
   is a verified observed set, not a whole-game catalogue.
3. **Generate more from assets.** Recover material/shared-pass bindings and actual
   pass ownership/state so valid pipelines can be derived without observing every
   draw. Keep unknown bindings unresolved. This remains the main scaling path
   toward GT5; GT5 also needs its own asset formats and rendering contexts verified.
   Phases 189-191 add built-in fallbacks, explicit initialized LV depth resources
   and separately selectable environment absence. The environment publication
   gate/gamma write is measured; its live nonnull-owner assignment and complete
   pass ownership remain unresolved. These rules do not enlarge the shipped starter.
4. **Complete settings and context support.** Cover remaining MSAA, anisotropy,
   precision, root-signature, branching-vertex and pass/attachment combinations.
   Automatic selection currently handles supported translation modes only; custom
   overrides and non-ASCII storage paths conservatively fall back. Rebuilding
   known keys does not prove every combination used by a setting is covered.
5. **Reduce remaining preparation costs.** Avoid repeated asset lookup and
   per-pipeline shader staging, retain more fragment progress across cancellation,
   extend verified reuse where measured costs justify it, and diagnose intermittent
   missing offline-completion markers while keeping rejection strict. Preserve byte limits,
   process/queue ownership, cancellation and safe compatibility rejection.
6. **Finish acceptance and release integration.** Validate representative routes
   and settings changes across additional GPUs/drivers, complete packaged-player
   checks and document actual limits. The launcher/preparer mechanics are already
   implemented; merging/releasing the latest development work is a separate step.
   Ship metadata only, keeping game-derived programs/source/binaries local.

The next practical priority is runtime hit/residency measurement for the supported
settings, followed by the observed misses and costs it identifies. Stable features
should become defaults after appropriate validation, with rollback switches.
Optional preparation remains a player choice. No zero-stutter or whole-game
coverage promise follows from offline pipeline creation.

### Local bytecode packs before first use (Phase 194)

Native pipeline warming does not remove the need to obtain shader bytecode
before forming a draw's native key. The runtime already keeps source-keyed
menu/race bytecode packs, but previously learned them during play. Phase 193's
first indexed route starts with both packs empty. Its sampled `dxbc` timing
includes cached-bytecode lookup, allocation and possible compilation; it is
not a shader-compilation counter or an isolated disk-read measurement.

The player helper now builds those packs for translation `default` only
(720p/1080p 16:9, including the first-run preset). It uses the bundled plan
`config/pipeline-warmup/gt5p-disc-v2.json`, which the preparer packages beside
the other config data. `native-scaled` and `ultrawide-native` do not take a
phase plan. The preparation directory token mixes `shader-packs-v1` when packs
are on, so an older unpacked generation stays on disk and can be imported.
Developer `pipeline_template.py prepare --warmup-plan` builds packs unless
`--no-shader-packs` is set. `--shader-packs` without a plan still rejects.
The library `prepare(..., shader_packs=False)` default is unchanged.

After successful native preparation the builder selects both vertex and fragment
source identifiers for that plan's default-template targets. Every local DXBC
file must match the template's bytecode hash and length. Conflicting mappings,
missing, corrupt, redirected or hard-linked files reject. Source identifiers
are not interchangeable with bytecode hashes. No shader bytes or packs are
distributed.

The builder uses the existing `GT5PSPK1` format and existing loading hooks,
without another worker or a change to async draws, queue ownership or shutdown.
Per-scope payload is capped at the runtime's default 64 MiB and 12,288 entries;
the union is at most 128 MiB, plus one bounded file-read buffer/metadata. Work is
sequential and polled for cancellation and a 60-second time budget. Inputs are
verified before either pack publishes. Unique temporary files are cleaned on
failure; completed packs remain. Existing learned packs are preserved/rejected;
resume accepts byte-identical generated packs and can finish partial publication.
The format version is pinned in the preparation checkpoint. The current runtime
reader does not authenticate pack payloads itself: the builder verifies bytes
before writing, as for the other local cache data. Do not replace those files
with untrusted packs or treat the format as a transport/security boundary.

Both stages are included: the current plan generates 145 menu and 1,873 race
entries (1,978 distinct source keys), about 2.1/25.3 MiB of bytecode. The native
test compiles the actual runtime reader and checks every lookup against expected
bytecode identities, missing-key fallback, caller reference ownership across
scope changes, and `RSX_SHADER_PACK=0` rollback. It creates no GPU device/game.

```powershell
# A fresh developer command with a plan now writes packs.
# Append --no-shader-packs to keep membership without packs.
# Or create packs alone in a separate locked ignored output, reading an idle cache:
python scripts/preparation_shader_pack.py `
  --template assets/pipeline-templates/gt5p-disc-v2 `
  --plan config/pipeline-warmup/gt5p-disc-v2.json `
  --report <successful-generation/report.json> `
  --cache <successful-generation/shadercache> --output scratch/local-pack-proof
python scripts/test/shader_stutter.py `
  --fixture <private-fixture> --engine <isolated-engine> `
  --prepared <generation-without-packs/shadercache> `
  --coverage-report <generation-without-packs/report.json> `
  --warmup-plan config/pipeline-warmup/gt5p-disc-v2.json `
  --shader-pack-template assets/pipeline-templates/gt5p-disc-v2 `
  --startup-policy paired-packs --trials 2 --output scratch/bytecode-pack-pair
```

Both paired conditions use the same indexed native warming and ordinary async
policy. Only the second condition starts with generated bytecode packs; both
keep runtime packs enabled and can learn normally. Four trials use unseeded/
seeded/seeded/unseeded order. The source must have no existing packs; the harness
never deletes learned packs. All copied caches, logs and screenshots remain.
One visible ordered High Speed Ring pair, unpacked first, showed fewer long
frames with packs (race window 37.7 to 49.4 FPS, p99 121.7 to 44.1 ms). Shader
compiles did not fall, and the packed run also had warmer OS and driver caches.
That is not an ABBA result, a mirror-LOD isolation, or a claim that hitches are
gone. Pass `--no-shader-packs` on a fresh developer generation to skip pack
publication. Set `RSX_SHADER_PACK=0` to disable runtime pack use, preserving
all cache files. This is default-template membership only; extra translations
and unobserved programs are not inferred. The reported mirror reflection/LOD
hitch remains an unconfirmed cause, including possible model, texture or upload
work. A pack lookup proof is not a hitch fix.

### Observed phase plans for native warmup (Phase 193, developer experiment)

Prepared files alone do not make a live D3D12 pipeline object available. The
existing worker can replay known menu/race recipes, but the portable starter
previously supplied no phase membership. Do not turn that absence into a blanket
scan or guess pass ownership from a shader name.

`config/pipeline-warmup/gt5p-disc-v2.json` contains observed numeric membership
intersected with successful default-stage preparation: 124 menu keys and 1,979
race keys, 2,070 distinct keys with 33 shared. The source is the local runtime's
historical notifier indices, including prepass requests across prior play.
These are warmup targets, not a new live-coverage percentage or a first-use claim.
Unknown/unprepared keys were excluded. No game bytes, shaders or driver blobs
are included, and the existing template records are unchanged.

Developer preparation accepts `--warmup-plan <plan.json>` after the usual
`pipeline_template.py prepare` arguments. The plan pins the exact template
digest, supports default translation only, and becomes part of the checkpoint
contract. Only complete successful native preparation can publish its two
membership files. Resume accepts identical files and can finish partial metadata
publication; different learned membership is preserved and rejected. A changed
plan requires a new generation. Phase 194 is the player default for translation
`default`; this phase did not itself change the active cache pointer.

The existing worker owns loading-time native creation, demand priority,
deduplication, count/source budgets and shutdown. Its independent recipe,
bytecode and root-signature/native-key checks still apply. No new worker,
draw wait or synchronous draw policy is introduced. Normal async demand remains
the fallback for missing/incompatible entries. Resident-table references do not
prove GPU residency. The existing resident cap and loading-gate budget still apply.

```powershell
python scripts/pipeline_warmup_plan.py export-local `
  --cache <genuine-runtime-learned-cache> --report <successful-preparation-report> `
  --output scratch/observed-phase-plan
python scripts/pipeline_warmup_plan.py merge `
  --plan <plan-a.json> --plan <plan-b.json> --output scratch/merged-phase-plan
# Append to the normal prepare command, using a fresh output:
# --warmup-plan config/pipeline-warmup/gt5p-disc-v2.json
python scripts/test/shader_stutter.py `
  --fixture <private-fixture> --engine <isolated-engine> `
  --prepared <generation/shadercache> --coverage-report <generation/report.json> `
  --warmup-plan config/pipeline-warmup/gt5p-disc-v2.json `
  --startup-policy paired-indexed --trials 2 --output scratch/phase-warmup-pair
```

The paired mode compares the same prepared files with demand-only versus indexed
warming; four trials use demand/indexed/indexed/demand order. Copies, saves,
indices and logs are private. Only the indexed condition stages the plan and
enables existing race warming. `export` can also use a completed, unseeded
`--startup-policy indexed` benchmark session; seeded sessions cannot manufacture
new observation evidence. Local-index export does not imply a completed route.
Inputs and plan sizes/counts are bounded, versions/templates must agree, and
merging cannot silently convert translation modes or add unresolved keys.

Developer rollback for a fresh generation is to omit `--warmup-plan`, which also
omits packs, or to pass `--no-shader-packs` and keep membership only. For an
existing phase-enabled generation, `RSX_SHADER_WARMUP=0 RSX_RACE_PREWARM=0`
disables its startup/loading replay while retaining ordinary async demand and
all cache files. Do not delete shadercache. The released player selects this
bundled plan, and builds its menu/race bytecode packs, for the default
translation only. `RSX_SHADER_PACK=0` disables runtime pack use. Broader
translation mapping remains separate from that default.

Two initial live collection routes missed menu navigation at approximately
4 FPS with the window in the background. Windows refused the harness's foreground
request, and the earlier measured engine reproduced the issue. Those failures
provide no stutter comparison. A subsequent foreground-controlled HSR pair
completes: demand jobs fall 2,336 to 169, early p99 192.2 to 162.1 ms, later p99
20.8 to 21.8 ms, and sampled private memory rises about 114 MiB. Grid arrival is
66.77/65.73 s. Indexed startup holds 2,070 native objects before the race gate;
this is not GPU residency. Most driver creation moves earlier rather than
disappearing. Runtime shader compiles are 6/12, and complete draw sets differ.
Inspected indexed images render normally; the early demand shot is overexposed.
One pair does not justify a player default or a general stutter claim. The user
reports the mirror reflection/LOD hitch in both modes; its cause remains open.
See Phase 193 for evidence, limitations and the next diagnosis.

### Measuring requested native keys (Phase 192)

The optional development patch `patches/ps3recomp-pipeline-use-coverage.patch`
applies after the normal compatibility overlay in an isolated runtime. It is
not part of the release/default patch. Check before applying: the local
`ps3recomp-gt5p-provenance` tree already contains it. Build an isolated engine
against that runtime. Exactly `RSX_PSO_COVERAGE=1` enables collection; unset,
`0` or other values disable it. Draw/queue policy is unchanged.

The diagnostic records complete native keys for executing guest VP/FP draws.
Prepass/prewarm/offline work and no-guest-FP fallback draws are excluded.
Shader-pending submissions are a separate repeated-draw count. Do not add them
to unique keys. Overflow beyond 16,384 keys or inconsistent/incomplete evidence
withholds coverage. First-key/snapshot IO can affect frame timing.
First overflow emits an invalid snapshot immediately. Shutdown is not instrumented;
a consistent snapshot proves neither orderly shutdown nor completion of a route.

```powershell
python scripts/pipeline_runtime_coverage.py `
  --log <completed-route-stderr> --report <successful-preparation-report.json> `
  --output scratch/coverage-result
python scripts/test/shader_stutter.py `
  --fixture <private-game-fixture> --engine <isolated-diagnostic-engine> `
  --prepared <generation/shadercache> --coverage-report <generation/report.json> `
  --output scratch/coverage-pair --trials 2 --startup-policy demand
```

`--condition prepared` selects a single diagnostic route instead of a pair.
The benchmark requires the report beside its prepared cache, records hashes
and conditions, captures frames/screenshots, and cleans only disposable game
copies. Every shadercache remains. Tests are sequential; another game prevents
launch. Owned graceful close retains existing timeout cleanup.

Coverage is an intersection with successful native preparation rows, not mere
template membership. The standalone analyzer cannot prove the game selected
that cache; capture the launch configuration too. Bad schemas, failed native
keys/inventories, incompatible or inconsistent snapshots reject. Translation rows need
their own successful batch evidence. Driver calls can differ from created-key
counts because of memory hits and rejected-blob retries. Residency, actual driver acceptance of a
cached hint and avoided hitches remain separate measurements.

The final HSR 1080p/2x trial matches **1,036/1,039 keys (99.7%)**, with 17 runtime
shader compiles. Three observed keys are outside the prepared set. This is one
save/car/camera/route/settings combination, not whole-game coverage, and it does
not replace the independent 349/1,497 asset-reconstruction metric. The earlier
empty-cache trial compiles 1,731 shaders, but early/later frame times are mixed
and black/overexposure transients remain. Native driver creation still happens
during play. Prioritize targeted loading-time readiness and actual phase ownership,
then broader representative tests. No zero-stutter claim follows.
See Phase 192 in [progress](progress.md) for timing, memory, evidence and limitations.

### Separate environment absence (Phase 191)

Developer `--environment-resource-path absent` selects only the environment
callback's null-resource branch. It can combine with initialized LV shadows;
it leaves unselected shadow/mirror bindings unresolved. The older
`--dynamic-resource-path absent` still means all supported dynamic resources
are absent, so combining that broader choice with separate resource choices rejects.

```powershell
python scripts/prepare_material_shaders.py `
  --catalog <local-catalogue> --engine <isolated-offline-gt5p.exe> `
  --decoder <production-decoder.dll> --game-root <private-game-root> `
  --output scratch/mixed-resource-proof --object-pass-path ccw `
  --native-target-path rgba16-msaa2 --global-sampler-path active `
  --shadow-resource-path initialized-depth-lv `
  --environment-resource-path absent --limit 32
python scripts/test/material_preparation_keys.py --output scratch/mixed-resource-proof
```

The verified disc ELF is required. Resume pins environment rule version 1.
Omit the environment option and use a separate output to roll back; changing an
existing generation rejects without changing its cache. The explicit condition
is environment slot 0 null at binding time, unchanged built-in fallback and no
later publisher. This is not inferred automatically from a fresh constructor,
missing capture or missing shader metadata. Local/global conflicts and unknown
signatures remain unresolved. Existing shadow alias/compare prerequisites apply.

The real constructor/gate clears a stale environment binding with a null owner.
The controlled active continuation writes gamma field 7 for a nonzero byte, but
its actual live owner assignment is still untraced. No active environment recipe
or player default is introduced. The eight-context constructor produces 60,798
conditional candidates; this does not justify preparing them all at player startup.
A fresh authored-diversity sample passes 32 mixed-resource requests / 29 distinct
native keys, with both shaders and persisted driver verification. Four additional
retained HSR keys reproduce exactly. The profile audit is 349/1,497 retained links,
not a whole-game percentage or live stutter result. The starter stays unchanged.
See Phase 191 [progress](progress.md) and [reconstruction](shader-reconstruction.md).

### Asset-derived dynamic fallback context (Phase 189)

Developer `prepare_material_shaders.py --dynamic-resource-path absent` extends
the existing capture-free material constructor. It requires the verified disc
ELF in the private game root and assumes all supported dynamic environment,
shadow, shadow-colour and mirror resource pointers are null at binding time.
This chooses the original callbacks' fallback branch explicitly. It never treats
an unresolved binding, absent capture, or supplied active descriptor as evidence
of a null resource. Dither/PCF active/fallback remains a separate explicit choice.

The original initialized fallbacks supply known non-depth shape, read gamma,
normalized coordinates and sampling. Environment/mirror use a cube; shadows use
2D. Material state, GPU-fetch inputs, compact fragment control and the explicit
object/target context still supply the other fields. Local cube/depth uploads,
unknown global signatures, duplicate units and local/global overlaps retain
their existing rejection. Active environment/shadow/mirror options cannot be
combined with the contradictory absent context. No new renderer switch, live
worker, queue, draw policy or player-cache selection is introduced.

For a bounded developer proof, using original assets/catalogue read-only and a
private game root containing the user's verified `input/EMAIN.ELF`:

```powershell
python scripts/prepare_material_shaders.py `
  --catalog <local-catalogue> --engine <isolated-offline-gt5p.exe> `
  --decoder <production-decoder.dll> --game-root <private-game-root> `
  --output scratch/dynamic-absent-proof --object-pass-path ccw `
  --native-target-path rgba16-msaa2 --global-sampler-path active `
  --dynamic-resource-path absent --limit 32
python scripts/test/material_preparation_keys.py --output scratch/dynamic-absent-proof
```

`--enumerate-only` constructs metadata without running compilers. Existing
`--context-set supported|rgba16` can expand explicit face/target/dither choices;
it does not select live ownership. Jobs record the fallback signatures/units
that justified the rule. Resume requires the same engine, decoder and context,
including the versioned dynamic rule. Omit `--dynamic-resource-path` to restore
the prior constructor, using a separate output; trying to change this context
inside an existing resumed generation rejects without modifying that cache.

The original-asset scan finds 7,698 distinct candidate profiles for the explicit
CCW/RGBA16-MSAA2/active-dither/absent-resource context. These are constructor
candidates, not all natively prepared or observed live. Two empty-cache samples
of 32 requests pass both-stage compilation, native creation, independent key
recomputation and persisted driver-envelope checks. The diverse sample spans all
four callback signatures and ten authored signature/unit combinations; its 32
requests produce 25 distinct native pipelines. A separate repeat uses driver
blobs for all 32 requests. Cold/warm callback tests cover every sampler unit.
No live rendering/stutter test or whole-game coverage claim follows.

Phase 190 below recovers a conditional initialized depth/LV chain. Remaining
active-material blockers include actual environment gamma/ownership and proving
the shadow context's prerequisites for live draws. A new shared
`ConvoluteResampleX` wrapper is only a lead:
its inherited draw state needs a native oracle before adding another full profile.
The existing ColorCorrect/Convolution rules remain unchanged. See Phase 189 in
[progress](progress.md) and [reconstruction](shader-reconstruction.md).

### Initialized LV shadow resources (Phase 190)

Developer `--shadow-resource-path initialized-depth-lv` constructs shadow profiles
from a fresh original framebuffer descriptor, depth-format enum `0x40`, successful
local setup and the enabled LV pass. The original constructors initialize gamma,
normalized coordinates and comparison function 6; the LV pass forces linear
sampling/border wrap and publishes the depth descriptor. Its shadow-colour copy
is converted to non-depth format. Both bindings are reconstructed; the old
sampler-only `shadow-lv` proof still leaves resource facts unresolved.

```powershell
python scripts/prepare_material_shaders.py `
  --catalog <local-catalogue> --engine <isolated-offline-gt5p.exe> `
  --decoder <production-decoder.dll> --game-root <private-game-root> `
  --output scratch/shadow-lv-proof --object-pass-path ccw `
  --native-target-path rgba16-msaa2 --global-sampler-path active `
  --shadow-resource-path initialized-depth-lv --limit 32
python scripts/test/material_preparation_keys.py --output scratch/shadow-lv-proof
```

This context requires the default local shadow-alias path to be enabled and its
allocation to succeed. It assumes no later descriptor overrides or other alias
redirects. Production chooses the comparison from the first depth-format binding,
including unsampled units. Conflicting or unresolved earlier declared bindings
are rejected; any unlisted/stale earlier depth binding must have the same
comparison or be absent. That residual state is an explicit prerequisite, not a
fact recovered from a captured draw. Active environment/mirror bindings stay
unresolved and can still exclude a material. Local depth uploads remain outside
the ordinary material rule. Ordinary profiles cannot silently drop shadow state.

The same verified disc ELF gate applies. Resume identity records shadow rule 1.
Omit the option and use separate output to roll back; changing the resumed
context rejects without modifying its cache. It cannot be combined with the
contradictory all-dynamic-resources-absent context. No renderer/draw-policy change
or player default is introduced.

`audit_material_variants.py` accepts the same option. It freezes the asset-derived
candidate manifest before opening the retained oracle. Matching a profile is
distinct from reproducing shader bytecode and the full native pipeline key.
See Phase 190 in [progress](progress.md) for the native proofs, measured retained
matches and remaining live-ownership/stutter limits. The shipped starter remains
the existing observed-state set; these are independent construction rules.

### Exact vertex batching (Phases 183-184)

Developer template preparation defaults to `--vertex-mode batch`;
`--vertex-mode serial` restores serial compilation. Development frozen helpers
default to batching when `GT5P_PREPARE_VERTEX_BATCH` is unset or `1`; `0`
restores serial compilation. Other values fail safely. Phase 184 changes only
the algorithm inside optional preparation, not whether preparation runs.
These switches are a feature-branch change and are
not implemented by the already published v0.2.1 helper.

`shader_vertex_batch.py` deduplicates exact program/GPU-input variants and
checks reused shaders before starting workers. Each of at most two persistent
hidden processes owns its decoder's mutable globals and compiles sequentially
through the production decoder/system D3D compiler. It does not start gt5p.exe.
The source and frozen entries dispatch the internal worker sentinel before
ordinary preparation argument parsing. Workers receive only a bounded program,
translation mode and expected identifiers over pipes; they receive no cache path.
The parent verifies program identity, source key and bytecode hash before saving
any result. Incorrect identity, extra output and unknown protocol frames retire
that worker; no automatic worker replacement is attempted. Valid compiler
failures remain failures, and exhausted workers leave demand fallback available.

Limits are two in-flight jobs, 32 KiB per program, 256 KiB per generated source,
4 MiB per bytecode and the existing 128 MiB aggregate vertex-bytecode budget.
Private Windows jobs enforce 512 MiB committed memory per worker / 1 GiB for the
worker job. Job-reported peak commit excludes the parent and subsequent
fragment/native phases. Each job has an absolute 180-second deadline; startup
has 60 seconds per worker. Cancellation is checked while waiting at 100 ms
intervals, followed by bounded owned-process shutdown. A private non-inherited
kill-on-close job is mandatory, including inside the launcher's existing job;
job attachment failure refuses batching rather than relying on an arbitrary
parent job. Termination uses only handles created by this module.

No valid reused variant is queued, and a fully cached run starts zero compiler
workers. The existing checkpoint/generation contract is unchanged because
outputs must match serial preparation. Completed accepted files survive
cancellation; resume revalidates them. Memory-budget exhaustion can reject a
different variant from serial record order because batch completion order
differs. Unsupported branching contexts remain excluded on export. Template
schema, renderer settings/root signature, native creation, fragment batching
and asynchronous live draws are unchanged.

Reports add `vertex_preparation` and
`requests/vertex-preparation-report.json` for batch work, including workers,
launches, variants, wall time, limits and job peak commit where available.
Serial reports identify the serial mode with zero worker launches. The serial
`failed_variants` field counts incompatible records; batch failures count unique
compile variants. Do not compare those failure fields as a coverage percentage.

Sequential checks are `scripts/test/shader_vertex_batch.py`, then
`scripts/test/shader_vertex_batch_native.py` with original `--assets`, `--elf`,
`--engine`, `--decoder` and fresh ignored `--output`. Its default 32-record
sample compares exact shaders, creates native pipelines in separate empty
application caches, tests worker cancellation/owner death and resumes with zero
workers. `--count 351 --vertex-only` compares all current starter vertex variants
without claiming another whole-pipeline proof. Rebuild the frozen helper with
`build_preparer.py`, then run `scripts/test/player_vertex_batch_native.py` with
`--zip`, `--helper-dir`, the sampled `--template`, original `--elf`/`--assets`
and a fresh `--output`. The ownership test
`scripts/test/shader_vertex_batch_ownership_native.py` additionally kills a
nested owner while an outer job survives. Run every executable check one at a
time. Preparation timing is distinct from gameplay frame-time/stutter evidence;
see Phase 183 progress for measured results and limitations.

### Next preparation speed opportunities

Keep fresh-cache and incremental-update measurements separate. The Phase 183
all-vertex comparison isolates compilation, while the Phase 180 player evidence
is an incremental expansion with most shaders reused. Neither establishes a
gameplay stutter improvement.

The next useful targets are:

- **Repeated cache I/O and verification.** Phase 180's 30.50 s cache-setup timer
  includes its 27.55 s copying verified hints; these are overlapping measurements.
  The transient shader handoff described below avoids an immediate reread of
  accepted copies. Broader inventory and duplicate staging work remain useful;
  retain ownership, file-change and compatibility checks.
- **Duplicate native-request shader files.** Current request staging writes two
  DXBC files per pipeline, even when many records share code. A shared immutable
  content-addressed staging store could reduce small-file writes/reads and
  storage. It needs a compatible bounded native reader and exact-key validation;
  do not hard-link mutable user caches or distribute the shader contents.
- **Remaining compilation and driver work.** Fragment requests already use
  deduplicated batches. Measure fresh-cache fragment and native stages after
  default vertex batching before changing concurrency. Driver pipeline creation
  is separate from shader compilation and must still run on the user's hardware.
  More workers or overlapping stages need measured CPU/memory budgets, existing
  queue ownership and cancellation guarantees.

In that same Phase 180 incremental run, packed lookup is 9.27 s, fragment work
16.31 s, and the native batch reports 18.55 s for 2,892 driver calls (2,335 with
cached blobs). Native checksums already reduce hashing to 1.36 s. These are
stage observations, not additive predictions of a new total or fresh-run
bottleneck. Prefer avoiding repeated I/O over removing integrity/native checks.
Evidence: `scratch/c180-player/validation.json` and its generation's `native.log`.

### Transient verified shader handoff

Incremental preparation can pass the bytes it just verified and copied directly
to the same locked preparation pass, avoiding a second file read/hash. Existing
destination files are still read and verified. The handoff checks template source
and bytecode identity, file identity, size, timestamps, regular-file/reparse/link
shape and the shared 128 MiB shader budget. Changed files fall back to a full
verified read. It is a transient object, not a trusted persistent manifest, and
is not protection against another process deliberately forging file metadata.
No driver-blob verification or native pipeline creation is removed.

`GT5P_PREPARE_REUSE_HANDOFF=0` restores destination rereads; unset/1 enables the
handoff. Other values fail before output generation changes. This development
change does not alter the published v0.2.1 helper. Source cache generations remain
read-only and accepted complete files survive cancellation for verified resume.

The report's `cache_reuse.shader_handoff` identifies the selected path. As of this
change, `resume.cache_verification_seconds` measures only the final shader loader;
older reports include seed/reuse time in that field. `cache_reuse.seconds` remains
the copy/seed stage. Do not compare old/new timer values as the same operation.

Twenty-five synthetic checks cover source preservation, bounds, cancellation,
corruption, pre-existing files and same-size mutation/replacement. Separate empty
application-cache 32-pipeline reuse proofs pass both modes with identical shaders,
zero shader compiler launches and all native driver calls using verified hints.
An I/O-only whole-starter pair verifies 2,663 shader files: the handoff avoids
their immediate destination rereads. Copy stages have different warm-cache/budget
outcomes, so total wall times are not a controlled speedup measurement. Evidence:
`scratch/settings-preparation-185/{handoff-native32/validation.json,handoff-io/validation.json}`.

### Resolution, ultrawide and first-use visibility (Phase 184)

Pixel width/height and viewport/scissor are not fields in the native graphics
pipeline descriptor/key. A pixel-size change alone generally reuses shader code;
MSAA count, target/depth formats and other changed pass state can require new
pipelines. Guest display modes can also select different passes. Do not infer
complete settings coverage from preparation completing the starter template.

Ultrawide is a concrete translation exception: `rsx_vp_decompiler.c` conditionally
emits an edge-adjustment epilogue when `RSX_ULTRAWIDE` is enabled. Native scaling
also conditionally rewrites WPOS in qualifying fragment programs. The game maps
display settings to these environment switches before translation. Per-draw
constants supply actual sizes/aspect. The Phase 184 default-only helper does not
generate those additional variants; the explicit development modes below add
them. Repeating default-only preparation does not close that gap.

Offline preparation leaves verified shader/driver files on disk. A later game
process still creates live GPU pipelines, possibly on the background worker.
Missing/unready asynchronous draws can appear late even with a prepared cache.
The newest player log inspected in Phase 184 is a 1080p/16:9 run with MSAA 4,
not the reported ultrawide-1440p occurrence; it cannot identify that occurrence's
cause. Asset/scene loading remains another possibility. No async policy change
or ultrawide rendering/stutter fix is claimed.

### Additional local translation modes

Development `pipeline_template.py prepare --translation ultrawide-native` first
verifies the ordinary template preparation, then adds locally derived vertex,
fragment and native pipeline variants. `--translation native-scaled` adds the
scaled fragment path with unchanged default vertex programs. `default` remains
the default and rollback, and does not read/write translation sidecars.

The development player helper accepts the same fixed mode through
`GT5P_PREPARE_TRANSLATION=ultrawide-native` or `native-scaled`. Phase 188
defaults an unset value to `auto`; explicit `default` restores default-only
preparation. Invalid values fail before cache selection.
The already-published v0.2.1 helper does not implement these modes.

| Mode | Vertex translator | Fragment translator |
| --- | --- | --- |
| `default` | Ultrawide off | Native scaling off |
| `native-scaled` | Ultrawide off | Scaled WPOS gate on via render height 1440 |
| `ultrawide-native` | Ultrawide epilogue on | Scaled WPOS gate on via native ultrawide |

The scaling gate represents generated shader text, not a new shader for each
pixel dimension. The current game enables it for native 1440p/4K and native
ultrawide. Some fragments do not use WPOS and retain their default code. Only
explicit modes are generated; anamorphic ultrawide remains outside this helper.

#### Automatic selection from launcher settings (development, Phase 187)

From Phase 188, running **Prepare shaders.cmd** or accepting the first-run
preparation choice uses `auto` when `GT5P_PREPARE_TRANSLATION` is unset. Explicit
`=auto` is equivalent. Automatic selection reads the launcher's storage file
`gt5p_settings.toml`; it does not inspect desktop dimensions. Canonical saved
21:9 selects `ultrawide-native`. Canonical 16:9 at native 1440p/4K selects
`native-scaled`; 720p/1080p selects `default`. Missing settings use the launcher's
720p/16:9 first-run preset. The selected extra mode still follows default
preparation. Explicit `GT5P_PREPARE_TRANSLATION=default` restores default-only
behavior; explicit mode names continue to bypass settings lookup. Published
v0.2.1 is unchanged.

The selector reads at most 64 KiB, accepts one regular unlinked file, and writes
neither settings nor game data. Reports include `player_settings` with the
requested/resolved mode, reason, settings digest and scope. A second snapshot
check before publishing `prepared-cache.txt` rejects settings changed during
preparation, preserving the old selection and completed cache for another run.

Automatic selection is deliberately conservative. Unsupported values, unsafe or
unreadable files, non-ASCII storage paths, anisotropy other than 16, disabled
smooth colour and custom resolution/translation/root-signature overrides fall
back to default preparation with a reported reason. The override list is
`GT5P_NO_SETTINGS`, `GT5P_RESOLUTION`, `GT5P_ULTRAWIDE`, `GT5P_RENDER_NATIVE`,
`RSX_ULTRAWIDE`, `RSX_RENDER_HEIGHT`, `RSX_FP_OPT`, `RSX_PSO_KEY_RS`, `RSX_ANISO`
and `RSX_HIGH_PRECISION`. Explicit modes remain available for developer proofs.
This selects translation text only: MSAA, attachment formats, pass state and
all other numeric fields retain observed template values. It does not claim
that the selected settings have complete pipeline coverage.

Nine synthetic selection/snapshot checks and 24 canonical cases linked against
the actual C++ settings parser pass sequentially, including a UTF-8 BOM and
non-ASCII comment contents. A probe exposed the existing parser's narrow
environment-path handling on one non-ASCII storage path; auto selection excludes
such paths instead of claiming parity. Frozen 32-record paths separately select
ultrawide/native-scaled from the saved file and pass cancellation/resume,
zero-worker reuse, explicit serial rollback and invalid-mode preservation.
The native-scaled run also changes settings during preparation and confirms
rejection before replacing the cache selection. Tests:
`scripts/test/preparation_settings.py`, `preparation_settings_native.py`
(compile `preparation_settings_probe.cpp` with production `gt5p_settings.cpp`
and `gt5p_keymap.cpp`), and `player_vertex_batch_native.py --translation auto`
with `--auto-aspect 16:9|21:9`. No live-draw or frame-time improvement follows.

The complete frozen automatic native-scaled run also passes all 2,892 default
and 2,892 derived records from original packed files in a fresh application cache.
Its derived set has 2,810 additional native keys and 82 shared with default. It
starts no extra vertex workers. The fragment stage has 2,312 unique requests,
2,260 actual new compiles, and all 2,892 native driver calls succeed (82 use
default-stage cached blobs). One run takes 654.22 seconds including default
preparation; OS/driver caches remain warm. This establishes known-state disk
preparation, not faster gameplay, complete settings coverage or GPU residency.
Evidence: `scratch/settings-auto-187/full-scaled/validation.json`. Reproduce with
`scripts/test/player_settings_full_native.py` and a fresh ignored output.

Each vertex worker receives a sanitized UTF-16 environment for one mode,
including surrogate pairs. Mutable decoder globals never change mode in-process.
Derive requests carry original program identity/GPU-input mode; the parent
recomputes returned source and DXBC ids. Two workers remain the maximum, with the
existing private kill-on-close jobs, byte/memory limits, deadlines and owned
shutdown. `--vertex-mode serial` uses one owned worker for additional translations
to avoid the decoder latch. Default serial preparation retains its existing path.
Fragments use the production exact-request batch with a fixed mode overlay after
case-insensitive environment sanitization. Original fragment instruction
identities normalize inline constants, while batch payload checksums cover the
actual asset bytes. No changed shader is saved under an old default source id.

Before writing derived shaders, `native_pipeline_key.py` serializes the current
five-parameter/16-sampler root signature through system D3D12 and calibrates every
default record against its verified shader bytes and expected native key. Its
anisotropy remains the pinned 16. Derivation changes only shader ids, the native
key and descriptor bytecode-length words 4/5 and 8/9. Input layout, target/depth
formats, MSAA count and all other recorded state stay unchanged. Fresh native
creation then independently checks every derived key and persisted driver blob.
This does not enumerate new MSAA/pass combinations or recover unknown bindings.

The parent preparation lock covers both modes' writes to the shared cache.
Separate versioned checkpoints at `tr/uw` and `tr/rs` pin the parent contract,
translation mode and calibrated root signature. Content-addressed local manifests
retain accepted shader ids across cancellation. Resume verifies manifest digests,
shader bytes/lengths, root calibration and native pipelines. Each shader-stage
pool is bounded to 128 MiB; manifests are capped at 4 MiB and native batches stay
within the template record bound. Compact staging paths stay within the existing
native request path-length budget. Default files and the shipped template bundle
are preserved. The player changes its selected cache only after every requested
stage succeeds. New programs, source and DXBC remain local.

Reports include `additional_translation`, its mode/record and unique-key counts,
shader work/reuse, driver calls/cache-hint calls and time. Primary `counts` still
describes default records; `default_preparation_seconds` isolates that stage,
while `preparation_seconds` includes the requested translation. Disk coverage is
distinct from resident pipelines: the existing background policy and resident
limit remain, so live first-use visibility is still a separate validation task.

Sequential tests: `shader_translation.py`, `shader_vertex_batch.py`,
`shader_fragment_batch.py`, `native_pipeline_key.py`, `pipeline_translation.py`
and `pipeline_translation_native.py` under `scripts/test/`. The native test uses
original `--assets`/`--elf`, current `--engine`/`--decoder` and a fresh ignored
`--output`. It verifies both modes, unchanged descriptor fields/default bytes,
native keys/persistence, cancellation/resume and default rollback. The frozen
`player_vertex_batch_native.py` accepts `--translation` for the same player path.
No live stutter reduction or complete settings/whole-game coverage follows.

Phase 185's complete frozen-helper proof reads the original packed game in place
and starts with an empty application cache. All 2,892 default records and all
2,892 distinct ultrawide-derived pipelines pass exact native keys and persisted
driver-blob verification. The extra pass compiles 351 vertex variants with two
workers. Its fragment batch has 2,312 unique requests and 2,260 actual new shader
compiles; request counts are not compile counts. Its 2,892 native driver calls
use no supplied application-cache blobs. OS/driver caches remain warm. Total
default-plus-ultrawide preparation takes 905.66 seconds on this machine; this is
one preparation run, not a speed or gameplay-stutter comparison. Worker-job peak
commit is 119,017,472 bytes; this excludes the parent and native pipeline process.
Evidence: `scratch/settings-preparation-185/full/ultrawide-validation.json`.

Both additional modes separately pass frozen 32-record cancellation/resume,
zero-worker reuse, serial rollback and invalid-mode cache-pointer preservation.
At Phase 185, full native-scaled preparation was unmeasured; Phase 187's complete
automatic proof is recorded above. Nested owner-death and
default-root calibration of all 2,892 records also pass. Fragment manifests are
published after a completed batch, so cancellation can repeat fragment work;
vertex progress is incremental. Resume's conservative vertex accounting can
count shared bytes more than once against its budget. Neither limitation permits
accepting unverified code. A static integration review finds no actionable
correctness, ownership, integrity or bounds defect.

### Preparation window (Phase 181)

Development launchers now offer preparation after successful first-run file
setup, before the first game process starts. **Skip and play**, Escape or closing
the offer starts normal play. **Prepare now** uses the existing helper/UI/cache
contract. Cancelling waits for the helper's owned cancellation, then continues
into the game; completed files and any earlier selection are preserved. A failed
optional step reports its error and allows play. Later configured launches do
not repeat the offer; **Prepare shaders.cmd** remains the explicit prepare/resume
entry. `GT5P_PREPARE_OFFER=0` disables the new offer. This is development behavior
after v0.2.1, not a change to the published ZIP or asynchronous draw policy.

The optional launcher `--prepare` uses the in-game PC Settings visual language:
grey panels, dotted rows, black values and a focused pill Cancel button. It is
standalone Win32/GDI code in `launcher/preparation_ui.h`; it does not depend on a
running game or change its settings UI. `GT5P_PREPARE_UI=0` restores the existing
TaskDialog. A creation failure falls back; a failed wait unwinds the launcher's
owned process job instead of orphaning preparation or claiming completion.

The existing helper writes `prepare-status.txt`. A read is bounded to 32,769
bytes and accepts at most 32,768 bytes of valid UTF-8. The first nonempty line is
shown. A trailing `completed/total` is counted only for two decimal fields of at
most 18 digits, positive total and completed no greater than total. Unknown
phases remain visible; malformed fractions remain uncounted. Archive progress is
labelled as bytes. Phase/detail display text is bounded; exact counts remain
accessible through native controls. Large counts use a scaled control range,
while the text and painted bar preserve the real 64-bit values. Other phases
remain indeterminate; there is no invented overall percentage or ETA.

The UI waits on the existing owned helper handle, polling at 200 ms and reading
status at most every 100 ms. Cancellation writes the same existing request file
and waits for helper exit. No worker queue, shader lookup, cache selection,
generation/resume contract, compiler policy or runtime draw behavior changes.
Preparation remains optional. No coverage or performance gain follows from UI
work. v0.2.1 uses the title **Tourline Prologue** for both preparation dialogs.

Sequential developer checks: build the launcher with
`scripts/release/build_launcher.cmd <output>`, then run
`scripts/test/launcher_native.py --launcher <launcher.exe> --probe <launcher-probe.exe>`
with the UI switch unset and with `GT5P_PREPARE_UI=0`. Build
`scripts/test/preparation_ui_native.cpp` with C++17, `/EHsc /MT /DUNICODE
/D_UNICODE /D_WIN32_WINNT=0x0A00`, linking `user32.lib gdi32.lib comctl32.lib`.
Run `scripts/test/preparation_ui_native.py --probe <ui-probe.exe>
--output <ignored-shots-directory>`. The stand-in checks status bounds, cancellation
inputs, waiting for owned completion, failed cancel writes, resource cleanup and
scaled layout. Screenshots use synthetic status, not a measured preparation run.

### Compare representative sessions before more collection

Export each recorded session with `pipeline_template.py export`, then compare it
with the current verified starter. This reads metadata only and starts no game:

```powershell
.venv/Scripts/python scripts/pipeline_template_coverage.py `
  --baseline assets/pipeline-templates/gt5p-disc-v2 `
  --session HSR=scratch/hsr-template.json --session Daytona=scratch/daytona-template.json `
  --output scratch/session-coverage.json --delta-output scratch/new-candidates.json
```

The report counts shared/additional pipeline keys, program identities, observed
program pairs, source variants and translation states. It distinguishes new
pipelines reusing existing programs from those needing additional programs, and
ranks supplied sessions by marginal pipeline gain after earlier selections.
This ranks recorded content, not unvisited cars/tracks. Counts are metadata
candidates until preparation verifies them; they do not measure runtime hits.

Conflicting records fail by default. Explicit `--quarantine-conflicts` removes
all conflicting session versions and reports their keys/differing fields while
preserving the supplied baseline. It never picks a conflicting new record by
session order or majority. Incompatible renderer/game contracts always fail.
Exporter exclusions and quarantine counts must accompany coverage claims.

Prepare the delta against original assets into a fresh private cache; add only
positively verified entries to the baseline. The supplemental asset-map generator
accepts repeated `--trace` arguments for multi-session lookup. Invalid oracle
blobs are counted and skipped, never used to derive a program location. Merging
compatible templates does not require the user to drive every car-track pair;
it also does not prove that unvisited content is covered.

Phase 160 adds [named shared-pass selection and isolated state checks](shader-reconstruction.md#named-shared-passes-phase-160).
This is developer reconstruction work. CPU inputs and one conditional shared-pass
rule are now independently constructed; other shared resource/pass contexts remain open.

### Additional course collection and incremental locations (Phase 180)

`train_pipeline_cache.py` now accepts `--course-slots` instead of `--tracks` and
can record/export provenance in its owned output. The default remains the two
measured named routes. This developer command visits one slot at a time:

```powershell
.venv/Scripts/python scripts/train_pipeline_cache.py `
  --fixture <copied-audit-fixture> --engine <modern-isolated-gt5p.exe> `
  --decoder <production-decoder.dll> --course-slots 2 --provenance `
  --output scratch/course-slot-collection --seconds 90
```

`--provenance` is off by default and writes `<output>/provenance`; export writes
`session-template.json` without replacing earlier exports. An incomplete recorder
log fails the run after keeping the partial template/cache. Numeric slots mean
RIGHT taps from the initial Course Select cursor. Slots 0/1 are High Speed Ring
and Daytona. The Phase 180 pit screenshot verifies slot 2 as Fuji Speedway F;
`--tracks FujiSpeedwayF` / `race.ps1 -Track FujiSpeedwayF` selects that same route.
The ceiling 9 is experimental, based on ten distinct logo assets rather than a
decoded menu length. Higher slots may stick/wrap and require visual confirmation.
Slots 3..9 remain unnamed; do not infer names or coverage from ordinals alone.

Direct owned route scripts also accept `race.ps1 -CourseSlot 2` without `-Track`.
Names and experimental slots cannot be mixed. The old named-route timing, async
draw policy and owner-only cleanup remain intact. Only one game/test runs at a
time. These automated sessions sample the grid/opening section with the current
car/AI lineup; they do not traverse every track section or every car combination.
Provenance is diagnostic I/O, unsuitable for performance comparisons.

For a verified session delta, generate only previously unknown program locations:

```powershell
.venv/Scripts/python scripts/pipeline_asset_map.py `
  --template scratch/new-candidates.json --trace scratch/session-provenance `
  --known-map assets/pipeline-templates/gt5p-disc-v2/player-map.json `
  --assets <maintainer-reference-assets> --elf <verified-user-ELF> `
  --output scratch/additional-program-locations
```

`--known-map` accepts up to 16 validated maps and combines with `--catalog`.
It skips already located identities; it does not substitute captured bytes for
original assets or verify a whole pipeline. Merge the additional locations with
the prior map, regenerate/verify the numeric volume map, then prepare the delta
in a fresh cache. Only positively verified records join the starter. Maintainer
reference extraction remains local; players use their existing packed game.

## Direct preparation from the configured game files (Phase 178)

The development launcher passes its already verified disc/PS3_GAME folder to
the standalone helper with `--game`. The helper reads `USRDIR/GT.VOL` in place;
users do not install or run GTToolsSharp and do not create an unpacked asset copy.
Ordinary disc setup and the verified user-supplied ELF are still used. This
implements direct reading, not a bundled whole-volume extraction step.

`volume-map.json` contains only archive/member hashes, sizes, byte offsets,
numeric entry IDs/compression flags and locations of parameters in the user's
ELF. It contains no file names, keys, shader bytes, source or compiled cache.
The original ELF and complete volume must match SHA-256 before decoding. This
map supports the measured original BCUS98158 v03.00 volume; other builds/modded
volumes need separately verified maps. No unknown layout or parameter is guessed.

The small repository-authored `volume_reader.dll` performs fixed-width byte
rotations using parameters read from the user's verified ELF. ABI/known-vector
tests gate its use. Python's bounded raw-deflate stream handles supported
compressed members. Each complete decoded container must match its existing
SHA-256 before selected program slices are accepted; every program identity is
then checked, followed by the unchanged shader/native pipeline verification.
The Phase 179 reader also drains zlib's buffered output when a full output chunk
consumes all available compressed input; every drain retains the same chunk cap
and cancellation/deadline checks. Truncation and trailing data remain errors.
No external unpacker code or key data is shipped. The format investigation used
the public [GTToolsSharp readers](https://github.com/Nenkai/GTToolsSharp); original
local volume bytes and existing container/program hashes are the acceptance oracles.

Only requested containers are decoded, in archive order, with 128 KiB input/output
chunks, a 1 GiB per-member limit, a 4 GiB sum of decoded volume-member sizes,
a 128 MiB program-data limit and a 600-second deadline checked between chunks.
Maps are capped at 1 MiB and
1,024 members, reject overlaps/unknown fields and validate every byte range.
All archive reads are read only. Cancellation is checked between hashing/decode
chunks; status writes are throttled while cancellation checks remain immediate.
No new background queue or game instance is introduced. The new map identity
is checkpointed; completed bytecode/driver hints can be reused from earlier
asset-based preparation. Failure/cancellation preserves the selected old cache.

Rollback: `GT5P_PREPARE_VOLUME=0` restores the legacy folder selection, and
`tourline-prologue.exe --prepare-assets <folder>` explicitly uses unpacked assets.
The helper accepts mutually exclusive `--game` / `--assets` inputs. Source tools
can pass `--volume`, `--volume-map` and `--asset-map` to `pipeline_template.py
prepare` without `--catalog`; select the local native utility with
`GT5P_PREPARE_VOLUME_LIBRARY=<absolute volume_reader.dll path>`.

For a developer direct-volume run, use a fresh ignored output (or `--resume` for
the same checkpoint):

```powershell
$env:GT5P_PREPARE_VOLUME_LIBRARY='<absolute volume_reader.dll path>'
.venv/Scripts/python scripts/pipeline_template.py prepare `
  --template assets/pipeline-templates/gt5p-disc-v2 `
  --asset-map assets/pipeline-templates/gt5p-disc-v2/player-map.json `
  --volume <configured-game/USRDIR/GT.VOL> --elf <verified-user-ELF> `
  --engine <isolated-engine> --decoder <production-decoder.dll> `
  --game-root <isolated-game-root> --output scratch/packed-preparation
```

Maintainers generate the numeric map using `scripts/release/build_volume_map.py`
with a local archive listing (`GTToolsSharp listfiles`), their already extracted
reference assets, the original ELF/volume, the player program map and independently
located ELF parameter/data offsets. The generator refuses existing outputs and
verifies all decoded containers/programs directly in the original volume before
writing metadata. Listings, reference assets, parameters and unpacker files stay
local. The strict packager checks that the numeric archive map covers exactly
the non-ELF player-map containers and includes the required manifest-listed DLL.

## Identifier-only templates (Phase 173; optional preparation path)

This adapts the hash/numeric-state design in [Project Pyrrhus's template patch](https://github.com/undecuple/project-pyrrhus/blob/main/port/patches/2071-pipeline-template-prewarm.patch),
[context/key correction](https://github.com/undecuple/project-pyrrhus/blob/main/port/patches/2077-pso-key-vp-start-template-default.patch)
and [session export correction](https://github.com/undecuple/project-pyrrhus/blob/main/port/patches/2120-first-use-pipelines-hitch-count-own-template.patch).
Its [known-issues measurements](https://github.com/undecuple/project-pyrrhus/blob/main/docs/KNOWN_ISSUES.md)
concern a different game/renderer and are not GT5P evidence. No patch stack was imported.

GT5P recipes already hold native state and local bytecode; shader packs reduce
repeated disk reads, while menu/race prewarming prepares learned recipes. They
cannot ship first-run shader contents. Templates bridge that gap with identifiers
and numeric state. Original SHDS assets are available before guest boot; guest
memory scanning would wait for uploads and repeatedly scan changing memory.
This version uses bounded read-only asset lookup and the existing offline/native
preparer. Runtime-generated/unrecognized programs stay unresolved. Asset lookup
measured 48.93 s, so its cost must be included in any first-launch assessment.

All examples are developer-only; use isolated copied game data, local original
assets/catalogue and an isolated runtime EXE. First record representative play
with `RSX_PSO_PROVENANCE=<new ignored directory>` and normal recipes enabled.
Diagnostic recording is off during performance tests. Export each session:

```powershell
.venv/Scripts/python scripts/pipeline_template.py export `
  --trace scratch/session-provenance --cache scratch/session-cache `
  --elf ../GT5P/input/EMAIN.ELF --engine scratch/pass-build/gt5p.exe `
  --decoder scratch/reconstruction-build/decoder.dll --output scratch/session-template.json
.venv/Scripts/python scripts/pipeline_template.py merge --output scratch/starter-template.json `
  scratch/session-template.json scratch/another-template.json
.venv/Scripts/python scripts/pipeline_template.py prepare `
  --template scratch/starter-template.json --catalog ../GT5P/shadercache/library-v1/all `
  --elf ../GT5P/input/EMAIN.ELF --engine scratch/pass-build/gt5p.exe `
  --decoder scratch/reconstruction-build/decoder.dll `
  --game-root scratch/pipeline-training-20261031/game --output scratch/template-prepared
```

Templates contain hashes, translation state, numeric native state and canonical
ATTR inputs. No game-derived shader bytes/source/binaries are included. Keep all
experimental outputs ignored. A verified 2,892-record metadata starter is in
`assets/pipeline-templates/gt5p-disc-v2`; pass that directory to `--template`.
Game ELF, renderer source contract, explicit default settings and
schema/key/Windows x64 ABI compatibility are required. Format 2 excludes
per-install EXE/DLL timestamps; actual helper hashes stay in diagnostic reports. Rebuilt
source and bytecode identifiers and exact native keys verify settings/root
compatibility. Current export excludes branching vertices until their start-slot
context can be represented. Unknown or conflicting records fail safely; a user
can launch normally without template preparation. Individual missing/incompatible
programs are reported and remain on the asynchronous demand path. Optional
`--demand-fallback` writes an empty preparation result for invalid/incompatible
template headers without starting a compiler; strict preparation otherwise fails.

Phase 169 introduced a version-1 program location map for code outside supported
SHDS tables. Phase 180 extends `asset-map.json` to 286 locations (59 vertex,
227 fragment), adding all 167 new program identities. New locations can overlap
supported SHDS lookup. Each entry contains a container SHA-256, file offset,
size, encoding and program identity. No filenames, guest addresses or shader
contents are included.
Supply `--assets <original unpacked GT.VOL directory>` when preparing the bundled
starter; the map is selected automatically. For a standalone template, also pass
`--asset-map <map.json>`. Existing SHDS lookup remains available without a map.

Preparation hashes candidate-sized original containers, verifies the selected
program slices, then applies the same shader-source/bytecode/native-key checks.
Renaming or relocating identical assets is supported; changed assets cannot serve
their old locations. Missing containers stay unresolved. The measured full lookup
resolves the retained observed-state records. The Phase 180 starter has 2,892
records, including an additional Fuji Speedway F grid/opening session.
Unsupported branching contexts remain excluded; Phases 170/180 detail export
exclusions and conflict quarantine.
This closes an extraction gap, not the unknown-state problem for unseen content.

Generate a map once from representative developer provenance and original assets:

```powershell
.venv/Scripts/python scripts/pipeline_asset_map.py `
  --template scratch/starter-template.json --trace scratch/session-provenance `
  --catalog ../GT5P/shadercache/library-v1/all `
  --assets <original-unpacked-assets> --elf ../GT5P/input/EMAIN.ELF `
  --output scratch/session-program-locations
```

Captured programs supply search anchors only during map generation; each match
is reread/verified in the original asset. End users need no captures. `--catalog`
omits already supported programs. The generator uses one CPU thread, bounded
memory mappings, at most 8,192 files/1 GiB per file/16 GiB searched, a 600 s
between-candidate deadline and 4,096 anchor candidates per program/container.
Unlocated programs remain unresolved. Preparation limits map payloads to 4 MiB,
8,192 entries and 128 MiB resolved code; hashing has a 60 s between-container
deadline and 16 GiB budget. The local supplemental lookup hashed five containers
(438,542,896 bytes) in about 1.1 s with warm OS caches in Phase 169; the expanded
map hashes six containers/528,044,272 bytes in 1.54 s. No guest-memory scanning,
new live worker, asynchronous draw-policy change or player default is introduced.
Rollback is to omit `--assets`/`--asset-map` or skip optional preparation entirely.

The guarded offline persistence switch is `RSX_PSO_TEMPLATE_PREPARE=1`, default
off. Rollback: omit preparation/use the normal launcher; `=0` disables this
extension. No live draw policy or player defaults changed. Preparation uses the
existing two compiler workers, bounded queues and sequential native device owner,
then exits before play. Preparation does not invent menu/race membership indices:
normal demand consumes prepared bytecode/driver blobs, and real play learns
membership. Existing worker limits, deduplication and shutdown remain unchanged.
Offline windows stay hidden. `RSX_SHADER_LIBRARY_EXACT=1` omits unnecessary
base-profile compiles in explicit preparation only; ordinary library defaults
remain unchanged. Limits and current evidence are in Phases 166-168.

For a versioned metadata bundle (no shader contents):

```powershell
.venv/Scripts/python scripts/pipeline_template.py bundle `
  --template scratch/starter-template.json --output scratch/starter-template-bundle
```

`--template` accepts the bundle directory directly. Each part is checksum checked;
conflicting/incompatible generations are rejected.

### Exact fragment batching (default)

Template preparation, conditional material/shared preparation and paired-route
validation now use exact fragment batching by default. Select
`--fragment-mode legacy` to roll back to per-profile processes. The runtime path
is independently guarded by
`RSX_SHADER_LIBRARY_BATCH=<private work directory>` and
`GT5P_SHADER_PRECOMPILE_ONLY=1`; normal gameplay does not read batch manifests.

The preparer deduplicates exact fragment-program/profile requests, partitions
only by final-dither policy, and sends at most 4,096 requests to each offline
process. It never applies every profile to every program. The manifest names
hash-identified local programs, their raw checksums and explicit profile fields.
Header/version/counts, sorted unique identifiers, numeric widths, sampler masks,
program bounds/checksums and sampled-texture masks are validated before use.
Malformed manifests queue no work; malformed individual programs produce failed
results. Result joins require every expected ID exactly once. Missing/failed
bytecode remains unresolved; templates still verify source/bytecode identities
and the final native key before acceptance.

The existing two compiler workers, source-key deduplication, queue backpressure
and shutdown are reused. The queue is drained before returning, and no new live
worker or asynchronous draw policy is introduced. Batch metadata is bounded;
source/driver contents stay in ignored local caches. Matching intermediate inputs
can be reused by material/shared `--resume`; cache directories are preserved.

The 32-record paired empty-application-cache check produced identical bytecode
and native keys in both modes. Fragment preparation measured 37.81 s/20 processes
with legacy versus 5.64 s/2 processes batched; whole preparation was 57.40 versus
17.77 s. This is a small ordered test with warm OS/driver caches, not a universal
speedup or gameplay/stutter measurement. The full 2,334-record starter subsequently
passes every shader/native/persistence check in one empty application cache:
108.11 s fragment preparation in two processes, 467.42 s total and 57.17 s native
driver creation. Serial vertex preparation and cache verification remain part of
the total. Eleven native protocol/gating cases and all 36 shared candidates plus
cache-reusing resume pass. See Phase 171 for evidence and limitations. No
shadercache is cleared or moved.

### Resume template preparation

Repeat the original `pipeline_template.py prepare` command with `--resume` and
the same output directory. A fresh run creates `preparation-state.json` before
lookup. The checkpoint binds the canonical validated template and asset map,
plus the actual EXE/decoder hashes. Incompatible checkpoints are rejected without
changing their state or caches. Older outputs without a checkpoint cannot resume;
keep them and use a new ignored output directory.

Each attempt rechecks the original assets and verifies cached source-keyed DXBC
against the template's expected bytecode identifier and length. Missing shaders
are rebuilt; corrupt shaders cause a safe failure and stay intact for inspection.
Verified cached shader bytes have a 128 MiB pool limit. Every requested native
pipeline is still checked/created on resume, using persisted driver blobs when
accepted. Pending result markers prevent an earlier successful native result
from satisfying a new attempt.

An exclusive OS file lock prevents concurrent preparation of the same output;
it releases when its owner exits. Resume rejects redirected or hard-linked
output entries and bounds the directory walk. `preparation-state.json` records
the attempt, phase and phase progress atomically; `complete` means that cache
verification finished. Check its phase and compare the attempt with
`report.json`'s `resume.attempt`: a report from an older attempt can remain after
an interruption. The lock file's presence alone does not mean a process is live.

A controlled interruption after real shader preparation resumed all 32 test
records without vertex/fragment recompilation, then passed native creation and
a second driver-blob reuse pass. Changed-template, corrupt-bytecode and separate
process ownership checks pass (Phase 172). This verifies developer resume, not
graceful launcher cancellation or recovery of every partially written artifact;
partial/corrupt files fail safely. There is no new live rendering policy,
coverage or stutter claim.

Fresh application-cache paired validation:

```powershell
.venv/Scripts/python scripts/test/pipeline_template_route.py `
  --template scratch/starter-template.json --catalog ../GT5P/shadercache/library-v1/all `
  --elf ../GT5P/input/EMAIN.ELF --engine scratch/pass-build/gt5p.exe `
  --decoder scratch/reconstruction-build/decoder.dll `
  --fixture scratch/shader-stutter-20261031/fixture --output scratch/template-route --trials 4
```

It prepares from original assets into an empty cache, then runs the existing
control/prepared/prepared/control HSR route with distinct application caches.
Reports separate preparation/lookup time, runtime shader compilation, native
driver calls/cached calls, live demand jobs, warmup hits, frame hitches, grid
loading and sampled memory. Five-second counters can omit the final interval.
Inspect saved screenshots for missing draws before interpreting timing; OS and
driver caches are retained. Add offline preparation to the first-launch wait.
The Phase 168 experiment reconstructs 1,196 of 1,494 exported records; 298 remain
unresolved and three branching vertex contexts were excluded at export. Both
shader stages and exact native keys pass verification. Preparation took 723.9 s,
including lookup/translation/compiler process overhead; native creation accounted
for 26.1 s. Local driver blobs occupy 82.6 MiB. These are retained-route records,
not whole-game coverage. A fresh-cache bundled one-record smoke also passes.

Four bulk-preload trials and a final demand-only pair do not establish a consistent
stutter improvement. Runtime shader compiles fall in prepared trials, but cached
driver creation still occurs and frame-time results vary substantially. Screenshots
show later prepared scenes drawing, but differing progress prevents pixel-equal
rendering proof. See Phase 168 for counters, timings and evidence. `warm_hits`
includes startup bookkeeping; it is not an independent draw/preparation-hit count.

Benchmark trials now remove only their disposable private `game` directory after
saving results. Shader caches, logs and screenshots remain. Use
`--keep-game-copies` only when debugging requires them. Before copying, a free-space
check reserves the writable game copy, prepared cache and 2 GiB headroom. Fourteen
old copies were removed on request, freeing 54.53 GiB; their report paths remain
as historical evidence, but those disposable game directories no longer exist.

## Incremental preparation across template updates (Phase 176)

Resume still requires the same template/helper contract. For a different template
or engine, use a fresh output and read verified hints from an older cache:

```powershell
.venv/Scripts/python scripts/pipeline_template.py prepare `
  --template scratch/expanded-template.json --catalog ../GT5P/shadercache/library-v1/all `
  --elf ../GT5P/input/EMAIN.ELF --engine <isolated-engine> `
  --decoder scratch/reconstruction-build/decoder.dll --game-root <isolated-game-root> `
  --assets <original-unpacked-assets> --asset-map <verified-program-map> `
  --output scratch/expanded-preparation --reuse-cache scratch/older-preparation/shadercache
```

The new template remains authoritative. Only requested source-keyed DXBC files
with its exact bytecode identifiers and lengths are copied. Missing, damaged or
different shader files are skipped and rebuilt normally. Requested native cache
blobs need the existing bounded/checksummed envelope; they are driver hints, not
proof of compatibility. Every requested pipeline still passes native key/creation
and persisted-cache validation. D3D12 rejects incompatible hints through the
existing uncached creation fallback. Original assets are still located/verified.
No recipe, membership list, shader pack or checkpoint is imported from the source.

Reuse reads at most the template's requested filenames, with 128 MiB of shader
copies, 256 MiB of driver hints, a 4/32 MiB per-file limit respectively and a
60-second deadline checked between files. Over-budget files remain compilation
work. Redirected roots/ancestors are rejected; redirected/hard-linked selected
files are skipped. The old cache is read only; the new output has the existing
exclusive preparation lock. Complete individual copies survive cancellation and
the normal checkpoint path verifies them on resume. No caches are removed.

Optional player preparation automatically reads the previous generated cache
selected by `prepared-cache.txt` when its new output identity differs. It accepts
only the launcher's generated storage-relative selection. Success selects the new
cache; failure/cancellation leaves the old selection intact. `GT5P_PREPARE_REUSE=0`
or helper `--no-reuse` disables this optimization. Developer preparation defaults
to no cross-generation reuse unless `--reuse-cache` is supplied. `report.json`'s
`cache_reuse` separates copied/rejected/missing/budget-skipped files and bytes;
shader reuse counters and native driver counters retain their existing meanings.
The reuse source is an optimization rather than checkpoint identity: a matching
resume can change or omit it, while destination shader verification stays strict.

The growing-template native regression is `scripts/test/preparation_reuse_native.py`.
It checks an independently prepared base, expansion, fresh control and complete
reuse, including exact keys, driver-hint use and unchanged source generations.
This improves update preparation cost, not first-run coverage or live frame times.
Phase 180 grows the starter to 2,892 observed-state records; this reuse mechanism
does not derive additional pipelines by itself.

## Native checksum verification (Phase 177)

Development standalone helpers include a small repository-authored `cache_hash.dll`
to accelerate the existing cache checksum. It uses the exact renderer FNV-64
algorithm and nonstandard seed; cache formats, IDs and verification requirements
do not change. The helper loads only its own absolute DLL path, with DLL-directory
and System32 dependency lookup. ABI 1 and known-vector parity checks gate native
use. Missing, redirected, incompatible or failed-self-test libraries retain the
original Python implementation. No compiler is required on the player's PC.

`GT5P_PREPARE_NATIVE_HASH=0` forces the Python path. Source tools remain Python-only
unless the developer explicitly sets `GT5P_PREPARE_HASH_LIBRARY` to an absolute
local helper DLL path before starting them. Frozen helpers use their bundled
location. These controls affect offline integrity verification, not rendering,
shader translation, native driver creation or draw scheduling. Hashing stays on
the caller's thread and checks the same bounded inputs. Existing cancellation,
memory/file limits, cache ownership and native revalidation still apply.

`build_preparer.py` compiles the helper with the maintainer's existing x64 toolchain
and runs native/Python parity tests before writing the distribution manifest. The
strict packager verifies and includes the manifest-listed DLL. Only utility code
is shipped; game-derived bytes remain local. The frozen-tool test checks native
loading with PATH restricted to System32. Renderer/template contracts and the
decoder/checkpoint identity remain unchanged because checksum results are identical.

Successful preparation reports a `hashing` object: backend, optional native ABI /
library SHA-256, call/byte counts, native/Python call counts and checksum wall time
inside the preparation body. Counts exclude header validation before the body and
the startup self-test. This separates checksum cost from shader compilation and
native driver calls; a faster checksum is not evidence of reduced gameplay hitches.

## Automatic shared vertex preparation (developer only)

Phase 162 adds a capture-free step toward shared-pass preparation. It scans the
original ELF automatically, selects only authored named SHDS pairs, deduplicates
their supported vertex programs and prepares the CPU VS cache. No game run,
manual bank offset or pass name is needed:

```powershell
.venv\Scripts\python scripts\prepare_shared_shaders.py `
  --elf ../GT5P/input/EMAIN.ELF --decoder scratch\reconstruction-build\decoder.dll `
  --output scratch\shared-vertex-preparation
```

The measured disc ELF supplies 46 pairs across five supported banks and 14
distinct CPU vertex programs, all compiled successfully. Two unhandled banks
remain reported/excluded. The output contains source-keyed runtime DXBC and an
ignored manifest of original offsets/hashes. No fragment profile or whole
pipeline is guessed. This command prepares vertex shaders only; use the explicit
pipeline mode below for the supported rule. Other shared contexts remain unresolved. It is not yet wired
into the launcher or material precompiler, and does not establish stutter impact
or compatibility with GT5's asset layouts. See
[input-layout validation](shader-reconstruction.md#automatic-shared-vertex-preparation-phase-162).

Phase 163 adds the first complete conditional shared-pass rule. Add `--pipelines`
with an isolated `--engine` and `--game-root`. Phase 164 also enumerates explicit
host depth attachment: `--context-set supported` has 24 ColorCorrect contexts
and the default `rgba16` set has 16, using `--depth-context both`:

```powershell
.venv\Scripts\python scripts\prepare_shared_shaders.py `
  --elf ../GT5P/input/EMAIN.ELF --decoder scratch\reconstruction-build\decoder.dll `
  --output scratch\shared-pipelines --pipelines --engine scratch\pass-build\gt5p.exe `
  --game-root ../GT5P --context-set supported
```

This is offline only. Source/target read/write gamma, format/samples and host
depth attachment are explicit candidates; real draw ownership is unproven. Use
`--depth-context backed` for the Phase 163 subset, or `colour-only` for targets
without depth. The
source must be a successfully initialized RGBA8 2D FrameBuffer, distinct from
the destination, with no unexpected redirects or later overrides. Unknown
resources and feedback are excluded. All 24 supported candidates create and persist, and
repeat preparation reuses their driver blobs. They do not match the retained
HSR snapshot, so no live coverage/stutter gain is claimed. Other pairs still
receive vertex preparation only. No player defaults or launcher integration.
Use the same command with `--resume` to revalidate/reuse matching output. All
outputs remain local/ignored. See the [shared rule](shader-reconstruction.md#conditional-colour-correction-pipelines-phase-163).

Phase 165 adds `Convolution_8`: `--context-set supported` now prepares 36 requests
(24 ColorCorrect plus 12 convolution); `rgba16` has 24. All 36 persist; two
convolution native keys match retained HSR evidence. Context assumptions remain.
Earlier counts above describe Phase 164.

## Automated route learning and preparation (developer only)

`scripts/train_pipeline_cache.py` provides a pragmatic alternative to recovering
each pass independently. One command drives the existing High Speed Ring and
Daytona automation, learns actual shader/pipeline requests into one private
cache, then prepares every learned native pipeline offline before returning.
It needs no manually selected shader names, material pairs, capture lines or
pipeline keys. This uses observed draw state and locally generated bytecode;
it is **not** independent reconstruction from assets or a whole-game catalogue.

```powershell
.venv\Scripts\python scripts\train_pipeline_cache.py `
  --fixture scratch\shader-stutter-20261031\fixture `
  --engine scratch\pass-build\gt5p.exe `
  --output scratch\pipeline-training
```

The fixture must contain copied `input/EMAIN.ELF`, `input/pkg/`, `assets/` and
`gamedata/` inside ignored storage in this checkout, with no links back to another
checkout. The tool copies writable data and links only the private copied disc
directory. It refuses another game and cleans up only its owned child tree.
It preserves caches, disables recipe pruning, uses `PS3_VERBOSE=0`, keeps bulk
startup scanning off while learning and runs the final preparation before play.
No runtime, launcher, release or player defaults change.

Defaults are both supported routes, 90 seconds after reaching the grid,
1080p/2x MSAA and one visit per route. `--tracks HighSpeedRing`, `--seconds 60`,
`--resolution 720p`, `--msaa 1` and `--passes 2` select an explicit sweep.
Use the same command with `--resume` after interruption. Add `--prepare-only`
to resume native preparation without driving again. Engine, fixture and route/
renderer settings must match the run's saved configuration. Failed runs retain
their cache and report rather than silently claiming partial success.

`report.json` records each completed route, newly learned recipe counts, grid
milestones and presented-frame checks. Logs and screenshots remain alongside it.
The tool checks recipe envelopes/checksums and bytecode dependencies, requires
the native warmup to accept the entire set, verifies the offline guest-entry
guard and validates every persisted driver-blob envelope/checksum. The pinned
runtime's 8,192-recipe offline cap is explicit; larger sets are rejected rather
than silently truncated. Recipes for incompatible root-signature/settings
generations are rejected by the runtime. Driver blobs are hardware/driver local.

Only the supported routes, current car and selected settings are visited. Grid
and presentation checks are not proof of complete geometry or visual readiness;
inspect the retained shots. Runtime-generated variants in unseen content still
need discovery, and short cold-cache visits can miss late asynchronous draws.
More visits can learn additional states but cannot prove completeness. This is
cache training, not a stutter-reduction benchmark. Use the separate paired test
below to measure any benefit. The resulting `shadercache/` stays local and is
not a distributable release asset.

## Capture-free material subset (developer only)

Phase 157 adds a conditional asset-to-native preparation path that needs no live
capture or learned translation profile. It currently supports ordinary 2D uploads
with complete sampled facts, prepared material state, compact fragment binding
and explicitly selected object/target/global context. Actual pass ownership is
not established. Unknown resource bindings are rejected; absence of resource
aliases is an explicit context assumption. It does
not yet integrate with the launcher or change normal player defaults.

With the isolated patched runtime EXE and production vertex decoder already built:

```powershell
.venv\Scripts\python scripts\prepare_material_shaders.py `
  --catalog ..\GT5P\shadercache\library-v1\all `
  --engine scratch\pass-build\gt5p.exe `
  --decoder scratch\reconstruction-build\decoder.dll `
  --game-root ..\GT5P --object-pass-path ccw `
  --native-target-path rgba16-msaa2 --global-sampler-path active `
  --limit 0 --output scratch\material-preparation
```

The catalogue supplies original source-container paths, not capture state. Close
the game first. Use separate ignored output, never the original checkout or its
cache. Default `--limit 8` is a smoke run; `--limit 0` prepares all eligible
candidates. `--enumerate-only` writes the inventory and candidate manifest without
compiling. Repeat the same command with `--resume` to reuse cached fragment
bytecode and revalidate native driver pipelines; vertex translation still runs.
Changed engine, decoder or context choices require a new output directory.

`report.json` records assumptions, exclusions, individual results and timings.
`shadercache/` contains source-key DXBC, local driver blobs and warmup recipes in
the renderer's ordinary formats. Keep all generated files local. This command
does not install its output into a player's cache. Driver compatibility is checked
through native pipeline creation on every run; stale blobs use the existing
renderer fallback. A partial failure returns nonzero and preserves results.

The measured subset prepared 474 candidates into 467 distinct native pipelines.
This establishes preparation, not exhaustive coverage or measured stutter
reduction. See [the reconstruction evidence](shader-reconstruction.md#capture-free-conditional-material-preparation-phase-157).

### Explicit context unions

Use `--context-set rgba16` instead of the individual object/target/global options
to prepare both supported winding choices, both RGBA16 sample configurations and
both active/fallback global candidates in one cache:

```powershell
.venv\Scripts\python scripts\prepare_material_shaders.py `
  --catalog ..\GT5P\shadercache\library-v1\all `
  --engine scratch\pass-build\gt5p.exe `
  --decoder scratch\reconstruction-build\decoder.dll `
  --game-root ..\GT5P --context-set rgba16 --limit 0 `
  --output scratch\material-context-union
```

`--context-set supported` additionally includes RGBA8/single. The independent
candidate audit found no extra retained HSR matches from those RGBA8 choices, so
the measured preparation uses `rgba16`. These named sets explicitly enumerate
conditional variants; they do not infer which pass a material uses from capture
settings. Identical shader/state jobs are deduplicated, their supported contexts
remain in `manifest.json`, and each native request uses its own target sidecar.
`--resume` works with the same named set and executable/decoder identity.

The measured RGBA16 union prepares all 3,446 candidates into 3,402 native pipelines.
It confirms 131/1,497 retained HSR native-key matches (8.75%), up from 52 (3.47%),
with no baseline matches lost. This developer run takes 11.3 minutes and saves
204 MB of driver blobs, plus bytecode and intermediate files. That is preparation
cost on the measured machine; actual stutter reduction remains unmeasured.

To repeat the read-only candidate comparison before compiling:

```powershell
.venv\Scripts\python scripts\audit_material_variants.py `
  --catalog ..\GT5P\shadercache\library-v1\all `
  --audit scratch\provenance-snapshot-hsr-20261030\audit-final.json `
  --trace scratch\provenance-snapshot-hsr-20261030 `
  --output scratch\material-context-audit
```

This freezes asset-derived candidates before reading the oracle. Program/profile
matches are predictions. Confirm them against persisted native pipeline keys:

```powershell
.venv\Scripts\python scripts\audit_prepared_materials.py `
  --prepared scratch\material-context-union `
  --baseline scratch\capture-free-material-full-subset-20261030 `
  --audit scratch\provenance-snapshot-hsr-20261030\audit-final.json `
  --output scratch\material-context-native-audit.json
```

The native audit checks preparation results and persisted recipe checksums/blob
presence. Its denominator is the retained snapshot, not every draw or all game
content. No measured stutter reduction follows from a key-match percentage alone.

### Measuring first-visit frame times

`scripts/test/shader_stutter.py` compares fresh application caches with the
generated subset on an automated HSR route. Supply a private ignored fixture
containing copied `input/EMAIN.ELF`, `input/pkg/`, `gamedata/` and `assets/`.
Each trial copies the fixture's writable game data, uses a separate shadercache,
and shows only its owned game window. Other `gt5p.exe` processes block launch;
cleanup never stops an unrelated session. All trial files remain ignored.

```powershell
.venv\Scripts\python scripts\test\shader_stutter.py `
  --fixture scratch\shader-stutter-20261031\fixture `
  --engine scratch\pass-build\gt5p.exe `
  --prepared scratch\material-variant-union-prepare-20261030\shadercache `
  --output scratch\stutter-demand-abba --startup-policy demand --trials 4
```

The order is control/prepared/prepared/control. `--trials 2` runs one pair.
`--startup-policy demand` uses normal learned-index startup without scanning every
recipe; `scan` explicitly tests bulk startup scanning. Both use async shaders and
pipelines, VSync, 1080p/2x MSAA, `PS3_VERBOSE=0` and race prewarming disabled.
The OS and driver caches are preserved. This is a cold **application-cache** test,
not a clean-driver first-install test. It excludes offline subset preparation.

Frame CSVs, window timestamps, logs and screenshots distinguish the first 45 s
after the grid from 45-90 s and the whole presented route. The first window
includes the intentional 30-FPS rolling start; route gaps also include loading
transitions. Reports include p99/max intervals and counts over 50/100/250 ms.
Five-second compiler counters can omit a final partial interval. Used recipe
timestamps help check actual subset encounters without provenance recording.
Inspect the screenshots: higher FPS while drawing incomplete geometry is not a
visual-readiness improvement. Scripted navigation does not ensure identical draw
workloads or race progression across runs, so small differences need caution.

## Existing raw-program preparation

`scripts/precompile_shaders.py` reads embedded `SHDS` fragment programs from
the local executable and unpacked game assets, then runs the production
translator/compiler before guest entry. It writes ordinary DXBC entries to
the same shadercache used during play. It is separate from F1's **Preload
known shaders**, which prepares previously recorded native pipelines during startup.

Keep the shader cache enabled. Close the game before compiling. All extracted
programs, bytecode, source indexes and logs remain local and must not be
committed or distributed with the port.

## Full asset pass

Use [GTToolsSharp](https://github.com/Nenkai/GTToolsSharp/releases) to unpack
your own `GT.VOL`. The tool is an external dependency; this repository does
not include its executable, keys or source. Either provide its executable:

```powershell
.venv\Scripts\python scripts\precompile_shaders.py --unpacker C:\Tools\GTToolsSharp.exe
```

Or point at an existing unpacked directory:

```powershell
.venv\Scripts\python scripts\precompile_shaders.py --assets C:\Games\GT5P-extracted
```

The wrapper's unpacker invocation writes intermediate assets and third-party
tool output into ignored `scratch/`. It does not alter the game dump. The
executable is also scanned, regardless of the assets option.

For better coverage, first play representative menus and races on this build.
The renderer learns shader-affecting state profiles in
`shadercache/fp-profiles-v2/`. The offline pass applies learned profiles to
file programs with matching texture-unit usage. This can prepare unvisited
content using states observed elsewhere. With no learned profiles, only
base 16/32-bit export variants are prepared; a base-only pass showed almost
no reduction in the measured dealership route.

Up to 64 learned profiles are used by default. For more coverage:

```powershell
.venv\Scripts\python scripts\precompile_shaders.py --compile-only --profile-limit 256
```

`--compile-only` reuses `shadercache/library-v1/all/`; extraction is unnecessary
on every run. It also resumes safely after interruption: completed DXBC
entries remain usable. Existing shadercache files are never removed.

For an even broader, substantially slower cross-product of states and programs:

```powershell
.venv\Scripts\python scripts\precompile_shaders.py --compile-only --profile-limit 256 --all-profile-combinations
```

Normal shader compiler worker configuration (`RSX_SHADER_WORKERS`) also applies.
The job table now defaults to 65,536 slots: the former 16,384 slots forced
large passes into serial compilation once full. `RSX_SHADER_JOB_SLOTS=16384`
restores that limit; values are rounded down to a power of two between
1,024 and 131,072. The table occupies a bounded amount of memory.
The source queue is bounded to about 64 jobs; parallel compilation can still
consume CPU and memory. Progress is printed in the terminal and window title.
`shadercache/precompile.log` contains the summary and bounded failure details.
The program exits after preparation; it does not start the game.

## Smaller passes and checks

```powershell
# Executable only, without unpacking assets:
.venv\Scripts\python scripts\precompile_shaders.py --scope executable

# Extract/index without compiling:
.venv\Scripts\python scripts\precompile_shaders.py --assets C:\Games\GT5P-extracted --catalog-only

# Separate cache for experiments, without touching the player's cache:
.venv\Scripts\python scripts\precompile_shaders.py --scope executable --cache scratch\shader-test

# Maximum programs in one pass (up to 16384):
.venv\Scripts\python scripts\precompile_shaders.py --compile-only --limit 128
```

Extraction records bounds-checked SHDS table entries and deduplicates identical
payloads. The local index lists source filenames and offsets for diagnosis.
The native reader separately validates file size, alignment and termination.
Failed programs/variants are skipped and reported as partial coverage.

The catalog directories for `all` and `executable` are separate. An optional
`--catalog PATH` overrides the directory. The supported layout was checked
against this disc build; other builds are unverified. The SHDS layout was
researched using [PDTools' public readers](https://github.com/Nenkai/PDTools/tree/master/PDTools.Files/Models/Shaders)
and checked against local runtime shader bytes.

Tests:

```powershell
.venv\Scripts\python scripts\test\shader_library.py
.venv\Scripts\python scripts\test\shader_library_runtime.py
.venv\Scripts\python scripts\test\shader_job_table.py
```

The first uses synthetic containers. The second requires the local game/build
and uses an isolated scratch cache to verify real compilation, repeat-cache
reuse, bad inputs and profile filtering. The third exercises the production
job-table helpers at their default, legacy and clamped capacities.

## Remaining compilation

This is not an exhaustive shader/pipeline database. Vertex programs are not
prepared by this extractor. Runtime-generated or modified programs, unsupported
records, unobserved states, different renderer settings, and native driver
pipelines can still compile during play. Some file payloads contain register
references rejected by the current translator/compiler; the authored fixups
and unsupported cases need further investigation. No claim is made that
shader preparation fixes the separately observed command-production freezes.

Environment controls for direct native use: `RSX_SHADER_LIBRARY=<catalog>`
with `RSX_SHADER_WARMUP=1`, `RSX_SHADER_ASYNC=1`, and an enabled shader cache;
`GT5P_SHADER_PRECOMPILE_ONLY=1` exits before guest entry. Library preparation
does not run during normal play unless explicitly requested.
`RSX_SHADER_LIBRARY_LIMIT`, `RSX_SHADER_LIBRARY_PROFILE_LIMIT`,
`RSX_SHADER_LIBRARY_PROFILES=base` and `RSX_SHADER_LIBRARY_BROAD=1` correspond
to the CLI controls. `RSX_SHADER_PROFILES=0` disables profile learning and
`RSX_SHADER_ERRORS=0` silences new bounded async compiler diagnostics.
`RSX_FP_CATALOG=<existing parent/dir>` is an optional raw-program diagnostic;
it is not needed for normal preparation.

Volume textures (Phase 96): learned profiles also record volume-unit bindings
in the upper half of the existing `ghi` field. Offline warmup uses those
bindings to compile Texture3D variants; older profiles remain readable and
represent 2D/cube-only states. Visiting wheel materials once learns their new
variants. `RSX_TEX3D=0` selects the older 2D interpretation for diagnostics.

## Race loading and background pipelines

The F1 settings page now offers **Background pipeline creation** and
**Prepare race pipelines**. Both default to On and apply after restart. Their
keys belong under the existing `[video]` table:

```toml
pipeline_async = true
race_preload = true
```

Driver pipelines are built by one background worker, including loads from
native driver cache blobs. The renderer retries pending draws instead of
waiting for that build. A new effect can appear late on its first encounter.
The queue owns its input data and is bounded to 256 jobs / 64 MiB of copied
shader data.

Race loading prepares the pipelines learned during earlier race visits before
entry, with a default 30-second waiting budget. The learned set includes
observed mirror, shadow and replay states across races. It is a conservative
shared race set, not an exhaustive list for the selected track or every camera.
First visits still learn; later visits reuse those recipes. Startup-wide
**Preload known shaders** remains a separate option and can be left enabled.

Membership is stored beside local recipes in
`shadercache/warmup-v1/race-v1.txt`. Preserve it with the rest of the cache.
Loading and the runtime queue share up to 4096 resident pipelines; invalid,
missing or unretained recipes remain eligible for background demand creation.
The window, audio and renderer continue while the loading caller waits. A
loading timeout releases the caller and lets preparation continue in the
background.

Direct controls: `RSX_PSO_ASYNC=0` restores synchronous driver creation;
`RSX_RACE_PREWARM=0` disables race-set learning/preparation;
`RSX_RACE_PREWARM_WAIT_MS=0` keeps preparation but removes the loading wait.
The waiting budget is clamped to 0..60000 ms. Race preparation requires the
shader cache and background pipeline creation. F8 reports include queue and
preparation counters. Tests: `scripts/test/pso_async.py`,
`scripts/test/shader_warmup.py`, `scripts/test/settings_test.ps1` and
`scripts/test/debug_export.ps1`.

## Background startup preparation

With **Preload known shaders** and **Background pipeline creation** enabled,
normal startup now queues preparation and starts the game immediately after
backend initialization. Opening screens, the movie, audio and menus run while
the existing below-normal-priority pipeline worker prepares the cache.

Live draw requests take priority at each worker turn. The worker first prepares
previously observed opening/menu recipes from `warmup-v1/menu-v1.txt`, then scans
the remaining recipes. Race-loading preparation can interrupt that scan too.
Only one native driver creation runs on the worker at a time; an active driver
call cannot be interrupted. The priority list is learned during opening screens
and main-menu visits, and stops collecting when entering dealerships or races.
It requires a visit to learn a new menu scene; unseen states can still appear
late. Preserve this index along with the shader cache.

Startup scans remain bounded to 4096 menu entries and 4096 directory records,
sharing the existing 4096-resident-pipeline limit. Progress and active startup
state appear in logs/F8 exports without replacing the movie's window title.
The `loaded` counter includes reuse in both passes, so it is not a unique
pipeline count. Unprepared records include invalid/missing recipes and recipes
that exceed the resident limit; they retain normal demand creation.

`RSX_SHADER_WARMUP_BACKGROUND=0` restores blocking startup for comparison.
Disabling **Background pipeline creation** also selects the blocking path.
The offline precompile-only command keeps its existing blocking completion
semantics. Explicit offline library compilation is still separate from this
normal-play startup preparation. No cache files are removed or invalidated.


## Asset-derived preparation research

The developer reconstruction workflow now has conditional dither/PCF, LV shadow
and framebuffer environment sampler paths; see
[shader reconstruction](shader-reconstruction.md#conditional-framebuffer-environment-samplers-phase-148).
These options require explicit pass assumptions and leave remaining translation/
pass/target state captured. They do not change this player preparation command,
launcher behavior or release contents. Capture-free catalogue generation and
first-run native pipeline preparation remain unfinished.


The developer mirror scene-copy option derives filter bits only, leaving input
wrap unresolved. Schema 2 texture audits carry per-lane masks; these partial
constraints are not complete pipeline recipes. See the
[mirror investigation](shader-reconstruction.md#partial-mirror-scene-copy-sampler-phase-149).


Developer `--material-texture-shapes` can now replace supported local cube/volume
translation bits during reconstruction proofs. Measured real asset bindings in
this subset are all 2D; global shapes and remaining translation/pass fields still
use capture state. This does not enable a new player preparation path; see the
[shape proof](shader-reconstruction.md#asset-local-texture-shape-bits-phase-150).


Developer `--material-texture-state` additionally derives supported read-gamma
and upper-coordinate bits, including conditional dither/PCF facts. It preserves
unknown global/pass fields and does not enable a player preparation path; see
[sampling-state reconstruction](shader-reconstruction.md#texture-sampling-state-bits-phase-151).


Developer `--environment-texture-path` adds an explicit initialized RGBA8
framebuffer shape candidate. It retains unknown read gamma and requires the
corresponding sampler/texture proof options; it does not enable player setup.
See [framebuffer shape](shader-reconstruction.md#conditional-initialized-framebuffer-shape-phase-152).


Phase 153 adds developer-only conditional object-pass winding/culling and output
gamma reconstruction. Five partial shader/native pipeline proofs pass; live
pass ownership and remaining target/translation fields are unresolved. See
[the reconstruction scope](shader-reconstruction.md#conditional-object-pass-fields-phase-153).
This does not change player preparation or release defaults.


Phase 154 adds fresh native descriptor construction for explicit developer
GPU-fetch/depth-backed target candidates. Five pipeline proofs and a zeroed
captured-descriptor check pass. Remaining shader translation and actual pass
ownership still depend on investigation; no player or release default changes.
See [the measured scope](shader-reconstruction.md#fresh-conditional-native-descriptor-construction-phase-154).


Phase 155 derives export precision from the authored compact fragment-control
word for explicit no-later-override binding candidates. Three fresh-descriptor
pipeline proofs pass; remaining global/coordinate/shadow fields and actual pass
ownership are unresolved. See
[the reconstruction scope](shader-reconstruction.md#authored-compact-fragment-export-control-phase-155).


Phase 156 proves a whole conditional ordinary-upload translation profile and
fresh native descriptor in three samples. The profile takes no captured state;
unknown sampled facts fail closed. No-alias/no-later-override context assumptions
and actual ownership still limit coverage. See
[the independent subset scope](shader-reconstruction.md#whole-independent-ordinary-upload-profile-candidate-phase-156).
Player first-run preparation and launcher integration remain unfinished.
