# Progress log

The port's investigation, newest phase first. Numbers in a phase are what was
measured *at that phase*; later phases correct earlier readings, and the
corrections are left in place rather than rewritten.

**Working rule for this port.** Structural readings of lifted code have been
wrong far more often than the measurements under them. Before a conclusion goes
in here, run the one command that would falsify it; label anything untested as a
hypothesis in the text itself.

## Phase 235 - Short foreground preparation for the current settings (2026-11-10)

**Request.** Reduce the initial preparation to common menu/race pipelines for the
player's settings; keep broader coverage optional and available in the background.

**Behavior.** Foreground preparation takes the deterministic union of the observed
warmup plan: 3,546 input records, pinned to the shipped 12,669-record template.
It keeps original-asset checks, shader derivation, native creation, persistence,
fresh-process lookup, settings translation and MSAA mapping. It skips catalogue
enumeration and interpreter work. Private subset/plan metadata and a separate
token preserve existing full generations. Scope/settings completion metadata
distinguishes short readiness from full readiness, and settings are checked again
before publication. The library preparation API is unchanged.

The launcher uses short preparation for existing foreground entry points and
offers. A current short cache allows broader idle-priority background work on the
next launch, reusing checked results and skipping its redundant race-first stage.
The game keeps its starting cache; the completed full result is selected next
launch. Old full completions remain accepted. Cleanup is scheduled only after
full completion. `Prepare all shaders.cmd`, launcher `--prepare-full` and helper
`--full` select full preparation. `GT5P_PREPARE_QUICK=0` rolls foreground behavior
back; `GT5P_PREPARE_BACKGROUND=0` disables background continuation.

**Fresh measurement.** Same packaged DXC engine as the prior profile, fresh private
application cache, no reuse, aggregate profiling enabled, RTX 4060/12 logical CPUs,
1080p/21:9/8x/HP on/aniso 16. Short preparation: **199.048 s**, full baseline:
**978.308 s** (79.7% less). Both 3,546-record native passes report
`[3546,3546,3546,0]`; 8x mapping creates and verifies 1,672 pipelines with
`[1672,1672,1672,0]`. All 1,466 menu and 2,113 race memberships remain after
mapping; the 2,113-recipe race pack is written. Catalogue/interpreter work is
absent. OS/driver caches were not cleared: an ordered local comparison with
different coverage, not a universal time or hitch claim. Evidence:
`scratch/k236/{validation,timeline,report}.json`; full baseline in
[preparation-profile-025.md](preparation-profile-025.md).

**Initial checks.** Scope/plan determinism, unknown-input rejection, settings
identity, quick/full readiness and legacy full acceptance pass. Packaging includes
the full-preparation command. Launcher background tests pass all 12 cases,
including quick-selected continuation; first-run/DXC/cleanup offers pass all 26
native cases. The final frozen helper and launcher build successfully; hash/volume
native tests pass. All builds and tests use the machine-wide lock.

The final frozen helper's 32-record packed-game test passes cancellation with
eight translated fragments retained and reused on resume, fresh native proof
`[32,32,32,0]`, cached/handoff/code-bundle rollbacks, invalid-option rejection,
quick/full read-only readiness and old-selection/source preservation. After a
successful quick revalidation, background full preparation skips the race-first
stage, reuses all 32 default shader derivations and driver blobs, promotes a
separate full generation, and leaves the quick shader cache unchanged. Evidence:
`scratch/q237/validation.json` and `background-full.log` (173.23 s for the suite).

**Limits.** This is observed menu/race coverage, not whole-game preparation.
Unseen pipelines still compile on demand. Existing automatic translation limits
remain; the default proof also still precedes the additional settings translation,
so this does not eliminate every off-mode driver creation. No engine/runtime patch,
starter, main branch, tag or release change. See [quick-preparation.md](quick-preparation.md).

## Phase 234 - Skip opening movie uses the game's own option (2026-11-10)

**Request.** "Skip opening movie" injected a Cross press (`PAD_SKIP_MOVIE=MovieRoot`) after the movie screen appeared. Link that setting to the game's own option instead.

**Which flag.** The boot movie is `opening_after_autoload` on the user profile (1 plays, 0 skips). The in-game control is Misc → Other → Opening Movie. The Demo page checkbox (`visible_demo_opening`) skips only the attract-mode movie.

**Behavior.** On by default. Wrappers on this title's `mAttributeEval`, `mAttributePush` and `mAssignPop` execute functions run after `ppu_recomp_register`. The eval result is an hByte; its value is the byte at object+0x14, and every eval of this name is overwritten from the setting. Writes are `ATTRIBUTE_PUSH` then `ASSIGN_POP`. Assigns before the first eval are forced to the setting. Later assigns of 0 or 1 update `skip_movie` and the settings file, unless `PAD_SKIP_MOVIE` was already set outside the file. The setting is the source of truth both ways, so a save that was skipped only from the in-game option plays the movie until "Skip opening movie" is turned on. F1 applies to the movie on the next launch. `GT5P_NATIVE_OPENING=0` installs nothing and presses Cross as before. No main-patch edit. A re-lift moves the three execute addresses.

**Measured** on a private engine, TV contents visible, no `FS_HIDE`, 1080p 16:9, 2x MSAA, through the test lock.

Skip on: the boot eval was an hByte 1 rewritten to 0. No `MovieRoot`. `TopRoot` at 14968 ms and `TopMenuTemplate` at 15062 ms. The same contents with the hook not yet writing hBytes still reached `MovieRoot` at 11734 ms.

Skip off: the eval stayed 1. `MovieRoot` at 11625 ms.

`GT5P_NATIVE_OPENING=0` with skip on printed the Cross-press line and installed no hooks. `MovieRoot` at 11859 ms; that run was stopped on the movie screen, so the Cross press was not watched through to the menu.

The profile init assign rewrote an hInt from 1 to 0 when skip was on, and the later eval still read 1 before the result patch. The branch follows the patched eval. A profile load that does not go through this attribute push can restore 1; the eval patch covers that read. An in-game Opening Movie change updating the settings file is implemented and was not clicked in these boots.

## Phase 233 - DXC migration offer and optional old-cache cleanup (2026-11-10)

**Request.** After successful preparation, offer to remove old caches and show the
recoverable GB. Add a one-time startup explanation of the DXC compiler change and
offer preparation. Work stays on `0.2.5`; no release or tag.

**Behavior.** Configured installs now get one DXC migration dialog before gameplay,
including with default background preparation. Prepare now, Skip and play and close
all count as an answer. A current preparation records the migration as handled
without a dialog. FXC/interpreter overrides keep their earlier flow, and fresh setup
does not get a second migration dialog. Skipping leaves background preparation
available under its existing controls. The copy explains the compiler change, cache
incompatibility and retained FXC rollback, rather than claiming the old files are
corrupt or forcing preparation.

Full preparation schedules cleanup only after successful validation and publication
of its selected generation. Foreground completion offers it after the progress
window closes; background completion defers it until next launch, before gameplay.
The native Yes/No prompt shows the approximate total GB of older completed preparation
generations, defaults to No, and explains the learned-cache/FXC rollback consequence.
It does not appear with no eligible old cache. Answers are remembered per selected
generation. Ordinary `shadercache`, saves, settings, the selected generation and
unfinished preparation work are excluded. Older DXC settings generations are also
eligible; this is explicitly described as removal of older prepared caches.

`scripts/preparation_cleanup.py` validates bounded storage-relative generation names,
complete checkpoints, selection and pending-completion identity, refuses redirects
and hard links, skips locked/incomplete work, revalidates targets after the dialog and
locks every deletion target. The launcher holds its storage lease and the helper
requires no game running. Cleanup errors report a notice while retaining the selected
preparation and allowing play. Rollbacks: `GT5P_PREPARE_CLEANUP=0` disables scheduling
and cleanup offers; `GT5P_PREPARE_DXC_OFFER=0` disables the migration offer. Existing
`GT5P_PREPARE_OFFER=0` and `RSX_SHADER_COMPILER=fxc` keep their meanings. Marker names
and scope are documented in [dxc-preparation.md](dxc-preparation.md).

**Validation.** All builds/tests use `run_locked.py`. Native launcher builds pass.
Synthetic cleanup tests cover exact offered bytes, Yes/No, repeat suppression,
disabled mode, incomplete selection, selection/target changes, running-game guard,
hard links, junctions and active generation locks; protected files remain byte-identical.
Native dialogs pass both choices from source and the frozen helper. The 26-case
first-run/update launcher matrix passes, including DXC prepare/skip/close/current,
skip with background preparation enabled, no repeated migration dialog, and deferred
cleanup before the game child starts. The separate 11-case background launcher suite
and packaging integrity checks pass. Frozen helper build includes the new module and
passes the existing hash/volume tests (8/9 cases). No runtime renderer change or
gameplay performance claim is made in this phase.

The real frozen 32-record packed-game check passes in 130.19 seconds: cancellation
retains 8 translated fragments, resume reuses all 8, native verification reports
`[32,32,32,0]`, and source files/old selection remain unchanged. No cleanup pending
marker exists after cancellation; successful resume records the new selected cache
for cleanup. Cached/chunk/handoff/code-bundle rollbacks and invalid-input rejection
still pass. Evidence: ignored `scratch/q234/validation.json` and
`scratch/cleanup-ui` builds; tests `preparation_cleanup.py`,
`launcher_first_run_native.py`, `launcher_background_native.py`,
`player_fragment_checkpoint_native.py` and `player_package.py`.

## Phase 232 - Consolidated 0.2.5 branch, DXC default (2026-11-10)

**Request.** Combine the interpreter/hitch/DXC work with the race-pack prewarm/loading bar and
RecompLauncher integration, make DXC the default after the user's visual acceptance, and remove superseded
development branches/worktrees. `main` remains the published release baseline; no tag or release is created.

**Integration.** `0.2.5` combines `feature/hitch-texture-lru` through ba66f87 and
`feature/prewarm-bundle` through 2947fe7. RecompLauncher d4a0272 was already included through d394f68.
The other development tips (interpreter preparation, shader coverage scaling and hitch attribution) are
ancestors of the combined history. All worktrees were clean before consolidation, with no uncommitted or
untracked non-ignored work. The main runtime patch and progress log had merge conflicts. The backend source
was merged in three-way form against c767f2d, then its patch section regenerated from a clean pinned
4e8f3ca8 export. The historical Phase 228-231 evidence is retained below in order.

**Default.** Unset `RSX_SHADER_COMPILER` now means DXC in the engine and helper; `=fxc` restores FXC.
`RSX_SHADER_INTERP=1` still selects FXC for compatible paired interpreter stages. DLL loading fallback and
strict `-Gis` source keys are unchanged. The user explicitly accepted promotion based on the game visuals;
Phase 231's synthetic numeric differences and the lack of fixed-frame/other-vendor parity remain limits of
the evidence, not new claims of exact equivalence.

**Cache preservation.** DXC preparation uses a separate generation/identity and never deletes prior FXC
caches. Source bytes are verified and reused by copying when compatible. Selection changes only on success;
cancellation/failure retains the old selection. Branch/worktree cleanup is separate from player cache storage.

**Validation.** The merged full main patch and all four current overlays apply to a clean pinned export.
Both compiler selections pass shader-compiler, native-key (13 cases), translation-environment, race-pack
(2 cases), preparation-reuse (26 cases), packaging and RecompLauncher-manifest checks. Every manifest setting
round-trips and the first-run preset matches. A private integrated engine recompiles the backend, decompilers,
changed runtime adapters and current shader-badge/loading-bar source, then links against read-only reference
objects. The frozen helper builds and passes its native hash/volume-reader checks (8/9 cases).

**Integration follow-up.** Checking the now-default compiler against both interpreter parsers exposed
forced and vertex-only modes that the earlier `RSX_SHADER_INTERP=1` check missed. The engine and helper now
mirror both parsers' enabled prefixes (`1`, `f`, `F`), keeping all such paths on FXC. Off/invalid interpreter
values retain default DXC. Selection cases for both stages, default/FXC compilation, and all four overlay
applications pass; the final engine and frozen helper were rebuilt with this fix.

**Real FXC-cache preservation.** A default-DXC frozen preparation (no `RSX_SHADER_COMPILER` override)
creates a new generation alongside a real private FXC cache. All 12,669 native requests, keys, persisted
blobs and lookups pass (`[12669,12669,12669,0]`), and its final race pack contains 2,113 recipes, 1,084
shader bytecodes and 2,113 driver blobs (53,066,538 bytes). Wall time is 310.61 s. Catalogue enumeration
was disabled for this integration run; Phase 231 already covers the full 24,522 DXC catalogue. The entire
old FXC cache is hashed before and after: all **51,113 files**, their relative names and bytes are unchanged.
Selection moves to the new generation. Evidence: ignored `scratch/m232/validation.json`.

**Branch/worktree cleanup.** `0.2.5` is pushed to origin. The five superseded local and remote branches
(`feature/hitch-texture-lru`, `feature/interp-pipeline-prep`, `feature/prewarm-bundle`,
`feature/shader-coverage-scaling`, `t3/hitch-attribution`) are deleted only after their tips are verified as
ancestors of the combined branch. The three obsolete feature worktrees are removed. Their two `.venv`
junctions were unlinked first, leaving the shared Python environment intact. The original `main` checkout
and published release branch are retained; `0.2.5` is the sole development branch/worktree. No player cache
or save data is deleted. The active worktree's existing directory name is unchanged.

**First prepared-pack correction.** The first combined race completed normally and the loading bar
reported 2,113/2,113 ready, but the test correctly rejected it as a pack-path acceptance run: the loader had
fallen back to files. Startup maintenance reordered `race-v1.txt`, invalidating the reader's strict ordered
checksum even though membership was unchanged. The reader now verifies the pack's own ordered checksum,
requires exact nonzero/unique membership, and rearranges bound items to the live priority order. A missing,
extra or duplicated member still rejects the pack; the payload checksum and all per-recipe/code/driver
validation remain. `RSX_RACE_PREWARM_PACK=0` remains the rollback. A native test compiles the actual runtime
helper and covers order preservation/permutation, payload association, changed/duplicated membership,
corrupt checksum, zero keys, null inputs and bounds. All cases pass. The complete patch and overlays apply;
the corrected backend and frozen helper build. The old bytecode/native output is unchanged by this reader fix.

**Final combined acceptance.** With no compiler override, the corrected engine selects DXC, loads all
12,674 prepared fast-lookup rows and takes the pack path on the first prepared race. It reads the 53,066,538-byte
pack in 54 ms and completes all 2,113 pipelines with zero rejections in 313 ms on four threads. The loading bar
reports 0.2 s and 2,113/2,113. The inspected game-window capture shows the road, cars, mirror and HUD.
The 62 s FrameTest is 59.9 FPS, p99 18.2 ms, max 30.2 ms. The wider grid-to-end trace still has 14 intervals
over 50 ms and seven over 100 ms (worst 311 ms); this is a smoke test, not a claim that every hitch is solved.
A relink changes the fast-lookup epoch, so this private fixture's verified rows were republished under the
final executable's tag before copying it for play. The original FXC cache was not touched.

The final frozen default-DXC 32-record checkpoint suite also passes: eight interrupted fragments are retained
and reused, native counts are `[32,32,32,0]`, old selection/source bytes survive cancellation and rejection,
and the cached/chunk/handoff/code-bundle rollbacks pass (114.97 s). This uses the final engine/helper,
including both interpreter-mode compatibility and pack-order fixes. Evidence: `scratch/m232/game-summary.json`,
`checkpoint-validation.json`, and logs/screenshots in `scratch/hitch/routes/hsr-prepared-025-packfix`.
No game remains running. The combined development history is on `0.2.5`; no tag or release was made.

## Phase 231 - DXC preparation and pinned distribution; rendering acceptance remains open (2026-11-10)

**Scope.** Resume the interrupted DXC close-out from Phase 227. The independently completed race pack and
loading bar are on `feature/prewarm-bundle` through 2947fe7 (Phases 228-230); they are not merged here.
A read-only merge check reports one conflict, in the shared main runtime patch. Combining the branches
requires regenerating the backend section from the combined source, then checking the overlays again.

**Implemented.** `scripts/shader_compiler.py` selects FXC by default or DXC with
`RSX_SHADER_COMPILER=dxc`. The player helper, vertex subprocesses and offline engine use the same selection.
The frozen helper includes the compiler module. Player preparation loads the compiler beside its engine;
developer tools can use `GT5P_PREPARE_DXC_LIBRARY`. Compiler selection and the DLL digest distinguish DXC
preparation generations, retaining previous caches and selection until success. The interpreter forces FXC
for guest stages, because generic FXC interpreter stages cannot share a pipeline with DXIL guest stages.

DXC uses SM 6.0, HLSL 2018, and `-Gis`. The strictness flag preserves the output NaN cleanup that DXC otherwise
removed. Source keys now include `0x2000` for DXC strictness in both implementations, avoiding reuse of
Phase 227's non-strict DXC artifacts. The FXC source-key calculation is unchanged. No starter records change.
The backend section was regenerated from a clean pinned 4e8f3ca8 archive; the complete main patch and each
current interpreter/trace/coverage/source-dump overlay apply to a clean export. Literal CRLF context in the
main patch's unrelated headers is preserved.

`scripts/get_dxc.py` fetches Microsoft's pinned v1.8.2502 release with a checked archive SHA-256, compiler,
signer and three license digests. CI fetches it; CMake copies both DLLs beside the engine. Packaging checks
the built DLLs against that distribution and ships its LLVM/NCSA, MIT and Microsoft notices and version/source
manifest. There is no requirement for a separately installed DXC on the player's machine. Gameplay falls back
to FXC if the compiler cannot load; an explicitly requested DXC preparation fails early instead.

**Checks completed on resumption.** All through the machine-wide test lock:

- Full FXC rollback preparation completes: 12,669/12,669 reconstructed native keys, fresh native requests,
  persisted blobs and lookups pass (`native_counts = [12669,12669,12669,0]`). MSAA mapping and fast lookup
  report complete. Catalogue enumeration prepares 24,434/24,522; its 88 exclusions match the earlier FXC
  baseline count, and all 16 retained failure examples have the same identities. They are not new regressions.
- `get_dxc`, `shader_compiler`, `native_pipeline_key` (13 cases), `prepare_material_shaders`,
  `shader_vertex_batch`, `shader_translation`, and `player_package` pass under each compiler selection.
  Checks cover signed deterministic DXIL, distinct strictness keys, compiler propagation, protocol bounds,
  archive/signature-DLL/notice integrity, package exclusion rules, and mismatched packaged DXC rejection.
- Fresh final frozen DXC preparation completes in **482.57 s wall**, including all **12,669** native
  requests/keys/persisted lookups (`native_counts = [12669,12669,12669,0]`) and **24,522/24,522** enumerated
  shaders, zero failures. MSAA mapping and fast lookup report complete. A prior selected cache marker is
  preserved and selection moves only after success. The core report time is 406.60 s; the FXC rollback's
  report is 783.86 s. Different process/cache/driver histories make these validation timings, not a controlled
  compiler speed comparison. Evidence: ignored `scratch/dxc-closeout/frozen-full.json`, `dxc-summary.json`
  and `fxc-summary.json`.
- Final private engine links and the frozen helper builds. Its hash-library (8 cases) and volume-reader
  (9 cases) checks pass. All outputs remain private; shared runtime/build/game/cache inputs are read-only.

- Frozen 32-record checkpoint suites pass with each compiler, using four workers and both default and
  ultrawide-native translations. Each retains eight interrupted fragments, reuses all eight on resume,
  and passes `[32,32,32,0]` native validation. Existing selection/source caches remain intact through cancel
  and invalid-input rejection; cached, chunk-size, native-handoff and code-bundle rollbacks pass. The suites
  take 116.72 s (DXC) and 118.38 s (FXC); most of this repeated test is archive/reuse/rejection work, not a
  compile benchmark. Records: `scratch/dxc-closeout/frozen-*-checkpoint.json`.

- A prepared High Speed Ring route with the final engine and fresh DXC cache completes (1080p, 16:9,
  2x MSAA, interpreter off, no background helper). Logs confirm DXC and 12,674 fast-lookup rows loaded,
  ending with 1,677 fast hits; no shader compilation or pipeline-creation failures are reported. Inspected
  game-window captures show the road, cars, mirror and HUD rendering. The 62 s FrameTest reports 59.9 FPS,
  p99 18.0 ms and max 31.0 ms. The wider grid-to-end trace, excluding capture overlap, has five intervals
  over 50 ms, none over 100 ms (worst 95 ms). This single route is a smoke test, not fixed-frame parity,
  whole-game coverage, or a new performance comparison. Logs/screenshots remain in
  `scratch/hitch/routes/hsr-prepared-dxc231`; its summary is `scratch/dxc-closeout/game-summary.json`.

The resumed validation commands were the locked source `scripts/player_prepare.py` with
`RSX_SHADER_COMPILER=fxc`, a freshly built `GT5P-Prepare.exe` with `RSX_SHADER_COMPILER=dxc`,
`scripts/test/player_fragment_checkpoint_native.py --count 32 --chunk 8` under each compiler,
and `scripts/test/hitch_capture.py hsr prepared --suffix dxc231 --env RSX_SHADER_COMPILER=dxc`.
The small orchestration scripts and metadata summaries remain under ignored `scratch/dxc-closeout`.

**Recovered rendering evidence, not a pass.** The November 6 GPU harness uses identical synthetic inputs
for 264 GPU-fetch vertex and 1,073 pixel shaders. All compile, and pixel coverage agrees. It flags 40 vertex
and 53 pixel shaders: 9,736 of 74,579,968 pixel values exceed its 1/1024 relative threshold, maximum relative
error 1.32; vertex results include one-sided NaNs/infinities on extreme random inputs. Eighteen CPU-fetch
vertex shaders are not exercised. The FXC skip-optimization control also differs (17 pixel shaders, 1,282
values beyond threshold), which does not prove the additional DXC differences harmless. Both comparisons
exit 1. Earlier commentary calling these differences acceptable was stronger than the evidence.

The interrupted work had already completed a source-helper DXC preparation (12,669 native pipelines plus
24,522/24,522 enumerated shaders; 575 s wall), and a prepared HSR route reported 59.9 FPS with three intervals
above 50 ms. Those runs predate the strictness source-key correction; their bytecode used `-Gis`, but their
keys are obsolete. A 110-source strictness timing sample retained the compile advantage (FXC 8.4 s, DXC
3.2 s, zero compile failures). These are historical local samples, not a new controlled preparation-time claim.

**Cleanup limit.** New private build/cache trees were checked to stay under this worktree's scratch directory;
no junctions/reparse points were found. Automatic command approval rejected both the bounded cleanup script
and a single literal-directory deletion as `blocked by policy`. No deletion was performed. The private
artifacts remain under `scratch/dxc-closeout`, `scratch/d31`, `scratch/q31`, `scratch/q32`,
`scratch/fx/storage-fxc` and `scratch/hitch/caches/hsr-prepared-dxc231`; the exact manifest is
`scratch/dxc-closeout/cleanup-blocked.json`. No game remains running. No protected shared inputs were changed.

**Decision and remaining acceptance.** FXC stays the default, following the standing rule that unproven
experiments remain developer options. `RSX_SHADER_COMPILER=dxc` enables the complete development path;
unset or `=fxc` restores FXC. Fixed in-game frame comparison, CPU-fetch coverage, and other GPU vendors/drivers
remain open before default promotion. The interpreter remains default-off. No merge to main, tag or release.
See [dxc-preparation.md](dxc-preparation.md) for setup and the comparison harness.

## Phase 230 - Thin bar under the GT logo while the race set loads (2026-11-08)

**Aim.** Loading into a race leaves the GT logo on screen until the race pipelines are ready. The guest is blocked inside that gate, so the picture does not move. Show how far the set has got.

**What changed.** The backend counts pipelines finished (ready or rejected) against the race-set count, and whether the gate is waiting. A layered window on the shader-badge thread draws a 6 px bar centered under the logo, about 62% of the way down the window, and about a fifth of the width (220 to 480 px). It appears once the gate has run for 200 ms and hides when the gate releases. `GT5P_RACE_LOAD_BAR=0` leaves it off.

**Seen in game.** A private `gt5p.exe` (this patch linked against the reference build, not the installed launcher executable) was started on the player's prepared cache: 1080p, 21:9, 8x, and no race pack yet. The bar showed for 19.6 s and filled to 4,973 / 4,973. The gate finished in 19.8 s, all ready, none rejected, inside the 30 s budget. The player confirmed the bar. That run then wrote `race-pack-v1.bin` into the prepared cache: 4,973 pipelines, 2,399 shaders, 254,758,530 bytes. A later race with this build reads that file. The installed launcher executable was not replaced.

## Phase 229 - Background warmup reads the race pack (2026-11-08)

**Aim.** The menu-time warmup still prepared the learned race set one file at a time, and a cache with no `race-pack-v1.bin` still paid that walk on the first race. The loading gate then wrote the pack after play had started.

**What changed (main patch, pack on).** The background warmup's race phase uses `warmup-v1/race-pack-v1.bin` when its checksum matches `race-v1.txt`. It still prepares one pipeline per turn, and the worker still waits one millisecond between turns. The bytes stay resident, so the loading-gate prewarm does not read the file again. The menu index stays one file per pipeline. `RSX_RACE_PREWARM_PACK=0` keeps both paths on the per-file opens. The patched backend was typechecked with the reference `clang-cl` command. `gt5p.exe` was not linked, and no game was launched, so this path was not timed in a race.

**Player cache.** `race-pack-v1.bin` was written beside the live `race-v1.txt`: 1,754 pipelines, 1,631 shaders, 1,754 blobs, 158,410,322 bytes. The recipes and bytecode were not deleted. A later race with this build reads that file instead of opening the set again. The in-game loading screen was not measured.

## Phase 228 - One file for the race prewarm; queued creates overlap (2026-11-08)

**Aim.** The race prewarm opened a recipe, two bytecode files and a driver blob for every pipeline. Offline preparation already reads that data as one bundle. Do the same for the race set, and measure whether several `CreateGraphicsPipelineState` calls at once, or an `ID3D12PipelineLibrary`, make an existing pipeline cheaper to bring back.

**What changed (main patch, pack on).** `warmup-v1/race-pack-v1.bin` stores the race index in order: each recipe, each DXBC once, and the raw driver blob without its 24-byte header. Objects in the payload are 16-byte aligned. `scripts/race_preload_pack.py` writes it at the end of preparation, after the membership lists are final. The renderer uses it when its index checksum matches `race-v1.txt`. A missing or stale pack keeps the per-file opens, and the last helper writes the pack for the next race. `RSX_RACE_PREWARM_PACK=0` skips the read and the write. Both paths still use `RSX_RACE_PREWARM_THREADS` (default 4). `=1` still reads the pack, one recipe per worker turn. The patched backend compiled with the reference `clang-cl` command. That produced an object file only: `gt5p.exe` was not linked, and no game was launched.

**File reads.** Live race index, 1,754 pipelines. The pack was written under TEMP. The player's shader cache was only read.
- First touch of the recipes, the driver blobs and the vertex bytecode: 19.2 s, 228 MB, 7,016 opens. That pass used the wrong shader-hash offset, so the pixel bytecode was not included.
- Full set afterwards (pixel bytecode included, the rest already cached): 7.8 s, 243 MB.
- That same full set again: 0.67 s.
- One read of the pack just written: 0.063 s. The file is 158 MB, with 1,631 shaders and 1,754 blobs.

**Pipeline creates.** 64 pixel shaders, each with its own bytecode (an 80-step `sin` loop), RTX 4060, driver 32.0.16.1088. One discarded create ran first.
- Driver had not compiled these shaders: 362 ms on one thread (5.66 ms each), 196 ms on two (1.9x), 120 ms on four (3.0x).
- Same process, after that compile: creating them again with no blob was 20.3 ms; with the cached blob, 17.6 / 5.7 / 4.7 ms on 1 / 2 / 4 threads.
- A new process, driver cache already warm: a blob load was 20.1 ms (0.31 ms each) and a no-blob create of the same shaders was 22.0 ms (0.34 ms). Four threads of blob loads in the warm process were 5.0 ms.
- `ID3D12PipelineLibrary` load of those 64, one thread, new process: 11.7 ms (0.18 ms each). Four blob threads were faster (5.0 ms). The library is not in the engine.

## Phase 227 - DXC for guest shaders (opt-in): compile time 2.6x lower (2026-11-06)

**Aim.** On an empty cache a High Speed Ring race compiles about 1,075 shaders on demand. Make the compiles
themselves quicker.

**Where the time goes.** The engine with the source-dump overlay (`RSX_SHADER_SRC_DUMP`) recorded the real
on-demand set of one empty-cache race: 1,075 HLSL sources (854 pixel, 221 vertex). Offline, one thread,
FXC (`D3DCompile`, the engine's flags): 86.7 s in total, median 74 ms, p90 151 ms, worst 437 ms; the slowest
100 shaders are only 24% of it. Our own translation is negligible (Phase 211: 0.07 s against 472 s compiler).
- **FXC flags do not help:** optimisation level 0 = the default (level 1); `SKIP_OPTIMIZATION` is ~30%
  faster but the bytecode is 2.2x larger.
- **Text ablations** (time, and whether the bytecode stays identical): an empty `main` compiles 80 pixel
  shaders in 0.17 s (fixed cost negligible); the body is the cost. Plain variables instead of the `r[]`/`h[]`
  register arrays: -15%, 70 of 80 bytecodes identical. Hoisting `1/w`: -4%. Vertex shaders: 74% of their
  time is the GPU vertex-fetch decoder (5.24 -> 1.37 s for 40 without it); unrolling it is slower (9.1 s).
- **DXC** (`dxcompiler.dll` 1.8.2502 from the Windows SDK, shader model 6.0, `-HV 2018` because the text
  uses vector `?:`), in process, same files: **32.1 s against 84.8 s**, no failures. Pixel 57.1 -> 23.7 s
  (median 55 -> 24 ms, worst 419 -> 122 ms); vertex 27.7 -> 8.4 s (median 129 -> 39 ms, worst 334 -> 69 ms).
  `-O0..-O3` take the same time (the cost is DXC's front end).

**What changed (main patch, default off).** `RSX_SHADER_COMPILER=dxc` compiles guest vertex and fragment
shaders with DXC: `dxcompiler.dll` (and `dxil.dll`, which signs the DXIL) beside the engine, loaded at run
time; one compiler object per thread; COM declared by hand (the backend is C). The target becomes
`vs_6_0`/`ps_6_0` before the source key is computed, so cache file names and native pipeline keys never mix
with FXC's. DXIL declares a resource array's whole range, so for DXC the `rsx_samp[16]` and `rsx_tex[16]`
arrays (constant indices only) are rewritten into separate declarations; without that every pixel shader
failed pipeline creation ("Shader sampler descriptor range ... not fully bound in root signature", D3D12 debug
layer). No DLL: FXC with one log line. The port's own helper shaders stay on FXC. The frame-trace overlay's
context lines were updated.

**Measured.** High Speed Ring, 1080p 16:9 2x, empty cache, no helper, same private engine, one locked run per row.

| Compiler | Excess | >50 / >100 ms | Worst (ms) | Frame test | Shader compiles / pipelines |
| --- | --- | --- | --- | --- | --- |
| FXC | 11.2 / 12.2 s | 147, 171 / 49, 40 | 318, 554 | 56.1, 55.9 FPS; p99 46, 49 ms | 1,064-1,071 / 1,880-1,885 |
| DXC | 6.6 / 6.8 s | 89, 86 / 27, 31 | 300, 372 | 57.9, 58.6 FPS; p99 33, 26 ms | 1,098-1,099 / 1,971-2,184 |

- No compile or pipeline failures with DXC (D3D12 debug layer clean on the dealership route); dealership and
  race screenshots look the same as FXC's. This is a visual check, not a per-pixel comparison of one frame.
- Driver time in slow frames is about the same (pso ms in >50 ms intervals 1,110-1,264 against 1,145-1,511):
  pipeline creation from DXIL is not slower here.

**Not done (needed before it can be the default).** Preparation still produces FXC bytecode, so a prepared
cache is not used by a DXC game: the offline engine and the helper's cached-shader checks need the same
compiler and target. `dxcompiler.dll`/`dxil.dll` must be packaged (from the Windows SDK or the DXC release;
redistribution terms to confirm). Rendering parity needs per-pixel comparisons on fixed frames. Other GPUs and
drivers untested. The interpreter overlay's own compiles are unchanged.

## Phase 226 - Background preparation: trickled race files, pause at the race start (2026-11-06)

**Aim.** Phase 225 helped only a player who stayed in the menus for about 1.5 minutes: the race stage's files
reached the live cache all at once when it finished (~90 s after launch), and the helper was paused from the
race loading screen on. A player who went straight to a race got the same 10-11 s of excess as with no helper.

**What changed.**
- **Trickle** (`scripts/background_preparation.py` `Trickle`, helper only): while the race stage runs, every
  progress call (at most every 5 s) copies the stage's new shader containers (`<16hex>.dxbc`,
  `warmup-v1/code_<16hex>.dxbc`) and driver blobs (`pso_<16hex>.bin`) into the live cache, by the same
  never-replacing atomic rename as the final merge. A file is placed only when complete: a DXBC whose own
  length field matches the file, a driver blob whose length and FNV checksum match (`complete()`; 900 of 900
  real cache files pass). Incomplete files wait for a later pass; the final merge applies the same check
  (`incomplete` count). Recipes and the race list still wait for the proven stage, so the loading-screen
  prewarm is unchanged; draws before then find the shader bytes and blobs on disk instead of compiling.
  The MSAA re-target stage trickles too. `GT5P_PREPARE_BACKGROUND_TRICKLE=0` copies only at the end.
- **Pause at the race start** (main patch, `race_signal`): no script loads when the race itself starts (a
  scripted route shows `LoadingRoot`, then `OnboardMeterRoot`/`RaceRoot` +1.3 s, `QuickArcadeRoot` +3.5 s,
  then nothing until the menus). The loading screen now only arms the signal; a watcher thread (50 ms) sets
  `GT5P_RACE_EVENT` on the first Cross or Start press at least 1 s later (`g_pad_menu_buttons`: every pad,
  the keyboard and scripted presses), the grid preview's Start, or `GT5P_RACE_SIGNAL_CAP_MS` after the loading
  screen (default 45000, 0..600000) if no press comes. Menu scripts reset it as before. The helper so works
  through the loading screen and grid preview. `GT5P_RACE_SIGNAL_AT=loading` restores Phase 225.
  Launcher unchanged.

**Measured.** As Phase 225: High Speed Ring, 1080p 16:9 2x, empty cache, one locked run per row, private
engine (main patch + frame trace), source helper started with the game (`hitch_capture.py --background-helper`).

| Case | Excess | >50 / >100 ms | Worst (ms) | Helper paused at | Files trickled by then |
| --- | --- | --- | --- | --- | --- |
| Straight to the race, Phase 225 behaviour on this engine (`_TRICKLE=0`, `AT=loading`) | 11.2 s | 164 / 43 | 535 | 62 s (loading screen) | - |
| Straight, trickle only (`AT=loading`) | 4.5 s | 48 / 20 | 474 | 62 s | 1,048 |
| Straight, trickle + pause at the race start | 3.9 / 3.2 s | 37, 34 / 16, 16 | 525, 389 | 71-73 s (start press) | ~1,050 |
| 90 s more in the menus, both | 3.0 / 3.6 s | 28, 34 / 13, 14 | 782, 776 | 159-160 s (start press) | 4,189 (all; merged at 94-110 s) |

Phase 225 for comparison: straight 10.3-11.1 s, with menus 3.5-4.5 s, empty cache without helper 12.0-12.8 s.
- Straight to the race the stage is not finished at the race start (vertex shaders and the fragment batches are
  done at ~62 s, native creation is not); the shaders trickled before then remove most of the excess. The
  later pause adds about 10 s of helper time (loading screen and preview) and a little less excess.
- With menus first the result is within run-to-run spread of Phase 225 (everything is merged before the race
  either way). The 780 ms worst frames there remain (as in Phase 225).
- Packaged: `scripts/test/background_launcher_e2e.py` with a rebuilt launcher, frozen helper and this engine
  passes: game at 1.1 s, race stage merged at 87.2 s (4,269 files trickled over 10 passes in an identical
  earlier run), launcher exits 3.7 s after the window closes, second launch already merged at 10.4 s. Its
  record line limit was raised (the merge record is longer now).

**Tests.** `scripts/test/background_preparation.py` adds the completeness check (torn shader and blob not
placed), the trickle (interval, incomplete retried, game files kept, recipes and race list not trickled) and
`prepare_race` with stand-in stages (files live before the stage returns; only at the end with `_TRICKLE=0`).

**Limits.** One run per row. Only High Speed Ring at 1080p 2x. The press heuristic pauses early if the player
presses Cross/Start on the loading screen, and pauses on any Cross in the preview (Exit included; the menu
script then resumes it). A mode without a press before driving pauses at the cap (45 s). Multi-race sessions
through the real launcher are still untested.

## Phase 225 - Background preparation, race pipelines first (2026-11-06)

**Aim.** A player who never runs preparation gets about 1,075 shader compiles and 1,900 pipeline creations in
their first race (Phase 224: 11-13 s of excess on an empty High Speed Ring). Preparation itself works, but
it is a 10-20 minute wait the player has to choose. Do it while they play, starting with what races need.

**What it does.** `launcher/launcher.cpp`, `scripts/player_prepare.py --background --live-cache <dir>`,
`scripts/background_preparation.py`, one renderer function in the main patch.
- **Launcher:** when no completed preparation of this release is selected (`--check-selected`, now asked on
  every launch until it answers "current", then remembered in `prepare-current-<version>.txt` beside the
  selection), the helper starts beside the game: idle priority (inherited by its compiler and offline
  processes; the helper does not enter `PROCESS_MODE_BACKGROUND_BEGIN`, which measured as resetting the class
  its children inherit to normal), its own kill-on-close job, logs in `logs/prepare-background.*`. There is no offer dialog in
  this mode. Settings restarts keep it; any other game exit stops it (`prepare.cancel`, 30 s, then the job
  closes); it resumes next launch from its checkpoints. `GT5P_PREPARE_BACKGROUND=0` restores the one-time
  offer; `GT5P_PREPARE_OFFER=0`, `GT5P_PREPARE_VOLUME=0` and `--no-prepared` start nothing.
  Prepare shaders.cmd and F1 > Debug > Prepare shaders still run the foreground preparation (the background
  helper is stopped first).
- **Race stage:** the 2,113 race records of the bundled warmup plan (557 of 2,824 fragment programs) as their
  own template bundle, through the same preparation, translation and MSAA re-target stages and the same proofs,
  into `preparation/race-<token>/stage`. Its shader bytes, driver blobs and code files are then copied into
  the cache the game is using (atomic rename, never replacing a file the game has), recipes last, and the
  race keys are appended to that cache's `warmup-v1/race-v1.txt`, which the renderer reads at every race
  loading screen. Done once per live cache (`merged-v1.json`).
- **Full stage:** the ordinary full preparation, reusing the race stage's verified shaders and driver blobs
  (4,230 present, 2,113 blobs copied), selected only on success as before, so the next launch uses it. The
  race stage folder is removed then.
- **Paused while racing:** the renderer sets `GT5P_RACE_EVENT` (a manual-reset event the launcher creates)
  at the race loading script and resets it when a menu script loads (results and replays count as racing).
  A launcher thread suspends every process of the helper's job while it is set and resumes them in the
  menus (`NtSuspendProcess`, polled every 250 ms; the totals go to `logs/prepare-background-pause.txt`).
  `GT5P_PREPARE_BACKGROUND_PAUSE=0` never pauses. Without the launcher's variable the renderer does nothing.
- **Workers:** half the logical processors (2..12; 6 here), `GT5P_PREPARE_BACKGROUND_WORKERS` overrides.

**Measured.** High Speed Ring, 1080p 16:9 2x, empty cache, one locked run per row, private engine (main
patch + frame trace), source helper started with the game as the launcher does (`hitch_capture.py
--background-helper`). Excess = time above the frame budget in display intervals over 50 ms from the grid.

| Case | Excess | >50 / >100 ms | Worst (ms) | Note |
| --- | --- | --- | --- | --- |
| Empty cache | 12.8 / 12.0 s | 177, 164 / 50, 44 | 349, 324 / 452, 293 | race loading ~55 s after launch |
| Helper running, no pause (3 workers)* | 17.0 / 15.0 s | 197, 182 / 75, 70 | 556, 422 / 506, 370 | race stage still compiling in the race; 51 FPS frame test |
| Helper, paused while racing | 10.3 s (11.1 s*) | 156 (151*) / 30 (49*) | 230, 227 (246, 208*) | paused 119 s; race stage not finished before the race |
| Empty cache, 90 s more in the menus | 10.5 / 11.1 s | 162, 148 / 29, 39 | 224, 184 / 783, 210 | |
| Helper, paused, 90 s more in the menus | 3.5 / 4.5 s (3.1 / 3.0 s*) | 35, 38 / 15, 18 | 856, 240 / 840, 399 | race stage merged 89-91 s after launch (111 s*), race at 153-156 s |
| Race stage copied in only (no helper running) | 2.6 / 3.8 s | 27, 30 / 14, 14 | 329, 245 / 795, 785 | stands for a later race of the same session |
| Full preparation selected | 0.36 s | 9 / 0 | 67 | next launch |

\* Runs before the priority fix: the helper itself was idle, but `PROCESS_MODE_BACKGROUND_BEGIN` had put its
compiler and offline children back to normal priority. The unpaused case was not repeated at idle priority.

- The race stage alone (no game) takes 106 s with 3 workers; the whole background preparation 20 min.
  Beside the game in the menus, 6 workers at idle priority: merged 89-91 s after launch (88 s in the packaged
  run below).
- In the menus the helper costs a little: over about 120 s of menus 30.4-31.1 against 31.4 FPS, frames over
  50 ms 20-30 against 11-13, over 100 ms 4-13 against 0-3, p99 39-45 against 37 ms.
- A first race started within about two minutes of launch is the same as before; it is no worse because the
  helper is paused. The next race loading screen prepares the race set.

**Tests.** `scripts/test/background_preparation.py` (switches, race selection on the starter, merge rules);
`scripts/test/launcher_background_native.py` (11 cases with the probe: started at idle priority with the
live cache, old selection as live cache, finishes or is cancelled with the game, survives a settings restart,
suspended while the probe signals a race and resumed after, no event with `_PAUSE=0`, current preparation
remembered, check error, disabled switches); `launcher_first_run_native.py` (20 offer cases, run with
`GT5P_PREPARE_BACKGROUND=0`) and `launcher_native.py` pass. `scripts/test/background_launcher_e2e.py` runs the
real launcher, the frozen helper (`build_preparer.py`) and the engine with nothing prepared: no offer, game at
1.1 s, helper and its workers at idle priority, race stage merged at 88 s (2,113 race keys, 2,116 recipes in the
live cache), game window closed -> launcher exits 4.1 s later with no helper or game process left, nothing
selected, work resumable; the second launch reports the race stage already merged at 11.5 s. The route
measurements use the source helper with the same arguments, priority, job and pause rule (that run stays on
the menus, so the race pause itself is covered by the route runs and the probe test).

**Limits.** Race membership is the observed plan (High Speed Ring, Daytona, Fuji runs); other tracks gain from
the shared states only. The menus are not prepared first. A player who changes resolution while it runs
gets a race stage for the old mode (the full stage then fails its settings check and restarts next launch).

## Phase 224 - Per-frame interpreter budget (GPU cost cap) (2026-11-06)

**Aim.** Help players with no prepared cache. With the interpreter on, every pending draw is interpreted, and an
interpreted pixel costs several times a specialized one (Phase 216 gap 5: force mode about 79 ms GPU per frame
against 3-5 ms). A burst of pending shaders could therefore push frames past the vblank.

**Change** (`patches/ps3recomp-shader-interp.patch`, overlay only; the interpreter stays default-off):
- `RSX_SHADER_INTERP_BUDGET` sets a GPU frame-time target in ms (default 14; `0` = unlimited, the earlier
  behaviour).
- The number of pending draws the interpreter may take each frame adapts to the previous frame's measured GPU
  time (`RSX_GPU_TIME`). It is halved, from what was used, when that frame was over the target. It rises by an
  eighth (at least 8) when the frame is under 80% of the target. The floor is 4 and the start value 64
  (`RSX_SHADER_INTERP_BUDGET_START`).
- Draws past the allowance are left out exactly as with the interpreter off, and appear once their shader is
  ready. Forced mode (`=2`) is not limited.
- `[interp-budget]` lines report frames, frames over the target, the allowance, interpreted draws per frame and
  denied draws.

The overlay was regenerated with `interp_make_patch.py` (hunk offsets now match the current main patch). New
build script: `scripts/test/interp_hitch_build.py` builds main + interpreter + frame-hitch trace, with
embedded interpreter DXBC. The trace overlay's three skip counters are re-applied on the interpreter's lines.

**Measured.** High Speed Ring, empty cache, `hitch_capture.py hsr cold`, the same private engine, interpreter
stages both on (`RSX_SHADER_INTERP=1`, `_VP=1`). Excess is the time above 50 ms summed over frames after the
grid.

| Settings | Mode | Excess | Frames >100 ms | Worst frames (ms) | Interpreted draws | Interpreter PSO ms (max) |
| --- | --- | --- | --- | --- | --- | --- |
| 16:9 2x | budget | 12.3 / 11.6 s | 52 / 50 | 334, 237 / 530, 281 | 31,350 / 35,425 | 4 (2) / 4 (2) |
| 16:9 2x | no budget | 13.7 / 12.7 s | 47 / 53 | 408, 369 / 422, 315 | 56,692 / 56,408 | 9 (2) / 14 (3) |
| 16:9 2x | interpreter off | 12.1 / 11.6 s | 59 / 46 | 286, 211 / 348, 213 | - | - |
| 21:9 8x | budget | 12.3 / 12.4 s | 47 / 39 | 281, 253 / 312, 252 | 23,807 / 28,665 | 5 (1) / 3 (1) |
| 21:9 8x | no budget | 10.5 / 12.6 s | 37 / 42 | 745, 246 / 828, 683 | 36,730 / 36,959 | 835 (755) / 1,475 (771) |
| 21:9 8x | interpreter off | 10.3 / 11.3 s | 44 / 46 | 538, 206 / 229, 208 | - | - |

What it says:
- **On this PC the interpreter's GPU cost is not what makes an empty cache hitch.** Total excess is 10-14 s in
  every mode, and the pairs overlap.
- The GPU went over the 14 ms target in only 104-131 of about 7,500 frames, even at 21:9 8x. Those frames fall
  in the compile bursts: each halves the allowance and it recovers over tens of frames. That is why the budget
  still denied 150-184k draws and cut interpreted draws by about 35-45%.
- The cold hitches are shader compilation (about 1,075 compiles) and pipeline creation (about 1,900) on the
  replay path. In long frames the replay batch time was 3.6-3.8 s with the interpreter off, 4.5-4.7 s with the
  budget, and 4.2-5.6 s without it.
- At 21:9 8x both no-budget runs had 745-828 ms worst frames. Their counters show interpreter pipeline creation
  of 755-771 ms for classes outside the startup set. With the budget, fewer classes were reached and none took
  over 1 ms. At 16:9 2x the worst frames do not separate.
- This is two runs per row on one machine with a fast GPU. A weaker GPU, which the budget is for, was not
  available, so the benefit there is the design intent, not a measurement.

**Measurement note.** With nobody at the PC, Windows turns the display off. DXGI Present then blocks for
about 200 ms per call (19-27 presents per 5 s), boot is about 8 s slower, and the scripted menu presses miss:
"Starting grid not reached". Six runs failed this way and were discarded. Unattended route runs need the
display kept on (a `SetThreadExecutionState(ES_DISPLAY_REQUIRED)` holder) and woken first. Two batches also
overlapped once; each kept run's configuration was checked from its own interpreter counters.

**Recommendation.**
- Keep the budget as the interpreter's behaviour (`RSX_SHADER_INTERP_BUDGET=0` rolls back), and keep the
  interpreter default-off.
- For players without a prepared cache, the lever is the compile/creation work itself, not the interpreter:
  e.g. preparation in the background from first launch, or more of the starter prepared before play.

## Phase 223 - Prepared pipelines at the player's MSAA sample count (2026-11-06)

**Problem.** At 21:9 with 8x MSAA (the user's settings) the prepared High Speed Ring race still created about
920-930 pipelines during play. The worst frames were 386-842 ms, and the time above budget was 3.7-4.5 s. The
starter observed its multisampled targets at 2x (5,835 records) and 4x (662). The renderer gives every
multisampled target the configured `RSX_MSAA` count (`off_rt.ms_n` into bits 16-19 of the key's cube field,
then `SampleDesc.Count`), so at 8x none of those 6,497 prepared pipelines can be used.

**What depends on the count.** In `vp_get_fp_pso` the sample count only sets `pd.SampleDesc.Count`. Nothing
else in the descriptor (rasterizer, blend, sample mask) changes. The vertex shader never depends on it, and since
Phase 213 (`RSX_FP_SAMPLE_SHARE`, default) the fragment text is the same for every count. The count is word 154
of the 656-byte descriptor the template stores; a compiled probe against `d3d12.h` confirms offset 616 (Quality
at 620).

**Change.** New preparation stage `scripts/msaa_pipeline_map.py`, run by `player_prepare.py` after the
default/translation passes:
- It takes every multisampled resolved record of the translation the player runs. Translated records are
  rebuilt from the default record plus the translated shaders in the cache, and must reproduce the translation
  pass's own native key.
- It sets descriptor word 154 and the key's sample bits to the MSAA in `gt5p_settings.toml`. For 1x the bits
  are 0 and the count is 1.
- It computes the new native key and asks the driver to create the pipeline through the existing native batch.
  No shader is compiled. Each result must be created, with actual == expected == derived key, and every blob must
  persist (inventory check).
- It adds the re-targeted rows to the fast lookup table (`extra_rows`), and rewrites the preparation's own
  menu/race lists so each re-targeted pipeline replaces its source.
- It never changes the token, the template, prepared shaders or default records. A failure keeps the
  preparation, and the game creates these pipelines during play as before.

Rollback: `GT5P_PREPARE_MSAA_MAP=0`. A later preparation run after an MSAA change adds that count (output
folder `ms/<count>`).

**Measured (21:9 ultrawide-native preparation, 8x, build-final engine).**
- Stage on a copy of `prep-uw`: 6,497 multisampled records were re-targeted to 5,840 distinct 8x pipelines. All
  were created (5,840 driver calls, 0 rejected) and persisted, in 173 s: about 50 s input, 30 s driver, 80 s
  verification.
- The race list re-targeted 964 of 2,113 entries; the menu list 713 of 1,466. The fast lookup table went from
  12,669 to 18,509 entries.
- High Speed Ring prepared route, 21:9 8x, all runtime defaults:

| Run | Seed | Excess >50 ms | Frames >50 / >100 ms | Worst frames (ms) | Demand pipelines | Fast-lookup hits |
| --- | --- | --- | --- | --- | --- | --- |
| Uon2 (Phase 221) | prep-uw | 4,469 ms | 27 / 18 | 842, 722, 380 | 1,129 | 868 |
| M8off3 | prep-uw | 3,700 ms | 41 / 18 | 386, 252, 201 | 1,106 | 868 |
| M8on3 | prep-uw + 8x | 601 ms | 10 / 1 | 170, 100, 86 | 301 | 1,671 |
| M8on4 | prep-uw + 8x | 643 ms | 10 / 2 | 161, 101, 93 | 301 | 1,671 |

- Without the 8x pipelines the runtime made 2,289-2,310 cached-blob driver calls and about 930 fresh ones. With
  them it made 2,409 cached and 5 fresh calls.
- The fast lookup had 10 absent keys, against 935 before.
- M8off4 matched the other baselines' pipeline counts (1,127 demand, 868 hits), but its frame trace recorded no
  intervals after the grid, so its frame numbers are left out.
- The first four runs (M8on/M8off/M8on2/M8off2) failed to reach the grid while the machine was resuming from
  sleep (slow loading made the scripted presses miss); they are discarded.
- A race screenshot at 21:9 8x renders normally.

**Tests.** `scripts/test/msaa_pipeline_map.py` covers:
- the descriptor offset probe;
- re-targeting to 1/2/4/8, including key bits, the descriptor word and refusals;
- that only the count changes the key;
- membership rewriting;
- optionally (`--report`), that a real preparation reproduces every multisampled key.

`scripts/test/fast_lookup_table.py` still passes.

**Limits.** These are one route and one settings combination. High precision off (`smooth_colour = false`)
changes the target format of the R16G16B16A16 records too and is not mapped. The roughly 300 remaining demand
pipelines are draws outside the starter.

## Phase 222 - RecompLauncher manifest, launcher-edited settings, storage link (2026-11-05)

Branch `feature/recomplauncher-manifest` (commit d4a0272), merged into `feature/hitch-texture-lru`; that branch and its worktree are closed. See
[recomplauncher.md](recomplauncher.md).

- `launcher/recomplauncher.json` (level 1 and 2) starts `tourline-prologue.exe` and exposes ten
  settings over `gt5p_settings.toml`; the packager ships it at the ZIP root and refuses a manifest
  that starts anything else.
- `config.new` and the launcher's first-run preset now both write `[meta] defaults_version = 1`,
  so a Preload choice made in RecompLauncher before the first start survives the 0.2.4 migration.
- Relocated storage: rewriting the manifest was rejected (updates replace it, and RecompLauncher
  writes settings before our launcher runs). The launcher keeps a junction
  `%LOCALAPPDATA%\GT5PRecomp\selected-storage` instead, made on storage change and repaired or
  removed on every start; `GT5P_STORAGE_LINK=0` rolls back.
- Measured: `recomplauncher_manifest.py` (a Python port of RecompLauncher's TOML editor) passes
  every choice of all 10 settings against the game's saved layout; `player_package.py` passes;
  `storage_link.py` passes the junction probe and the compiled launcher's `--set-storage`,
  start-up repair, stale-link removal and rollback in a private `GT5P_LAUNCHER_HOME`. Probe and
  launcher compile cleanly at /W4.
- Not measured: RecompLauncher itself (Developer tools "Add a build"), a real install/update, or
  the game reading a RecompLauncher-edited file. No game run, build or release.
## Phase 221 - Race hitches: texture allocation, race prewarm, pipeline lookup (2026-11-05)

Branch `feature/hitch-texture-lru` (from `feature/interp-pipeline-prep` plus the `t3/hitch-attribution`
tooling). Not merged; no tag or release. Method: the Phase-hitch trace overlay (`RSX_HITCH_LOG`,
refreshed for the v0.2.4 main patch), High Speed Ring `hitch_capture.py hsr prepared`, 1080p 16:9 2x MSAA,
`GT5P_NO_SETTINGS=1`, interpreter off, a fresh copy of the user's prepared 0.2.4 cache per run. Focus was
not enforced (`--no-foreground`; Discord repeatedly took focus); the analyzer still marks foreground per batch.
One locked run per row. New readers: `scripts/diag/hitch_list.py` (each long display interval with its
replay, texture, allocation, pipeline-lookup and recording costs) and `scripts/diag/hitch_summary.py`.

### What the long frames were

With every switch off the two largest race frames are the race start (353-407 ms) and the camera change about
7 s later (299-317 ms). In both, about 190 / 180 textures appear for the first time. Each new texture made two
committed resources (the texture and its own upload buffer), about 1 ms together: 150-200 ms of
`CreateCommittedResource` in one frame. The rest: pipeline lookup about 85-100 ms (with about 1,000 draws
waiting for pipelines) and draw recording 55-70 ms. The race prewarm (on for players) prepared about 4,000
learned race pipelines one at a time; the new split shows recipe reads 20.7 s, bytecode reads 12.8 s, driver
creation 27.4 s (mostly the driver-blob file read): 66-69 s in total, so the 30 s loading gate timed out.

### Changes (main patch, default on; rollback switches)

- `RSX_TEX_LRU` (Phase 199 overlay folded in): least recently used eviction when the 1,024 slots are full.
  `=0` restores first-unused eviction.
- `RSX_TEX_POOL`: evicted textures parked for reuse by an identical description (`RSX_TEX_POOL_MB`, 256), and
  one persistently mapped 64 MB staging ring (`RSX_TEX_RING_MB`, `0` off) reset after the per-batch GPU drain.
  `=0` restores both old paths.
- `RSX_RACE_PREWARM_THREADS` (default 4, `=1` rollback): the race index is prepared on helper threads; the
  pso-worker keeps serving demand jobs; shutdown and a new race load stop the helpers between recipes.

The separate `ps3recomp-texture-slot-lru.patch` overlay is removed; the interp, frame-hitch-trace and
pipeline-use-coverage overlays were rebased and all four overlays apply on the new main patch.
`texture_slot_policy_native.py` passes both modes against the new main patch.

### Measurements (race start / +7 s camera change; frames over 100 ms in the grid-to-end window)

| Engine / switches | Runs | Allocations | Race start | +7 s | >100 ms | Prewarm | 60 s FrameTest late / max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all off (overlay builds) | a1, a2, a3 | 2,280-2,509 | 370-407 ms | 299-317 ms | 7-14 | 66-69 s, gate timed out | 0.7-3.2% / 37-133 ms |
| LRU only | b1, b2 | 744-846 | 353-399 | 300-310 | 4-8 | timed out | 1.7-2.2% / 43-144 |
| LRU + pool/ring | c1, c2, d1 (pool only) | about 560 | 267-288 | 270-291 | 3-7 | timed out | 1.1-2.0% / 45-102 |
| LRU + pool/ring + 4 prewarm threads | c4, c5 | about 520 | 296-310 | 257-259 | 5 (excluding shots) | 15.7-16.2 s, gate ready | 0.1-0.9% / 35-37 |
| new main patch defaults, no switches set | e1 | about 520 | 262 | 246 | 7 (excl. shots) | 14.9 s | 0.1% / 26.8 |

With the defaults no draw waits for a pipeline at race start (`skip_fp` 0 against about 1,000), texture
allocation in those two frames is 56-80 ms instead of 150-200 ms, and the staging ring served every upload
(peak 57.6 MB, no fallback). The pool itself rarely hits (86 of about 1,390 allocations): most of the gain is
the ring. Screenshots of the race (intro, on-track, mirror, signage, crowd, HUD) match the baseline;
textures render correctly through the ring.

Limits: one save and route; prepared cache only (cold not measured); one GPU/driver; the remaining race-start
frame is still about 250-300 ms (next item). Startup menu warmup still runs single-threaded (not changed).

### Persistent fast pipeline lookup (`RSX_PSO_FAST_LOOKUP`, default on, `=0` rollback)

After the changes above the race-start frame still spent about 85-100 ms in pipeline lookup with every
pipeline resident: the in-memory pipeline cache is keyed by session state (vertex-shader slot, generation),
so the first draw of each shader/state combination in a process rebuilt its HLSL (`[pso-time]`: 350-385
misses, hlsl 170-200 ms and dxbc 60-80 ms per 5 s around the race start) before it could find the resident
pipeline. The renderer now keeps `warmup-v1/fp-lookup-v1.bin`: a session-independent key (fragment program
content identity, vertex program content hash plus fetch mode, every native and translation field of the
in-memory key) mapped to the native pipeline hash the full path produced. A miss whose mapped pipeline is
resident uses it directly. The file carries an epoch (engine executable size/time plus every `RSX_`/`FP_`/`VP_`
environment value that is not a path); a different epoch starts an empty table. Only pipelines resident under
the current root signature and bytecode can be returned (recipes are re-hashed against the current root
signature when loaded), so a stale or absent mapping falls back to the full path. New entries are written
every 20 s (at least 64 new) from a short-lived thread and at shutdown. `[fast-lookup]` every 5 s.

| Run (same learned cache, defaults) | Race start | +7 s | pipeline lookup in those frames | recording | >100 ms |
| --- | --- | --- | --- | --- | --- |
| f1 (table empty; learns 1,981 entries) | 275 ms | 244 ms | 86 / 76 ms | 62 / 66 ms | 8 (excl. shots) |
| f2 (table loaded: 1,675 hits, 22 absent, 556 not resident) | 113 ms | 106 ms | 1.7 / 2.4 ms | 6.8 / 7.6 ms | 6 |
| f3 (same cache, `RSX_PSO_FAST_LOOKUP=0`) | 350 ms | 286 ms | 122 / 104 ms | 75 / 63 ms | 15 (excl. shots) |

f2's 60 s FrameTest: 59.9 FPS, p99 17.9 ms, max 28.9 ms, 0.0% late. "Not resident" entries are menu
pipelines (the test route runs without startup warmup); with the player default (warmup on) those would hit too.
f3 also showed several 0.6-1.6 s frames at 10-28 s, mostly overlapping screenshots, one with 912 ms in
pipeline lookup; that run has the new path off, and the cause was not investigated. f2 screenshots (grid,
bridge, on-track with mirror) render correctly.

What remains in the race-start frame (113 ms): texture creation for about 190 first-time textures (52 ms),
the rest of texture handling (13 ms) and replay. A first launch (empty table) still pays the old cost once.
The rollback run r1 (`RSX_TEX_LRU=0 RSX_TEX_POOL=0 RSX_RACE_PREWARM_THREADS=1` on the default engine)
reproduced the old behaviour (single-thread prewarm 56.8 s, two allocations per texture, race start 371 ms).

### Placed textures, preparation-built lookup table, route matrix (Phase 221, continued)

- `RSX_TEX_PLACED` (default on, `=0` rollback): textures are placed resources in 64 MB default heaps
  (`RSX_TEX_HEAP_MB`, `RSX_TEX_HEAP_MAX` 32, two made ahead `RSX_TEX_HEAP_PRE`, one more whenever free space
  falls under a heap), first fit with coalescing, 4 KB alignment for small textures when the driver accepts it,
  committed fallback. `scripts/test/texture_heap_alloc_native.py` compiles the real allocator: 179,431 random
  operations, no overlap, alignment kept, free bytes conserved, one range per heap after freeing everything.
  High Speed Ring: 1,305 placed textures cost 48 ms in total (committed: 455 ms), 4 heaps 17 ms.
- Fast lookup v2: the key uses the FNV-1a 64 of the vertex shader's bytecode (the template records' `vs`) and the
  file is `warmup-v1/fp-lookup-v2-<tag>.bin`, where the tag is reproducible offline (engine size/write time,
  `RSX_ULTRAWIDE`, native scaling, `RSX_HIGH_PRECISION`, `RSX_FP_*`/`RSX_VP_*`/`FP_*`/`VP_*`/`RSX_VFETCH_LOOP`).
  `scripts/fast_lookup_table.py` writes the table from a preparation (fragment structural hashes are now kept in
  the report as `fp_code_identity`; the translated pass is rebuilt from its records and the cached vertex
  bytecode); `player_prepare.py` and `hitch_prepare.py` call it (`GT5P_PREPARE_FAST_LOOKUP=0` skips).
  `scripts/test/fast_lookup_table.py`: the Python structural hash matches the runtime C function on 400 catalogue
  programs and edge cases; key/tag/file checks pass. In game the prepared table loads on the first launch
  (12,669 entries, tag matched) and serves 1,677 lookups at High Speed Ring.
- Translated preparations (`ultrawide-native`, `native-scaled`) now also publish menu/race membership mapped
  through the translation pass (`pipeline_warmup_plan.stage_translated`, `GT5P_PREPARE_TRANSLATED_PLAN=0`
  skips); before, a 21:9 preparation had no race list, so the race prewarm loaded nothing.

Route matrix: fresh preparations with the final engine (16:9: 647 s, 12,669 table entries; 21:9 ultrawide:
995 s), one locked run per row, focus not enforced. "Off" = `RSX_TEX_LRU=0 RSX_TEX_POOL=0
RSX_RACE_PREWARM_THREADS=1 RSX_PSO_FAST_LOOKUP=0 RSX_TEX_PLACED=0`. Excess = time above the frame budget in
display intervals over 50 ms from the grid on (dealership: above 33.4 ms), screenshot overlaps excluded.

| Route, settings, cache | Defaults on: excess / >100 ms / worst | Off: excess / >100 ms / worst | Note |
| --- | --- | --- | --- |
| High Speed Ring 16:9 2x prepared | 1,490 ms / 3 / 129 ms | 3,344 ms / 12 / 346 ms | race start 73 ms (was 370-407) |
| Daytona 16:9 2x prepared | 1,814 ms / 9 / 220 ms | 3,199 ms / 11 / 208 ms | worst frames at +90-97 s: pipelines outside the prepared set |
| Dealership 16:9 2x prepared, warmup off | 818 ms / 2 / 128 ms | 4,821 ms / 17 / 175 ms | menu set not resident (test route default) |
| Dealership, startup warmup on (player default) | 1,225 ms / 5 / 480 ms | 1,167 ms / 5 / 230 ms | cars differ per visit; one pair, inconclusive |
| High Speed Ring 21:9 8x prepared (with translated lists) | 4,536 ms / 18 / 842 ms | 4,902 ms / 22 / 995 ms | 8x MSAA pipelines are not prepared at all |
| High Speed Ring 16:9 2x empty cache | 11,238 ms / 47 / 247 ms | 13,760 ms / 47 / 308 ms | first "off" run never left the grid (rejected) |

At 21:9 8x the prewarm (8 s) and lookup work (pipeline lookup 41 ms against 2.2 s off), but the race start
(722 ms) and the +7 s change (842 ms) are dominated by about 2,200 pipelines created on first use: the
starter's multisampled pipelines were observed at 2x/4x, the sample count is part of the native pipeline, so
none of them exist at 8x. Shaders are shared between sample counts since Phase 213, so an MSAA-mapped native
pass in preparation (driver creation only) is the next step for 8x players.
Remaining at 16:9 prepared: first-draw GPU time after race start (26-45 ms frames), about 18 ms of texture
upload at race start, game-thread (outside the renderer) frames of 85-130 ms around +10-15 s, and Daytona's
late pipelines outside the starter.

## Phase 220 - Shader-interpreter pipelines prepared ahead of use (2026-11-05)

Branch `feature/interp-pipeline-prep` from `feature/shader-coverage-scaling` 839eb15 (v0.2.4 plus docs). 0.2.5 work;
not merged, no tag or release. Full write-up, switches and the measurement table: the Phase 220 status section of
[coverage-shader-interpreter.md](coverage-shader-interpreter.md).

- Finding: with independent `RSX_SHADER_INTERP=1 RSX_SHADER_INTERP_VP=1` most interpreter pipelines paired the
  fragment interpreter with the draw's *specialized* vertex shader, so they were program-specific; and the Phase 216
  prewarm used the starter's raw 2x/4x sample counts, which never match at 8x. That explains 274 pipelines in the
  user's cold play against 173 embedded classes.
- Change (overlay only): the 173 starter classes are mapped to the process settings (RSX_MSAA count for every
  multisampled class, 8-bit format without high precision, per-sample variant with SSAA): 318 pipelines at 2/4/8x,
  188 at 1x. A lowest-priority thread creates them at startup when both stages are configured, yielding to queued
  demand pipelines, counted as preload work, persisted as `ipso_*` with an `ipso-set-<identity>` marker. Fragment-only
  interpreter draws of a prepared class use the paired generic pipeline. The helper runs the same creation offline
  as a separate final stage (`interp-pipelines.json`, `--interp-pipelines-only`), never touching the token, prepared
  shaders or selection. Rollbacks: `RSX_SHADER_INTERP_PIPELINE_PREP=0`, `RSX_SHADER_INTERP_PREP_PAIR=0`,
  `RSX_SHADER_INTERP_PREP_YIELD=0`, `GT5P_PREPARE_INTERP_PIPELINES=0`.
- Measured: interpreter pipeline creation during play falls from 346-482 to 15-42 per run, waiting draws from
  4,309-8,187 to 15-42, fragment draws left out for a pipeline to 0. User shape with a prepared cache + stage:
  57.7 FPS, p99 28.9 ms, 1.9% late against 55.3 / 52.3 / 7.0% (one pair). Default 1080p 16:9 2x cold is **worse**
  with paired routing (16.8-18.4% late against 4.2-10.0%): draws that used to be skipped are now interpreted for the
  whole compile (fragment-interpreter draws 52k -> 57-98k), the known interpreter GPU cost. Without pairing the step
  is neutral (4.0% late). Interpreter stays default-off; a per-frame interpreter budget is the proposed next step
  for consistent frame times.
- Offline/helper: 12 derivation unit tests; offline engine cold/warm/MSAA/precision/kill-resume/existing-cache checks;
  helper cancel/resume/stage-only/rollback on a 32-record install with the user's settings shape all pass.

## Phase 219 - 0.2.4 RC: preload on by default, separate indicator, one-time precompile offer (2026-11-05)

The maintainer tested the 0.2.4 release candidate and asked for three changes
(branch `t3/rc024-ux` from `feature/shader-coverage-scaling` 28e8e6d; runtime edits
go in the main patch, which was regenerated from a clean `git archive 4e8f3ca8`
export: only the `rsx_d3d12_backend.c` section changed, the result applies to a clean
tree and the shader-interp, shader-source-dump and frame-hitch-trace overlays still apply).

### 1. Preload known shaders defaults to On

`Gt5pSettings::shader_warmup` is true, so a new settings file writes
`shader_warmup = true` and the settings layer sets `RSX_SHADER_WARMUP=1`. A file that
says `false` keeps false (checked: `scripts/test/debug_export_check.py` now covers
default, explicit false, true, both overrides, an invalid value and `GT5P_NO_SETTINGS`).
Every v0.2.3 settings file written by the game contains an explicit
`shader_warmup = false`, so at the maintainer's request (after the merge) a file without
the new `[meta] defaults_version` (generation 0, i.e. written before 0.2.4) is switched on
once and rewritten at generation 1; a later explicit false is kept. `GT5P_SETTINGS_MIGRATE=0`
skips it and leaves the generation unrecorded. `debug_export_check.py` adds upgrade-off,
upgrade-on and migration-disabled cases (33 cases pass). The
backend's own default (no settings layer, `GT5P_NO_SETTINGS=1`) is unchanged, so
measurement scripts are unaffected. The F1 help text no longer says default off.

### 2. "Compiling shaders" counts draws only; optional "Loading shaders" badge

Cause of the old behaviour: `pso_startup_open` held `g_rsx_shader_busy` for the whole
background warmup and every recipe's driver call (`create_guest_pso_driver`) counted
into the same busy counter and totals as a draw's miss. The worker serves both kinds
of job, so origin is carried by a thread-local, `t_shader_preload`, set around the
driver call in `pso_prepare_recipe` (startup warmup, race prewarm, the optional
directory scan) and around the blocking prewarm scan. `create_guest_pso_driver` and
the synchronous D3DCompile path pick the busy counter from it:

- demand: `g_rsx_shader_busy`, `g_rsx_shader_demand_total`;
- preload: `g_rsx_shader_preload_busy`, `g_rsx_shader_preload_total`;
- `g_rsx_shaders_compiled` / `g_rsx_pipelines_built` keep counting everything
  (diagnostics, F8, `[pipeline-metrics]`).

Each total is written by one increment so the badge thread never subtracts two
counters. `RSX_SHADER_INDICATOR_LEGACY=1` routes preload work to the demand
counters again. `src/gt5p_shaderbusy.cpp` now draws two badges from one thread:
"Compiling shaders" (unchanged look) and a smaller, dimmer "Loading shaders" (196x30,
alpha 170, grey-blue, 0.4 s before it shows), same bottom-right placement and still only
an asynchronous `SetWindowPos` when the position changes. If both would show only
"Compiling shaders" does. Toggle: F1 Game > Shader preload indicator,
`video.preload_indicator`, `GT5P_PRELOAD_INDICATOR=1`; default off. The WARP queue test
`scripts/test/pso_async.py` now also checks that recipes run as preload work (busy on
the preload counter, none on the demand counter) and a draw queued during one does not.

### 3. One-time precompile offer

The launcher, on a configured install, asks the helper `--check-selected`. If a
completed preparation made by this release is not selected, it shows the existing
styled dialog (shared code with the Phase 186 post-setup offer, now parameterised by
kind and a time estimate) before the game starts. Yes runs the existing preparation
window and cancel/resume path; No, close, cancel and failure continue to the game; the
answer is recorded in `prepare-offer-<port_version>.done` (`port_version` comes from
`release.ini`). A fresh install gets the post-setup offer, which records the same
marker, so the two never appear in one launch. `GT5P_PREPARE_OFFER=0` disables both;
`--no-prepared` and `GT5P_PREPARE_VOLUME=0` skip the update offer without recording
anything; an unanswerable check offers nothing and records nothing.

Design note: the first version of `--check-selected` recomputed the exact preparation
token, which needs the templates parsed and validated (profiled: about 10 s frozen, 30 s
in the profiler, mostly `pipeline_template.read` and the enumeration loader), too long
for a launch with no window (it measured 10.9 s before and 9.6 s after a full preparation).
A completed preparation now writes
`prepared-identity.txt` beside `prepared-cache.txt`: a SHA-256 over the engine, decoder,
bundled template and enumeration files and the warmup plan, not the player's settings.
The check compares it, the pointer's shape and the selected generation's
`phase == complete`. A preparation made by an earlier build has no such file, so it
counts as not prepared (one extra offer for early RC testers; none for a 0.2.4
preparation).

### Measured preparation time (the number behind the window text)

One full fresh preparation through the frozen helper on the development machine (i5-12400F,
6 cores / 12 logical processors, so four compiler workers; original GT.VOL/ELF read in
place; empty storage; 720p/16:9 default translation; serialised by the test lock, and the
maintainer's own RC preparation started after it finished): **578.9 s**, exit 0, 12,669
records, 983.7 MiB of preparation data. Stages from `prepare-status.txt` sampled every
0.5 s (`scripts/test/rc024_prepare_time.py`, evidence under `scratch/rc024/prep`):

| Stage | Seconds |
| --- | --- |
| Start-up, archive check and asset reads (both phases) | 49 |
| Vertex shaders (627) | 23 |
| Fragment shaders (12,669 records) | 124 |
| Native pipelines (input 15.5, create 83, lookup 24, verify 4) | 127 |
| Shader packs | 3 |
| Enumeration (24,522 jobs) | 253 |

Window text: "about 10 to 20 minutes" for eight or more logical processors (the measured
9.7 minutes plus headroom for slower CPUs), "about 20 to 40 minutes" below that (two
workers; Phase 209 measured 632.7 s versus 457.0 s for two versus four workers on the
5,669-record starter, about 1.4x, and slower CPUs add to that). Only the four-worker
figure was measured in this phase; the two-worker window is scaled, not measured. One run
on one machine.

### Evidence

All through the machine-wide test lock, private engine (`scripts/test/rc024_build.py`: the
changed runtime and `src/` objects recompiled with the v0.2.3 reference build's commands and
relinked over its objects) and a frozen helper from `build_preparer.py`:

- **Runtime patch:** main patch applies to a clean 4e8f3ca8 export; shader-interp,
  shader-source-dump and frame-hitch-trace overlays still apply on top. `scripts/test/pso_async.py`
  (WARP, real queue) passes, including the new preload/demand attribution assertions.
- **Settings:** `debug_export_check.py` (settings loader, 29 cases) passes: preload default
  true, explicit false kept, both environment overrides, invalid value, `GT5P_NO_SETTINGS`, and
  the new `preload_indicator` (default false). A new settings file written by the real engine
  contains `shader_warmup = true` and `preload_indicator = false`; the F1 Shaders page shows
  Preload known shaders On and the Game page shows the new row, and toggling it from the page
  wrote `preload_indicator = true` (`rc024_settings_pages.ps1`, shots inspected).
- **Launcher:** `launcher_first_run_native.py` now covers 20 scenarios and passes: fresh-install
  offer (Prepare/skip/close/cancel/helper unavailable/disabled/cancelled setup), update offer
  (Prepare/skip/close/cancel/preparation failure), no offer when already prepared, on helper
  error, on hash mismatch, with `GT5P_PREPARE_OFFER=0`, `--no-prepared` or
  `GT5P_PREPARE_VOLUME=0`, and after an earlier answer. A fresh install never asks the helper,
  and a second launch never offers again. `launcher_native.py` and `launcher_pipeline_tools.py`
  pass unchanged. One run of the first-run test failed in its first scenario because the file
  picker's automated input was not accepted (the launcher exited as cancelled); the rerun passed.
- **End to end** (`rc024_launcher_e2e.py`: real launcher, frozen helper, private engine, original
  disc read in place, private data folder): the offer appeared 1.0 s after launch, Prepare now ran
  the real preparation, the game started 615.9 s after launch and was stopped; `prepare-offer-0.2.4.done`,
  `prepared-cache.txt` and `prepared-identity.txt` were written. A second launch showed no window
  and started the game in 0.5 s. With the marker deleted, the helper check answered "prepared",
  no offer appeared, and the marker was rewritten (game start 1.0 s).
- **In game** (`rc024_badge_probe.py`, Acura dealership at 720p, private save copy and private
  cache, badge windows polled every 100 ms and saved with PrintWindow):

  | Run | Cache | Switches | Result |
  | --- | --- | --- | --- |
  | A | empty | preload on, indicator on | "Compiling shaders" shown five times for demand compiles (up to 193 shaders and pipelines); no recipes to preload, no loading badge |
  | B/E/F | A's | preload on, indicator on | preload of 317-322 recipes took 0.8-1.0 s; "Loading shaders" 2.8-3.4 s (116-117 pipelines); "Compiling shaders" not lit by it, only by later demand work |
  | C | A's | preload on, indicator off (default) | same preload, no badge at all during it |
  | D | A's | `RSX_SHADER_INDICATOR_LEGACY=1` | "Compiling shaders" lit 2.7-3.4 s during the preload (115 pipelines): the old behaviour |

  The first loading badge had no visible spinner (a 3x3 GDI ellipse draws nothing); it now uses
  the same 5 px dots on a smaller ring, checked with an offline render and a game shot.
- **Other tests:** `player_package.py`, `release_trigger.py`, `preparation_reuse.py`,
  `cache_hash.py`, `pipeline_template_inputs.py` and `pipeline_warmup_plan.py` pass with the new patch.

### Not verified

Race loading preparation is covered by the WARP queue test but was not driven in a real race in
this phase (its code path is the same recipe function). Only 720p was checked for the badges. The
two-worker time window is scaled, not measured. No CI or release build was run; main, tags and
releases are unchanged. `scripts/test/settings_test.ps1` was edited for the new default but needs
`build\gt5p.exe`, so it was not run; `rc024_settings_pages.ps1` covers the same toggles against a
private engine. Existing v0.2.3 settings files are switched on once (see item 1).
Switches: `RSX_SHADER_WARMUP=0`, `RSX_SHADER_INDICATOR_LEGACY=1`, `GT5P_PRELOAD_INDICATOR`,
`GT5P_PREPARE_OFFER=0`.

## Phase 218 - Analog L2/R2 pressure past the digital threshold (2026-11-05)

The user assigned accelerate/brake to R2/L2 in the game's own Options > Change
Button Assignments. Partial throttle and brake work only for the first part of
the trigger travel; after that both read 100%. Cause, from the runtime source:
an analog trigger also sets its L2/R2 digital bit once the SDL axis exceeds
3000 of 32767 (about 9%; XInput uses PAD_TRIGGER_THRESHOLD). The pressure
fix-up added for injected input then raised every pressure below 255 to 255
whenever the digital bit was set, discarding the real analog value.

The fix-up now fills only a pressure the host left at zero, which is the
injected-input case it was written for (PAD_HOLD/PAD_SCRIPT, keyboard; the
keyboard already writes 255 for L2/R2). Real controller values pass through
unchanged, so L2/R2 report 0-255 across their whole travel. Face buttons are
unaffected: the host only reports 0 or 255 for them. `PAD_PRESS_FORCE_FULL=1`
restores the old rule. The main runtime patch applies to a clean 4e8f3ca8 tree,
the overlays apply on it and cellPad.c compiles. Not yet tested in game; the
user will test the trigger response. No response curve or dead-zone setting is
added; add one only if the linear 0-255 range proves wrong in play.

## Phase 217 - Dealership logo loading stall: Windows PPU join lifetime (2026-11-05)

Numbered 208 on its investigation branch; renumbered 217 when merged into
`feature/shader-coverage-scaling`, which already has a Phase 208. The fix is
default-on; `PS3_PPU_JOIN_WAIT_HOST=0` restores the previous Windows join
(slot freed at the guest exit event). The rollback switch was added at merge
and is not separately exercised in game; the rendered repeated-dealer check is
left to the user.

Investigation branch `investigate/dealership-logo-freeze` starts at main
37a696f in `../Tourline-Prologue-dealer-freeze`. The user supplied
`gt5p-debug-20261105-085802-060-37360-1.zip` after Mazda stopped on its logo
on approximately the fifth entry; audio continued. The private export and
reproduction evidence stay under `scratch/dealer-freeze/`.

### The supplied export identifies thread creation starvation

All 64 guest thread-table slots are occupied: 34 RUNNING and 30 FINISHED.
Thread 24 is sleeping for 2,000 microseconds at `0x00B442A0`, returning to
`0x00B44624`. Original-disc disassembly identifies that as the retry branch
following failed thread creation at `0x00B44648`, not an SPU ring-space wait.
The runtime returns CELL_EAGAIN when no FREE table slot exists. The proposed
worker has entry `0x0132A3E0`, argument `0x400CE8C0`, priority 256 and flags 1.

The renderer still presents: the last present is 28 ms old; the last four
completed frames each contain only two logo draws. The shader worker is idle,
all 691 queued native pipelines have completed, and device_lost is zero. The
FIFO has get=put=`00011080`; render workloads 0/1 are idle with no remaining
jobs. These observations differ from the older ring/profiling-corruption stalls.
The two remaining temporary workers' condition waits alone do not establish a
lost notification. The busy guest `Main Thread` is in its timer-service loop;
the same loop is busy in the reproduction before exhaustion, so its CPU use
alone does not identify the cause.

### Measured host join/epilogue race and correction

`sys_ppu_thread_exit` publishes FINISHED and signals `finish_event` before
longjmp unwinds to `ppu_host_thread_proc`. Windows `sys_ppu_thread_join`
previously waited only for that event, closed the host handle and marked the
slot FREE. The old procedure subsequently takes the table lock and writes
FINISHED again. This can resurrect an already joined slot; early slot reuse
can also let the old epilogue touch a new thread's descriptor. The latter is a
structural risk, not a separately observed failure in the user's export.

The compatibility overlay now waits for the host thread handle before join
cleanup. The wait is outside the table lock, allowing the old epilogue to
finish. The 64-slot limit, guest scheduling, shader/draw behavior and POSIX
join path are unchanged. The shared runtime checkouts are not modified.

`scripts/test/ppu_join_lifetime.py` extracts the actual pinned runtime exit,
host procedure and join functions, with a host-profiler-exit stub holding the
old procedure before its final table update. The unmodified source reproduces
premature FREE followed by resurrected FINISHED on the first case. The fixed
source passes 128 delayed exits/joins, verifying slot ownership until host
completion and big-endian guest exit status. No game code/data is required.

The original released executable also exhausts its table during a private
315-second headless repeated-dealership route: its final dump has 32 RUNNING
and 32 FINISHED slots and the same 2-ms creation retry. This provides an
in-game counterpart to the deterministic native race. The fixed 315-second
headless route completes 87 successful thread creations across 63 distinct
created IDs, ending with 34 RUNNING slots and no retained FINISHED slots.
The loader is no longer in the creation-retry loop. This verifies recycling
beyond the baseline exhaustion point, without raising the table capacity.

### Build, reproduction and limits

The candidate recompiles only `sys_ppu_thread.c` against a private copy of
pinned v0.18.0 plus this branch's compatibility overlay, replaces that member
in a private runtime library and relinks the retained release object files.
The cache's baseline executable is byte-identical to the public v0.2.3 engine
(SHA256 `960f8ec2534b6c03f7305bcbc197ce58469411f4f59754d00fb7dd078deba887`),
and the baseline thread source matches the release runtime cache after newline
normalization. Candidate SHA256:
`576d4c94f2ddc61b46164ab2f24fcafe7379c9c30dba6f48252065c99c82288f`.
This is a private incremental candidate, not a fresh full release build.

Live tests hold `Local\Tourline-Prologue-Isolated-Validation`, run sequentially,
read the existing disc assets, and use copied saves and private cache/storage.
The automated route schedules ten entries into the initially selected dealer,
with right/left input and Circle between entries. It does not claim Mazda was
selected, and scheduled button presses alone are not ten visually accepted
visits. PS3_HEADLESS disables the D3D12 backend, so the blank window captures
are not visual acceptance. A rendered Mazda/repeated-dealer acceptance run
remains required before publication; the user's exact session was not replayed.
No main/tag/release/CI change or general loading-reliability claim is made.

Reproduce the native checks with the repository Python environment, inside
`scripts/test/isolated_validation.ps1`, passing:

- `scripts/test/ppu_join_lifetime.py --runtime <private-patched-runtime>`;
- add `--source <unmodified-sys_ppu_thread.c> --expect-legacy` to verify the
  original race. The source override still uses the selected runtime's headers.

The full overlay reverse-application check passes against the isolated runtime.
Build identities, logs, fixture output and the candidate remain private under
`scratch/dealer-freeze/` and `scratch/ppu-join-*/`.

## Phase 216 - Shader interpreter fallback re-verified; not yet a default (2026-11-05)

Branch `t3/interpreter-default` (development, `[skip ci]`; main, tags and releases untouched). The RSX shader
interpreter fallback (`RSX_SHADER_INTERP=1`, `RSX_SHADER_INTERP_VP=1`: interpret only draws whose specialized shader
or driver pipeline is pending) stays **default-off**. Details, tables and switches are in
[coverage-shader-interpreter.md](coverage-shader-interpreter.md#status-phase-216-2026-11-05-re-verified-on-a-corrected-private-build).

- **Correction to earlier readings.** Earlier private interpreter engines were linked with the v0.2.3 decoder objects
  (no Phase 215 text); the builder now compiles the patched decoders. Every in-game number was re-measured on the
  corrected engine; the earlier cold/warm tables are replaced.
- **Closed, verified in game:** the ACURA wordmark (interpreted red 39-40 against specialized 39 in the alternating
  capture; the cause was the missing "redirected stencil-mask pass forces colour to 1" behaviour); depth-copy and
  stacked-mip draws (gap counter 0, was 780 / 3,141); the replay vertex omission rise (those were the same draws, and
  with async pipelines the counter again counts draws waiting on a queued interpreter pipeline); interpreter pipelines
  persisted as `ipso_*.bin` and created on a worker (0 ms on the replay thread, 0 rejected blobs, 93-142 disk hits in
  warm runs).
- **Not done:** creating observed interpreter classes at startup (fragment-only `=1` pipelines contain the specialized
  vertex shader, unknown until a draw names it); cheaper interpreter shader. Two experiments (decode gating, 16-register
  files) left the force-mode GPU cost at about 79 ms and were reverted.
- **Measured (single locked runs, one GPU, one save; Daytona cells repeated):** draws left out fall from 44-216k to
  1.4-6k per race run; p99 on cold caches is equal within run-to-run spread; High Speed Ring warm equal; Daytona warm
  slightly worse (p99 27-36 against 24-25 ms; one unexplained 723 ms frame). Cold dealership shows complete materials
  during compilation but GPU-bound windows up to 260 ms.
- **Recommendation:** do not make it the default yet; see the document's list of what a default change would touch.
- **Tooling.** `interp_game_probe.py` gained `--menu-delay` and `--settle`, and now deletes its ~2 GB private game-root
  copy after each run (`RSX_INTERP_KEEP_ROOT=1` keeps it): a 60-run matrix filled the volume. `interp_matrix_summary.py`
  tabulates probe runs. Foreground loss by other windows rejects frame tests (the driver retries them).

## Phase 215 - De-specialized shader text: cheaper to compile, same shaders (2026-11-04)

Preparation cost is dominated by the D3D compiler, so the generated HLSL was made cheaper without changing what
it computes. Four generator changes are now **default**, each with a renderer switch (`0` restores the previous text)
and a helper-side rollback that must also be set for the game run (the text is the cache key). Full details,
tables and the equivalence method are in
[coverage-enumeration](coverage-enumeration.md#de-specialized-shader-text-phase-215-now-default).

| Change | Renderer switch | Helper rollback |
| --- | --- | --- |
| Looped GPU vertex fetch (one loop over the attribute mask) | `RSX_VFETCH_LOOP` (2; 1 or 0 for older text) | `GT5P_PREPARE_VFETCH_LOOP` |
| Fragment register files sized to the highest literal index | `RSX_FP_REG_SIZE=0` | `GT5P_PREPARE_FP_REG_SIZE=0` |
| sRGB helper functions only when called | `RSX_FP_GAMMA_LAZY=0` | `GT5P_PREPARE_FP_GAMMA_LAZY=0` |
| No output encode when a stencil-mask pass forces its colour to 1.0 | `RSX_FP_MASK_ENCODE=0` | `GT5P_PREPARE_FP_MASK_ENCODE=0` |

The changes live in the main runtime patch (`patches/ps3recomp-4e8f3ca8-local.patch`, only the three decoder/backend
sections changed; the standalone vertex-fetch overlay patch was folded in and removed). The format-3 starter, plan,
maps and warmup plan are byte-identical to Phase 214: the starter holds inputs only, so no re-key was needed. Engine
and helper hashes change, so existing generations are not reused for the new text; rollbacks get their own
generation.

**Equivalence (no output claim rests on a sample alone).**
- Vertex: all 1,120 enumerated vertex programs bit-identical on the RTX 4060 (128,450,560 values, 0 differences).
- Fragment registers: rollback text equals the previous decoder for 7,929 of 7,929 catalogue programs; the default
  compiles to byte-identical bytecode for 94.6-95.0% of 4,141 sampled programs and to an identical instruction
  stream for every other one (the declared `dcl_indexableTemp` size is the only difference).
- Enumeration, 22,194 jobs: lazy-helper and mask-encode changes leave every DXBC unchanged; the full frozen helper run
  with all four rollbacks set equals the format-2 reference exactly.

**Measured.** Enumeration stage 504.3 -> 262.0 s (seeded). Frozen full 12,669-record preparation, consecutive runs:
249.9 -> 158.6 s until native input is published, then 204.9 -> 176.9 s to finish (stage-times pairs: vertex
104-107 -> 19-20 s, fragment ~150 -> 126-141 s). Cancellation at native input and resume pass (retained shaders
4,230-4,231, 627 vertex programs and all fragment jobs reused, 12,669/12,669/12,669 native, the previous selection
preserved). In game (dealership, High Speed Ring, Daytona; 720p 1x and 1080p 2x MSAA) GPU time and frame statistics are
the same within noise, with no PSO failure or device removal, and the window shots look the same. The looped fetch
has no measurable GPU cost, so `RSX_VFETCH_LOOP=1` was not needed.

**Axes.** Of 19,094 distinct fragment sources, removing the sampler-lane axis could save at most 2,482 (13%), the
gamma bits 1,810 (9.5%), both 4,360 (22.8%) if they became run-time values; that needs renderer uniform
plumbing, is not provably identical and was not implemented (design in the coverage document). A different finding was
implemented: 1,293 sources compile to the same bytecode as a sibling, 1,001 of them stencil-mask passes whose colour is
forced to a constant after the output encode was added (the mask-encode change; 235 sources merge, 1.2%, within timing
noise). 817 + 94 sibling pairs remain uninvestigated.

**Limits.** One GPU, one save, a few routes, consecutive-run timings with run-to-run variation (an earlier defaults
run on a busier machine was 619 s end to end, so do not compare numbers across sessions). Only the combination of the
four helper rollbacks was run through the frozen helper; each switch alone was not (their plumbing is unit-tested and
the combined rollback is exact). The 780 enumeration jobs whose bytecode differs between the first two changes and
the full rollback were not disassembled individually. `reject` through the frozen helper and
whole-game/other-GPU/stutter claims are not made. Published v0.2.3 is unchanged.

## Phase 214 - Renderer-independent pipeline input templates (2026-11-04)

Format 3 replaces shipped renderer-output expectations with canonical inputs.
The starter remains **12,669 records / 3,446 original program identities**;
all program identities/sizes, numeric translation/native state, GPU-fetch modes
and ATTR layouts are preserved. Shader/source/native identifiers are removed,
and compiled shader-length descriptor words are zero until preparation. Each
64-character `key` is a domain-separated SHA-256 of the complete canonical
input record. ELF, key/root-signature ABI, translation policy and default settings
stay pinned. The renderer source fingerprint is no longer a template gate.
There is no renderer/runtime behavior or patch change in this phase.

The converter `scripts/pipeline_template_inputs.py` reads format 2, drops outputs,
computes input identities and remaps observed phase membership. Format-2 envelopes
keep their original checksum validation before conversion. Output-only differences
collapse to one input; review quarantines claimed identity/content conflicts.
The 99-shard starter/index and plan are migrated together. All four program/location
maps remain byte-identical. Enumeration only re-pins its input-template digest;
program/profile/job membership is unchanged. Current input bundle index SHA-256:
`aa2e1ea6e686b9133386446e057bcb895de0414aa4d64de52df578cc02030fbc`.

Preparation uses the existing bounded derive workers, actual installed engine/decoder
and native request ABI. The host derives a proposed key from locally produced
shaders and the pinned ABI; the engine independently computes its actual key,
creates the pipeline and persists the result. Fresh native processes then repeat
every unique request through the runtime's normal driver-blob lookup. Every request
must use its persisted blob, and all final recipe/shader/driver inventory checks
remain mandatory. Outputs exist only in local reports/checkpoints. Maintainer-only
`--reference-report` / `--reference-template` optionally compare every local source,
bytecode and native identifier with a private reference before publication.

Warmup plan version 2 stores input identities. Successful local results supply
native membership and shader-pack dependencies, including standalone pack generation.
Observed membership remains **1,466 menu / 2,113 race / 3,546 distinct**; no new
phase ownership is inferred. The plan byte ceiling grows to 1 MiB for SHA-256
identities; its target ceiling remains 4,096. Player generations pin actual engine/
decoder hashes and saved settings, independently of the shipped source fingerprint.
Cancellation/failure preserves the previous selection and cache. Format-2 generations
can supply bounded driver hints after outputs are derived; their shaders are compiled
again because they lack input-keyed derivation manifests. Engine-matched format-3
generations can also reuse checked shader derivations. No learned recipes, packs or
membership are imported. Existing worker, memory, native chunk and ownership limits stay.

**Full frozen proof.** A private engine recompiles only the current backend and
links read-only reference objects; engine SHA-256 is
`8673bc002af3aec7bc8481b643cb84a76d4599a518b9ecde2696ded3b029e0e6`.
`scripts/release/build_preparer.py` builds the frozen helper. Direct original-volume
preparation starts in fresh private storage with a clean PATH and no reuse. At
native input, controlled cancellation exits 2 in 354.82 s, preserving the old
selection/cache and retaining 4,231 shader files. Resume reuses all 627 vertex
variants and 12,669 fragment jobs and completes in 563.32 s wall / 520.45 s internal.
All **12,669** source/bytecode/native outputs exactly match the current format-2
reference from `ab77487`. First native requests/created/driver calls/cached calls:
**12,669 / 12,669 / 12,669 / 0**. Fresh-process runtime lookup:
**12,669 / 12,669 / 12,669 / 12,669**. Inventory has 12,669 recipes, 12,669 valid
driver blobs and zero rejected entries. Both packs publish (555 menu / 1,092 race
source entries), and native phase indices have the unchanged observed membership.
The separate frozen fresh 32-record smoke proof passes the same reference and
runtime lookup checks. Shader enumeration is explicitly disabled in these native
proofs to isolate starter preparation; its plan-load/pin/checkpoint tests run separately.
These are application-cache-fresh/cancel-resume proofs with OS/driver caches preserved,
not driver-cold timings, speed claims or live-draw/stutter measurements.

**Compatibility and controls.** New exports use format 3; format 2 converts on load,
including contributions in the wild and native-key plans with their original bundle.
The directory remains `gt5p-disc-v2` for package-path compatibility. Old frozen helpers
need updating. `GT5P_PREPARE_INPUT_TEMPLATE=0` requires a separate format-2 template
and restores its source/output gates; it safely rejects format 3. Format 3 uses
bounded fragment batches with existing `GT5P_PREPARE_FRAGMENT_CHUNK=1..4096`
(default 256); legacy fragment rollback requires the format-2 path. Published
v0.2.3, main, tags, releases, normal draw/async policy and runtime patches stay unchanged.

See [format design, migration and limits](template-input-format.md),
[contribution contract](pipeline-contributions.md#file-contract) and
[preparation workflow](shader-precompile.md). Focused template/contribution/coverage,
plan/pack/reuse/enumeration/package/collection/re-key/runtime-coverage regressions
pass sequentially under `C:\tmp\gt5p-testlock\run_locked.py`. Native evidence is
`scratch/if3/{smoke32,full}/validation.json` (private; removed after this phase,
small summaries kept).

**Remaining acceptance (all frozen helper, direct original-volume, enumeration
disabled, one locked run each).**

- *Format-2 generation -> format-3 incremental reuse (32 records).* A real format-2
  seed (`GT5P_PREPARE_INPUT_TEMPLATE=0`) feeds a format-3 run: 32 driver blobs copied
  (963,688 bytes), zero shaders copied (format-2 generations lack input-keyed
  derivation manifests, so shaders compile again), none rejected. All 32 outputs
  exactly match the reference; native 32/32/32/32, runtime lookup 32/32/32/32;
  the old selection and cache are unchanged. 19.9 s.
- *Format-3 growth (33 records from the 32-record cache).* Input-keyed derivation
  manifest reuse plus one new record: 33/33 exact, native 33/33/33 with 32 driver
  calls reusing blobs, one blob missing (the new record) and created; runtime lookup
  33/33/33/33; old cache unchanged. 12.4 s.
- *Renderer-source comment probe.* A harmless source change (private engine built
  with one extra comment line, plus the helper's patch-resource) gives the **same
  template digest** (`378f0016...`) and a **different engine hash**
  (`8673bc00...` -> `a8011517...`); no template, plan or gate change is needed, and
  32/32 exact outputs, native 32/32/32 and runtime lookup pass. Under format 2 this
  change invalidated the source-contract gate.
- *Maintainer strict reference comparison* (`--reference-template`, native
  regression driver, 32-record fixture): 32/32 prepared against the reference with
  native 32/32/32/32 and lookup 32/32/32/32, zero vertex/fragment workers (all
  derivations reused), the renderer source fingerprint never read, an incorrect
  reference rejected without a report, a corrupted derived shader refused at resume,
  and the source cache/selection preserved. *Native pack reader* against the full
  12,669-record generation: PASS disabled reader and production lookups (menu 555 /
  race 1,092 entries), bytecode identities, miss fallback and blob ownership.

**Defect found and fixed.** Growth from a cache with usable input-keyed hints failed
with `'total'`: `pipeline_translation.py` reported `reusing-cache` progress with
`completed` but no `total`, and the player's status formatter indexed `counts['total']`.
Reuse progress now carries a total, and the formatter tolerates a missing total.
A first reuse attempt also failed once with Windows error 1450 (insufficient system
resources) creating vertex workers while the machine was short of memory (about
1.7 GiB physical free at the time); the identical run alone through the lock passed
(twice, including after the fix), so it is attributed to the environment. Job
objects and handles are released per pool; no leak was observed, but none was
measured directly.

**Rebase onto `feature/shader-coverage-scaling` (69dcaa0).** Clean, no textual
conflicts (the enumeration speed work touches `preparation_enumeration.py`,
`preparation_workers.py`, `shader_vertex_batch.py` and adds opt-in overlay patches).
The official `scripts/release/build_enumeration.py` re-pin against the format-3
starter reproduces the shipped `plan.json` byte for byte except one trailing
newline (kept as committed); fragment jobs 34,355 / profiles 1,540 are unchanged.
After the rebase the focused regressions (template, inputs, contribution, coverage,
warmup plan, shader pack, reuse, enumeration, vertex batch, package, collection x3,
re-key, runtime coverage) pass, and the helper was rebuilt from the rebased tree for
a repeat frozen 32-record smoke (exact 32/32, native/lookup 32/32, cancel at native
input in 14.4 s with 38 shaders retained, resume reuses 16 vertex programs and 32
fragment jobs, both packs written). The 12,669-record fresh run predates the rebase
and was not repeated (hypothesis: unaffected, since the rebase only adds the
enumeration/worker-count speed work and enumeration is disabled in that run; the
new automatic worker default can change worker counts, not outputs).
Two test-harness items surfaced: the 32-record cancel trigger raced the status
debounce once native input became faster (the subset run now cancels on any
`Native input` status and polls at 5 ms; the full run keeps the strict trigger), and
`collection_search_map` lacked the enumeration asset the packager now requires
(fixture fixed).

No whole-game/settings, GT5, other-GPU or stutter claim follows. Push only the
feature branch with `[skip ci]`.

## Phase 213 - Fragment sample sharing by default, with a re-keyed starter (2026-11-04)

`RSX_FP_SAMPLE_SHARE` (Phase 212's coverage experiment, previously opt-in `=1`)
is now **on unless it is exactly `0`**. A one-sample and a multisample profile
of one fragment program compile to one pixel shader; `SampleDesc.Count` and
everything else about the pipeline is unchanged. The separate overlay patch is
folded into `patches/ps3recomp-4e8f3ca8-local.patch`, so CI/setup apply one
patch. See [coverage-sample-share](coverage-sample-share.md) for the design.

**Patch.** The fold is a surgical 18-line edit to the existing patch (hunk
counts/offsets adjusted), not a regenerated diff: an earlier regeneration with
`git diff` rewrote ~19,000 lines and, through a blanket string replacement, had
also flipped the `RSX_CLEAR_TRACE` and `RSX_TEX_DIMDBG` diagnostics to
default-on; it was discarded. Applying the old and new patches to fresh trees
at `4e8f3ca8` differs only in `libs/video/rsx_d3d12_backend.c`, by the two
intended hunks (20 diff lines, no CR changes). `ps3recomp-shader-interp.patch`
still applies. A private engine (the v0.2.3 reference objects with only the
patched backend recompiled and relinked, SHA-256 `26ce6760...`) is built from
it. `fp_sample_share_native.py` proves the switch (unset/`1`/`2`/empty/`00`
share, `0` does not; units 17/18 are not cube units).

**Re-key.** The renderer contract moves `e266e6af...` -> `2250280f...`. One
fresh full preparation with the new engine (624.9 s) proposes new fragment
identifiers and native keys; `scripts/pipeline_template_rekey.py` accepts them
only for one-sample records and only if each native `actual` key equals the
proposal. Result: 6,172 of 12,669 records change (6,151 new keys; 21 changed
fragment text only, same DXBC and key); 6,497 multisample records, all vertex
fields, the four maps and (remapped old to new key) warmup membership are
unchanged. Distinct fragment sources 6,990 -> 3,604, pixel-shader bytecodes
6,965 -> 3,592. The plan (1,466 menu / 2,113 race, 3,546 distinct) is re-pinned
to template digest `d603d90d...`. `pipeline_rekey_contract.py --baseline cf08d79`
and the synthetic `pipeline_template_rekey.py` (scope, MSAA/vertex preservation,
creation/actual, collision, plan pin) pass.

**Strict acceptance of the re-keyed starter** (private engine, cache/outputs
removed afterwards; original game files read-only):

| Check | Result |
| --- | --- |
| Frozen helper, direct from the game volume, clean PATH, fresh storage; cancel once native input starts | exit 2, old selection and old cache snapshot unchanged, 4,231 shader files retained, state `interrupted` (320.5 s) |
| Resume the same generation | all 12,669 prepared; 12,669 recipes / valid driver blobs, 0 rejected; both shader packs written (555 menu / 1,092 race shaders); warmup indices written; 382.4 s wall (371.6 s internal); pointer switched only after success |
| Same starter, old `=0` engine behaviour (old starter, non-frozen path) | 12,669 prepared, 0 rejected (723.8 s): the rollback reproduces every old record |
| Incremental run from that pre-re-key generation (frozen helper) | 12,669 prepared in 379.4 s; reuse copied 4,013 shaders and 3,488 driver blobs (268 MB), 0 rejected, but the existing 60 s / byte budget skipped 3,500 blobs, so it is no faster than the fresh resume |
| `ultrawide-native` and `native-scaled` additional translations, first 64 records (all one-sample) | default 64/64 and extra 64/64 prepared (39.1 s / 28.9 s) |

**In game** (private engine, fresh copies of the prepared cache per run,
`PS3_VERBOSE=0`, `GT5P_PRESENT_PROF=1`, PrintWindow shots inspected). A =
default sharing + re-keyed cache. B = `RSX_FP_SAMPLE_SHARE=0` + the pre-re-key
cache (previous behaviour). C = `=0` + the re-keyed cache (rollback). GPU is the
mean of `[present-prof]` 5-second averages (first sample dropped); "new DXBC" is
files the run added to its cache copy. No PSO failure or device-removed line in
any log.

| Scene | A GPU ms / new DXBC | B | C |
| --- | ---: | ---: | ---: |
| Dealership 720p, 1x MSAA | 4.30 / 10 | 4.16 / 10 | 4.47 / 250 |
| Dealership 1080p, 2x MSAA | 6.22 / 8 | 6.05 / 8 | 6.38 / 248 |
| HSR 720p, 1x (60 s frame test) | 4.83 / 12 | 5.09 / 12 | 5.19 / 1,721 |
| HSR 1080p, 2x | 5.36 / 8 | 6.00 / 8 | not run |

HSR frame test (FPS / median / p99 / late share): 720p A 58.2 / 16.7 / 24.1 ms /
2.8%; B 59.1 / 16.7 / 20.5 / 1.6%; C 55.2 / 16.7 / 59.1 / 6.7%. 1080p/2x A 59.6 /
16.7 / 20.2 / 1.1%; B 58.9 / 16.7 / 18.8 / 0.8%. All dealership runs: 30 fps,
2,150-2,225 draws. Dealer and race frames show the same showroom (cars vary per
visit) and the same track, HUD, crowd, shadows and mirror. These are single runs
on one GPU/save/route: the A/B GPU and frame-time differences are inside
run-to-run variation, shots are not phase-locked pixel-identical pairs (HSR A/B
frames differ by mean absolute channel sum 34-36 at 1080p, with the car at a
slightly different place), and the large C counts are the effect to note:
with the re-keyed cache `=0` has no prepared one-sample entries, so it compiles
them on demand and the 720p race shows more late frames (p99 59 ms). Cold
driver-cache, other tracks/cars/settings and ultrawide in-game were not run.

**Not changed.** Published v0.2.3, main, tags and releases; vertex state and
maps; observed membership. Old ordinary player caches are left alone; recipes
learned before this phase may still replay old-key one-sample shaders until the
14-day pruning removes them. No whole-game, all-settings or stutter claim.

Evidence/tools: `scripts/pipeline_template_rekey.py`,
`scripts/test/{pipeline_template_rekey,pipeline_rekey_contract,player_rekey_frozen_native,fp_sample_share_native,fp_sample_share_build,fp_sample_share_batch}.py`.
Every run used `C:\tmp\gt5p-testlock\run_locked.py` one at a time; private
builds, caches and game copies are removed, and timing metadata stays in this
document.

## Phase 212 - Verified content-sweep starter expansion (2026-11-04)

The 1080p/2x MSAA/default-16:9 content sweep contributes **7,000 verified
records**. The development starter is **12,669 records / 3,446 original programs
(622 VP, 2,824 FP)**; all previous 5,669 records are preserved exactly. The
7,790-record delta reviews to 7,790 additions and zero further conflicts. Of
these, 790 remain `unresolved-program`, depending on 185 fragment identities
absent from the supplied catalogue and existing program-location maps. There
are zero incompatible shader, unsupported-state or native-key rejections in
the completed candidate reports. The sweep's earlier 47 conflicting keys remain
quarantined and do not appear in the delta or new additions. No pending record
is promoted because its metadata was observed or its program hash looked valid.
Original `delta-candidates.json` SHA-256:
`0814f1589f6f0c1881ed3dd0e100a2ba666fbd7c805b9e1c597d623b417702fe`.

**Explicit contract reissue.** Despite the v0.2.3 reference engine used for the
sweep, its exports actually pin Phase 210's renderer source hash
`a0d3444f77ffe9d1cb0fd2301e2e76607c1d28993166f6c740975f981e802c43`,
not the published v0.2.3 pin `227c1fcd...`. This discrepancy is recorded rather
than silently treating the inputs as already current. The candidate ELF,
settings, key/root-signature ABI and translation policy match the current
starter. Only `renderer_sha256` is reissued to Phase 211's `e266e6af...` in a
private copy; every record stays identical. Reapplying the current main patch
to its pinned upstream sources and comparing with the reference runtime finds
73 patched files unchanged, including both decompilers and reconstruction
headers. The only differences are backend profiling/offline input/result
transport and its new `rsx_offline_batch.h`; rendering keys, translation calls,
compiler flags and descriptor construction are unaffected. Fresh exact shader
and native proofs below independently gate acceptance. No runtime patch or
default is changed by this metadata update; sample sharing and the other
coverage experiments stay off.

**Original assets and player lookup.** Fragment catalogue filenames hash raw
payloads including constants; matching instead uses `fp_identity` with inline
constants normalized. Vertex matching hashes the bounded, word-swapped program,
including candidate lengths within original SHDS wrappers. Catalogue source
offsets and the existing player map locate 2,436 of 2,621 candidate program
identities, leaving the 185 FP identities above. All source container/program
hashes and bounded slices are checked. No deleted private recorder trace is
used, no hash is treated as an asset offset, and no new extraction is made.

Independent packed resolution hashes the original 2,052,954,112-byte GT.VOL,
the ELF, 298 containers including ELF, 1,811,994,944 decoded bytes and every one
of the merged starter's 3,446 program slices (13.17 s). Numeric
volume locations add 96 members already verified in the unchanged 592-member
search map: 201 -> 297. The complete player map adds 1,565 identities (145 VP,
1,420 FP); supplemental asset locations are extended too. Old player/archive
rows are preserved. Maps use compact JSON to stay below the existing 1 MB Git
file guard; no allowlist or guard is relaxed. The 99-shard bundle/index and
warmup-plan digest are reissued together. Observed menu/race membership stays
unchanged; new keys are not assigned invented preload ownership.

**Fresh candidate and acceptance proof.** Eight separate locked preparation
runs use fresh private outputs/application caches, the current Phase 211 backend,
production VP decoder, default settings and `RSX_FP_SAMPLE_SHARE` unset. Their
requested sizes are seven chunks of 1,000 and one of 790. Completed counts total
7,000 prepared / 790 unresolved; summed internal preparation is
618.79 s (OS/driver caches preserved). Both rebuilt shader/source
identifiers, exact native keys and persisted driver blobs are required. The
four partially successful chunks are filtered by successful proof and complete
player locations, then prepared again from GT.VOL in new outputs with verified
shader/driver reuse (112.34 s total). `pipeline_contribution.py accept` consumes each exact candidate digest and its own local complete proof;
report digests are never relabelled to fit a subset. The coherent union is
written only after these gates. Private engine SHA-256:
`862f6687c6bef5d34a4b3fab87b1d159cc915fc218d31fde8d19da0e82273bc7`.

**Full frozen acceptance.** A fresh private `scripts/release/build_preparer.py`
build runs the enlarged starter directly from the original packed game, with
a clean PATH, default translation and no previous-cache reuse. Invalid template
rejection and vertex-stage cancellation preserve the old selection/cache.
Cancellation retains 8 shader files; resume revalidates
them and completes every pipeline in the same originally empty generation.
Both shaders, all 12,669 native keys and persisted driver blobs pass; native chunks
are 4096, 4096, 4096, 381, with requests/created/
driver_calls/cached_blob_calls = 12669/12669/12669/0. Both local shader packs
publish. Resume wall time is 564.62 s; its internal preparation
is 553.85 s. This is fresh application-cache
acceptance with checkpoint reuse, not driver-cold timing or an incremental
growth benchmark. The complete locked harness (installation copy, rejection,
cancellation and resume) spans 610 seconds in the second-resolution lock log.
An initial Visual Studio diagnostic was treated as a terminating PowerShell
wrapper error; that helper output was discarded and a fresh private helper was
built with native stderr retained and explicit exit-code checks. No product
validation guard was changed.

Focused template, contribution, asset-map, packed-search, template-coverage,
warmup-plan, shader-pack, catalogue-growth, search-map/package and translation
regressions pass separately under the lock. Final coherence checks verify
strict JSON input, quarantined keys, exact old-record/location preservation,
complete maps, every native proof, current contract, LF index pin, unchanged
observed membership and strict package metadata allowlists. A foreground HSR
route uses a copy of the full prepared cache at 1080p/2x/16:9, with ordinary
async policy; inspected window-only race samples verify representative
presentation. It is a single route, not visual acceptance of every added state
or a stutter measurement.

Evidence: `scratch/s/` contains contract/input pins, review, map proof, chunk
summaries, frozen/coherence results and window shots; full preparation reports
are retained compressed in `scratch/s/evidence`. Every test, compiler/build,
preparation/native and game run uses `C:\tmp\gt5p-testlock\run_locked.py`, the
shared validation mutex and `tasklist` preflight. The retained private controllers
ran `work.py prepare 0..7`, `work.py accept 0..7`, `full.py`, the ten named
`scripts/test` suites, `coherence.py` and `live.py`, each run separately locked.
Private build/helper outputs,
game fixture and shader/driver caches are removed after recording evidence;
original inputs and other checkouts remain read-only. No whole-game, all-car,
all-camera, arbitrary-settings, GT5, multi-GPU or hitch-free claim follows.
The 790 pending records need independently located original programs; deleting
the sweep traces does not authorize reconstructing missing bytes from hashes.
Published v0.2.3, main, tags and releases stay unchanged; push only this branch
with `[skip ci]`.

## Phase 211 - Shader-stage profiling and fewer preparation file opens (2026-11-03)

`GT5P_PREPARE_SHADER_PROFILE=1` adds default-off aggregate instrumentation.
Vertex workers report translation and D3DCompile intervals once at shutdown;
the owner reports startup, dispatch, acceptance, checkpoint callbacks, idle
polling and shutdown. Fragment batches report raw input reads, translation/queue
submission, throttle/drain waits, accumulated compiler/persistence intervals and
queue residence, with host staging/process/result intervals. These are elapsed
intervals, not sampled CPU time. Worker totals, queue residence and owner waits
overlap and must not be added to wall time. Normal gameplay never enables them.

The full control's 482 vertex variants take 120.46 s wall, with 472.35 s accumulated
in four compiler workers, 0.072 s translation and 0.479 s checkpoint callbacks.
Its main fragment batch spends 402.35 s accumulated in compiler calls versus
1.04 s translation/submission. The bounded queue remains occupied; its 98.02 s
owner throttle and accumulated queue residence overlap compiler execution. This
does not identify polling or translation as a large remaining optimization.
The host instead spends 8.61 s staging fragment inputs and 9.37 s reading results.

Native preparation now capability-gates `GT5P_OFFLINE_CODE_V1` alongside V2
recipe/result handoff. `GT5P_PREPARE_CODE_BUNDLE=auto` is the default; `=0`
restores individual reads and repeated code timestamp operations, while `=1`
requires matching capabilities. The private transient transport contains a
16-byte header, at most 8,192 numeric index entries and 128 MiB of bytecode.
Host writes stream existing verified references without another bytecode copy;
incomplete pooling/budget overflow falls back to the existing individual path.
The native owner validates exact layout, sizes, offsets, uniqueness, complete
checksums, DXBC markers and every recipe dependency before any requested driver
call. It never mixes an invalid/incomplete bundle with disk fallback. Owned
arena bytes are freed on completion. The successful helper removes only the
transient request bundle after native children exit; interrupted transports are
rebuilt on resume. Durable shader checkpoints/cache formats and full final
persistence verification are retained. Shared durable code timestamps need the
existing successful operation once per code per native batch, avoiding repeated
metadata opens while preserving that generation's retention timestamps.

The fragment host defaults to `GT5P_PREPARE_FRAGMENT_IO=1`; `=0` restores the
earlier per-request checks/rereads. Raw input is checked/written once per distinct
program per chunk, with complete-byte identity checks. Native children finish
before results are read. The existing opened-handle size/sentinel reader checks
each distinct output key once per chunk into the existing 128 MiB pool. A key
seen in another chunk must match the complete retained bytes; collisions or
changed outputs still reject. Source/code IDs, native keys, chunk callbacks,
checkpoint publication and cancellation ownership stay mandatory/unchanged.

Three ordered, profiled, application-cache-fresh full runs use default translation,
four compiler workers, the same original packed volume/ELF and all 5,669 records.
The first two share one private engine and the earlier fragment host; the final
run adds the fragment host changes with another private build of the same runtime
patch. Hardware: i5-12400F (6C/12T), 16 GB RAM, RTX 4060, driver 32.0.16.1088;
`PS3_VERBOSE=0`. OS/driver caches are retained. This is a development series,
not ABBA or a driver-cold test.

| Measured cost | Individual code reads | Native bundle | Final fragment I/O |
| --- | ---: | ---: | ---: |
| Full preparation | 364.20 s | 313.25 s | 313.98 s |
| Vertex batch wall | 120.46 s | 120.55 s | 114.77 s |
| Fragment stage wall | 128.98 s | 120.78 s | 111.09 s |
| Fragment host input/results | 17.98 s | 15.56 s | 1.28 s |
| Native stage process wall | 76.67 s | 36.68 s | 53.12 s |
| Native shader/bundle loading | 22.11 s | 0.236 s | 0.225 s |
| Driver creation | 24.57 s | 9.57 s | 25.35 s |
| Recipe/code persistence | 11.39 s | 8.51 s | 8.85 s |

Final preparation is 50.22 s / 13.79% shorter than the control. The middle run's
driver interval changes substantially; it must not all be credited to transport.
The final driver interval is closer to the control, but compiler and other
timings still vary, so this is not a universal speedup claim. Native individual
code reads fall 4,468 -> 0, replaced by two bundle reads; 6,870 repeated timestamp
operations are skipped. The bundle carries 4,067 code bodies / 62,189,856 payload
bytes (62,254,944 serialized bytes). Native arena highwater is about 59.3 MiB;
the previous first chunk's code cache was about 51.0 MiB. Final fragment input
checks are 1,406 for 3,696 exact requests, and 3,609 distinct output reads. Output
file count stays 20,926: this reduces opens/rereads, not the durable cache layout.
The transient bundle is confirmed absent after successful preparation.

Every full run compiles 482 VP variants / 3,696 exact fragment requests (3,609
canonical compiler jobs), with zero application shader reuse. All 5,669 exact
native requests and persisted blobs pass in 4,096/1,573 sequential chunks, with
zero supplied cached-driver-blob calls. Menu/race packs match each other and
Phase 210 byte-for-byte. No native concurrency, draw-policy, root-signature/key
ABI, compiler/job memory cap or coverage change is introduced. The conservative
runtime source fingerprint and all starter/plan/index pins are reissued;
all 5,669 records, maps and observed warmup membership stay unchanged.

Real native rejection checks cover corrupt/truncated bytecode bundles and a valid
bundle missing a recipe dependency: zero requested driver calls, prior result
manifest preserved. Existing corrupt shared code, valid-checksum pointer, recipe
truncation and ID negatives still pass. Actual-header native tests cover bounds,
uncached fallback, default-off clocks, bundle offsets/checksums and timestamp
scope. Host tests cover bounded spill, old-capability fallback, interrupted bundle
writes/rebuilds, transport removal, changed output across chunks, rollback, result
membership, timeout and publication/cancellation failures. Metadata, translation,
large-catalogue and package checks pass. Final frozen default/ultrawide 32-record
acceptance cancels after eight fragments, resumes all eight, validates every
native key/blob, preserves source/selection, and passes both native handoff
rollbacks, chunk reuse and invalid worker/handoff/profile/fragment-I/O rejection.

Evidence: ignored `scratch/native-preparation-211/{subset,full,final}/` summaries,
acceptance/frozen reports, `policy.json` and `comparison.json`. Reproduction:
`preparation_native_profile.py --full --code-study --fragment-io 0`, followed by
`--full --shared-only --fragment-io 1`, with the reference/input arguments in the
retained controller CMDs, under `isolated_validation.ps1` and an x64 VS environment.
All private test shader/driver caches, raw intermediates, helper/PyInstaller and
engine/build outputs are removed automatically; existing user/OS/driver caches
stay intact. No live gameplay/stutter, whole-game or multi-GPU acceptance is
claimed. Main, tags and published v0.2.3 stay unchanged; feature push `[skip ci]`.

Cleanup exception: automatic approval review blocked deletion of the ignored
`native-preparation-211/author-source` copy (0.87 MiB) and its two authoring scripts,
returning only "blocked by policy". They remain private. They are runtime source,
not game data, shader caches or build outputs; the test-output cleanup above passed.

## Phase 210 - Native timing and bounded intermediate handoff (2026-11-03)

Native preparation now exposes default-off aggregate timing via
`GT5P_PREPARE_NATIVE_PROFILE=1`. One summary per native chunk separates recipe
validation, shader reads/hashing, driver-hint reads, existing driver-call timing,
GetCachedBlob/write/rename persistence, warmup recipe/code persistence and result
publication. Child creation-to-batch entry is measured from Windows process
creation time and includes initialization/manifest parsing. Other intervals use
QPC; controller timers separate request serialization, result parsing and process
wall time. The residual includes host launch/preflight, wait, native cleanup and
exit. It must not be called pure startup. No per-frame trace, new native worker,
parallel native process or live draw policy is introduced.

The full legacy diagnostic control identifies file traffic, not driver creation,
as the largest native cost. Keeping driver calls sequential, the final transport
uses capability-gated `GT5P_OFFLINE_HANDOFF_V2`, a shared verified bytecode pool,
one bounded numeric recipe bundle per chunk and an atomic result manifest.
`GT5P_PREPARE_HANDOFF=auto` selects it only for matching engines; `=0` restores
per-request inputs/results and `=1` requires the capability. The executable scan
uses bounded buffers; larger/unknown engines conservatively fall back. A real
32-record fresh proof with the existing release engine confirms legacy fallback,
exact keys/persistence and cache cleanup, with timing disabled.

Host bytecode references are bounded to 128 MiB and complete recipe buffering to
16 MiB. Overflow recipes use the old file path and are read into bounded chunks;
no records are silently omitted. A chunk has at most 4,096 records / 11,567,120
serialized bytes, including 64-byte identifiers and the unchanged 2,760-byte
recipe. Native input validates magic, exact size/count, identifier membership and
every original envelope/descriptor check before the first driver call. Its code
cache is limited to 128 MiB / 8,192 entries per process; cache-full reads use
ordinary owned buffers. All caches free on batch completion or process teardown.
Input arrays are private to the guarded offline owner. Normal gameplay never
activates this state. Existing async policy, shader workers, native chunk limits,
root signature/key ABI, process jobs and shutdown guarantees stay intact.

Grouped results retain the existing result fields and publish only after every
native creation succeeds and the stream closes without error. Publication does
not itself establish persistence or authorize cache selection. Completion publication,
exact membership, duplicate/missing IDs, expected/actual keys and persisted cache
verification are independently checked by the owner. An earlier manifest is
invalidated before each launch; partial/stale results cannot authorize success.
Shader checkpoints stay durable; native input is rebuilt on resume from verified
shaders plus pinned numeric metadata. Cancellation polls during input generation
and native chunks retain their existing owned cleanup. Switching transports on
resume preserves selection/source cache. Existing legacy files are not deleted.

Three ordered full fresh runs measure legacy input, shared bytecode/results,
then the final bundled transport. The final format adds recipe bundling after
the first comparison showed individual recipe opens still cost about 30 seconds.
All runs use four compiler workers, four verification readers, the original
packed game, default translation and identical 5,669 numeric records/observed
plan membership. All 482 vertex variants / 3,696 exact fragment requests
(3,609 canonical compiler jobs) compile without application-cache reuse. Every
native request/persisted blob passes, in 4,096/1,573 chunks with zero cached-blob
calls. Menu/race pack hashes are identical. The legacy control and final format
use separate private engine builds; the intermediate and final formats therefore
are an ordered development series, not a single ABBA compiler/native trial.

| Measured cost | Legacy control | Final bundle |
| --- | ---: | ---: |
| Full preparation | 451.93 s | 336.33 s |
| Host native-input staging | 19.08 s | 3.76 s |
| Native stage wall time | 149.50 s | 70.05 s |
| Aggregate native batch time | 144.13 s | 65.63 s |
| Recipe reads/validation | 32.52 s | 0.042 s |
| Shader reads/validation | 59.42 s | 20.20 s |
| Actual driver creation | 24.17 s | 23.92 s |
| Blob persistence | 11.76 s | 10.20 s |
| Warmup recipe/code persistence | 12.58 s | 9.57 s |
| Result writes/publication | 1.964 s | 0.054 s |
| Child startup, both chunks | 2.72 s | 2.48 s |

Full preparation takes 115.60 seconds / 25.58% less time; native batch time falls
78.50 seconds / 54.47%. Driver creation is approximately unchanged at the endpoints;
it did vary in the intermediate run. Compiler times also vary (252.26 -> 236.51 s
combined), so the whole preparation gain must not be attributed solely to native
transport. Bucket/report scopes differ and must not all be added together.
Hardware: i5-12400F, 16 GB RAM, RTX 4060, driver 32.0.16.1088, `PS3_VERBOSE=0`.
These are profiled, application-cache-cold runs; OS/driver caches are preserved.
No live rendering, stutter, all-settings or whole-game acceptance is claimed.

Fresh working-file count falls 43,600 -> 20,926 (52.0% fewer); bytes at completion
fall 1,016,339,582 -> 632,305,430. This counts files, not every filesystem operation.
The owner checks/writes 4,067 shared code bodies instead of 11,338 per-request
copies. Native reads fall 11,338 -> 4,468, with 6,870 verified in-memory hits across
two separate processes. Peak host references are 62,189,856 bytecode bytes and
15,646,440 recipe bytes; native cached code peaks at 53,471,336 bytes. Recipe
serialization and current uncached payloads have additional bounded buffers.
Maximum individual offline-engine peak commit is about 2,221 -> 2,222 MiB; this
does not measure the parent/process-tree peak. Existing old generations retain
their files; the lower count applies to fresh outputs.

A 128-key same-cache old/new/new/old native trial creates all 128 PSOs from cached
driver blobs each time, verifies every key and leaves selected seed blobs
byte-identical. Wall times are 3.866 / 2.070 / 2.054 / 2.076 seconds. The first old
trial's input-file reads are much slower than the last old trial's; after warming,
overall wall time converges near 2.1 seconds. This does not establish a stable
large cached-preparation gain. Per-request result writes remain about 45 ms vs
2 ms aggregate, but startup dominates this small subset. Full fresh file creation
and first-open behavior are separate from steady warm-cache costs.

Real native negative proofs reject corrupt shared bytecode, a nonzero descriptor
pointer with a recomputed valid envelope checksum, truncated input and a mismatched
ID. Every failed batch performs zero requested driver calls and leaves an earlier
result manifest unchanged. The actual header's synthetic native test proves
byte/slot-cap fallback, ownership/freeing, default-off clocks and bundle guards;
it stubs the loader/recipe validator, while the real negative proof exercises
production validation. Host malformed-result, byte/recipe-budget spill, content
conflict, marker-boundary/fallback, translation, large-catalogue, metadata-contract
and package regressions pass. The final frozen clean-PATH default/ultrawide subset
cancels after eight saved fragments, resumes them, validates all 32 native calls,
reuses shaders on cached/chunk rollback and switches to legacy native handoff.
Invalid chunk/worker/handoff/verification settings preserve selected cache, source
and derived work. Existing UI/launch ownership is retained; no new live route is run.

The runtime patch changes its conservative source fingerprint. All 45 starter
shards and index are reissued with the same 5,669 records; maps and observed
membership are unchanged, and the plan's template hash is re-pinned coherently.
Bundle indices now use explicit LF generation/checkout because their bytes are
hashed by warmup plans, matching the existing shard policy. The metadata audit
against 7a5c950 checks records, other compatibility fields, maps and membership.
No new shader/pipeline coverage is added. Old contribution contracts still require
maintainer re-verification/reissue; a fingerprint change is not permission to trust
an old claimed proof.

Ignored evidence: `scratch/native-preparation-210/full/{legacy,shared}.json`
(first transport), `final/shared.json` (final format), each `acceptance.json` and
`frozen-validation.json`, `native-policy.json`, `old-engine.json`, controller logs
and comparison metadata. `preparation_native_profile.py --full` builds the changed
backend/presentation objects privately and links unchanged read-only CI objects;
`--shared-only` runs the final proof against an already measured control. It verifies
the pinned baseline backend before applying the authored patch. No shared runtime,
CI objects or install are overwritten. Every build/test/compiler operation owns
the shared validation mutex through child cleanup. All private shader/driver/raw
program caches, engines, objects, helper/PyInstaller outputs and native test builds
are removed; only metadata/logs remain. Original game files, user caches and driver
caches stay intact. Main, tags, v0.2.3 and release workflows remain unchanged;
development commits/pushes use `[skip ci]`.

## Phase 209 - Compiler concurrency and size-aware cache verification (2026-11-03)

Offline preparation now selects four compiler workers on CPUs reporting at
least eight logical processors, otherwise two. Explicit
`GT5P_PREPARE_COMPILER_WORKERS=2|3|4` overrides the selection; `=2` restores
the previous count. This controls vertex processes and the existing fragment
compiler threads in sequential stages, not eight simultaneous compiler jobs.
Vertex workers retain private kill-on-close ownership, 512 MiB per-process and
1 GiB aggregate job memory limits, existing timeouts and bytecode budgets.
At most four requests are in flight. The runtime patch, normal game worker
selection and async draw/queue policy are unchanged.

Cache verification now separates recipe metadata, unique bytecode dependencies
and persisted driver blobs. Four read-only workers each process at most 32
metadata results per scheduled task, retaining only one payload at a time.
Shared bytecode identities are checked once per scan, with errors attributed to
every referencing recipe. Reads use the opened file's size plus a sentinel byte
instead of speculative 4/32 MiB requests for small files. Oversize files reject
before allocation; short reads, growth or changed size reject. Every complete
recipe, bytecode identity and driver envelope/checksum still verifies.
`GT5P_PREPARE_VERIFY_BATCH=1` restores the previous task/read path. Callbacks and
publication remain on the owner; cancellation joins outstanding reads before
returning. Neither change requires a new cache format or invalidates resumable
work. Invalid tuning settings reject before preparation output creation.

Three ordered, profiled full runs start in separate empty application caches,
using the same private engine, original packed inputs, default translation,
5,669-record starter, observed plan/packs and four I/O readers. Every run compiles
all 482 vertex variants and 3,696 exact fragment requests (3,609 canonical
compiler jobs), prepares every native key in 4,096/1,573 chunks with zero cached
driver-blob calls, and verifies all persisted blobs. No prior application shaders
are imported. Both shader packs have identical counts, bytes and SHA256 across
all three runs. The two-worker control reproduces Phase 208's 631.59-second
result within about 1.2 seconds.

| Run | Full preparation | Vertex compiler | Fragment preparation | Native stage |
| --- | ---: | ---: | ---: | ---: |
| Two workers, original verification | 632.74 s | 181.76 s | 200.04 s | 158.97 s |
| Three workers, batched verification prototype | 492.08 s | 138.99 s | 148.98 s | 129.62 s |
| Four workers, final size-aware verification | 457.04 s | 117.25 s | 124.97 s | 152.70 s |

The final run takes 175.69 seconds / 27.77% less preparation time than the
two-worker control; compiler reports together fall 381.80 -> 242.22 seconds
(36.56%). Report scopes differ and are not an additive wall-time breakdown.
Native creation also varies despite no native scheduling change, so the whole
gain must not be attributed solely to worker count. Three-worker verification
used batching before the size-aware read refinement; the final four-worker run
includes both changes. Hardware remains i5-12400F, 16 GB RAM, RTX 4060,
driver 32.0.16.1088, `PS3_VERBOSE=0`. This is one ordered 2/3/4 local series,
not an ABBA compiler trial or a universal CPU/GPU/storage guarantee. OS/driver
caches remain intact. Application-cache-cold is not OS/driver-cold. No live
rendering, hitch, whole-game or all-settings claim follows.

After the final run, an unprofiled read-only same-cache original/new/new/original
verification comparison returns exactly the same 5,669 recipes, 5,669 valid
driver blobs and empty rejection list each time. Original scans take
31.366 / 30.039 seconds; new scans take 1.638 / 1.596 seconds, about 94.7% less
elapsed scan time by pair means. This comparison excludes compilation, native
creation, report serialization and UI callbacks; it is a warm same-cache scan,
not a fresh-storage benchmark. Final whole-stage verification timing also
includes report/checkpoint work and must not be substituted for this scan result.
The opened-handle size optimization avoids large read requests without skipping
integrity checks. Synthetic shared/corrupt-code, conflicting-length, oversized,
short/growing-file and cancellation checks pass.

Observed vertex worker-job peak commit is 115.60 / 170.09 / 223.79 MiB for
two/three/four workers, below the unchanged 1 GiB cap. Offline engine lifetime
peak commit counters are about 2,179 / 2,198 / 2,219 MiB respectively (maximum
across each run's engine processes). These are process/job measurements, not
whole-machine or simultaneous process-tree peaks. The final engine-process
maximum is about 40 MiB above the control. Parent memory and other hardware
remain separate acceptance limits.

Final source scheduler/environment, recipe/dependency, size-aware reader and
bounded I/O cancellation regressions pass. A fresh 32-record rollback restores
two workers, 100 ms polling, exit replay and original verification successfully.
The private frozen helper passes a clean-PATH 32-record default/ultrawide
checkpoint proof with four workers: cancel after eight saved fragment results,
reuse all eight on resume, verify 32 fresh native calls and zero cached blobs,
then reuse every fragment on the 4,096-chunk rollback. Invalid chunk, worker
and verification settings reject while preserving source cache, selection and
translated work. Separately, the new parent pool launches four protocol-compatible
frozen release workers; killing its owner retires all four while the outer job
remains open. This tests OS job ownership without starting a game. The probe uses
the read-only release worker binary; new-helper cancellation/resume is covered
by the separate frozen proof. All owned children exit before cleanup/release.

The harness retains timing/count/hash/resource metadata under
`scratch/preparation-speed-209/`: `workers-{2,3,4}.json`, `worker-study.json`,
`fresh-rollback-32.json`, `frozen-validation.json` and `acceptance.json`, plus small
controller logs. `preparation_speed_acceptance.py --worker-study` reproduces the
owned sequential comparison using read-only CI objects and a private engine/helper
build. The fresh harness records Windows lifetime peak process counters and
optionally compares verification implementations on its own cache. Every full
test cache is removed after its verification comparison. The private engine,
helper, build outputs and PyInstaller caches are also removed after acceptance;
existing player generations, driver caches and original files remain untouched.
All build/compiler/test operations own the shared validation mutex and complete
child cleanup before releasing it. Published v0.2.3, main, tags, starter/maps
and release workflows remain unchanged. Development pushes use `[skip ci]`.

## Phase 208 - Fresh preparation speed and disposable validation (2026-11-03)

The fresh path now polls the existing two vertex workers every 10 ms instead
of 100 ms. `GT5P_PREPARE_VERTEX_POLL_MS=100` restores the previous interval.
Worker count, queue ownership, protocol, cancellation, timeout and memory caps
are unchanged. Separately, the native startup barrier still executes the exact
offline preparation batch, but skips its subsequent recipe replay when
`GT5P_SHADER_PRECOMPILE_ONLY=1`: those pipelines were already created and
persisted, and the process is about to exit. `GT5P_PREPARE_OFFLINE_WARMUP=1`
restores replay. Ordinary gameplay retains its existing warmup behavior.
Disabling `RSX_SHADER_WARMUP` cannot replace this guard: that flag also enables
the startup barrier which invokes offline preparation. Completion flushing and
strict native/persisted-blob acceptance remain intact. New engine and helper
are required for the combined improvement; older engines remain correct.

Two complete profiled runs use the original packed game files, default
translation, the same 5,669-record starter, observed warmup plan and shader
packs, four I/O readers and two compiler workers per stage. Both start in fresh
application-cache directories, import no old shader/driver blobs, compile all
482 vertex variants and 3,696 exact fragment requests (3,609 canonical compiler
jobs), and prepare all 5,669 native requests in 4,096/1,573 chunks. Native calls
use zero cached blobs. Every requested native key and persisted blob passes
verification. Menu/race pack hashes and byte counts are identical.

| Measured elapsed time | Baseline | Improved |
| --- | ---: | ---: |
| Full preparation | 731.20 s | 631.59 s |
| Vertex compiler report | 198.82 s | 185.37 s |
| Fragment compiler report | 202.44 s | 204.67 s |
| Native stage wall time | 250.62 s | 150.47 s |

Total preparation falls 99.60 seconds / 13.62%. Baseline exit replay attempts
9,765 recipes across the two native chunks and reports 76.110 seconds of replay;
the improved run performs none. These are overlapping report scopes, not an
additive time breakdown. Hardware: i5-12400F (6 cores/12 threads), 16 GB RAM,
RTX 4060, driver 32.0.16.1088, `PS3_VERBOSE=0`. This is one ordered local pair,
baseline first, with profiling enabled. OS/driver caches were preserved, and
native engine paths differ; it is not an OS/driver-cold, ABBA or universal speed
result. Fragment timing does not improve. No live rendering, hitch reduction,
whole-game or all-settings claim follows.

The fresh native harness and private-build acceptance harness are checked in
under `scripts/test/preparation_{fresh_native,speed_acceptance}.py`. The latter
compiles only the changed presentation translation unit into private output,
links read-only matching CI objects, and builds a private frozen helper. No
game copy or shared runtime output is written. Native policy tests cover 29
cases. Source 32-record fresh/rollback proofs pass with the same worker caps.
Frozen packed-game ultrawide subset acceptance cancels after eight saved
fragment results, resumes all eight, verifies 32 native calls with zero cached
blobs, and passes old selection/source preservation, chunk rollback reuse and
invalid-configuration rejection. Vertex scheduler, reconstruction/environment
and package rejection regressions pass. Every test/build owns the shared named
validation mutex through child completion and cleanup.

At the user's request, all newly generated test shader/driver/raw-bytecode
caches, private engine/object/helper outputs and private PyInstaller caches are
deleted after validation. Existing player/driver caches and original inputs are
untouched. Helper builds now place PyInstaller's cache under their selected
output directory so private builds can clean it too. Both fresh summaries
assert `test_cache_removed`; the acceptance summary asserts
`private_build_removed`. Retained ignored evidence in
`scratch/preparation-speed-208/` consists of timing/count/hash JSON and small
controller logs, including `fresh-baseline.json`, `fresh-optimized.json`,
`fresh-rollback-32.json`, `frozen-validation.json` and `acceptance.json`.
Published v0.2.3, starter/maps, renderer/runtime patches and async draw policy
stay unchanged. Development commits/pushes use `[skip ci]`; no release or CI
build is requested. Remaining speed work should profile inventory and fragment
compilation with the same cache controls rather than increase worker caps blindly.

## Phase 207 - v0.2.3 publication (2026-11-03)

After accepting the candidate, the user explicitly authorized main integration
and v0.2.3 publication. Merge 451a815fb3ee6ef0af7b66210f7d20c0537896b7
integrates main's player README, branding and v0.2.2 notes with the tested
candidate. VERSION resolves to 0.2.3. Gameplay/preparation code is unchanged
from RC3; player documentation and release links are updated. The Windows
release build now runs through the existing owned validation-mutex wrapper,
including process preflight and finally release through joined children.
Three release-trigger tests pass, and the tracked/history policy scan passes
513 files / 2,208 historical blobs. Normal commit hooks remain enabled.

Main/tag promotion pushes use [skip ci], followed by exactly one explicit
[v0.2.3 workflow](https://github.com/mathewdouglas/Tourline-Prologue/actions/runs/41557476751).
Both player and publish jobs pass. The build/validation step takes 111 seconds;
the Windows job including checkout/upload takes 145 seconds. This is a cached
release build, not a first-time preparation or gameplay performance result.
Tag v0.2.3 dereferences 451a815; published v0.2.2 remains eb49fb8. Later
documentation commits do not move either release tag.

The [published release](https://github.com/mathewdouglas/Tourline-Prologue/releases/tag/v0.2.3)
is public, non-prerelease and latest. Its ZIP is 92,972,484 bytes / 241 files:
`tourline-prologue-v0.2.3-windows-x64-451a815fb3ee6ef0af7b66210f7d20c0537896b7.zip`.
SHA256: `1a7d3218b65a0c7dfae84a6051dd5ff7580154ba9ef97d15f700c4720ca11fc0`.
An independent public asset download, under the same mutex, passes the shipped
checksum, ZIP CRC, release.ini version/target and executable hashes, every file
in the CI helper's packaging manifest, and byte-identical metadata shards with
all 5,669 records. The helper manifest is a build-time input, not a shipped file;
the private post-download harness was corrected to read that input before the
successful check. Evidence: `scratch/v023/published-release-validation.json`;
the downloaded ZIP/checksum are also retained outside this worktree in
`C:/Users/GGPC/Downloads/Tourline-Prologue-v0.2.3-release/`.

Phase 206's offline/native and foreground visual acceptance remain the live-use
evidence; the public rebuild was checked without launching another game. No
whole-game/all-settings or solved stutter claim is added. The texture-retention
experiment remains outside the shipping runtime. No cache/evidence or worktree
is deleted, and no additional release build is dispatched.

## Phase 206 - Private v0.2.3 candidate and full starter growth (2026-11-03)

The isolated feature branch integrates Phase 198's translated fragment checkpoints
as cf28f06, sets VERSION to 0.2.3 with authored release notes (063b20c), and builds
a private candidate without main/tag/release/CI changes. A fresh CMake/Ninja
Release build compiles the runtime and all native/generated game translation
units into scratch/v023/engine (846.73 s, two build workers). Existing private
generated source and dependency inputs are read-only; this is not a fresh lift.
The runtime is the pinned d2be355a7fe73c59750f compatibility-patch identity, with
build outputs only in this worktree. Phase 199 diagnostic/texture-retention
overlays are excluded. Launcher, production decoder, checksum/volume DLLs and
frozen helper build successfully; icon, setup/storage, managed restart,
first-run choices and all three tool-handoff regressions pass sequentially.

The user's later collection is incorporated from the separate review/proof:
1,368 shared records contain 149 existing records and 1,219 additions, with no
conflicts. Three branching contexts were excluded before export. Original-volume
search locates all 300 new program identities across 353 searched containers
(69.19 s). Independent candidate preparation verifies all 1,219 native keys and
persistence, reusing shaders independently checked after collection. Private
evidence is scratch/contribution-review-84569c82,
new-program-locations-84569c82 and candidate-proof-84569c82/out. Commit 9254369
preserves all 4,450 earlier records and issues the 5,669-record starter / 1,881
programs (477 VP, 1,404 FP), player map and 201-member volume map coherently.
The additional 36 containers were already verified in the search map. Observed
menu/race membership is unchanged and re-pinned; new keys without observed phase
membership stay on demand. No whole-game, all-settings or first-draw readiness
claim follows from this growth.

Commit 8e9f601 incorporates and reviews the user's retained-cache scan fix. A
read-only scan of the actual reported storage now encounters 194,180 entries:
the old 100,000-entry guard rejects it; the revised bounded allowance passes in
16.62 s. Per-output allowance is 1,196,288 entries, derived from the metadata
catalogue ceiling, request/translation/cache layout and warmup allowance; the
parent scan allows 64 such budgets. Existing generation search, every link and
hard-link rejection, checkpoint identity/ownership and cache preservation remain.
The checkpoint/reuse/translation/collection/package regressions pass. These are
safety ceilings, not proof that a ceiling-sized catalogue or tree is practical.
No retained cache or user storage file is deleted, repaired or rewritten.

The initial 4,450-record frozen candidate passes template rejection,
cancellation/resume, every native key and persisted blob, and unchanged source
cache. The final 5,669-record frozen candidate then grows a separate cache from
that verified generation, retaining all 3,493 available shader files and a bounded
2,000-driver seed. It passes the same rejection/cancellation/source-preservation
checks and all 5,669 exact native requests in 4,096/1,573 chunks. It reuses 447
vertex variants and compiles 35 new ones; 1,004 missing fragment jobs deduplicate
to 563 exact requests in one batch. Every native pipeline is created/persisted,
with 2,000 cached-blob calls. Measured preparation is 253.91 s; the lifecycle
harness includes copying, cancellation and rejection and takes longer. This is
one local growth proof with OS/driver caches preserved, not a speed comparison
or an empty-cache/driver-cold/other-GPU acceptance claim. Evidence:
scratch/v23full/validation.json and scratch/v23fullfinal/validation.json.

The superseded RC2 ZIP is assembled with strict allowlists and verified dependency
manifests: 240 selected files, 91,986,089 bytes, SHA256
9ea3dd344980b740865ded72321210dc49d710a316a5428dd2076fd33b6b5924.
ZIP integrity, version metadata, template/map/plan coherence and exclusion of
game/cache inputs pass. Helper/metadata source is 9254369; the unchanged C++
engine/launcher were compiled at 063b20c. Private build/package evidence is
scratch/v023; all caches, failed harness evidence and original inputs remain.
An initial source-only translation harness omitted its explicit volume DLL path
and rejected before native work; the corrected harness supplies the bundled
library. This did not change the product or relax its guard.

The source translation check subsequently reproduces Phase 188's intermittent
missing native-completion output: partial logging with exit code zero is safely
rejected. An eight-run cached 32-request probe loses completion/guard output once;
the same engine with explicit-flush rollback also loses it once in eight. The
default explicit-flush probe completes all eight, and the separate 32-record
default/ultrawide/scaled cancellation/resume/persistence/default-rollback proof
passes. This is bounded local acceptance, not a universal absence-of-failure claim.
Commit 41b92c8 flushes offline stdout/stderr before releasing the startup barrier
and before the guarded offline main return. Normal play remains buffered. The
helper forwards GT5P_OFFLINE_FLUSH=0 to restore historical exit-only flushing;
unrelated inherited overrides remain filtered. The completion guard stays strict.
No renderer/runtime source, queue policy or draw ownership changes. Repeated
probe evidence is scratch/v023/native-log-{baseline,flush,rollback}.json;
both-translation proof is scratch/v23flushnative/validation.json.

RC3 rebuilds the affected native translation units and the helper from 41b92c8,
retaining the unchanged launcher and starter/maps/plan. Its 240-file ZIP is
91,961,439 bytes, SHA256
6e21d4f19220767195d0d157195f937c58685eb1f19cd293832bf1b4fbf4a00b.
The checksum sidecar and build/package evidence are in scratch/v023. RC1/RC2 and
failed-run caches/logs remain preserved; they are superseded for user acceptance.

Final RC3 acceptance passes all 5,669 frozen-helper requests again, with all 482
vertex variants and 5,669 fragment jobs reused, zero compiler workers, both
native chunks, persisted blobs and unchanged source-cache hashes. Its frozen
32-record fragment cancellation/resume/rollback and separate source 32-record
default/scaled/ultrawide proof pass. A frozen retained 121-record collection
verification passes cancellation/resume without resumed shader compilation,
exact native persistence, incompatible-volume rejection and preserved share/
ordinary cache selection. See scratch/v023/accept-rc3-validation.json,
scratch/v23f3, v23c3, v23t3 and v23v3. These are final-bit checks; the earlier
RC2 growth run provides the missing-shader compilation evidence.

Three real saved-resolution/aspect restarts pass with distinct replacement
game PIDs and old-process retirement. The actual RC3 F1 Debug actions also pass:
Collect replaces the game, startup/movie play exports and verifies six records
(zero pending), Verify revalidates that session, and Prepare opens the matched
precompiler and cancels during reuse without changing the selected cache.
All owned game/helper children exit. This collection is a small startup check,
not menu/race coverage, and F1 preparation is a cancellation check; full completion
is proven separately by the frozen helper. Debug, verification/result and
preparation window-only captures are visually inspected. Both interactive
Windows REPL tools fail initialization with "failed to write kernel assets"
after reset/retry, so existing owned-process native harness messages and the
existing PrintWindow approach perform these checks. A private controller first
expects the helper to own preparation's window; it safely rejects that target,
then is corrected to the actual launcher owner before cancellation. No product
change or guard relaxation follows. Evidence: scratch/v23restart and v23ui.

A final launcher-owned High Speed Ring route completes at 1920x1080, 16:9,
2x MSAA, anisotropy 16, smooth colour, PS3_VERBOSE=0 and ordinary async policy.
The starting grid highlights Honda Integra Type R '04 at row 8. The existing
private save/cache fixture is retained (selection cccc.../shadercache); packs
are enabled and local learned indices are used. Neither application, OS nor
driver caches are cleared. The owned window is shown and foreground is required
through intro/sampling; present counters and advancing race-clock images confirm
live frames. Menu/loading/grid, rolling intro and gameplay at race-clock 19.550
and 34.116 s, including nearby cars and the rear-view mirror, look correct in
inspected samples. This single 30-second gameplay sampling run uses screenshots
and variable AI/draw workloads; it is not a controlled hitch comparison or a
claim that either reported hitch is solved. A native CLI argument-forwarding
attempt fails before launch; an explicit PowerShell parameter wrapper runs the
same harness successfully. Evidence: scratch/v23route. Save/settings, selected
cache and post-play pack/index hashes are retained privately in
scratch/v023/candidate-validation.json along with all final acceptance results.

All build/compiler/native/game operations hold the shared
Local\Tourline-Prologue-Isolated-Validation mutex with process preflight and owned
cleanup; validation is sequential. No full game-data copy, cache deletion, shared
runtime edit, main merge, tag, publication or CI build is performed. The RC3 ZIP
and checksum are ready for the user's local acceptance using
docs/release-v0.2.3-testing.md. Whole-game/settings/GPU breadth and controlled
hitch acceptance remain separate work; only feature commits are pushed [skip ci].

## Phase 205 - Bounded parallel preparation reads (2026-11-03)

Preparation now defaults to four bounded read workers for verified cache reuse,
recipe/driver-blob inventory and shader-pack dependencies. The owner still makes
every cache write, atomic replacement, progress/cancellation call and publication.
An ordered pool retains at most four outstanding requests plus the currently
consumed result, with the existing per-file limits (4 MiB shader / 32 MiB driver
blob). This adds bounded read buffers; it does not raise the 128 MiB shader-copy,
256 MiB driver-copy or 60-second reuse budgets, compiler concurrency/memory caps,
or native batch limits. All original asset, shader, recipe, native-key and driver
persistence checks remain. No renderer/runtime or draw/queue change.

GT5P_PREPARE_IO_WORKERS=1 restores serialized reads; 2 is also supported. Invalid
settings reject safely. Executor shutdown explicitly cancels queued reads and
joins every started read before a checkpoint/lease can be released or a verified
handoff published, including when an exception traceback retains the generator.
Only reads/checksums happen on workers; source caches remain read-only. Native
checksum counters are synchronized and the native backend initializes before the
read pool. The frozen build explicitly includes concurrent.futures.thread.

A full cached 4,450-record diagnostic profile found substantial file-open/read
overhead: reuse reached its 60-second budget, inventory took about 36.09 s and
pack verification/publication 16.06 s; native job waits took about 138.05 s.
That profiled run took 282.84 s and is diagnostic, not the speed comparison.
No shaders needed compilation. Repeated inventory-only checks preserve identical
4,450 recipe/driver sets: serial 98.996 s, four readers 23.599 / 22.856 s, serial
38.208 s. The slow initial serial observation is retained; warming or other
machine activity is not isolated, so it is not used as a steady-state baseline.

The separate unprofiled full pair uses the same original volume/ELF, engine,
decoder, template, maps, phase plan and read-only complete shader/driver seed.
Application output caches are fresh and separate; OS/driver caches stay intact.
Four readers run first, serial rollback second on this i5-12400F / RTX 4060:

| Measured preparation work | Serial reads | Four readers |
| --- | ---: | ---: |
| Full 4,450-record preparation | 261.34 s | 202.52 s |
| Verified cache reuse | 60.00 s | 24.79 s |
| Driver hints copied within unchanged budgets | 2,702 | 3,471 |
| Menu/race shader-pack stage | 15.97 s | 5.28 s |

The full preparation is 58.82 s / 22.5% shorter in this one ordered local pair.
Both reuse all 447 vertex variants and all 4,450 fragment jobs with no compiler
workers. Every exact native key is created and persisted in the two existing
4,096/354 chunks; all 4,450 driver blobs and recipe dependencies validate. Both
shader packs are byte-identical, and full source-cache SHA256 snapshots plus the
selected-cache pointer remain unchanged. Faster reads allow more driver hints
through the existing time budget; byte budgets and native revalidation stay in
force. These results cover cached preparation, not first-time shader compilation,
OS/driver-cold performance, other storage/GPU hardware, or live stutter. The
remaining native creation and fresh shader compilation work is not removed.

Default-four and serial source checks pass reuse corruption/missing/link/budget
rejection, verified handoff, cancellation, pack preservation, template/translation,
contribution, collection and packaging checks. Focused pool tests prove ordering,
bounded submissions, two/four-reader caps, error propagation and joined cleanup;
reuse tests verify worker reads with owner-only writes. A final frozen real
121-record acceptance passes original packed assets, both shaders, native keys,
persistence, cancellation/resume with zero resumed shader compiles, incompatible
volume rejection, and old selected-cache/verified-share preservation. Its roughly
35.54 s total includes cancellation/rejection; it is not another speed comparison.

Private evidence: scratch/s205profile and s205b (diagnostic), s205micro (repeated
inventory checks), s205pair / s205p1 / s205p4 (full ordered pair), s205checks,
s205frozen / s205f (frozen lifecycle), and s205h (helper). Strict packaging and ZIP
integrity pass for a private 230-file candidate containing the frozen read-pool
dependencies and no game/cache data; SHA256
ba8e78c80a08606d2a10ce1c294f7bdf268813c8eb175d37f9819a77930e2b0f.
Caches and evidence are preserved. Starter remains 4,450 observed records; no
coverage expansion, guest execution, release, main merge, tag or CI build.
Development push uses [skip ci].

## Phase 204 - Settings pipeline tools and matched verification styling (2026-11-03)

The existing F1 Debug page now includes Collect pipelines, Verify last collection
and Prepare shaders, with Start buttons and action-specific help. Enter/Cross
and clicks activate them; Left/Right remains harmless on action rows. Collection
requires the existing supported saved context. A missing last-session selection
reports on the page without exiting. Direct engine launches, incomplete packages,
legacy restart mode and active collection sessions cannot start a tool. During
collection, close the game to finish/export/verify before starting another tool.
GT5P_PIPELINE_TOOLS=0 rolls back the new launcher handoffs; ordinary CMD entries
and preparation remain available.

Three distinct managed exit codes let the launcher wait for the old game and
retire its private job before starting a tool. The installed helper's release
hash gates availability and is checked again before handoff. Preparation keeps
the launcher's storage leases and uses its existing progress/cancel/resume flow.
Collection/verification release only that launcher's storage/home leases before
the normal collector launcher or verifier reacquires them. The parent still owns
the helper's kill-on-close job, including nested launcher/compiler descendants.
Nothing runs concurrently with the old game. Finishing/cancelling a tool leaves
the game closed; launch normally afterward. Both new launcher and engine are
required. No renderer worker, async draw policy or preparation default changes.

The verification window matches launcher/preparation_ui.h's settings palette,
Segoe UI sizes, title gradient, black/green fields, grey underlines/dotted rules,
real counted or indeterminate stage bar, and glass pill button. System DPI and
work-area fit size the panel at startup. Standard child text/buttons preserve
keyboard/accessibility behavior; owner-drawn fonts/brushes are released after
children are gone. The existing one-snapshot progress/cancellation worker and
verified-only publication rules stay intact. No overall percentage or ETA is
invented, and no UI dependency is added. Multi-monitor DPI migration and every
display scale are not claimed by this one-display acceptance.

Sequential synthetic launcher probes pass all three handoffs, success/cancel,
both lease releases for collection/verification, retained preparation lease,
active-recorder exclusion, tool rollback and legacy-restart rollback. Existing
launcher/setup/storage/managed-restart and first-run preparation checks pass.
Native UI tests cover counts, rejection, cancellation and cleanup; collection,
contribution and package regressions pass. Private launcher and engine builds
compile/link the authored settings source; the engine reuses read-only existing
objects/runtime into an isolated output. No shared runtime/build output changes.
Final frozen helper and checksum/packed-reader tests pass.

A real 1080p/2x/16:9 foreground startup check uses the retained own save/cache
fixture (aniso16, smooth colour, PS3_VERBOSE=0). F1 Debug displays all three actions.
Right on Collect does not exit; Enter exits the old PID, then the normal collector
starts a different game PID. Startup/movie frames visibly present at 60 FPS.
Closing that game starts the styled verifier: all 121 captured pipelines / 91
original programs reconstruct both stages, exact native keys and persisted data,
pending zero; the result displays about 26 seconds. This narrow startup/movie
check is not a race/content coverage or performance claim. F1 Verify subsequently
revalidates the same 121 records, exit zero. F1 Prepare closes the game and opens
the existing full-starter precompiler; cancellation during verified reuse returns
normally with the prior prepared-cache selection unchanged. No full-starter
preparation is claimed for this cancelled acceptance. All owned descendants exit.
Window-only Debug, game presentation, styled result and precompiler views are
inspected. Existing user collection sessions and every cache remain preserved.

Private evidence: scratch/c204build (isolated native outputs), c204checks and
c204final (focused logs), c204live (real three-action acceptance and retained
previous/session logs), c204inspect (final frozen re-verification), and c204h3
(final helper). A 225-file private candidate passes strict packaging and ZIP
integrity checks, with no game/cache data; SHA256
e1b435ab833cf10d74b11dc5af00b92469d00401119b2b7e2e0cb1f7a5ffe8ee.
No main merge, release, tag or CI
build; development push uses [skip ci]. Starter remains 4,450 observed records.

## Phase 203 - Visible post-play verification progress (2026-11-03)

Collection and Resume now open a small repository-authored native Windows window
after gameplay. It reports the current original-asset/shader/native stage,
available stage counts, elapsed time, and final verified/pending totals with the
share filename. Long batches explicitly show that work continues; no fabricated
whole-operation percentage or ETA is shown. The result stays visible until Close.
No new GUI dependency, gameplay instrumentation or verification contract is added.

Cancel, window close and Escape during work request cooperative cancellation.
The UI waits for the verification worker, private child jobs and storage lease
cleanup before showing the cancelled result. Completed work and captured input
remain resumable with Resume pipeline verification.cmd. Failure is also visible;
technical details remain in the console. Tab/Enter/Space use the native button.
GT5P_COLLECT_VERIFY_UI=0 restores the previous console-only path; verification
itself stays enabled. The window consumes one bounded in-memory status snapshot,
without monitoring checkpoint files or changing atomic file publication.

The user's new foreground collection finishes independently under the Phase-202
helper: 1,353 verified records / 478 original programs, zero pending, exit zero.
That session's original verified envelope and prepared-cache selection are
snapshotted unchanged through a separate frozen UI cancellation/resume proof.
Cancel at the native phase returns 2 after cleanup; Resume independently checks
all 1,353 native pipelines/persistence and returns 0. The resumed window shows
1,353 verified, zero pending, elapsed about 35 seconds with warm checked caches.
This is a retained-cache acceptance run, not a fresh-session timing comparison.
Window-only working, cancellation, success and failure views are inspected.

Sequential native UI tests cover retained counts across heartbeats, success,
failure, button/close/Escape cancellation, and worker cleanup before completion.
Collection tests cover UI routing, console rollback and unchanged verified-only
publication/pending isolation. Contribution, package and private-job lifecycle
regressions pass. A final private frozen helper builds with the existing decoder;
checksum/packed-reader tests pass. A frozen missing-input check rejects visibly,
publishes no share and closes via Escape with exit 1. The initial UI test harness
mistook the venv launcher's PID for the actual Python window owner; using the
base interpreter fixes only the probe. No product process or cache was stopped.

Private evidence: scratch/human-collection-20261103-084525, scratch/c203live
(real frozen cancellation/resume), scratch/c203final (frozen failure/keyboard),
scratch/c203final2 (final frozen failure/keyboard), scratch/c203checks (focused
logs), and scratch/c203h3 (final helper). No game-data
copy, renderer/runtime change, new starter acceptance, release or CI run. Main
and published v0.2.2 remain unchanged; development push uses [skip ci].

## Phase 202 - Automatic post-play contribution verification (2026-11-03)

At the user's request, opt-in collection now retains its captured metadata and
automatically verifies it after the normal launcher-owned game exits. The game
gets no new asset scans, compiler work, instrumentation or queue changes. Saved
settings still gate collection to the existing supported default context. The
post-play pass locates original programs, reconstructs both stages, checks exact
native keys and driver persistence, and exports only prepared rows. Unknown and
rejected rows stay private in pending-template.json. No data is uploaded or
accepted into the starter automatically; maintainer original-asset/native proof
remains mandatory. The starter remains 4,450 records / 1,581 programs.

The private collected-template.json survives before verification starts. A
storage-relative last-session pointer supports Resume pipeline verification.cmd
without another game launch. Verification holds the normal launcher's exclusive
storage lease and its own checkpoint lock, uses a separate cv/<identity> output,
and never changes prepared-cache.txt or seeds from the played shader cache.
Ctrl+C or a session verify.cancel marker interrupts; completed lookup and checked
shader/native cache files resume. An interrupted unfinished search restarts its
bounded lookup. GT5P_COLLECT_VERIFY=0 retains pending input without a share file;
explicit Resume requests verification. Completed exports are immutable; a later
successful promotion of pending records publishes an additive digest-named file.
Partial native-process completion cannot authorize publication.

The separate metadata-only search-map.json contains 592 verified original
SHDS-bearing/reference archive containers (2,865,176,912 decoded bytes), beyond
the starter's 165 members. The maintainer builder checks existing numeric archive
locations against a private listing, hashes original reference containers, and
verifies every decoded packed member against the original volume/ELF. No names,
keys, program bytes or compiled contents are published. Existing count, 4 GiB
decode-map, 128 MiB member/oracle and 600-second search bounds remain. The FP
oracle path now uses the bounded END-derived identity length once per program,
instead of normalizing each file at every unrelated requested length. All
original volume/ELF/member/program hashes still gate reconstruction.

Hidden offline children are created suspended into a private kill-on-close job
atomically, then resumed; cancellation/timeout/owner death retires only owned
processes and descendants. Existing bounded vertex jobs remain unchanged. Real
Windows normal-exit, failure, timeout, cancellation and nested-owner-death tests
pass while an unrelated sentinel process survives. Synthetic policy checks cover
verified-only publication, unresolved/rejected pending rows, cancellation/resume,
unchanged selected cache, immutable/additive exports and pointer traversal.
Search/map/package, contribution, template, translation and report checks pass.

A frozen retained-session proof uses the original 1,484-record dealership export
and an older 3,102-record install/map. Wider search independently locates all 419
missing original programs in 353 containers, about 109.15 s. Cancellation at the
native stage publishes no share and keeps all pending input and the old cache
selection. Resume recompiles no shaders and prepares/persists all 1,484 native
pipelines; all 534 session program identities resolve. Incompatible-volume retry
rejects without changing the existing verified export or selected cache. Total
cancel/resume/rejection harness time is about 261.82 s; the final resume proof is
42.39 s. These are one PC/driver with preserved OS/driver caches, not cold-driver
or general performance guarantees.

An actual packaged foreground HSR collection at 1080p/2x/16:9 (aniso16, smooth
colour, retained Integra fixture, 4,450-record prepared seed, PS3_VERBOSE=0) closes
normally and starts verification automatically. All 1,632 exported records / 715
programs pass, pending zero. The fresh post-play pass compiles 216 VP variants and
1,403 exact FP requests, then creates/persists 1,632 native pipelines with zero
application-cached driver calls, about 215.58 s. The printed verified envelope is
metadata-only; the selected preparation cache stays selected. Window-only menu,
intro/race/mirror samples and presentation are inspected; collection I/O and a
short variable route make this unsuitable as a stutter comparison. No new starter
acceptance or rendering guarantee for every captured car/settings context.

The initial end-to-end harness attempt safely refuses before launch because its
explicit isolated GameRoot was not bound to GT5P_USER_DIR. The collector harness
now binds it and permits a bounded 1,800-second post-play wait (configurable),
instead of assuming export finishes within 120 seconds. The retry completes
through automatic verification with exit zero. A packaging fixture was updated
for the new Resume CMD; the archive listing's identical aliases are deduplicated
while conflicting physical locations reject.

Evidence stays private: scratch/c202q (retained-session frozen proof), c202h2
(private helper build), c202live and scratch/lod-camera/game/pipeline-contributions
(actual normal collection); c202p retains the safely failed test bootstrap.
The tested 225-file package SHA256 is
412b4d7297a3d13b6832b35373b6b1ba9f7dfc2ebd389075956d88d669f3159f.
Final strict repackaging, with the README's current program/member counts tidied
and identical tested engine/helper binaries, produces SHA256
649c4ebfb37f5a33dd1a05be1cb826c2f9958dfba5245d6aadfcf147a052fd8b.
Every build/compiler/native/synthetic/game operation owns the common Windows
validation mutex through all children and cleanup. The existing owned game
fixture is reused without another full game-data copy. All caches/evidence remain;
no shared runtime, main/tag/release, CI build or normal asynchronous policy change.
Push this feature branch with [skip ci].

## Phase 201 - Verified dealership contribution enters the starter (2026-11-03)

The user authorized original-asset shader/native proof and starter acceptance for
dealership test 1. All 1,348 unambiguous additions pass; the starter now contains
4,450 records / 1,581 original programs (443 VP, 1,138 FP). Every prior 3,102
record is preserved exactly. This is observed default-context coverage, not a
whole-game, GT5, arbitrary-settings or stutter result.

The initial bounded packed search locates 80 of 419 new programs in the existing
104 mapped members plus ELF (197.84 s); 339 remain unresolved there. The existing
maintainer SHDS catalogue and extracted reference assets supply all remaining
locations. A fresh local archive listing agrees with all old numeric locations;
the expanded numeric volume map covers 165 members (61 additions). Direct packed
verification hashes the original volume/ELF, every decoded container and all
1,581 program slices: 166 containers including ELF, 1,432,884,744 decoded bytes,
about 11.19 s. Original reference assets/runtime remain read-only; no new full
extraction or game-data copy is made.

Fresh candidate preparation (empty application cache, preserved OS/driver caches)
compiles 124 exact VP variants and 718 exact FP requests in bounded workers. All
1,348 reconstructed native keys create and persist; native summary is
requests/created/driver_calls/cached_blob_calls = 1348/1348/1348/0. End-to-end
preparation takes 150.66 s. The local contribution acceptance gate verifies the
exact candidate digest, both-stage proof rows and driver inventory before merge.
Player/supplemental maps add 419 verified original program identities.

Observed notifier membership adds 1,342 menu keys. Six additions have no observed
phase membership and are not guessed into the plan. The coherently reissued plan
has 1,466 menu / 2,113 race keys, 3,546 distinct, pinned to the new bundle digest.

The first full frozen acceptance catches a Phase-200 bug: native chunk progress
supplied completed/requested without the total expected by the player UI. It
fails before native creation and leaves the old selection/cache intact. Both
default and additive-translation callbacks now supply total. A fresh private
helper build and full retry pass rejection, cancellation/resume, unchanged old
source cache, all 4,450 native pipelines and local shader packs. Actual native
chunks are 4,096 + 354; aggregate counts are 4450/4450/4450/3102. The old generation
contributes 356 reused VP variants; 91 new variants and 690 exact FP requests are
compiled. Resume wall time is 299.53 s (265.23 s internal preparation), with a
clean PATH. The frozen regression now aggregates every bounded native log instead
of expecting a single oversized native summary.

A separate visible production-engine replay uses a copy of the passing frozen
cache, 1080p/2x MSAA/16:9, aniso16/smooth-colour defaults and the retained fixture
save (Integra Type R '04 on My Page). Provenance/coverage collection is off and
PS3_VERBOSE=0. The owned window is activated with computer-use; the existing
guest-pad dealership route reaches DealerTopRoot and the Acura NSX showroom.
Four window-only shots span 60 s, reporting 29/30/30/30 FPS; inspected first/last
shots show complete car bodies, glass, wheels and floor reflections as the camera
moves. This is a rendering/presentation sanity check, not a controlled stutter
comparison or visual acceptance of every new dealership/car/translation. The
last inspected metrics still report four shader compiles and 129 demand PSO
jobs; prepared template coverage is partial and does not eliminate demand work.
The owned game exits and mutex releases; no other game/process is stopped.

Focused template, contribution, warmup-plan, shader-pack and translation
regressions pass. Final coherence checks verify all old records and archive rows
are unchanged, complete program/container coverage, the pinned plan digest, both
fresh/frozen native results, and the failed fixture's retained selection/cache.

Private evidence remains under scratch/dealership-collection-20261103,
scratch/d201p (fresh proof), d201f (preserved failed fixture), d201g (passing
frozen growth), d201live (window-only replay) and d201h2 (private helper build). The strict 223-file candidate
package contains no game/cache data; SHA256
d2d7e8bfe31b94922c028583913db80a5882f77fb9bf8dbe95b53c4368b51758.
All compiler/native/build/package tests own the shared validation mutex through
children and cleanup. Published release, main, runtime defaults, async policy and
driver/user caches remain unchanged; push only this feature branch with [skip ci].

## Phase 200 - Bounded catalogue growth after dealership collection (2026-11-03)

The first user dealership session exported 1,484 metadata records, excluding three
branching vertex contexts. Normal review initially hit the 4,096-record template
cap. With this change the same review reports 1,348 additional candidates, 136
known records, zero conflicts and a proposed union of 4,450. There are 90 new VP
and 329 FP identities. Shader/native proof remains pending: the starter stays
3,102 records, with no map, warmup-plan or compatibility identity change.

Catalogue metadata now permits 65,536 records, 512 shards of 128 records, a
128 KiB index and 128 MiB total payload. Existing bundle bytes/checksums/schema
remain valid. Asset maps permit two locations per catalogue record, bounded to
64 MiB. Preparation report readers scale separately from live diagnostic limits.
Collection remains 4,096 records/session, with 32 MiB combined review input.

Default and additional-translation native preparation now issue sequential
manifests of at most 4,096 requests, retaining the native runtime limit. Each
chunk requires successful completion counts; per-record exact keys and final
cache persistence remain required. Translation counters aggregate across chunks.
Cancellation/progress is checked between chunks; native.log remains the first
log, with numbered later logs. No runtime/default/draw-policy change.

All checks own Local\Tourline-Prologue-Isolated-Validation with process preflight
and finally release. An 8,193-row metadata round trip spans 65 shards. A stubbed
8,500-request native run partitions exactly as 4,096/4,096/308 with aggregate
counts and separate logs; cancellation stops after one chunk and incomplete
completion rejects. Template, contribution, coverage, runtime-report, translation,
asset-map and synthetic player-package regressions pass. An initial contribution
regression caught a captured default byte-bound argument; dynamically selecting
the default restores the configurable guard. Real test-1 normal review passes.

Private evidence: scratch/dealership-collection-20261103/review-test1 and the
original share file, SHA256
9c9a00f6b5acd7817178994a9250bbf33f4850ed17a3595ff74750cbcffc7939.
Large native chunk execution is stub-verified, not a new 8,500-pipeline native or
frozen-helper acceptance. Worker, shader-pool, checkpoint-tree, warmup/pack and
residency budgets remain independent and may reject large preparations; no full
65,536-row execution claim. Next locate the 419 new original programs, prove
candidate shaders/native keys, reissue coherent maps/plan and validate rendering
before acceptance. GT5 needs its own verified game/renderer contract. No release,
main/tag merge, CI build, cache removal or whole-game coverage claim. Push [skip ci].

## Phase 199 - Frame-correlated allocation hitches and bounded texture retention (2026-11-02)

This work uses the isolated `feature/lod-camera-stutter` worktree at shared base
`cc47cee`, with the provenance runtime/reference build inputs read-only. Only
private backend objects, runtime library and executable are rebuilt. Authored
runtime changes are separate patches; no shared runtime, release/player engine,
starter or preparation contract changes. Every build, native/analyzer test and
game route owns `Local\Tourline-Prologue-Isolated-Validation`, preflights existing
processes and joins/cleans only its own children before releasing the mutex.

Five-second counters could not locate the reported close-car/mirror or
pre-gameplay-camera hitches. The separate default-off
`ps3recomp-frame-hitch-trace.patch` adds bounded batch-level timestamps, existing
PERF stage snapshots, shader/driver/demand completions, successful DXBC file-read
time, texture resource allocation/decode/hash/Map/copy/SRV splits, Present and
foreground state. It writes at most 32,768 buffered rows, without per-draw log
bursts. Unset/empty/`RSX_HITCH_LOG=0` rolls it back. Async stage completions are
correlations, not critical-path durations; stage times overlap. Guest model/file
streaming remains uninstrumented. See docs/frame-hitch-diagnosis.md for details.

The route harness now records actual screenshot intervals, including encoding,
and can require foreground during intro/sampling. A first route's early intro
was background and is excluded from acceptance; its later foreground samples
remain diagnostic only. A second route rejects safely at the grid when Windows
refuses SetForegroundWindow. Native computer-use activation of the exact owned
private executable permits the subsequent foreground routes. They independently
record foreground throughout both reported windows and actually present frames.
All window images and original/cache bytes remain ignored/private.

Settings are HSR, the fixture's Honda Integra Type R '04, 1080p/16:9, 2x MSAA,
anisotropy 16, smooth colour, VSync and existing async shader/PSO policy. The
expanded Phase 197 learned cache is copied, with runtime packs and indexed
warming enabled, provenance/coverage recording disabled and `PS3_VERBOSE=0`.
OS/driver caches are preserved and uncontrolled. The final rollback/LRU pair
uses the same engine SHA, identical starting menu/race pack and membership
hashes, identical save SHA, separate copied application caches and fresh
processes. Save SHA-256 is
`3ab57a9b25480e399e870a5737f9e7222b022c401f6a8fed80091328b6a0855a`;
the verified ELF is `8ee3523e8c05d6a27d3cc32f6caeb530059473e8b9ae04ad92fdbfb677603036`.
This is prepared application-cache testing, not application/OS/driver-cold proof.

The rollback close-car burst at grid +44.696 s lasts 152.834 ms. Replay is
142.778 ms, including 101.065 ms texture handling and 67.042 ms creating
163 texture/167 staging allocation calls. Decode is 0.413 ms, replacement hashing
4.913 ms, Map 0.856 ms, copy/barrier recording 2.259 ms and uploader SRV
creation 0.421 ms. Present is 0.296 ms, the measured frame-start GPU wait is
0.011 ms and the previous GPU sample is 4.617 ms. Shader compiles, driver PSO
calls and successful DXBC file reads all have zero deltas in this interval.
It does not overlap a screenshot. This falsifies shader/PSO compilation as the
cause of this particular burst; it does not exclude unmeasured work elsewhere.

The existing cache chooses the first unused slot after exact lookup, even when
an older unused texture remains elsewhere. The separate
`ps3recomp-texture-slot-lru.patch` adds opt-in `RSX_TEX_LRU=1`: choose the oldest
unused slot, retaining empty preference, exact dirty/replacement hits and the
same-batch protection/exhaustion rule. Unset/`=0` retains first-unused behavior.
Capacity remains 1,024 slots; no worker, scan, draw wait or queue policy changes.
More useful retention can change resident byte sizes, so memory is measured.

The final same-engine ordered pair gives the following backend display-batch
interval results. Windows are relative to observed grid arrival, not guessed
from screenshot numbering. Intro 16 is still overhead (rollback +18.403 s;
LRU +18.475 s), intro 17 is gameplay (+19.597/+19.657 s), bounding the camera
handoff. The 16..19.5 s approach/handoff window includes the preceding hitches;
it is not a sub-frame camera-state probe. Close-car shots at about +39.5 s show
reflected nearby cars; by about +50 s the pack has passed. Individual car/LOD
identity and the exact reflection-enable threshold remain untraced.

| Window / metric | First-unused rollback | LRU repeat |
| --- | ---: | ---: |
| Camera approach 16..19.5 s: texture allocations | 285 | 96 |
| Camera approach: allocation wall ms | 135.9 | 47.9 |
| Camera approach: max interval ms / intervals >50 ms | 105.7 / 5 | 96.3 / 2 |
| Close cars 40..47 s: texture allocations | 1,404 | 95 |
| Close cars: allocation wall ms | 597.9 | 49.4 |
| Close cars: p99 / max interval ms | 75.0 / 152.8 | 27.0 / 73.9 |
| Close cars: intervals >50 ms | 13 | 2 |
| Sampled peak process private MiB | 3,380.2 | 3,361.3 |

An earlier LRU route independently gives 96 close-window texture allocations,
52.8 ms allocation time, 30.9 ms p99 / 81.2 ms max and three intervals >50 ms.
An earlier foreground first-unused route gives 1,485 allocations and 156.2 ms
max. The early pair predates the extra texture substage probes; only the final
pair uses identical instrumentation/engine/cache seed. This is an alternating
exploration, not randomized/ABBA or multi-GPU acceptance. AI/game progress differs
slightly even with the same scripted route. Both LRU samples retain a roughly
94..99 ms pre-camera hitch: reduced churn is not a solved camera transition.
All final-pair shader compile counters remain zero; warmed native calls and
demand counts still differ slightly. Coverage/readiness are separate concepts.

The actual production selector loop passes 10 native cases in each mode with
fake resource handles: empty preference, protected/exhausted current batch,
hit recency, dirty/replacement generation, incompatible shapes and ties. This
does not prove GPU lifetime. Live inspected intro contact sheets, close-car
mirror shots and later race shots retain cars, reflections, scenery, track and
HUD; no new missing-draw regression is evident in those samples. Three analyzer
checks validate offscreen joining, screenshot/focus flags, counter/clock/reset
rejection and explicit killed-writer tail handling. Private builds pass. Raw
trace prefixes are timing evidence, not successful-shutdown/coverage snapshots.

Evidence in this worktree: `scratch/lod-camera/{foreground,lru1,rollback1,lru2}/`
contains context/frame/trace/shot/memory data and analysis; `comparison.json`
contains fixed-window totals. `first/` and rejected `second/` remain preserved.
Native selector evidence is `scratch/texture-slot-policy-b8d6b272cd0c4b9f87e3ad9881f6e614/`.
All caches and the private game copy remain. Next investigate genuine first
resource creation and non-allocation prepass work at the camera handoff, and
identify the exact car/model/LOD/streaming events before broadening attribution.
The experiment stays default-off, outside the shipped runtime patch. Main,
published v0.2.2, tags, launcher/preparation defaults and CI are unchanged;
development push uses `[skip ci]`.

## Phase 198 - Review replay overlap and retain translated fragment progress (2026-11-02)

The second packaged Phase 197 HSR replay contribution is reviewed against the
expanded starter. All 1,951 records already occur in the 3,102-record baseline;
there are zero additional records and zero conflicts. The contribution's
canonical digest is `4530c155ff9c5224efc04f62cf43c789bd5178aea97862dbb2d215d1f3ad8bfe`.
No records are promoted, so the template shards, program lookup maps and
observed phase-plan bundle remain unchanged. This review is overlap evidence,
not another native verification or whole-game coverage percentage.

The actual gaps rank as follows for this thread: another identical HSR capture
has no demonstrated marginal coverage; a new asset/shared-pass rule could scale
but still needs its native applicability oracle; translated fragment checkpointing
is a bounded, directly testable improvement now. `ConvoluteResampleX` at
`00820488`, bound from `0081E048`, remains a lead. No profile is added without
lookup, descriptor-edit and draw-packet evidence. Initialized LV/absent-resource
rules remain explicit, and 349/1,497 conditional retained-link matches remain a
different denominator from observed starter/runtime coverage. Archive-wide
discovery and broader contribution settings likewise remain open.

Additional native-scaled/ultrawide preparation now checkpoints each completed
chunk of at most 256 distinct exact fragment requests, retaining duplicate-record
joins and dither separation. Each chunk requires successful owned offline exit,
the guest-entry guard, a complete result join, matching summary request count,
valid source identifiers and bounded DXBC. A missing completion marker still
rejects; its intermittent cause is not diagnosed here. Publication/checkpoint
errors propagate instead of becoming compiler failures followed by more work.

The content-addressed shader manifest and its checkpoint are saved before the
progress hook polls cancellation. Resume revalidates manifest identity and every
retained shader before skipping work; exact native keys and persisted driver
blobs are still required before a player cache can be selected. The same ordering
also retains the last accepted translated vertex at a publication cancellation.
`GT5P_PREPARE_FRAGMENT_CHUNK=4096` restores the previous maximum batch size;
values 1..4096 are supported, and an invalid value rejects before preparation
starts for additional translations. Size changes on resume keep the same shader
semantics/generation. Default-only batching remains at 4,096 requests.

Sequential synthetic checks cover the 256/14 boundary, duplicate joins, result
and completion-count rejection, cancellation, publication failures and invalid
sizes before launch. Seven translation checks include corrupt/hard-linked shader
rejection and early invalid-chunk rejection. A fresh 32-record original-packed-game
native proof cancels after eight accepted fragment requests. Resume reuses all
eight and every translated vertex; both ultrawide-native and native-scaled pass
all 32 exact native keys and persistence. Default shader bytes and default-only
rollback sidecars stay unchanged. This bounds repeated work after interruption;
it is not a measured full-starter speed improvement. Smaller chunks add process
startup overhead and an interrupted chunk can still repeat.

A rebuilt frozen helper passes the same 32-record player path from original
packed files under System32-only PATH. Real helper cancellation retains eight
manifested fragment results while leaving the prior selected marker cache byte-identical;
resume reuses all eight, creates/persists all 32 translated native pipelines,
and switches selection only after success. A completed-cache rerun with the
4,096-request rollback starts no fragment processes and reuses all 32 records.
An invalid chunk size preserves selection and every translation-sidecar byte.
This bounded frozen run takes 70.00 seconds including cancellation/resume and
negative/reuse probes, with warm OS/driver caches; it is not a benchmark against
the previous implementation. The build also passes all eight checksum and nine
packed-reader checks.

Initial harness attempts are retained as negative evidence. Reading an actively
replaced checkpoint with ordinary Python opens can block Windows replacement;
the harness now observes player status and reads the checkpoint after exit.
An overly deep fixture path also exceeds the existing native reader path budget
and rejects all 32 native requests safely. The harness preflights that budget
and uses a shorter ignored output. Neither failure changes the old selection or
justifies weakening native/marker validation. Production long-path support and
intermittent missing completion-marker diagnosis remain separate work.

Evidence in this isolated worktree: `scratch/expansion-198/review/`,
`native/validation.json` and the rebuilt `helper/` under `scratch/expansion-198/`.
The successful frozen evidence is `scratch/f198b/validation.json` and adjacent
cancel/resume/cached/invalid-chunk logs. Earlier failed fixture outputs remain in
`scratch/expansion-198/frozen*` and `scratch/f198/`.
All validation/build/compiler operations own
`Local\Tourline-Prologue-Isolated-Validation`, with process preflight and finally
release. No shared runtime or other checkout is modified. Source/program/cache
bytes stay ignored; every failed-run cache/evidence directory is preserved.
No new settings/MSAA/asset-rule coverage, live rendering/stutter result, runtime
draw-policy change or release follows. Push this feature branch with `[skip ci]`;
main, the shared baseline branch and published v0.2.2 stay unchanged.

## Phase 197 - Real collection, packed lookup and verified starter expansion (2026-11-02)

The frozen opt-in contribution command now has a real-player acceptance run.
It starts the ordinary packaged launcher using private storage, a copied prepared
cache, the verified original disc folder and saved 1080p/16:9/2x settings. The
existing HSR script reaches the race, saves window-only screenshots and closes
the owned game normally. Export produces 1,582 complete metadata records, with
five branching-vertex joins excluded. Review against the prior starter finds
210 new records and zero conflicts: 168 use existing program identities, while
42 need at least one new original-program location. No private recorder/program/
source/cache files enter the contribution or tracked tree.

The initial route wrapper incorrectly reports failure after a successful export:
Windows PowerShell loses the redirected Start-Process object's exit code. The
collector itself returns normally and prints its successful JSON. The harness
now retains its owned process handle before exit and queries the exit code from
that handle. `race.ps1 -PlayerLauncher -ContributionCollector` drives the existing
helper -> launcher -> game chain, uses saved settings instead of renderer
overrides, waits for export and keeps collector logs separate. It never searches
for or terminates another session's game. Ordinary route modes are unchanged.

Searching the private installed game-data copy locates only one of 19 additional
program identities. `pipeline_volume_search.py` adds a maintainer-only alternative:
search existing verified GT.VOL members and the ELF directly, using recorder
programs as anchors. Original archive, ELF, complete decoded member and full
program identities must all match before a numeric location is accepted. It
does not trust captured bytes as preparation input, scan guest memory, write
extracted assets or invent archive locations. Unknown programs remain unresolved.
Bounds include 128 MiB of oracles, 128 MiB per decoded member, 8,192 recorder
files, 16 traces, 4,096 anchor candidates and ten minutes. The existing archive
map caps total decode and member count. Oversized members are skipped explicitly.
Synthetic checks cover decoys, endian conversion, identity failures, archive/ELF/
member rejection, memory/file limits, cancellation and unresolved results.

The packed search finds all 19 programs in already mapped containers: 104
containers searched including the ELF, 1,057,541,560 decoded archive bytes and
19.84 seconds locally. This is a bounded known-member search, not a whole-archive
shader catalogue. A fresh candidate preparation from original packed files
reconstructs 58 vertex variants and 196 exact fragment requests, then creates and
persists all 210 native pipelines with exact keys. Total 51.17 seconds, with warm
OS/driver caches; this is preparation work, not gameplay hitch measurement.
Proof-gated acceptance appends only these verified records. All previous records
are preserved, including their original shard encoding wherever shards are full.

The development starter now has 3,102 records / 1,162 program identities
(353 VP, 809 FP). Player/supplemental maps contain 1,162/305 locations; the same
104 archive-member map remains sufficient. No new member or key parameters are
guessed. The phase plan is rebound to the new bundle and merges only successful
candidate keys actually present in the private runtime notifier lists. It has
124 menu / 2,113 race entries, 2,204 distinct. Seventy-six new records lack that
recorded membership and receive no guessed phase. Existing plan evidence remains.

A rebuilt frozen helper under System32-only PATH grows a prior generation from
packed game files. Invalid metadata and actual cancellation preserve selection;
resume verifies all 3,102 records and driver blobs, reusing 351 vertex variants,
compiling five additional vertex variants and 44 exact fragment requests. All
3,102 native requests create successfully, with 2,892 cached-blob driver calls.
The old source cache stays byte-identical. Completed local packs/indices publish
only after native verification. Resume wall time is 145.91 seconds in this run;
it includes lookup, verified reuse, compilation, native creation and publication.

The actual candidate ZIP contains 213 allowlisted files and no game/cache data;
its SHA-256 is `f383c8afee6336daee257c0a0c158a5e3cabb9878fe704e56a87e6d2053543ef`.
Its normal launcher/helper completes a second HSR collection route with the
expanded private cache. The harness returns zero and the collector exports 1,951
records, excluding three branching joins. Saved menu/grid/race/mirror window
shots were inspected; no new missing-draw regression is evident in those samples.
Different draw/AI workloads and recording I/O prevent treating these sessions as
a controlled stutter comparison. A screenshot cannot establish that the reported
first-use mirror hitch is fixed.

Separate offline native-scaled and ultrawide-native checks each prepare all 210
new records plus all 210 locally derived pipelines with exact calibrated native
keys and persisted driver files. They retain the default records and compile
both required stages through the existing modes. These are additive 210-record
proofs, not a new single-batch full-starter translation measurement or live
ultrawide acceptance. Contribution collection still rejects these settings.
Focused template, contribution, lookup, warmup, pack and package checks pass
sequentially. The final packed-search memory/file/cancellation tests pass too.

Evidence: `scratch/contributions-197/route/`, the private recorder and exported
share file under `Storage/pipeline-contributions/`, `review/`, `new-locations/`,
`packed-locations/`, `new-native-proof/`, `accepted-template.json`, `warmup-audit.json`
and `frozen/validation.json`, `replay/`, `settings-rs/`, `settings-uw/` and
`validation.json`. The earlier installed-data search is retained as
negative lookup evidence. No whole-game coverage percentage, GPU residency,
consistent stutter reduction or mirror LOD fix follows. Broader contribution
settings and mirror first-use diagnosis remain open. Published v0.2.2, main/tag,
runtime, queue ownership and asynchronous draw policy are unchanged. Push only
development with `[skip ci]`.
Automatic approval review blocked removal of the private temporary game-data
copy; it remains under this phase's Storage folder. Every shadercache is preserved.

## Phase 196 - Metadata-only community pipeline contributions (2026-11-02)

The referenced Helghast discussion predates/overlooks this fork's existing
format-2 shareable templates. Both-stage SHA-256 identities, translation state,
native descriptor/input layout, source/bytecode IDs and renderer/root-signature
compatibility already exist. Hash lists alone cannot reproduce pipelines. The
missing practical path was player collection, safe sharing, review and acceptance.

`pipeline_contribution.py` adds version-1 `tourline-pipeline-contribution` JSON:
only schema/version, canonical template SHA-256 and the validated format-2
template. No path/annotation/source/binary fields are allowed. Unknown fields,
duplicate JSON fields, checksum changes, nonfinite numbers, excessive nesting,
incompatible contracts and oversized inputs reject. Bounds include 32 MiB total
submission bytes, 16 submissions and the existing 4,096-record template union.
This checksum is integrity metadata, not contributor authentication or proof.

Review reuses the existing overlap analysis and conflict quarantine, producing
only additional unambiguous candidate records plus a local review report.
Baseline records remain intact. No key conflict is settled by upload order or
majority. A local session's exporter now quarantines its first conflicting row
as well as subsequent versions, rather than retaining the first one. Maintainer
acceptance requires exact candidate-file identity, all successful native keys,
driver inventory and full default-stage counts from their own preparation report.
It writes a new merged template and never edits the shipped starter automatically.
User-supplied reports are not trusted as local verification. New program lookup
maps and a reissued phase plan/full package proof remain shipping prerequisites.

The helper gains opt-in `--collect-contribution` / `--export-contribution`.
`Collect pipeline template.cmd` is added to the package allowlist. Collection
reads the same storage selection, checks supported default settings and the
installed game/template contract before launch, then starts the ordinary launcher
with the existing local recorder enabled only for that child. The launcher owns
game/job/locks/restarts as before; async policy is unchanged and no other game is
stopped. After normal exit and unchanged settings, the helper exports one
`share-this-template.json`. No upload, cache selection or deletion occurs. Private
recordings remain in the adjacent private-recorder folder and must not be shared.
Collection requires 1 GiB free, an ASCII recorder path under 448 characters and
uses a 4,096-link limit. Current collection rejects ultrawide/scaled translation,
anisotropy/precision overrides and unsupported settings. Recorder I/O is diagnostic;
unsupported/branching/missing recipe joins remain excluded. No session-wide
percentage or readiness claim is derived from the export.

Synthetic checks pass schema/privacy/size/depth/duplicate-field rejection,
incompatible contracts, cross-submission and same-session conflicts, known/new
record deduplication, exact local proof gating, preserved output/input files,
storage lookup, opt-in child environment and unchanged async settings. Existing
template/coverage/pack/package checks pass sequentially. A rebuilt frozen helper
exports a single retained record through a constructed local recorder fixture,
whose original VP/FP programs are resolved from the verified packed game. Review
finds exactly the deliberately omitted baseline record; fresh preparation compiles
both stages, reproduces its key, creates/persists one native pipeline, and the
proof-gated accepted union matches every original starter record. This is a
workflow/reconstruction check, not a new player capture or additional coverage.

The frozen collection command also passes with a small native launcher probe:
unsupported settings reject before launch; supported collection discovers the
selected storage, propagates the private recorder, preserves async settings and
exports the expected record while cache/settings bytes stay unchanged. No real
game or GPU device is launched by that probe. Real-player collection and broader
context acceptance remain to be exercised before release. The repository gets a
manual metadata-contribution issue template; no issue/message is sent by tools.

Evidence: `scratch/contributions-196/validation.json`, `community-one.json`,
`review/`, `native-proof/`, `accepted-template.json`, `collector-native/` and the
private constructed recorder fixture. Those original program bytes stay ignored.
See docs/pipeline-contributions.md for player and maintainer commands. Shipped
starter, main/tag/release and normal play are unchanged. Push with `[skip ci]`.

## Phase 195 - Preserve learned caches when repeating preparation (2026-11-02)

Review of Grok's Phase 194 default/release integration reproduced two workflow
bugs. Ordinary runtime learning changes the pack byte order/content and notifier
indices; the strict seed publisher then rejects a repeated player preparation.
The generation token also contained only a constant pack marker, so a plan-only
update selected the same output and failed its changed checkpoint contract.
The strict publisher itself remains useful for controlled developer outputs;
the player needed generation selection before invoking it.

The helper now includes the canonical validated plan hash in its generation
identity. Whitespace-only JSON edits retain the identity; changed plan content
gets a new family, even with unchanged engine, decoder and template. No-pack
identity stays compatible. Existing v0.2.2 packed generations are preserved and
can supply verified hints through the existing incremental-reuse path.

Before resuming a completed player output, the helper compares its phase lists
to the plan and pack identities to the successful publication report. Changed
learned metadata selects another deterministic generation. The existing reuse
path imports only verified template shaders/driver hints from the selected cache;
it never imports packs or notifier membership. Unchanged complete outputs resume
without allocating another cache. Interrupted forks resume their own output.
Native-stage completion before pack/index publication remains resumable, including
the narrow owner-death interval before the subsequent stage checkpoint.

Selection checks are bounded (64 slots per identity, bounded local state/report/
membership and streaming pack reads). Pack hashing polls cancellation, including
the existing publisher's resume checks. Invalid/redirected/hard-linked inputs
still reject. Generation exhaustion preserves every cache. Different learned
files are never overwritten. Cancellation/failure keeps the selected pointer;
only full successful preparation can switch it. Additional generations consume
local storage; unknown learned shaders/pipelines remain in the earlier cache,
and the new generation handles uncovered draws through ordinary demand work.
No automatic cache cleanup, runtime/queue/draw change or new stutter claim.

Synthetic regression exercises actual `player_prepare.main`, checkpoint,
reuse and publication code with only native production mocked. It changes a
valid pack's entry order and appends a genuine prepared membership key, then
cancels a fork, resumes it and checks every byte of the learned generation and
the pointer. An unchanged rerun stays in the same generation. A plan-only change
gets a new family and reuses verified work. Pack-only changes, cancellation
during selection, generation cap and intermediate native completion are covered.
Existing pack, plan, template, translation, settings and verified-reuse checks
pass sequentially. Direct library resume remains intentionally strict; developers
use a fresh output and `--reuse-cache` after runtime learning.

Validation uses a private rebuilt frozen helper, the published v0.2.2 engine,
copied original ELF, read-only packed game and private cache copies. See
`scratch/preparation-fixes-195/` for frozen helper and full native evidence,
and the new `--learned-cache-repeat` mode of `player_prepare_reuse_native.py`.
The clean-PATH native run passes all 2,892 pipelines using verified reuse, then
reorders its private menu pack and adds a genuine prepared notifier key. The
next run selects another generation; cancellation preserves the learned cache
and pointer, and resume prepares/verifies all 2,892 pipelines with no new vertex
or fragment compiler processes. Every byte of the learned generation, including
its checkpoint/report/requests, is hashed before and after and stays unchanged.
Both new packs publish only in the fork, and selection switches after success.
Evidence: `frozen/validation.json`, `frozen/learned-validation.json` and their logs.
The final helper rebuild also passes archive cancellation, incompatible-volume
rejection and simulated intermediate native-completion resume without creating
another generation or starting shader/native work (`archive-final/`).
Published v0.2.2 assets, main/tag and all original caches remain unchanged.
Feature pushes use `[skip ci]` and do not trigger another build.

## Phase 194 - Prepare local shader packs before first draw (2026-11-02)

The user confirms the rear-view reflection/LOD hitch in both Phase 193 modes
and their own sessions. No timestamp or repeatable transition capture identifies
its cause yet. Three native-key misses recur in both earlier runs; additional
misses differ. Neither those misses nor their target formats prove mirror
ownership. No missing template entry or asset rule is invented from that guess.

The production path shows another concrete gap: native keys require shader
bytecode, and the existing pack lookup precedes the per-file/memory DXBC path.
Offline preparation did not build those packs. The earlier indexed log confirms
menu/race packs both start with zero shaders, then learn during play. Its sampled
`dxbc` total is 7,923 ms despite only 12 shader compiles. That total includes
cache lookup/allocation and compilation; it is not isolated disk time or evidence
that the mirror transition caused those samples. Async lookup still checks file
existence before the cached lookup; packs do not remove every file operation.

`preparation_shader_pack.py` builds the existing `GT5PSPK1` local cache format
from both shader stages of explicit observed default-template phase targets.
Source-key to bytecode hash/length mappings must be consistent. All needed DXBC
files are verified before writing. The plan/report/template must agree; unknown,
unprepared, corrupt, missing, redirected or hard-linked dependencies reject.
Caps are 64 MiB/12,288 entries per scope, 128 MiB unique payload, 4 MiB per input
and a polled 60-second work budget. No workers, compiler calls or runtime changes
are added. This is not an independently generated pipeline set or new coverage.

Explicit developer `pipeline_template.py prepare --warmup-plan ... --shader-packs`
publishes packs only after successful native preparation, under its existing
checkpoint lock. The contract pins pack version 1. Existing learned files are
preserved/rejected; resume accepts identical generated files, publishes a missing
scope and does not accumulate temporary files. Cancellation/write failure cleans
only this attempt's unique partial temporaries; complete cache files remain.
A standalone command reads an idle source cache and writes only packs plus
metadata in a fresh locked ignored output. No game-derived bytes are tracked.

Synthetic both-stage identity, deduplication, missing/corrupt/conflicting inputs,
byte/count/time caps, learned-file preservation, cancellation during verification
and second-file writing, partial publication and actual checkpoint enable/resume/
rollback checks pass. Existing phase-plan/template/translation, frame-statistics
and benchmark-storage checks pass sequentially. The native probe compiles the
actual production pack-reader block and verifies every loaded blob against the
template's bytecode hash/length, missing-key behavior, retained caller references
across scope changes and disabled mode. No device or game is created by that probe.
Its first failed run selected the ordinary root cache because the harness used
Win32 SetEnvironmentVariable rather than updating the C runtime environment;
it read existing packs without adding shaders or saving them. The harness now
uses `_putenv_s` and passes against only the isolated generated packs.

The standalone build verifies 1,978 distinct source keys / 28,148,188 bytecode
bytes. Its menu pack contains 145 entries / 2,150,276 bytecode bytes; race has
1,873 / 26,533,912. File sizes including headers are 2,152,028 / 26,556,400 bytes.
Native-reader hashes match every entry. A separate full packed-game preparation
passes all 2,892 records, exact native keys and persisted driver blobs with zero
vertex compiles; all 2,892 driver calls use cached hints. Total is 170.69 s,
including 10.22 s for packs. This reused-shader run is not a fresh-compile speedup.
Generated pack SHA-256 values agree between the standalone and integrated paths.

The benchmark's explicit `paired-packs` mode starts both conditions with identical
indexed warming, async settings and fresh copies of the same prepared files.
Only seeded trials get generated packs; both keep runtime packs enabled and
learn normally. Two trials use unseeded/seeded; four use ABBA. Existing source
packs reject rather than being deleted. Memory, shader/driver/demand counters,
pack load diagnostics, coverage and screenshots are captured. Cleanup's exact
new labels are tested; all shadercaches and evidence stay intact.

The user explains that earlier low-FPS test windows were affected by the PC
going to sleep, now fixed. Those failed collections remain excluded; the refused
foreground request alone did not establish the cause. The user will keep the
new test visible. Starter metadata, async policy and the runtime stay unchanged.

The visible paired run finished both 90-second High Speed Ring windows. The
user reports that the second window, the one seeded with shader packs, had much
less stuttering. The race-window sample agrees: unpacked 37.7 FPS, interval
median 21.4 ms, p99 121.7 ms, max 1,306.7 ms, 57.5% of intervals over 20 ms;
packed 49.4 FPS, median 17.0 ms, p99 44.1 ms, max 425.5 ms, 24.9% over 20 ms.
The racing half (45–90 s) is 36.8 FPS with p99 131.7 ms and four gaps over
250 ms without packs, against 51.5 FPS, p99 42.9 ms and no gap over 250 ms
with packs. Menu/race packs loaded 145 and 1,873 shaders in 15 ms and 31 ms.
Sampled DXBC time fell from 7,861 ms to 759 ms. Shader compiles did not fall
(87 unpacked, 107 packed), and native warmup stayed 2,103 loaded pipelines in
both. This is one ordered pair, unpacked first, so the packed run also had
warmer OS and driver caches. It is not an ABBA result, a mirror-LOD isolation,
or a claim that hitches are gone. Evidence:
`scratch/shader-packs-194/paired/report.json`.

Default-translation player preparation now builds these packs. Developer
`prepare --warmup-plan` does the same unless `--no-shader-packs` is set. The
library `shader_packs=False` default stays, so an explicit call without the
flag remains pack-free and the resume/rollback checks above still hold. The
helper bundles `config/pipeline-warmup/gt5p-disc-v2.json` and passes it only
for translation `default` (720p/1080p 16:9, including the first-run preset).
`native-scaled` and `ultrawide-native` do not take a phase plan. The
preparation token mixes `shader-packs-v1` when packs are on, so an older
unpacked generation is left in place and can be imported. `RSX_SHADER_PACK=0`
disables runtime pack use without deleting caches.

Evidence: `scratch/shader-packs-194/packs/`, `prepared/`,
`scratch/shader-pack-native-2f4c53ae06844f5d8c1f781b8f6b6976/`, synthetic
`scratch/shader-pack-test-*`, and `scratch/shader-packs-194/paired/`.

## Phase 193 - Observed phase membership for native warmup (2026-11-02)

The prepared generation had shader bytes, native recipes and driver hints, but
no menu/race membership. The existing worker therefore had nothing targeted to
replay before those draws. This change feeds that worker observed membership;
it does not add another worker, invent phase ownership, or scan all recipes.

`pipeline_warmup_plan.py` exports/merges bounded version-1 metadata. The checked
developer plan at `config/pipeline-warmup/gt5p-disc-v2.json` intersects genuine
historical local notifier indices with successful default-stage preparation.
Of 6,234 distinct menu and 8,192 race entries, 124/1,979 match verified starter
keys. There are 2,070 distinct targets, with 33 shared by both scopes. Remaining
keys are excluded. Historical scopes include prepass requests and prior content;
they are not first-use evidence, a new pipeline-coverage percentage, or a proof
of narrower track/car ownership. Only hashes/identifiers are tracked.

Developer `pipeline_template.py prepare --warmup-plan <plan>` validates template,
version, default translation and key membership before lookup. The canonical
plan digest joins the checkpoint contract. It stages menu/race indices only
after every requested pipeline and its persistence validate. Resume accepts
identical membership, finishes partial metadata publication with unique temporary
files, and preserves/rejects changed learned indices. Changed plans cannot resume
the same generation. Omitting the option leaves the default contract and path
unchanged. Source cache indices and the preparation reference report retain
their recorded hashes. There is no launcher pointer, helper, player-default,
main/tag or release change.

The full packed-game native proof succeeds in a fresh application cache using
verified hints: all 1,143 programs located, all 2,892 records prepared and native
keys matched, 351 vertex variants and all fragment jobs reused, zero vertex
compiles. All 2,892 native batch requests create pipelines; 2,755 calls supplied
cached driver blobs. Lookup hashes 2,052,954,112 archive bytes in 8.84 s; native
batch time is 66.25 s and total preparation 181.34 s. These are one reused-cache
preparation, not a measured speedup. Both phase lists publish after validation.
An initial plan preflight compared the report's template digest with the compact
checkpoint identity; rejection occurred before output creation. It now uses
the established `template_digest()` report identity.

Synthetic export, key filtering, bounds/version/template rejection, merge,
partial publication, actual checkpoint contract mismatch, resume, unsupported
translation and default rollback checks pass. Existing template/translation
checks pass. The production queue extracted into the offscreen D3D12 WARP test
passes demand priority, coalescing, owned bytecode/semantics, loading timeout,
resident/source caps, startup-to-race transition and concurrent shutdown checks.
The ordinary async draw and queue/shutdown implementation is unchanged. These
native tests use synthetic shaders and do not establish live stutter reduction.

The benchmark adds explicit indexed and paired-indexed modes. The paired mode
uses the same prepared cache files for both demand-only and indexed conditions;
four trials use demand/indexed/indexed/demand. Only private copied indices differ.
Normal source/cache bytes remain untouched, and the existing worker validates
recipe/code/root-signature/native state. Cleanup now recognizes the exact new
trial labels while preserving cache and junction-target guards; its tests pass.

Two initial route collections missed menu navigation at about 4 FPS. The visible
owned window was not foreground; Windows refused the harness's activation call.
The previously measured engine reproduced the slowdown. The user offered to
bring the test window forward for the paired retry. These failed collections
provide no performance/coverage result. Their disposable game copies were
guardedly removed (8,389,650,628 bytes); every log, cache and fixture remains.
The user then brought the test forward and a same-cache HSR 1080p/2x pair
completed. Both conditions start a fresh process/private copy of the same
prepared disk files; these are not empty disk shader caches. Async draw policy
is the same, and OS/driver caches remain warm and uncontrolled.

| Measurement | Prepared files, demand only | Prepared files, indexed warming |
| --- | ---: | ---: |
| Demand jobs queued/completed | 2,336/2,336 | 169/169 |
| Total driver calls / calls supplied cached hints | 2,336/2,331 | 2,239/2,232 |
| Runtime shader compiles, last sample | 6 | 12 |
| Grid arrival from launch, seconds | 66.77 | 65.73 |
| Early 45-second p99, ms | 192.2 | 162.1 |
| Early intervals >50 ms / >250 ms | 83 / 13 | 66 / 8 |
| Later 45-second p99, ms | 20.8 | 21.8 |
| Later intervals >50 ms | 5 | 5 |
| Sampled peak private bytes, MiB | 3,302.7 | 3,416.9 |

Indexed warming reports 124 menu and 1,979 race-ready entries, 2,070 distinct
held native objects. Startup finishes in 36.19 s; the subsequent race gate
reuses its full list in 0 ms. Loaded/hit totals include bookkeeping and shared
entries: 2,103 loads and 3,807 warm hits are not distinct draw hits or GPU
residency. The structural benefit is fewer demand jobs, not the elimination of
driver creation: most driver work moved earlier. Early frame times improve in
this pair, while later p99 and >50 ms counts do not. Both still have >1.3 s
maximum intervals. Memory rises about 114 MiB. A single ordered pair with
different complete draw-key sets is not a consistent stutter-win claim.

The coverage join remains valid: demand matches 1,036/1,040 complete keys and
indexed matches 1,038/1,045. Shader-pending submissions (60/90) are excluded.
Additional draws/misses and the different shader-compile totals show the
workloads are not identical. The original three misses occur in both trials;
the indexed trial has four additional misses. No template record is added.

Both inspected routes are HSR. The early demand screenshot is overexposed;
the indexed 20-second screenshot shows normal track/sky/car/mirror rendering,
and its later 60-second image retains track, scenery, HUD and mirror. This is
limited visual evidence, not full rendering acceptance. Both disposable game
copies are removed by the guarded cleanup, with every cache/log/shot retained.
Keep the developer plan explicit pending repeat routes, translation/settings
coverage and player integration.

The user reports a hitch when cars in the rear-view mirror cross from distant
nonreflective LODs to nearer reflective LODs, in both test windows and their own
sessions. That is a reported hotspot, not an established compilation diagnosis.
Next correlate remaining first-use pipeline/shader work with the transition and
check repeated model/texture/upload work; do not assume prewarming alone fixes it.

Evidence: `scratch/loading-warmup-193/local-plan/`, `prepared-with-phases/report.json`,
`prepared-with-phases/native.log`, `prepared-with-phases/preparation-state.json`,
`preparation.log`, `cleanup.json`, isolated `build/`, both failed collection logs
and the paired trial directory. Focused tests keep small synthetic fixtures in
`scratch/warmup-plan-test-*` and `scratch/benchmark-storage-*`.

## Phase 192 - Runtime pipeline-key coverage measurement (2026-11-02)

The user selected `GT5P` as the working checkout. Local continuation branch
`feature/shader-runtime-coverage` starts at `e600f96`; the previous player-setup
worktree and unrelated files are preserved. Two Grok tasks implemented the
collector/report tool; parent integration, fixes, builds and tests are sequential.

The separate `ps3recomp-pipeline-use-coverage.patch` adds default-off
`RSX_PSO_COVERAGE=1`. Its pre-diagnostic backend blob is `e573d203`, matching the
tracked compatibility overlay. It is not wired into the release/default patch.
Only executing guest-fragment draws record complete `guest_pso_hash` keys with
the existing root-signature policy. Prepass, warmup, offline preparation and
renderer fallbacks without a guest fragment are excluded. Shader-incomplete
submissions are counted separately, repeatedly across frames; they are not keys.

The collector stores at most 16,384 keys in 32,768 slots (about 288 KiB).
Overflow invalidates the percentage. Initialization is atomic; set/snapshot
access shares an SRW lock. Shutdown has no diagnostic instrumentation, preserving
its existing wait/ownership policy. Native cap rejection without a final callback,
deduplication, zero-key, concurrent-snapshot, pending and disabled-mode checks pass.
The shutdown check is a source invariant, not a simulated join-timeout test.

The initial prepared log had new keys after its last five-second summary.
The parser correctly withheld its full-route ratio. Each new key now also emits
a snapshot under the same lock, alongside periodic snapshots. First overflow
also immediately emits an invalid snapshot, even with no later callback. No summary
was fabricated or raw log edited. First-key/snapshot IO can affect frame timing.

`pipeline_runtime_coverage.py` joins only successful preparation rows with
matching native results and validated driver inventory. Translation rows need
consistent derived/parent-key and native-batch evidence. Templates alone, bad
schemas, failed HRESULTs, nonfinite completion times, counter resets, malformed,
inconsistent or truncated snapshots cannot produce a reassuring percentage. Counts
are bounded, large native counters work, inputs stay unchanged and output must
be a fresh ignored directory. Parser/rejection/CLI tests pass. This is a report
key-set intersection; the tool alone does not prove selected-cache provenance,
GPU residency, actual driver acceptance of a cached hint, or an avoided hitch.

The existing benchmark gains optional `--coverage-report` paired with its cache,
and `--condition` for a single diagnostic trial. It records launch conditions and
report hashes; a control reference intersection does not mean its empty cache
contained those files. Optional graceful close addresses only the owned window,
then retains existing owned-process cleanup. Async draw policy is unchanged.
Window close does not guarantee backend shutdown; the harness can still need its
owned-process kill. A consistent snapshot alone proves neither orderly shutdown
nor route completion. Sampling completion is recorded separately by the harness.
Disposable game copies are removed by existing guarded cleanup; every cache,
log and screenshot remains. The private fixture materializes the known PDIPFS
junction into copied install data; source saves/game files are not written.

The diagnostic engine verifies all 1,143 original programs from GT.VOL/ELF and
prepares all 2,892 starter records in a new private generation, using verified
local hints. A final-engine revalidation matches every native key and uses cached
driver hints on all 2,892 native batch calls. An initial command omitted its
location map and rejected safely. An initial incremental link selected the older
runtime library; pending result sentinels were rejected. The corrected link uses
the isolated library and a separate successful generation. All game-derived
outputs stay local. The shipped template and player defaults are unchanged.
An initial compiler output path also touched the primary backend object; that
object was restored by recompiling its configured baseline. The primary EXE
was not relinked. Diagnostic engine/library outputs are in ignored scratch.

The 1080p/2x MSAA/VSync HSR route uses private saves/install data, 90 seconds of
grid/race sampling, `PS3_VERBOSE=0`, existing async policy and demand startup
without a blanket recipe scan. OS/driver caches remain warm and uncontrolled.
An early banked-corner shot was initially misidentified as Daytona; subsequent
HSR signage and matching minimaps establish High Speed Ring in both trials.

| Measurement | Empty application cache | Initial prepared trial |
| --- | ---: | ---: |
| Runtime shader compiles, last sample | 1,731 | 16 |
| Driver calls / cached-hint calls | 853 / 0 | 2,345 / 2,338 |
| Demand queued / completed | 853 / 853 | 2,345 / 2,345 |
| Grid arrival, seconds from launch | 65.56 | 65.75 |
| Early 45-second p99, ms | 65.3 | 220.3 |
| Later 45-second p99, ms | 56.3 | 21.2 |

The control's 465/468 complete keys match the reference set (99.36%), although
that run selected an empty cache. Its 3,510,917 shader-pending submissions and
initial black scene/HUD show why this is not a complete draw-workload comparison.
The scene later recovers. The initial prepared trial reaches many more complete
keys but its incomplete final summary withholds the percentage; it also briefly
shows overexposure before recovery. This pair does not establish a consistent
stutter improvement. Warm-set hit/resident counters stay zero under this demand
policy; that is not a count of actual GPU-resident pipelines. Driver calls also
include prepass work, so they need not equal distinct executing-draw keys.

The final single prepared route with per-key snapshots passes complete accounting:
**1,036/1,039 keys match (99.7113%)**, excluding 80 shader-pending submissions.
The final five-second sample reports 17 shader compiles, 2,224 driver calls
(2,221 supplied cached hints) and 2,224 completed demand jobs. Grid arrival is
66.74 s. Sampled peak working set/private bytes are 3,319,054,336/3,492,528,128.
Early/later p99 are 161.9/22.1 ms. This follow-up is not a new controlled pair;
later images show track, cars/mirror, scenery and HUD, but early transients
prevent a clean rendering/stutter claim. It is one save/car/camera/route/settings
combination, not 99.7% of the game or the independent asset-reconstruction metric.

Three keys miss in both conditions. Their recipes share one vertex bytecode
identity; it and the three fragment bytecode identities are absent from the
starter. This metadata lookup does not prove branching or independent recovery.
Next identify these programs/contexts and target loading-time native readiness
using actual phase ownership, then broaden content/settings/GPU trials. No broad
scan or synchronous-draw default is introduced. Main/tag/release stay unchanged;
development pushes use `[skip ci]`.

Final Grok review found and parent fixes address three defects: overflow needed
an immediate invalid snapshot rather than depending on a final callback; valid
translation batches can have zero driver calls (memory hits) or extra calls
(cached-blob rejection/retry); and diagnostic shutdown locking could exceed the
existing join wait. Shutdown instrumentation is removed rather than claiming a
bounded diagnostic shutdown. Native tests now reject an overflowing log with no
final callback, report the shutdown source check accurately, and parser tests
accept valid zero-call/retry batches while still requiring every key created.
The measured 1,039-key route stayed below the cap; its saved evidence is unchanged.
The corrected backend compiles separately in `review-build` (existing backend
warnings remain), and the revised parser reproduces 1,036/1,039 from the saved
inputs. No new gameplay/performance result is claimed for these collector fixes.

Local evidence under `scratch/runtime-coverage-192/`: `prepared-verified/report.json`,
`runtime-revalidated-report.json`, `prepared-route/report.json`, the final
`1-prepared/coverage/coverage.json`, original `paired/report.json`, all route
shots/logs, `miss-analysis.json`, `fixture.json`, build and revalidation logs.
Final native checks: `scratch/pipeline-runtime-native-0145855986594a739a3cf6d48692d0c5/report.json`.
The earlier native report's `shutdown_timeout_invalidates` field was only a source
assertion and must not be interpreted as an exercised join-timeout test.

## Phase 191 - Composable environment absence and publication gate (2026-11-02)

Developer `--environment-resource-path absent` selects only the environment
callback's null-resource branch. It can combine with `--shadow-resource-path
initialized-depth-lv`, unlike the older all-dynamic-resources-absent context.
Unknown shadow/mirror bindings remain unresolved unless independently selected.
The exact environment signature is `envMapSampler`, kind `0x901`, identifier 71;
the supported record's callback selector is zero. Duplicate units and declared
local/global conflicts still reject. This is an explicit binding-time condition,
not an automatic inference from an unobserved resource or constructor.

The extended native oracle executes real `00811FC8` initialization, `00811BD0`
owner lookup, `00810F20` gate, framebuffer setup/getter, `0082E240` publication and
`00D6CAA0` callback. Constructor owner `+8` is zero while gamma byte `+0x50` is 1.
The gate clears environment slot 0 before returning on the absent owner. Even
with a stale nonnull slot initially, the callback then emits the initialized
non-depth cube fallback with address `0x60010101`, filter `0x02022000`, clear
gamma and normalized coordinates. No rendering occurs in that branch.

Controlled nonnull-owner tests use the real `00811BC0` setter, `008111F0` /
`00811264` continuation and `00811688` gamma getter. The write at `00811448`-
`00811474` clears address bits 20..27, then writes gamma field 7 for a nonzero
byte or 0 otherwise, preserving bits 0..19 and 28..31. The filter is unchanged;
another real framebuffer getter preserves the result. All 768 combinations of
owner presence, four gamma bytes, three poisoned address words, two mip counts
and sixteen sampler units pass. Allocation, scene rendering and scene-state
boundaries are controlled. The original code is extracted into ignored scratch,
never tracked. A first callback assertion exposed a selector left by an older
test; the new probe now initializes its selector explicitly. A clean final run
exits zero, including the earlier callback/framebuffer/shadow regressions.

This validates the conditional writer, not a live active owner. The only named
setter has no direct lifted caller; this investigation also finds no raw data
reference to its OPD. Inlining, copying and indirect ownership remain possible.
The store of a nonzero holder on the exact context passed by `00706398` remains
unresolved. No active environment profile or guessed gamma variant is added.

The new option uses the existing disc-ELF gate and pins environment rule version 1
in resume identity. Omission restores previous construction in a separate output.
Changing a resumed context or combining it with all-dynamic absence rejects
without changing the output/cache. A real CLI identity/resume test with an empty
synthetic catalogue passes; wrong ELF and missing audit inputs reject before
output creation. The audit tool now preflights its input locations. An initial
read-only audit with a mistaken trace path was stopped and rerun sequentially
with the retained snapshot directory. No game/native compiler was overlapped.

Asset-only CCW/RGBA16-MSAA2/active-dither enumeration finds 7,684 distinct
conditional candidates; 58,683 eligible material definitions use the environment
fallback. The eight explicit RGBA16 contexts deduplicate to 60,798 candidates.
These are not all natively prepared or observed live. A fresh sample selects
32 mixed shadow/environment requests by authored unit combinations and program
pair diversity, with no capture input. Both stages rebuild; 29 distinct native
pipelines persist and independent root-signature/key/envelope checks pass.
The repeat uses cached driver blobs for all 32 requests.

The complete asset-derived manifest is frozen before the retained HSR oracle
is opened. Profile matches are 349/1,497 links, preserving all previous 345 and
adding four. A separate fresh-cache proof retrieves programs from the original
assets using the frozen manifest and verifies their hashes; captures select
validation cases only. All four new cases reproduce both shaders and exact
retained native keys with fresh numeric descriptors and supplied expected key
zero. Independent key/persistence checks and all four driver-blob reuse calls
pass. This is a small conditional reconstruction gain, not a starter expansion,
whole-game coverage or evidence of stutter reduction. Material texture/profile/
variant/shadow regressions and new environment conflict/unknown checks pass.

Player packed-file integration, actual live resource/pass ownership, remaining
shared contexts and runtime hit/stutter measurement remain. No renderer, queue,
draw policy, starter, player default, main, tag or release changes. Feature push
uses `[skip ci]`; original checkout and its processes stay untouched.

Local evidence:

- `scratch/global-registry-9bb1080d42d94c50a3c3250aa1630b3a/report.json`
- `scratch/a191-mixed/{manifest,report}.json`, `native-first.log`, `native-reuse.log`
- `scratch/a191-audit/{manifest,report}.json`
- `scratch/a191-matches/{candidate-contract,manifest,report}.json`, native logs
- `scratch/environment-191/{proof,prove_matches,cli_checks}.py`, logs and `cli/report.json`

## Phase 190 - Initialized LV shadow resource reconstruction (2026-11-02)

Developer material preparation gains explicit `--shadow-resource-path
initialized-depth-lv`. It reconstructs active shadow and shadow-colour bindings
from a fresh original framebuffer descriptor, successful local depth setup and
the enabled LV pass. It is separate from the absent-resource context; combining
them rejects. The verified disc ELF gates preparation and shadow rule version 1
is pinned in material resume identity. Omission restores prior construction in
separate output; player defaults, shipped starter, renderer and release stay unchanged.

The structural owner lead is `008178A8`: its shadow framebuffer at object +0x18
is initialized through `0082A210` with format enum `0x40` and flags `0x302`.
The isolated oracle executes real `00B9F430` / `00BA6998` initialization,
`00BA1080` with real `00BD0080` conversion and `00B9EE50` mip calculation,
the `008293A8` getter, `008103F0` pass, `0082E330` assignment/conversion and
both `00D6D930` / `00D6D898` callbacks. Resource allocation, scene rendering and
virtual dispatch remain controlled boundaries; this is not a complete live-owner trace.

The initialized primary has a 2D non-cube depth base format `0x90`, clear read
gamma, normalized coordinates and comparison 6. The LV pass gives address
`0x60030404` and filter `0x02022000` (sampler 9). Its copied colour descriptor
converts to non-depth base `0x85`, retaining those sampling/gamma/coordinate
facts. These are constructor/pass results, not values taken from the retained
shadow word reported in Phase 49. The old sampler-only `shadow-lv` path remains
partial. New facts require the explicit initialized resource context.

The producer/consumer oracle passes 576 success cases over poisoned incoming
storage, two dimensions, automatic/single/multiple mips, both callbacks and all
16 units. Corresponding allocation failures exclude the new chain. An initial
probe exposed incomplete allocation-mock metadata: the real allocator writes its
r7 mode at texture +0x23, which the getter uses for extents. The mock now writes
that field from the actual input; the rerun passes. No game/runtime fix is inferred.

A second native oracle extracts the production shadow-alias conditional, first
depth-format compare loop, sampled-unit trimming and default location predicate
from the isolated renderer. 6,159 cases cover alias disable/failure, local/main
location, cube/volume, format bounds, unused units and earlier unsampled depth.
The latter can change the compare. The profile rejects conflicting/unknown
earlier declared bindings and inconsistent reconstructed sampling facts. Unlisted
or stale earlier units must be absent or share comparison 6; default local alias
allocation must succeed. Those are explicit prerequisites, not recovered live facts.
Other alias redirects/later overrides remain excluded. Local depth uploads stay
unsupported, and ordinary profiles reject explicit shadow-compare facts.

Asset-only CCW/RGBA16-MSAA2/active-dither enumeration accepts 56,593 material
definitions, including 38,732 using initialized shadow facts, and deduplicates
to 2,630 conditional candidates. These are constructor candidates, not all
natively prepared pipelines. The eight RGBA16 face/target/dither contexts give
20,538 distinct candidates after deduplication. Their manifest is frozen before
the retained HSR oracle is opened. `audit_material_variants.py` exposes the
resource option and records its rule version. All 131 previous material-profile
matches remain, and 214 additional profiles match, for 345/1,497 retained links.
Every added match has sampled-shadow profile `0x62000`. Unknown active
environment/mirror resources still exclude materials; counts are not whole-game coverage.

Two separate empty application caches pass 32-request shader/native tests.
The prefix sample includes 27 shadow requests; the diverse sample has 32 distinct
program pairs across shadow-only and shadow/shadow-colour combinations. Every
request creates a distinct native key within its sample; the diverse repeat
uses cached blobs for all 32. A separate proof freezes the complete independently
constructed manifest, then uses the retained oracle only to select validation
cases. All 214 newly matched candidates rebuild both shaders, construct fresh
native state with expected key zero, and exactly reproduce their retained native
keys. No captured state/descriptor is copied into requests. Independent root-
signature/key recomputation and persisted-envelope verification pass all 214;
a second native run uses cached driver blobs for all 214. This validates the
newly matched keys under their explicit contexts, not every enumerated candidate.

The actual CLI resume passes all 32 prefix requests and cached-driver calls.
Rollback/context changes, contradictory absent/active choices and wrong ELF
reject without changing existing output/cache files; wrong-build output is not
created. Synthetic shadow/ordinary/fallback/variant/texture tests and template
compatibility checks pass. One read-only audit was started before the diverse
native check finished, then stopped; it was rerun after that check, sequentially.
No concurrent game/native compiler was started. Original checkout, assets and
processes stay untouched; no shadercache is deleted/moved and no game-derived
outputs are tracked. Feature push uses `[skip ci]`; no main/tag/release change.

This improves independent material reconstruction. The observed starter already
contains these retained pipelines; it is not reissued. Player packed-file
integration of asset-rule enumeration, active environment gamma/ownership,
remaining pass/shared contexts and measured live use/stutter reduction remain.

Local evidence:

- `scratch/global-registry-763c9062f129486783a46f950d0b1414/report.json`
- `scratch/shadow-resources-native-1e7ab98a9d2c49dab9ac94274b63cf8c/report.json`
- `scratch/a190-shadow/{manifest,report}.json`, `pipeline-batch-0.log`
- `scratch/a190-diverse/{manifest,report}.json`, `native-first.log`, `native-reuse.log`
- `scratch/a190-audit-final/{manifest,report}.json`
- `scratch/a190-matches/{candidates,manifest,report}.json`, native first/reuse logs
- `scratch/active-shadow-190/{oracle-final.log,backend.log,prepare.log,diverse.log,audit-final.log,matches.log,resume.log,rollback.json}`
- Ignored `proof.py`, `prove_matches.py` and `rollback.py` in that investigation
  folder retain selection, construction-before-oracle order and preservation checks.

## Phase 189 - Asset-derived dynamic fallback bindings (2026-11-02)

Roadmap item 3 gains another capture-free rule: developer material preparation
accepts `--dynamic-resource-path absent`. Exact original global records identify
environment (71), shadow (87), shadow-colour (96) and mirror (115) callbacks.
The explicitly selected null-pointer branches use initialized built-ins. No
capture selects the branch or supplies construction values. The verified disc
ELF gates the CLI before output creation/reuse; output identity pins dynamic
rule version 1. Normal player defaults and the starter are unchanged.

Real handlers `00D6CAA0`, `00D6D930`, `00D6D898` and `00D6D9C0` call the original
fallback constructors. `00BA6B40` supplies a cube for environment/mirror;
`00BA6C68` supplies a non-depth 2D shadow fallback. Shared `00BA6998` / `00BA6590`
initialization fixes normalized coordinates and clear read gamma. The emitted
address/filter are `0x60010101` / `0x02022000` (sampler bank 8). Address compare
bits do not imply a depth-compare profile: this format is non-depth. Active
resources retain their prior unresolved facts.

The isolated native registry oracle checks the initial fallback BSS is zero,
then tests cold initialization and warm reuse after a supplied unrelated
descriptor for all four callbacks at every unit: 128 complete fallback cases.
Actual emitted descriptor-derived shape/gamma/coordinate fields equal the rule.
The dynamic check total is 1,152, including previous supplied-descriptor cases.
Existing dither, environment, shadow, mirror, fragment-control and object-pass
checks pass. No guest gameplay starts; resource/allocation/render boundaries
retain the documented mock scope. Synthetic tests cover all 64 callback/unit
combinations and explicit face/target variants, independent dither gates and
wrong-build rejection. Existing texture/profile/variant/envelope tests pass.

The ordinary profile still rejects unsupported local cube/depth uploads. It now
admits the explicit initialized global cube fallback alongside ordinary 2D local
uploads. Unknown signatures, overlapping/duplicate units, unsupported paths and
contradictory active-resource options fail closed. A missing local scalar alias
still reserves its unit, so a global cannot silently resolve that ownership
conflict. Final enumeration confirms this conservative guard preserves the
measured inventory and prepared prefix sample. Missing local bindings remain
rejected. An original-asset scan of 601 containers / 1,106 models finds 115,339
eligible material definitions for CCW/RGBA16-MSAA2/active-dither/null-dynamic
resources. 97,478 use the new rule; deduplication yields 7,698 candidate profiles
overall. These are conditional constructor candidates, not all prepared native
keys or live coverage. Actual material/pass ownership remains unestablished.

Two separate empty application-cache samples pass both shaders, fresh native
construction and persistence. The prefix sample's 32 requests produce 21 distinct
native keys. A second 32-request sample selects authored binding-signature
diversity, then distinct program pairs, without capture input. It spans all four
callback signatures and ten signature/unit combinations, including low-unit
mirror cubes, shadow-only, shadow-colour and environment/shadow materials. It
produces 25 distinct native keys. The new read-only `material_preparation_keys.py`
recomputes every key from the serialized root signature, numeric descriptor,
both verified bytecodes and input elements; it checks initial requests have no
captured native state and verifies persisted driver envelopes. Both samples
pass. Requests sharing a native key are not counted as distinct pipelines.

The prefix repeat passes all 32 requests with 32 cached-blob calls. Omitting the
absent context on `--resume` rejects before modification; a different ELF rejects
before output creation. A complete file/hash snapshot confirms existing proof
cache/output preservation after both rejections. All tests and offline processes
are sequential. Original checkout/assets/runtime/processes remain untouched;
no shadercache is deleted or moved and no game-derived output is tracked.

Grok read-only investigations confirm active-material blockers remain the
shadow depth/compare/alias writer and environment gamma/ownership. Observed HSR
counts are ranking evidence, not reconstruction inputs. Shared wrapper `00820488`
/ caller `0081E048` makes `ConvoluteResampleX` a follow-up lead, but inherited
fixed-function state and descriptor packets need a native oracle. No third
shared profile is added by analogy. No live draw, stutter, whole-game or GT5
compatibility claim follows. Main/tag/release stay unchanged; push `[skip ci]`.

Local evidence:

- `scratch/global-registry-0d3c1743cea44d4d90382747da533133/report.json`
- `scratch/a189-absent/{manifest,report}.json` and `pipeline-batch-0.log`
- `scratch/a189-mixed/{manifest,report}.json` and `native.log`
- `scratch/a189-final-inventory/{manifest,report}.json`
- `scratch/asset-rule-189/{rank.json,global-verified.log,prepare.log,resume.log,mixed.log,rollback.json}`
- Ignored `scratch/asset-rule-189/mixed.py` records diversity selection/proof;
  `rollback.py` records preservation checks alongside their local outputs.

## Phase 188 - Validated settings selection becomes the player default (2026-11-02)

The user requested that new features become defaults once appropriately
validated. The development player helper now treats an unset
`GT5P_PREPARE_TRANSLATION` as `auto`. Explicit `=auto` is equivalent;
`=default` restores the old default-only preparation and bypasses settings
lookup. Explicit additional modes are unchanged. Developer template CLI/API
defaults stay explicit/default because they have no launcher settings ownership
contract. Preparation remains an optional first-run/CMD choice.

The promotion uses Phase 185/187's complete shader/native proofs, production
settings-parser parity and frozen lifecycle checks. Existing bounded batching,
packed-file reads, checksum acceleration, verified reuse/handoff, preparation
window/setup offer and managed restart were already defaults. Conditional
reconstruction experiments and blanket live scanning remain developer options;
their partial proofs or unproven frame-time effects do not establish suitability
as player defaults. No live draw-policy change is made.

Ten synthetic tests pass, explicitly checking unset settings dispatch and its
publication guard as well as no-lookup explicit rollback. The frozen helper is
rebuilt, retaining native checksum/packed-reader checks. The 32-record lifecycle
harness removes the translation variable for automatic legs and explicitly sets
`default` for rollback. It also verifies a default-only rerun leaves translation
sidecar JSON unchanged and preserves the selected pointer/cache. The full native
test harness now likewise exercises the unset selection default; full Phase
185/187 results remain the basis for shader/native coverage, rather than claiming
another full run for this dispatch change.

An initial ultrawide test aborts safely when an existing offline fragment process
exits without the required no-guest-entry log marker, despite printing its batch
completion summary. No relaxed guard or automatic acceptance is introduced; the
previous cache pointer is preserved. A fresh ultrawide repeat passes cancellation,
resume, exact/native persistence, zero-worker reuse, serial rollback, invalid
switches, settings-change rejection and explicit translation rollback. Initial
failure evidence is under `scratch/settings-default-188/frozen32-uw`; the passing
repeat is under `scratch/settings-default-188/uw`. The missing-marker condition
remains a robustness investigation, without claiming its cause is established.

The separate native-scaled unset-default 32-record run passes the same lifecycle,
settings-change rejection and explicit translation rollback. Both passing runs
confirm zero new compiler workers on cached reuse and unchanged translation
sidecar JSON under explicit `=default`. Evidence:
`scratch/settings-default-188/{uw,rs}/validation.json`. Final selection/template,
package and release-trigger regressions pass sequentially.

The shader roadmap now lists completed mechanics separately from remaining
runtime hit/residency and stutter work, representative content, asset-derived
generation, settings/context combinations, efficiency/robustness, multi-GPU and
release acceptance. Its next priority is measuring actual runtime use of prepared
pipelines and diagnosing the resulting misses/costs. Player documentation records
the new default and rollback. Feature pushes use `[skip ci]`; main, tag and the
published v0.2.1 release remain unchanged.

## Phase 187 - Automatic translation selection from launcher settings (2026-11-02)

The development player helper now accepts opt-in
`GT5P_PREPARE_TRANSLATION=auto`. It selects the existing `ultrawide-native` mode
for canonical saved 21:9, `native-scaled` for 16:9 native 1440p/4K, and default
for 720p/1080p. No file means the launcher's first-run 720p/16:9 preset. Unset or
explicit `default` remains the old default-only path; explicit additional modes
remain independent of settings lookup. No player default or published binary
changes. The generic developer template CLI continues to require an explicit
mode, since it has no launcher storage/settings ownership contract.

`preparation_settings.py` reads at most 64 KiB from one regular unlinked storage
file, hashes the snapshot and reports the request/resolution/reason in
`player_settings`. It never writes the settings. Unsafe/unreadable files,
unsupported types/values, non-ASCII storage paths, non-default anisotropy/export
precision and listed custom translation/root-signature overrides select only the
ordinary default preparation with a reason. This deliberately avoids reimplementing
arbitrary environment parsing. Existing template numeric state, including MSAA,
attachments and pass state, remains observed; this is translation selection,
not validation of complete coverage for the player's settings.

A final snapshot check before report/pointer publication refuses changed
settings. Completed cache files remain available for another run and the previous
selection is preserved. Sidecar identity still pins the actual explicit mode;
settings changes do not relabel shader bytes or invalidate older cache files.
Worker/queue/process ownership, cancellation and live asynchronous draws are
unchanged. No game data, source or cache contents are distributed.

Nine synthetic selection/read-bound/type/override/hard-link/snapshot tests pass.
A standalone probe links the actual production settings and key-map parsers;
its unused input/glyph application hooks abort if called. Twenty-four canonical
settings cases match, including numeric/string resolution, both aspect ratios,
UTF-8 BOM and non-ASCII comment content. An initial non-ASCII storage-path probe
exposed existing narrow environment-path conversion in that parser; automatic
selection now excludes such paths rather than claiming parity. This does not fix
the broader Unicode-path issue. Evidence:
`scratch/settings-auto-187/{parser-validation.json,build-final2.log}`.

The rebuilt frozen helper passes native checksum and packed-reader checks, then
sequential fresh 32-record automatic ultrawide and native-scaled paths with a
System32-only PATH. Both pass real vertex cancellation/resume, selected-mode
shader/native creation, zero-worker cached reuse, serial rollback, invalid-mode
rejection and prior-cache preservation. The native-scaled run also edits the
settings during a cached pass: it rejects publication with the expected error,
keeps the selected pointer and preserves original settings after test cleanup.
Evidence: `scratch/settings-auto-187/{frozen32-uw,frozen32-rs}/validation.json` and
`frozen32-rs/settings-changed.log`. Tests remain sequential, original assets and
the other checkout remain read-only.

The full automatic native-scaled path now passes all 2,892 default and all 2,892
scaled records from the user's original packed GT.VOL/ELF in an empty application
cache, with exact shader/key/native/persistence checks. There are 2,810 additional
native keys and 82 overlapping default keys. The extra stage starts zero vertex
compiler workers, using default vertex code; it has 2,312 unique fragment requests
and 2,260 actual new fragment compiles. All 2,892 native driver calls succeed;
82 use the default-stage cached blobs. Total default-plus-scaled wall time is
654.22 seconds on one GPU with warm OS/driver caches. This is a single preparation
proof, not a comparison or live-stutter measurement. The saved settings stay byte
identical and the selected report identifies automatic native-scaled resolution
1440p/16:9 with the matching settings digest. Evidence:
`scratch/settings-auto-187/full-scaled/{validation.json,summary.json,prepare.log}`.

Final selection/template/checkpoint/package/release-trigger regression suites
pass sequentially. The shipped template and live renderer are unchanged. Feature
commits use `[skip ci]`; no workflow build, main merge, tag or release is requested.
Remaining work includes broader numeric-state coverage, custom-setting/Unicode
support and live residency/stutter validation; no whole-game claim follows.

## Phase 186 - First-run preparation choice and managed settings restart (2026-11-01)

At the user's request, successful first-run file setup now offers **Prepare now**
and **Skip and play** before starting the game. Skip, Escape and closing the offer
continue normal play. Preparation uses the existing owned helper, progress UI,
packed-file lookup and cache contract. Cancel waits for the helper to exit and
continues into play, preserving completed work for the existing CMD resume entry.
Failures are reported and allow play. Already configured ordinary launches do
not offer again. `GT5P_PREPARE_OFFER=0` restores the old setup flow. Explicit
`--prepare` remains standalone and does not start the game.

The reported settings restart failure has a concrete ownership cause: the game
spawned its replacement inside the launcher's kill-on-close job. After the old
game exited, launcher cleanup could kill that replacement. New engine/launcher
pairs use a reserved process exit code when `GT5P_LAUNCHER_RESTART=1`; the launcher
waits and retires its old job before starting a replacement, retaining both
storage locks and normal logs/cache configuration. A fresh child inherits the
launcher environment, not settings-derived renderer variables from the old game.
The F1 action still saves changes before requesting restart. Unset selects this
managed path through the updated launcher; `=0` rolls back to legacy spawning.
Direct engine launches retain their earlier behavior. Both updated binaries are
required; a new launcher cannot repair an older engine's direct-spawn action.

The launcher builds cleanly under /W4. Sequential synthetic native checks pass
actual folder setup followed by Prepare, Skip, offer-close, custom/legacy UI
cancel, unavailable-helper fallback, offer rollback and setup cancellation.
Accepted setup reaches the normal child afterward; cancelled setup starts none.
A second ordinary launch does not offer again. Existing launcher checks also
pass managed replacement with distinct PIDs and saved settings, explicit packed
preparation, helper cancellation, duplicate-launch blocking, owner death, cache
selection and storage relocation. No test kills another session by name.

A private engine links the changed production settings UI against read-only CI
objects into this checkout's ignored output; CI objects/runtime and the original
checkout are unchanged. Through the actual F1 settings window, 720p -> 1080p,
16:9 -> 21:9 and 21:9 -> 16:9 each exit with the protocol code and reopen a new
game/settings window under the same launcher. Boot logs show saved 1080p and
ultrawide aspect patches only in the ultrawide leg. All four owned game handles
are signalled on cleanup. Original game files are read in place, no GT.VOL copy.
Evidence: `scratch/launcher-flow-186/production-final/{validation.json,*-play.out}`.
`scripts/test/settings_restart_native.py` is the ownership-safe production test;
the older process-name-killing PowerShell restart test was not used. Initial
test automation failures were premature window readiness/file-picker input,
corrected before the passing runs; they are not renderer regression evidence.

Documentation records the setup flow, CMD entry and rollback switches. No live
race/frame-time/rendering claim or new release follows. Development commits use
`[skip ci]`; main, tag and published v0.2.1 remain unchanged.

## Phase 185 - Calibrated local translation variants and verified reuse (2026-11-01)

Development preparation now accepts `--translation default|native-scaled|ultrawide-native`;
the player helper uses explicit `GT5P_PREPARE_TRANSLATION`. Unset/default retains
default-only preparation. Invalid values fail before generation/cache selection.
No automatic settings-file detection or shipped-template revision is introduced.

The default set must finish before an additive stage under the same preparation
lock. Vertex workers receive one sanitized explicit environment per process;
derive-frame results are independently hashed by the parent. Fragment requests
verify normalized instruction identity and checksum the actual asset payload.
The production D3D12 root signature is serialized locally and every default key
calibrated before deriving keys. Only shader identifiers/native keys and descriptor
bytecode-length words change. All other observed state, including MSAA, stays
fixed. Versioned bounded local sidecars retain/revalidate progress. Accepted shader
bytes, generated sources and driver data remain ignored and local. Demand policy
and worker/process ownership remain unchanged.

A complete fresh application-cache proof through the frozen helper reads the
original GT.VOL/ELF without another asset copy. All 2,892 default records and all
2,892 unique ultrawide-derived pipelines pass reconstruction, exact keys, native
creation and persisted driver-blob verification. The additional vertex stage
compiles all 351 variants with two workers, no failures. Its fragment stage has
2,312 unique requests and 2,260 actual new shader compiles. Its 2,892 native driver
calls use no supplied application-cache blobs. Total wall time is 905.66 seconds;
worker-job peak commit is 119,017,472 bytes (not total application memory). This
is one GPU with warm OS/driver caches, not a timing comparison or live-draw proof.
Evidence: `scratch/settings-preparation-185/full/ultrawide-validation.json` and
the adjacent logs. Root calibration separately matches all 2,892 default keys.

Sequential frozen 32-record proofs for each additional mode pass cancellation,
resume, zero-new-worker reuse, serial rollback and invalid-mode prior-pointer
preservation. Source proofs check unchanged descriptor fields/default shaders,
native keys and native-scaled reuse of default vertices. Nested owner death
retires both frozen vertex workers. Initial failures exposed a normalized-FP
identity mismatch in the new coordinator and overlong native fragment staging
paths; both are corrected and covered by regression checks. Evidence remains
under `scratch/settings-preparation-185/{native32-final,frozen32-uw-final,
frozen32-rs-final,nested-owner-final}`. Full native-scaled coverage is unmeasured.

The reuse optimization publishes only bytes just validated/copied in this locked
pass. File identity, size, link shape and timestamps must still match; otherwise
the consumer rereads/hashes. Pre-existing shaders are always verified. Combined
shader memory remains bounded. `GT5P_PREPARE_REUSE_HANDOFF=0` restores rereads.
Twenty-five synthetic checks and separate 32-record native parity/source-cache
preservation checks pass. A full-starter I/O probe eliminates 2,663 destination
shader rereads, but copy timing/order/driver-blob budget differ, so it establishes
no controlled total speedup. Old Phase 180 verification timing overlapped copying;
new loader timing is exclusive and docs distinguish the fields.

Final synthetic protocol/environment/key/calibration/reuse/template/checkpoint,
package and release-trigger suites pass sequentially. A Grok static integration
review finds no actionable correctness/integrity/ownership/bounds bug. Known
limits include batch-end fragment manifests and conservative duplicate vertex
budget accounting on resume. No rendering/stutter, unknown-binding, whole-game,
all-settings or release claim follows. Feature commits/pushes use `[skip ci]`;
main, tags and published v0.2.1 remain unchanged.

## Phase 184 - Default vertex batches and settings coverage audit (2026-11-01)

At the user's request, developer CLI/API and development player helpers now
default to the Phase 183 bounded two-worker vertex compiler. Explicit developer
`--vertex-mode serial` or player `GT5P_PREPARE_VERTEX_BATCH=0` restores serial
compilation. Unset/1 selects batching; other player values still fail closed.
Optional preparation remains optional. No worker, memory/time limit, template
schema, queue ownership, root signature or asynchronous draw policy changed.

Sequential checks pass: protocol/dedup/acceptance, actual CLI default/rollback
dispatch, template contracts/bundles, checkpoint/link ownership, nine reuse tests
and packaging exclusions/digests. A fresh frozen helper build with the unchanged
production decoder passes eight native checksum and nine packed-reader tests.
The player's running game was left untouched; native checks began only after
the user confirmed closing it.

The rebuilt helper is tested with the vertex switch **unset**, System32-only
PATH, original read-only assets and a 32-record subset. Cancellation preserves
two accepted vertices and prior selection. Resume uses two frozen workers,
reuses those vertices and creates/persists all 32 exact native pipelines. A
cached rerun starts zero shader compiler workers. Explicit `=0` serial rollback
revalidates the cache; invalid mode preserves selection. The source native
proof omits the API option for its batch leg: serial/default-batch each prepare
32 records in separate empty application caches with identical DXBC. Cancellation,
owner death and zero-worker resume pass. Evidence:
`scratch/vertex-default-184/{build.log,frozen32/validation.json,
native32.log,native32/validation.json}`. OS/driver caches are warm. This repeats
default selection/integration evidence, not the whole-starter performance or
live stutter benchmark.

The speed roadmap now identifies repeated cache inventory/reuse I/O and duplicate
per-pipeline shader staging as concrete next candidates. Phase 180's incremental
expansion measured 27.55 s verified hint copying, 30.50 s cache verification,
9.27 s packed lookup, 16.31 s fragment preparation and 18.55 s native batch work.
These unlike stages/run conditions must not be extrapolated into a promised
fresh-run total. Native checksums and fragment deduplication already exist;
integrity/native verification must remain. Additional worker concurrency needs
measurement and bounded memory/CPU before changing its limit.

The user also reported late menu-background visibility at ultrawide 1440p.
Native pipeline hashing contains numeric descriptor state, shader bytes, input
layout and root-signature compatibility; viewport/pixel dimensions are not
descriptor fields. MSAA/target/pass changes can still select new pipelines.
Importantly, the production vertex translator conditionally emits an ultrawide
edge epilogue (`RSX_ULTRAWIDE`), even though its adjustment values are per-draw
constants. A separate-process production-decoder probe of one identical original
VP confirms different source and DXBC with ultrawide enabled:
`scratch/vertex-default-184/resolution-probe.json`. Current offline defaults and
starter do not derive this additional variant from player settings. Repeating
default preparation cannot provide that coverage. Settings-aware preparation
needs explicit translation identities and exact native-key validation, not just
passing a resolution to an unchanged template.

The user's newest available player logs were inspected read-only. They show a
1080p/16:9, MSAA-4 run, so cannot diagnose the reported ultrawide occurrence.
Background native creation remains possible after offline disk preparation;
scene/asset loading is another unexcluded cause. No cache/settings were changed,
and no rendering regression or stutter fix is claimed. Main/tag/published v0.2.1
remain unchanged; feature-only push uses `[skip ci]`.

## Phase 183 - Bounded exact vertex compilation batches (2026-11-01)

The next efficiency step batches the previously serial vertex translation /
D3D compilation phase. One requested Grok agent implemented the worker module,
template/player integration and unexecuted protocol tests. The parent reviewed,
hardened, built and performed every executable check sequentially. No original
checkout/runtime source, generated output, shadercache or other process changed.

Developer `pipeline_template.py prepare --vertex-mode batch` and development
player `GT5P_PREPARE_VERTEX_BATCH=1` opt in. Serial remains the developer/player
default and rollback; invalid player values fail without changing selection.
At most two hidden persistent processes each own one production decoder and
compile sequentially, preserving its mutable C globals. Source/frozen sentinel
dispatch happens before normal preparation parsing. No vertex worker runs the
game engine. The parent validates exact program identity, source key and DXBC
hash before cache writes. Reused valid variants bypass workers entirely.

Review removed the proposed arbitrary inherited-job fallback: being in some
parent job does not guarantee cleanup when the helper dies. Workers require
atomic attachment to a private non-inherited kill-on-close job, including when
nested. Kernel commit caps are 512 MiB per worker / 1 GiB for the worker job.
The existing 128 MiB aggregate vertex-bytecode budget remains. Two in-flight
requests, bounded frames, a 180-second absolute per-job deadline and 60-second
startup deadline bound work. Cancellation polls while waiting; cleanup retires
and joins only owned process handles. Slow partial output cannot extend the
deadline, incorrect identity/extra frames retire a worker, and partial pipe
creation failure closes already-created handles. No worker respawn is attempted.
The final source/frozen build includes these hardening changes.

Original-asset lookup resolves all **351 starter vertex variants**; serial and
batch match every source/bytecode identifier and byte sequence. One sequential
local vertex-only comparison is **241.3568 s serial / 142.4041 s batch**. Batch
includes worker startup/decoder loading/shutdown; the serial timer starts after
in-process compiler initialization. Two workers compile all 351 with no failures.
Their job-reported peak commit is 121,061,376 bytes (115.45 MiB), with largest
worker peak 59,740,160 bytes. This is worker commit, not total application RSS.
Lookup and subsequent fragment/native work are outside those timings. It is
one hardware-local pair, not a multi-run or gameplay stutter result. Evidence:
`scratch/vertex-batch-183/all351/validation.json` and `all351.log`.

A separate 32-record sample (30 program identities, including CPU/GPU variants)
resolves both stages from original assets, then prepares serial and batch in
separate empty application caches. Both create/persist all 32 exact native keys;
their DXBC files match byte for byte. The direct vertex sample measures
11.0445 / 7.4607 s serial/batch; full sample preparation measures 21.3972 /
17.0647 s. OS/driver caches are warm and order is serial then batch. Resume
revalidates both stages/native keys with zero vertex/fragment compiler workers.
Real cancellation preserves accepted results and retires workers; killing the
test owner also retires its workers. The first attempt lacked the private fixture
ELF needed by offline engine startup; the test fixture was corrected and rerun
in a fresh output, preserving its earlier cache/evidence. Final evidence:
`scratch/vertex-batch-183/native32-final/{validation.json,serial,batch}`.

The final frozen helper is rebuilt with the unchanged production decoder and
tested under System32-only PATH against original assets and a 32-record subset.
Cancellation retains completed vertex files and the prior selection; resume
reuses them, compiles pending variants through two frozen workers, and verifies
all 32 native keys/persistence. A second run starts no shader compiler workers;
serial-default rollback also revalidates the same cache without compilation.
Invalid player mode leaves selection intact. An additional nested-owner proof
kills the frozen workers' owner while its outer job deliberately remains open;
both workers exit. Evidence: `frozen32-final/validation.json`, its logs,
`nested-owner/validation.json` and `frozen-final-build.log` under the same root.

Protocol/dedup/rejection/scheduler checks, template/bundle/contract checks,
checkpoint ownership/link rejection, nine reuse tests and strict packaging
checks pass sequentially. Helper builds also pass eight native checksum and nine
packed-reader tests. No game entry or live route/screenshot test was needed for
this offline compiler change. All supported shader bytes remain identical.
Template schema/contract, settings/root signature, branching exclusions, fragment
batching and asynchronous draw policy are unchanged. Coverage remains 2,892
observed records / 1,143 programs. This does not prove a single fresh native
batch of all 2,892 records or a gameplay stutter improvement. New helper/code is
feature-only with `[skip ci]`; main, tag and published v0.2.1 are unchanged.

## Phase 182 - Tourline Prologue title and v0.2.1 release (2026-11-01)

The user requested the preparation window title **Tourline Prologue** and a
v0.2.1 release containing the accumulated changes. Both the custom window and
its TaskDialog rollback now use that exact caption. The native UI regression
asserts it. The game title and executable names are unchanged. VERSION is
0.2.1, with authored `docs/release-v0.2.1.md`, updated player instructions and
the existing metadata-only 2,892-record starter.

The release includes Phases 176-181: verified incremental cache reuse, native
checksums, direct packed game lookup and bounded-deflate fixes, Fuji candidates
and the PC Settings-style preparation UI. Preparation remains optional; no
renderer/asynchronous draw policy change, complete-coverage or new stutter claim.
Existing cache generations and source game files remain intact.

Local preflight runs sequentially: warning-free launcher/UI stand-in builds,
both custom and legacy launcher integration suites, focused UI checks including
the exact title, packaging exclusions/digests, three release-trigger tests,
nine native packed-reader tests and nine cache-reuse tests. Evidence is under
`scratch/release-v021/{launcher-build,ui-build,launcher-native,launcher-legacy,
ui-native,package,trigger,volume,reuse}.log` and `screenshots/` (synthetic status).
No game was launched. Prior real shader/native/visual evidence remains Phase 180;
this UI/version delta does not repeat or expand its performance claims.

The user's request explicitly authorizes main/tag/release promotion and a
dedicated release build, superseding the earlier feature-only/no-build rule for
this release. Development pushes retain `[skip ci]`; the versioned workflow is
dispatched once after a fast-forward main promotion and tag validation. It uses
the dedicated runner/private caches, strict packaging and authored release notes.
Publication is recorded after the build rather than presumed by this preflight.

Release result: main was fast-forwarded and annotated tag `v0.2.1` pins
`4c346b23e78348754f58741e3b569920f7de24fc`. One explicit versioned
[workflow run](https://github.com/mathewdouglas/Tourline-Prologue/actions/runs/41276412072)
passed both the Windows build/validation/upload and GitHub-hosted publish jobs.
The published [v0.2.1 release](https://github.com/mathewdouglas/Tourline-Prologue/releases/tag/v0.2.1)
is named exactly `v0.2.1`, is not a draft/prerelease, and is latest. It includes
the 90,401,878-byte player ZIP and SHA-256 sidecar. Its digest is
`846d4b213213c5db60e99a76747413d00a22b66874e1825905ea94d2a800d47c`.

Independent checks of the completed ZIP pass CRC, all helper manifest hashes,
engine/helper release hashes, exact template/source equality, 2,892 records /
1,143 program locations, and game/cache/path exclusions across 206 selected
files. Public sidecar and GitHub asset digest match the local package, and the
published notes match the authored file. Evidence:
`scratch/release-v021/{preflight,dispatch,workflow-status,package-verification,
release-verification}.json`. These checks do not add a new real-game stutter or
whole-starter fresh-compilation measurement. The tag/package are immutable;
subsequent publication documentation uses `[skip ci]` without another build.

## Phase 181 - PC Settings-style preparation window (2026-11-01)

The user requested one Grok agent to implement a preparation window resembling
the in-game settings menu. That agent edited source only; the parent reviewed,
built and ran the executable checks sequentially. The standalone Win32/GDI
window follows the existing grey-28 panel, grey-178 heading, grey-76 rules,
dotted rows, black fields and red-focused pill button. The existing launcher
icon is passed through. Preparation remains optional; only explicit preparation
uses the new window. `GT5P_PREPARE_UI=0` restores the existing TaskDialog.

Phase, detail, per-step counts and Cancel are native accessible controls. The
status reader bounds the read itself as well as the accepted file size, so a
growing/replaced status file cannot cause an unbounded read. Invalid UTF-8 and
failed reads keep the last good status. Counts require a valid trailing decimal
fraction, positive total, completed <= total, and at most 18 digits per field.
Archive counts are bytes; other uncounted phases remain indeterminate. No
overall completion percentage, ETA or inferred shader/pipeline total is shown.
Unknown phases remain visible with bounded text. User-facing help explains that
additional pipelines may still compile during play.

The window reads status at most every 100 ms and waits for the existing helper
handle with a 200 ms timeout. Close/Escape/Enter/Space/Cancel request cancellation
without abandoning the wait. A failed cancellation write displays an error and
still waits. Creation failure falls back to TaskDialog; an unexpected window or
wait failure unwinds the existing owned kill-on-close process job. Helper exit
codes, successful selection, source verification, resume, logs and async draw
policy are unchanged. No renderer/runtime or helper implementation is modified.

The parent corrected the missing explicit `gdi32.lib` link, a shadowed-variable
warning, the status read race, and native print-client handling needed to capture
the custom drawing. Final launcher and stand-in builds pass `/W4` without
warnings. Both custom and legacy launcher integration runs pass configuration,
helper arguments, progress/cancel, cache preservation, duplicate ownership,
owned-child shutdown and storage relocation. Focused native checks pass valid/
invalid/large counts, UTF-8/file bounds, first-line/BOM handling, unknown phases,
completion, failed wait and repeated-window GDI cleanup. Sequential windows test
each cancellation input, compatibility message and failed cancel write, proving
the wait remains until the owned stand-in signals completion. A 144-DPI layout
message keeps Cancel inside the window; this is not broad multi-monitor/high-DPI
acceptance. No game or real shader compilation was needed for this UI change.

Evidence: `scratch/preparation-ui-181/{build.log,test-build.log,launcher-native.log,
launcher-legacy.log,ui-native.log}`, `screenshots/{vertex,archive,fragment,scaled}.png`
and `live-window.jpg`. Screenshots use synthetic status through the production
window, not measured preparation progress. The live Windows capture confirms the
heading, progress bar, button and focus ring; native capture is also inspected
after print-client support. No whole-game coverage, loading/memory performance or
stutter improvement is claimed. The starter stays at 2,892 records. Original
checkout/runtime/cache/processes remain untouched. Feature-branch source/docs
only, `[skip ci]`; no main/tag/release change or distributed game/cache contents.

## Phase 180 - Fuji Speedway F session and incremental coverage (2026-11-01)

The user requested more coverage with Grok assistance and strictly sequential
tests. One Grok agent extended developer course selection/provenance export;
another audited older local recordings. Agents ran no builds/tests/game processes.
The parent alone performed executable validation, one test at a time. No source,
runtime, cache or process in the original checkout was changed or interrupted.

An isolated session selected Course Select slot 2 by the existing Daytona route
plus one additional RIGHT tap, recording the menu/pit/grid/opening section with
the current car/AI lineup. It exported 2,167 supported records. Export excludes
three branching vertex contexts and eleven missing joined files. Comparison with
the verified 2,334-record starter quarantines nine conflicting FP identity/source
keys, preserving the existing baseline. The remaining 558 new candidates include
64 using existing program identities and 494 needing at least one new program.
No conflicting record is selected by order or majority. Research found no other
unconsumed supported session; older HSR/Daytona exports are already represented.

Incremental `pipeline_asset_map.py --known-map` skips existing verified locations.
All 167 additional programs (55 VP, 112 FP) are found in original assets with zero
invalid/unresolved oracles: 729 containers / 2,415,031,816 bytes searched in
162.515 s on this machine. The complete player map grows to 1,143 identities
(348 VP, 795 FP); the supplemental map has 286 locations, including the original
119 outside supported SHDS tables and all 167 new locations. New locations can
overlap SHDS lookup. The regenerated numeric volume map verifies all 1,143 programs
from 104 archive members plus the ELF, with the same supported volume/ELF hashes.
It decodes 1,198,534,632 bytes including the ELF without writing extracted assets.

Every one of the 558 candidates then rebuilds both shader stages in a separate
empty application cache, matching expected source/bytecode IDs and exact native
keys. All 558 D3D12 pipelines create and persist; zero unresolved/incompatible/
key-rejected records. The run compiles 93 vertex variants and 374 exact fragment
requests in two sequential engine batches. Total preparation is 115.601 s;
fragment work is 19.027 s. Native creation makes 558 driver calls with zero cached
blobs (11.532 s). OS/driver caches remain warm from collection. Evidence:
`scratch/coverage180-slot2/{coverage,export,promotion}.json`,
`new-locations/report.json` and `prepared/{report.json,native.log}`.

Only these positively verified records are appended: the starter now contains
2,892 observed-state records, with every previous record unchanged. Existing
2,334 and new 558 batches have separate empty-cache proofs; this is not a single
fresh-cache compilation of all 2,892. The frozen player helper under System32-only
PATH grows an older prepared cache using only packed game files. Invalid-template
rejection and real cancellation preserve the previous selection/source generation;
resume verifies all 2,892 shader/native keys and persisted blobs. It reuses 296
vertex variants / 2,395 fragment jobs, compiles 55 additional vertices and 322
distinct fragment requests, and passes 2,892 native calls with 2,335 cached blobs.
The prior cache included one matching ordinary-demand key beyond the old starter;
do not describe it as exactly 2,334 driver files. Evidence:
`scratch/c180-player/validation.json`. The regression has explicit `--expanding`
mode, retaining strict complete-cache expectations without that flag.

The prepared-cache replay exercises `race.ps1 -CourseSlot 2`. Its Race Mode
screenshot explicitly reads **FUJI SPEEDWAY F**, establishing the measured name;
the first collection's legacy window tag said Daytona only because that route
provided the base navigation. The new scripts expose `FujiSpeedwayF` as a named
route and report numeric identity explicitly. High Speed Ring/Daytona remain the
defaults with identical timing. Slots 3..9 are an experimental ceiling from ten
logo assets, not decoded menu length/names; they may wrap/stick and need visual
confirmation. Optional training `--provenance --decoder` records under its owned
output and exports a portable template; incomplete captures fail while keeping
the partial template/cache. The automatic export helper also reproduces all
2,167 supported session records from the real capture and confirms the recorder
enabled line (`automatic-export-validation.json`). Export has a 600-second timeout. No new global
process termination, asynchronous draw policy or player preparation default.

Screenshots show pit/track/cars rendering in the prepared replay; initial capture
draws were incomplete before async work recovered. These are visual checks, not
pixel-equal comparisons. The replay's cumulative pipeline metrics were not
enabled, so empty counters must not be read as zero runtime compiles. It differs
in timing and recording from collection and supplies no controlled stutter result.
Evidence: `scratch/coverage180-slot2/visual/{report,metrics}.json` and its shots.

Course timing/selection, template/schema/conflict/bundle and strict package tests
pass sequentially. A local 206-file candidate also passes actual ZIP shard/helper
checksums and game/cache exclusion (`scratch/coverage180-slot2/package-validation.json`);
it is not published. A PowerShell precedence error in the new synthetic slot-9 test
was corrected before passing it. The temporary private game copy was removed
after visual checks, reclaiming 4,191,691,292 bytes; its fixture junction was
removed nonrecursively first. Every shadercache, report, shot, original asset and
fixture remains (`scratch/coverage180-slot2/cleanup.json`). Other cars/cameras,
track sections, settings, branching contexts and consistent stutter reduction
remain open. Metadata and source only; no new release/build or game bytes shipped.

## Phase 179 - Packed-reader review and buffered deflate output (2026-11-01)

Two requested Grok agents performed static review only; the parent alone ran
tests sequentially. The integration review found no actionable defect. The
reader review found no integrity bypass and reported a possible false rejection
when zlib retains output after consuming all compressed input.

A synthetic 131,101-byte repeated payload reproduces that failure at the real
128 KiB output limit: the old loop stops at 131,072 bytes with an empty input
tail, then reports an incomplete stream. A 16-byte-limit case reproduces it too.
The reader now drains buffered output using bounded empty-input calls after a
full output chunk, checking cancellation/deadline on every drain. Empty calls
that need more input yield control to the next input chunk. EOF, trailing-data,
decoded-size and complete-container/program identity checks are unchanged.

All nine native reader tests pass, including both regression sizes and existing
corruption/truncation/overflow checks. The 64 MiB ELF read limit now also applies
to the earlier renderer compatibility check and maintainer map generation.
Oversized input is rejected before native reader loading. Helper game-folder
normalization now mirrors the launcher's PARAM.SFO rule, avoiding selection of
an unrelated nested PS3_GAME folder. No new renderer/draw-policy/coverage claim.

The rebuilt frozen helper again passes the full 976-program lookup and all
2,334 exact native pipeline keys/creation/persistence checks using prior verified
shaders/driver blobs, under System32-only PATH. Cancellation/resume and old-cache
preservation pass (`scratch/v178-reviewed-player/validation.json`); archive-stage
cancellation and incompatible-volume rejection also pass without shader/native
work (`scratch/v178-reviewed-volume-safety/validation.json`). These remain reuse
checks, not a new whole-starter fresh compilation or live stutter measurement.
All executable validation is sequential. Source/helper/cache binaries remain
local; the reviewed feature is pushed with `[skip ci]` and no release change.
The rebuilt local candidate also passes strict packaging and an actual ZIP
manifest/exclusion check: 202 selected files, no game/cache contents
(`scratch/v178-reviewed-package-validation.json`). It is not distributed.

## Phase 178 - Read the player's existing packed game directly (2026-11-01)

The optional development launcher now passes its configured disc/PS3_GAME folder
to `GT5P-Prepare --game`, which reads the existing `USRDIR/GT.VOL` and verified
user ELF in place. Users need no GTToolsSharp installation or separate unpacked
asset tree for the starter. `GT5P_PREPARE_VOLUME=0` restores the legacy folder
picker; explicit `--prepare-assets` and helper `--assets` remain supported.
Preparation stays optional. The published v0.2 package is unchanged.

A repository-authored small native byte-rotation helper and bounded Python
raw-deflate reader handle the measured BCUS98158 v03.00 archive. Per-game
parameters are read from numeric locations in the verified user ELF. The bundled
map contains only container/archive hashes, numeric member ranges, seed IDs,
compression flags and ELF offsets: no keys, filenames or game-derived contents.
The maintainer generator accepts a local archive listing and reference assets,
then verifies every selected container/program directly against the original
archive before emitting metadata. No external unpacker source is vendored.

The complete ELF/volume must match SHA-256. Only requested members are decoded,
in archive order; each complete decoded container must match SHA-256 before its
selected program slices are accepted. Existing program identities, shader
bytecode, exact native keys and driver persistence checks remain authoritative.
Bounds are 128 KiB input/output chunks, 1 GiB per member, a 4 GiB sum of decoded
volume-member sizes, 128 MiB retained program data, 1 MiB/1,024-member maps and a
600-second deadline
checked between chunks. Overlaps/unknown fields/ranges and changed input files
are rejected. No extracted member is written to disk. The volume map joins the
checkpoint identity. Renderer settings/root signatures and asynchronous draw
policy are unchanged; unsupported inputs leave ordinary play available.

Measured lookup verifies all 976 starter programs (293 vertex, 683 fragment),
reading 101 volume containers plus the ELF. It hashes the 2,052,954,112-byte
volume and decodes 1,045,098,600 bytes including the ELF, retaining only selected
programs. The frozen full-player test measures 8.599 seconds for this lookup on
this machine with warm OS caches. This is not a general scan-time guarantee.

Validation is sequential: only one test runs at a time. Seven synthetic native
reader tests cover raw/compressed members, chunk/offset parity, malformed maps,
corruption, truncation, decompression overflow/trailing data and cancellation.
Legacy asset lookup and strict package checks pass. The rebuilt launcher passes
owned-process tests including configured-game forwarding without another folder
picker (including an unset rollback switch), legacy cancellation, duplicate
starts and job shutdown. A local package
contains the manifest-verified volume DLL/map with an explicit allowlist and no
game data (`scratch/v178-player-candidate.zip`, 202 files); it is not published.

A fresh application cache with 64 template records rebuilds both shader stages
from the packed inputs and passes exact native-key/creation/persistence checks
(`scratch/v178-fresh/report.json`). This is the fresh compile proof for this
reader, not a new full-2,334 first-run compile experiment. The frozen helper under
System32-only PATH resolves all 976 programs and passes cancellation/resume plus
all 2,334 exact native pipelines using verified prior shaders/driver blobs; zero
shader compiles are expected in that reuse experiment. The old source cache and
selection survive template rejection/cancellation (`scratch/v178-player/validation.json`).
Additional frozen archive-stage cancellation and incompatible-volume rejection
both stop before shader/native work and preserve the selected cache
(`scratch/v178-volume-safety/validation.json`).

This removes an installation/storage hurdle; starter coverage remains 2,334
observed pipelines. Other builds/modded archives need independently verified
maps. Broader contexts/settings, multi-GPU acceptance and consistent live stutter
reduction remain open. All original/shared resources stay read-only; caches and
private archive listings remain untracked. Push only the feature branch with
`[skip ci]`, without creating a new release build.

## Phase 177 - Native offline checksum acceleration (2026-11-01)

The optional standalone helper now builds a small repository-authored native
checksum DLL. ABI/known-vector self-tests gate it; missing/incompatible libraries
use the unchanged Python implementation. `GT5P_PREPARE_NATIVE_HASH=0` rolls back.
Source tools need explicit `GT5P_PREPARE_HASH_LIBRARY` selection. No renderer,
cache format, shader identifier, native-key contract or draw-policy change.

Eight hash tests pass with the native library, covering the nonstandard renderer
seed, empty/NUL/unaligned/random buffers, Python buffer semantics, loader selection,
ABI/self-test rejection, fallback and counter deltas. Existing schema, ownership,
fragment batching, coverage and packager checks pass; packaging validates/includes
the manifest-listed DLL. Native hashing also passes real fresh shader compilation,
growing-template reuse and exact native/persistence checks (`scratch/r177-fresh`).

The same frozen helper passes the full 2,334-record cancellation/resume experiment
with native hashing enabled and disabled, under System32-only PATH. Both modes
compile zero shaders, preserve the source generation/selection on rejection or
cancellation, and validate all 2,334 exact native keys using driver blobs. Both
measure 30,182 checksums over 802,877,280 bytes. Native checksum wall time is
1.168 seconds; Python is 61.736 seconds. Preparation-body time is 106.985 versus
160.074 seconds in this single sequential local pair. Copying, status updates,
filesystem checks and native creation remain costs. This is not a multi-machine
benchmark or live stutter evidence; OS/driver caches remain warm and cancellation
leaves slightly different numbers of already copied shader files in each trial.
Evidence: `scratch/r177-{native,python}/validation.json`, `scratch/r177-paired.json`
and `scratch/r177-checksum-benchmark.json`. All caches/binaries remain local.

The user then requested using the installed game dump directly, without a separate
GTToolsSharp asset extraction. That is the next task; no packed-volume reader is
claimed in this phase. Keep all pushes on the feature branch with `[skip ci]`.

## Phase 176 - Verified preparation reuse across catalogue updates (2026-11-01)

The user requested continued shader work without triggering a Tourline build.
This step makes growing templates practical to prepare repeatedly: developer
`pipeline_template.py prepare --reuse-cache <old shadercache>` reads verified
shader/driver hints into a fresh, separately owned output. The optional player
helper automatically considers the previously selected generated cache when its
new output identity differs. `GT5P_PREPARE_REUSE=0` / helper `--no-reuse` rolls
back. Original assets remain required and reverified; the normal asynchronous
draw policy, renderer contract, starter records and release defaults are unchanged.

The new template supplies every source/bytecode ID and expected native key.
Shaders require exact source-key filename, DXBC signature, length and bytecode
ID. Driver hints require the existing bounded/checksummed envelope; all requested
pipelines still pass exact native-key creation and persisted-cache verification.
D3D12's existing uncached fallback handles incompatible driver hints. No recipes,
packs, membership lists or old checkpoints are imported. Copying is atomic per
file, bounded to 128 MiB of shaders / 256 MiB of driver hints and 60 seconds
between files. Redirected roots are rejected; damaged/missing/linked selected
files remain normal preparation work. Source generations are never written or
removed; the new destination keeps the existing exclusive lock and checkpoint.

Nine synthetic checks cover corruption, different shader IDs/lengths, missing
files, mapping conflicts, overlap, redirected/hard-linked input, resource budgets,
cancellation and player-pointer confinement. Existing schema, checkpoint,
fragment-batch, coverage and packager checks pass. The first native test invocation
used the legacy material-proof engine, which lacks exact fragment batching; its
missing results were rejected. That failed evidence remains in `scratch/reuse176`.
The local instruction now distinguishes the modern template/batch proof engine.

The supported engine passes the growing-template test in `scratch/reuse176b`:
32 base records, 64 expanded records, a fresh 64-record control and complete
64-record reuse all pass exact shader/native/persistence checks. Expansion reuses
the base's 16 vertex variants, 32 fragment jobs and 32 driver hints, compiling
18 additional vertex variants and 31 distinct fragment requests. The fresh
control compiles 34 vertex variants and 53 fragment requests. Complete reuse
compiles neither stage and revalidates all 64 native pipelines from driver hints.
Preparation times for expanded/fresh/complete-reuse cases are 19.141 / 24.467 /
7.231 seconds in this one local experiment, not a hardware-wide guarantee.
Every reused source tree remains byte-for-byte unchanged.

A newly frozen helper is tested with the released icon-bearing engine, an
isolated copied prior cache and PATH restricted to System32. An invalid new
template and cancellation after real shader copies both preserve the old
selection. Resume verifies 2,286 cached shader sources, compiles zero vertex
programs / zero fragment requests, and creates/checks all 2,334 native pipelines;
all 2,334 driver calls use cached blobs. Every driver blob persists and the copied
source cache remains unchanged. The helper reports 166.217 seconds; the wrapper
measures 175.106 seconds including its remaining checks. Cache import takes
53.484 seconds, so copying/checksumming and native revalidation remain material
costs even with zero shader compilation. OS/driver caches are retained. Evidence:
`scratch/r176-player/validation.json`, its generation's `report.json`/`native.log`,
and `scratch/reuse176b/validation.json`. Tool binaries and cache contents stay local.

This is update efficiency, not added starter coverage, a new first-run timing
comparison or live stutter evidence. The optional starter still has 2,334
observed-state records. Work is kept on `feature/shader-incremental-preparation`
and pushed with `[skip ci]`; no main/tag/release push or workflow dispatch is used.

## Phase 175 - Project Tourline Prologue executable icon (2026-11-01)

The supplied PT / PROLOGUE artwork is the player icon. `launcher/tourline-prologue.png`
is the source. `scripts/release/make_icon.ps1` fits the mark into a square and
writes seven PNG-compressed sizes (16 through 256) to `launcher/tourline-prologue.ico`.
The wide black margin in the source is cropped so the wordmark remains readable
at small sizes. The repository game-file check allows these two branding files
only, still under its 1 MB cap.

`tourline-prologue.exe` embeds that icon and uses it on the setup, storage and
preparation dialogs. `gt5p.exe` embeds the same icon. Its window class is created
without one, so the game applies the resource to the title bar and taskbar when
the D3D12, null or SDL window appears, including a later replacement window.
The standalone preparer is frozen with the same icon. A local launcher build
carried all seven images. The engine icon is checked by the release build after
it links `gt5p.exe`; this session did not relink the engine. No rendering,
packaging or coverage change beyond the icon.

## Phase 174 - Tourline Prologue release workflow migration (2026-10-31)

After promotion to main and the v0.2 tag in the older GT5P repository, main was
copied with history into the independent public `mathewdouglas/Tourline-Prologue`
repository. The copied release action was skipped because its repository guard
still named GT5P. The workflow and private-input driver now trust only the new
repository, with a separate `TOURLINE_LOCAL_RELEASE_ENABLED` variable and
`tourline-prologue-release` runner label. Publishing already uses the triggering
repository dynamically. No tags or releases are copied by this change.

A separate local runner is registered, using its own checkout, runtime cache and
incremental cache. Existing private inputs/notices are read from their provisioned
directories. The old runner and its successful main/v0.2 builds were left alone.
Repository/ref rejection tests, actionlint and the tracked game-file audit pass.
The first new-repository main build then finished on the Tourline runner. The
player job for `ba6ad60` started at 2026-10-31 02:56:32Z and completed
successfully at 03:13:28Z. The build step took 16m07s and the ZIP upload took
24s. A branch push does not publish a release. No player rendering or
preparation behavior changed in that commit.
See `docs/local-release-ci.md` for provisioning and the disable switch.

## Phase 173 - Optional v0.2 player preparation candidate (2026-10-31)

The user requested the release preparation steps: fix packaging, expose optional
preparation, validate a packaged build, and author accurate release notes.
VERSION is now 0.2, with a local candidate and feature-branch implementation;
this phase does not merge main, tag or publish a release. Normal launching and
the live asynchronous draw policy remain available.

`Prepare shaders.cmd` invokes native launcher `--prepare`; `--prepare-assets`
accepts an explicit unpacked GT.VOL directory. The existing verified disc/ELF
setup is reused. A PyInstaller 6.16.0 standalone helper includes Python/tool
code, renderer contract text, licenses and a production VP decoder built from
the selected isolated runtime. Players need no Python/compiler install, but
currently need their own assets unpacked with GTToolsSharp. No unpacker or game
assets are bundled. The UI explains this extra requirement and partial coverage.

`build_program_map.py` verifies original catalogue source slices and SHDS VP
records, supplementing them with the existing verified map. Its player map
contains only container/program hashes, sizes, offsets and byte order. All 976
starter identities (293 VP/683 FP) are located directly without a player-side
developer catalogue. The existing smaller developer supplement is retained.
No observed pipeline record, expected native key, runtime source contract or
renderer setting changes. This extends lookup, not whole-game coverage.

The native progress/cancel dialog uses the existing launcher job ownership.
Only its actual verified launcher parent is eligible for exclusion from the helper's game
process check. The initial integration shared the GT5P.exe image name; the
branded public launcher is now tourline-prologue.exe. Other
sessions are rejected and never stopped. Each offline child is owned, timed and
checked for no guest entry. Checkpoints pin metadata and engine/decoder identity;
resume verifies original assets and cached bytecode and revalidates native PSOs.
Successful preparation atomically selects a storage-relative cache path. Failed
or cancelled new preparation preserves the previous selection. Ordinary/older
caches remain intact. `--no-prepared` selects the ordinary cache for a launch;
storage relocation preserves the relative preparation selection.

The first frozen-tool test safely rejects every vertex result: PyInstaller
bundled an SDK D3D compiler with different output. NativeCompiler now loads the
Windows system compiler by absolute path, matching the game's compiler lookup.
No verification is relaxed. Initial failing evidence remains in
`scratch/player-v02-validation`; it is not accepted as a successful preparation.

A corrected ZIP is extracted to a new install and fresh storage. A real helper
run is cancelled after one vertex result, then resumed through the launcher.
All 2,334 records pass shader identifiers, native keys/creation and persisted
cache verification. Resume reuses one VP and compiles the other 295 variants;
1,990 exact fragment requests compile in two processes, with zero rejected jobs.
Preparation reports 443.604 s including lookup through cache verification;
the launcher/test wrapper measures 451.714 s. Asset lookup reads 105 candidate
containers (1,058,112,104 bytes), matches 102 and locates all programs in 1.705 s.
OS/driver caches remain warm; this is interrupted fresh application preparation,
not a universal first-run time. Evidence:
`scratch/player-v02-acceptance/{validation.json,attempt2-report.json}`.

The final candidate passes setup check and another full resume with PATH limited
to Windows System32. It starts zero shader compiler processes and all 2,334
native driver calls use cached blobs. This verifies standalone execution without
Python/compiler tools on PATH. Its evidence is
`scratch/player-v02-acceptance/{final-candidate-validation.json,attempt3-report.json}`.
Engine/helper/ZIP hashes are recorded there. Candidate binaries and metadata
remain local; only identifier/numeric metadata and authored code are tracked.

Native launcher tests pass prepared-cache selection, ordinary-cache rollback,
real progress-dialog cancellation with an owned stand-in helper, duplicate
launch/shutdown ownership, settings preservation and storage relocation. Package
tests reject changed helper payloads and manifest traversal, and exclude an
unlisted synthetic private cache. Template/map/checkpoint/batch/reconstruction
checks and actionlint pass. CI builds the standalone helper and uses authored
version-specific release notes when a future trusted release tag is published.

The packaged launcher is exercised on the same scripted HSR route with the
prepared cache and `--no-prepared`, recording menu/introduction/race screenshots
under `scratch/player-v02-acceptance/route`. The prepared run draws track, cars,
crowd, shadows, HUD and rear-view image in the inspected frames. The fresh
ordinary-cache run initially omits scene draws during async preparation (for
example intro18), then renders the scene by its final shot. Both runs present
frames and reach the race, but their game clocks/cameras differ, so they are not
pixel-aligned or evidence of a repeatable frame-time benefit. The prepared run
still logs a slow demand driver build (`pso-hitch`); that counter alone does not
measure a presented-frame hitch. Existing private fixture gamedata is mounted
in the test storage to avoid another 4 GB game install copy; the original
checkout/build inputs are read only and its processes/caches are untouched.

Limitations: partial observed coverage/default settings, manual GT.VOL extraction,
single GPU acceptance and no consistent stutter claim. Cancellation/termination
can leave partial artifacts that fail verification and need inspection; no
automatic cache deletion/repair is added. Preparing pipelines on disk does not
establish menu/race preload ownership or remove every driver creation on demand.
Release notes and START-HERE make preparation experimental and optional.

Follow-up branding request: the player entry point and package shortcuts now use
`tourline-prologue.exe`; the launcher sets existing `PS3_TITLE` to
`Project Tourline Prologue`. Storage/compatibility namespaces remain compatible
with v0.1. The helper verifies the renamed parent, and the checked native window
title is exactly `Project Tourline Prologue` before frame statistics are added.
The game binary/decoder and pipeline keys do not change for branding. A tool-only
re-freeze reuses the verified decoder, and the branded candidate again passes
all 2,334 native cached-blob checks with zero shader compiler processes under a
clean PATH. Evidence:
`scratch/player-v02-acceptance/{tourline-candidate-validation.json,attempt4-report.json,tourline-window/report.json}`.
The local ZIP is `scratch/tourline-prologue-v0.2-candidate.zip`, SHA-256
`c381f43d4113fdb8064cf92cf7bd583e0b2fd5d6788a01c5db12874c8ce15e98`.

## Phase 172 - Default batching and verified template resume (2026-10-31)

At the user's request, exact fragment batching is now the default in template,
material/shared preparation and paired-route validation. Explicit
`--fragment-mode legacy` remains the rollback. The runtime offline environment
guards, two-worker queue, live draw policy and renderer/template key contract
are unchanged; no runtime rebuild or starter record reissue is needed.

Template preparation now checkpoints before lookup and supports `--resume`.
The checkpoint pins canonical validated template/map content and actual helper
EXE/decoder hashes. Every attempt re-locates original programs; expected
source-keyed DXBC can be reused only after exact bytecode identifier/length
verification with a bounded pool. Missing artifacts rebuild; corrupt artifacts
reject safely and remain intact. Vertex source/bytecode identifiers are computed
once per unique vertex variant instead of repeatedly for each template record.

An OS lock gives one preparation owner per output, released on exit. Resume
checks the output tree for redirected/hard-linked entries before writes and
bounds the walk. Atomic state records carry attempt/phase/progress; old reports
are distinguished by their attempt. Every native pipeline is revalidated on
resume, with pending markers replacing old per-request result files before
submission. Completion is recorded only after persisted cache verification.
Existing outputs without checkpoints cannot resume and are preserved. No
shadercache is deleted or moved.

A real 32-record default-batch run is deliberately interrupted immediately after
fragment preparation. Resume verifies 37 cached source files, reuses 12 vertex
variants and all 32 fragment jobs, starts zero shader compiler processes, then
creates/persists all 32 native pipelines. A subsequent resume again compiles no
shaders and successfully uses all 32 driver blobs. Attempts take 12.150 s and
12.319 s respectively; these are small resume checks with warm OS/driver caches,
not fresh full-starter performance or gameplay/stutter measurements. Cached
shader bytes remain unchanged. Evidence:
`scratch/template-resume-20261031/{validation.json,completed-attempt-2.json,completed-attempt-3.json}`.

The native test also rejects a changed template without modifying checkpoint or
cache, and rejects a deliberately corrupted bytecode copy before compiler/native
startup while preserving both that copy and the successful cache. Separate
process lock contention and real Windows junction/hard-link checks pass in
`scripts/test/preparation_checkpoint.py` (latest output
`scratch/checkpoint-test-8zhzikjt`). Template/schema, session coverage, asset map,
fragment batch, material envelope and shared profile tests also pass. No new
game copy, original-checkout change or distributed game-derived content.

This is developer interruption/resume support. Graceful launcher cancellation,
fine-grained native progress, broader representative coverage and a consistent
live stutter benefit remain open. An abrupt partial/corrupt file can require
inspection and a fresh output rather than automatic repair; caches are never
silently discarded.

## Phase 171 - Exact offline fragment batching (2026-10-31)

Preparation was starting a complete runtime/device for each fragment profile.
Added the default-off `RSX_SHADER_LIBRARY_BATCH` offline path and developer
`--fragment-mode batch` in template, material/shared preparation and paired-route
tools. `legacy` remains their default and rollback. The native guard requires
`GT5P_SHADER_PRECOMPILE_ONLY=1`, a device/cache and the existing async compiler.
The ordinary draw path, renderer settings and asynchronous draw policy do not
change. No new background worker or queue owner is introduced.

Manifest V1 contains at most 4,096 sorted unique request IDs, hash-named local
program files, raw checksums and explicit numeric profiles. All manifest syntax,
versions/counts/field widths/identifiers are validated before any compile is
queued. Program reads are bounded to 32 KiB, checked for END/constants/checksum
and exact sampled-texture mask, with per-request failures. Result IDs must join
exactly once to every requested record. Actual bytecode availability/expected
source and bytecode identifiers and final native keys still gate acceptance;
enqueue acceptance alone is not compilation/pipeline success.

Python deduplicates exact program/profile requests and partitions only by final
dither policy (cached globally by the existing translator). It emits the exact
requested pairs rather than a shader/profile cross product. The normal text
generator, two existing compiler workers, source-key deduplication and queue
backpressure are reused. Pending work drains before return, and profile globals
are restored. Metadata/program/code pools and native row counts stay bounded;
process timeout remains owned by the caller. Material/shared resume preserves
cache directories and rejects altered intermediate inputs. Templates still
require a fresh output; broader cancellation/resume remains open.

A paired 32-record empty-application-cache test under the same rebuilt EXE
matches all bytecode bytes, source keys and exact native keys. Legacy uses 20
fragment processes and 37.813 s for that phase; batching uses two processes,
25 distinct requests and 5.637 s. Whole preparation is 57.405/17.765 s. Order is
legacy then batch, OS/driver caches stay warm and this is one sample, so it is
not a universal speedup claim. Evidence:
`scratch/template-batch-20261031/parity.json` and its legacy/batch directories.

The full starter is then tested in a single new empty application cache. All
2,334 records reconstruct both stages, match expected source/bytecode identifiers
and exact native keys, create in D3D12 and persist validated recipes/driver blobs.
There are zero unresolved/incompatible/key-rejected entries. Fragment preparation
deduplicates to 1,990 requests in two processes: 1,974 without final dither and
16 with it, all actually compiled. This phase takes 108.106 s; full preparation
takes 467.422 s, including lookup, serial vertex translation/compilation, request
writing and cache verification. Native creation takes 57.172 s for 2,334 driver
calls with zero cached-blob calls. These are cold application-cache measurements,
not a cleared OS/driver cache or gameplay benchmark. Evidence:
`scratch/template-batch-20261031/full/{report.json,native.log}`.

The renderer source contract changes conservatively with the offline addition.
The starter header/shard checksums are reissued only after the complete native
proof; numeric/program records and expected keys are byte-for-byte unchanged.
There is no metadata ABI/key-version change, relaxed compatibility check or cache
clear. Old source-contract templates remain rejected by the existing check.

Eleven real native cases exercise wrong versions, overflow counts, duplicates,
unsafe filenames, invalid profiles, trailing records, bad raw hashes, mismatched
texture masks, oversized code, switch-off gating and a valid request. The repeat
of the valid request produces identical results and zero shader compiles.
Evidence: `scratch/fp-batch-native-20261031/report.json`. Synthetic tests cover
exact deduplication/dither split, duplicate/missing result joins, corrupted input,
timeout handling and reuse of matching intermediate inputs.

All 36 conditional shared pipeline candidates also prepare in batch mode, then
resume successfully: no fragment recompiles and all 36 driver calls reuse cached
blobs on resume. Evidence: `scratch/sb171/{report-first.json,report.json}` and
`pipelines/native.log`. The isolated build and runtime patch reverse-check pass.
The original checkout, shared runtime and their processes remain untouched.
Existing shadercache directories are preserved; writes use private caches. No
additional game copy, player defaults or live stutter/rendering claim; wider
content, template cancellation/resume and measured in-game benefits remain open.

## Phase 170 - Representative-session coverage and precompiler roadmap (2026-10-31)

Saved the seven remaining milestones in `docs/shader-precompile.md`: representative
coverage, asset-derived rules, branch/settings contexts, efficient resumable
preparation, demonstrated stutter reduction, launcher integration and player-path
validation. The next step now has a concrete developer tool:
`scripts/pipeline_template_coverage.py`. It compares compatible session templates,
reports shared/additional keys/programs/pairs/source variants/translation state,
distinguishes new pipelines reusing existing programs, ranks marginal session
gain and emits a delta template for verification. It measures metadata candidates,
not preparation success, whole-game coverage or runtime hits.

The existing extended HSR/Daytona recordings export 1,758/1,931 records. Export
rejects three/five branching contexts and two/seven raw-program integrity failures.
Three overlapping keys disagree in FP identity/source ID. Strict comparison and
the original merge reject conflicts. Explicit `--quarantine-conflicts` removes
all conflicting session versions, preserving the supplied baseline; conflicting
new keys are never selected by order/majority. Incompatible contracts always fail.
The three baseline keys already have Phase 169 proof and are not replaced.

After quarantine, the union has 2,334 candidate pipelines versus the verified
1,494-record baseline, a delta of 840. Of these, 253 reuse both original program
identities and 587 need at least one additional program. Daytona contributes 820
keys absent from the baseline; extended HSR contributes 20 more after Daytona.
The report only ranks supplied recordings, not the benefit of unvisited content.
Evidence: `scratch/template-session-expansion-20261031/{coverage-final,delta}.json`
and the two `*-export.json` reports in that directory.

Asset-map generation accepts up to 16 traces, counts/skips invalid oracle blobs
and still verifies every match against original asset bytes. All 49 supplemental
identities needed by the delta are located in 31.516 s; nine invalid oracle files
are skipped. Preparation lookup finds all needed programs; its supplemental pass
hashes three containers/224,921,136 bytes in 0.804 s with warm OS caches. Map merge
deduplicates identical entries and rejects conflicting locations. Synthetic tests
cover overlap/state-versus-program distinctions, greedy ranking, conflict
quarantine, incompatible contracts, multi-trace lookup and corrupt oracle skips.

The checkpoint's 840-entry fresh-cache proof then completed: all 840 reconstruct
both shader stages, match expected source/bytecode identifiers and exact current
native keys, create in D3D12 and persist validated recipes/driver blobs. There are
zero incompatible/unresolved/key-rejected records in this batch. Total elapsed
time is 693.387 s, including vertex translation and 263 fragment-profile processes;
840 native driver calls take 20.453 s with zero cached-blob calls. These are
application-cache proofs; OS/driver caches remain warm. Evidence:
`scratch/template-session-expansion-20261031/prepared/{report.json,native.log}`.

Only after this verification, the optional starter expands to 2,334 records.
The merged map has 119 locations (4 VP/115 FP) across six containers; identical
locations deduplicate and conflicts fail. Full lookup resolves 293 VP/683 FP
identities for all 2,334 records; its supplemental pass hashes 528,044,272 bytes
in 1.543 s with warm OS caches. See `full-lookup.json` and `merged-asset-map.json`
in the same evidence root. No shader contents/source/compiled binaries are
tracked. The existing private fixture is reused; guest entry is never executed
and no additional game copy is made. No player defaults, live draw policy,
rendering or stutter claims change. Broader unvisited content remains open.

## Phase 169 - Recover non-SHDS programs with verified asset locations (2026-10-31)

The largest immediate template gap was lookup: of the 298 unresolved records,
279 lacked only FP, 14 lacked both stages and five lacked only VP. The missing
program set is four VP and 68 FP identities. A read-only search of the original
ELF/unpacked assets finds all of them outside the currently supported SHDS table
lookup. This is an extraction gap; the evidence does not require inventing shader
variants or choosing pipeline state from guessed pass ownership.

`scripts/pipeline_asset_map.py` adds independently versioned location metadata:
stage/program SHA-256, program size, original container SHA-256/size, file offset
and native/swap32 encoding. No shader bytes/source/binaries, filenames or guest
addresses enter the map. Developer generation uses bounded captured programs as
search anchors, verifies each candidate against the expected program identity,
then emits only locations into original assets. End-user preparation needs no
captures: it hashes original containers, reads and verifies slices, and follows
the existing exact source/bytecode/native-key checks. FP identity still ignores
inline constant values under the explicit constant-buffer policy.

Map schema/version/counts/offsets/sizes/encodings are validated before use. A
changed asset cannot serve an old location; an incorrect program slice fails
verification before compilation. Renaming/moving identical assets is supported.
Missing containers remain unresolved on the existing demand path. The lookup
uses one CPU thread, at most 8,192 input files/1 GiB per container/16 GiB hashing,
a 60 s between-container deadline, 4 MiB metadata and 128 MiB resolved code.
Developer generation has a 600 s between-candidate deadline, 16 GiB search budget
and 4,096 anchor candidates per program/container. No live memory scout, worker,
queue owner, shutdown or asynchronous draw-policy change is introduced.

The initial generator locates all 121 identities referenced by the unresolved
record subset in 116.133 s; filtering out programs already available through
SHDS leaves 72 supplemental locations. `--catalog` now performs this omission
automatically for subsequent generation. Full template lookup finds 214 VP and
498 FP identities, resolving all 1,494 exported records. Supplemental lookup
hashes five containers (438,542,896 bytes), measured 1.112 s with warm OS caches.
Three branching VP contexts remain excluded. Evidence:
`scratch/template-asset-map-20261031/{report,full-lookup,minimal-map}.json` and
`scratch/template-missing-diagnostic.json`.

All 298 recovered records then rebuild both shader stages, match expected
source/bytecode identifiers, match exact current native keys, create successfully
in D3D12 and persist validated recipes/driver blobs in a fresh application cache.
No incompatible/unresolved/key-rejected entries remain in this subset. The old
working template header was reissued against the current normalized source
contract before validation; no mismatch bypass was added. Preparation takes
256.764 s, including 91 fragment-profile processes and vertex translation;
298 fresh driver calls take 7.156 s with zero cached-blob calls. Driver blobs
occupy 23.299 MiB. The existing private game fixture is reused; guest entry is
never executed. No additional game copy or gameplay benchmark was needed.
Evidence: `scratch/template-recovered-proof-20261031/{report.json,native.log}`.

The optional metadata starter now has all 1,494 positively verified records
(Phase 168's 1,196 plus these 298), and the 72-entry map. Supply `--assets` to
use the bundled map automatically, or explicit `--asset-map` for standalone
templates. A separate one-record bundled fresh-cache native smoke verifies
automatic map selection. Synthetic checks cover byte order, misleading prefix
candidates, container modification, bad offsets/versions, duplicate records,
unknown fields, empty requests and timeout behavior. Template/shared-profile
regressions pass. Rollback: omit supplemental lookup or skip optional preparation.

This is 1,494/1,497 retained HSR pipeline links, **not whole-game coverage** or
independent recovery of unseen material/pass state. It closes the measured
lookup gap without more driving. No new stutter/screenshot result is inferred
from an offline creation proof; Phase 168's live limitations still apply. No
player/launcher/release default changes. Broader route/session templates and
unrecorded branch/pass contexts remain future work.

## Phase 168 - Verified optional template, measured routes and bounded storage (2026-10-31)

Completed the Phase 167 experiment. Asset lookup finds 210 VP/430 FP identities;
1,196 of 1,494 exported records reconstruct both stages, match source/bytecode
identifiers and exact current native keys, and persist local driver pipelines.
298 remain unresolved-program; three branching VP contexts were excluded before
export. Total preparation is 723.881 s, including process/translation overhead;
fresh native creation is 26.109 s for 1,196 pipelines. Driver blobs total
82.568 MiB. Lookup was 8.035 s with warm OS caches versus the earlier 48.93 s;
this is not evidence of a lookup optimization. Evidence:
`scratch/template-hidden-route-20261031/preparation/report.json`.

The optional starter at `assets/pipeline-templates/gt5p-disc-v2` contains only
the 1,196 positively verified identifier/numeric-state records, checksum-sharded
into roughly 1.1 MB of text. No shader bytes/source/compiled binaries are tracked.
The source contract/default settings/root key checks remain mandatory. Native
compiler creation is lazy; malformed/incompatible headers with explicit
`--demand-fallback` produce an empty result without starting a compiler. Strict
mode still rejects them. A fresh-cache single-record bundle smoke passes:
`scratch/template-bundle-smoke-20261031`. Preparation no longer fabricates a
menu index: offline disk availability is not evidence of live pass membership.

Four completed HSR trials used fresh application caches, the same scripted route,
1080p/2x/VSync and existing asynchronous draw policy. OS/driver caches remained
warm. Bulk preload initially assigned all prepared records to menu membership;
that assumption was removed after these trials. Cumulative five-second counters
can omit the final interval. Native cached calls are included in driver calls;
shader compilation is a separate counter.

| Trial | Shader compiles | Driver calls (cached) | Demand queued | Early/late p99 ms | Grid s | Peak private GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Control 1 | 1603 | 942 (0) | 942 | 65.7 / 58.9 | 65.4 | 3.17 |
| Bulk prepared 2 | 666 | 2048 (1318) | 841 | 185.7 / 101.8 | 65.0 | 3.34 |
| Bulk prepared 3 | 674 | 2045 (1318) | 838 | 193.4 / 91.3 | 65.9 | 3.34 |
| Control 4 | 1646 | 1539 (1) | 1539 | 197.4 / 145.3 | 65.4 | 3.24 |
| Final demand control | 1559 | 1118 (0) | 1132 | 129.4 / 49.3 | 66.9 | 3.20 |
| Final demand prepared | 655 | 2126 (1393) | 2126 | 150.1 / 92.1 | 65.1 | 3.29 |

The final pair disables startup scanning and clears membership indices only in
new trial cache copies. Warm-loaded/resident/prewarm-hit counts are zero there;
prepared binaries are consumed through normal demand. Bulk runs report 2,292
warm hits, but that counter includes startup bookkeeping and cannot be claimed
as independently measured draw coverage. Shader compiles decrease; **no consistent
stutter improvement is established**. Prepared runs still have long hitches.
Controls and scene progression differ markedly; disk/memory pressure and desktop
activity limit attribution. Early/late >100 ms counts in the final pair are
31/1 control and 28/17 prepared. Later screenshots show road/cars/HUD in prepared
scenes; differing cameras/progression prevent a pixel-equal regression verdict.
No new persistent rendering fault was identified in inspected later images,
but missing-draw freedom is not proved. Reports/screenshots:
`scratch/template-hidden-route-20261031/trials/report.json` and
`scratch/template-demand-clean-20261031/report.json`. An older demand pair was
stopped for the user's urgent disk request and is excluded from these results.

The audit checkout held 75.436 GiB of regular files, mostly disposable benchmark
game copies. Removed exactly 14 verified private trial `game` directories,
reclaiming 54.53 GiB. All shadercache directories, original checkout/runtime,
base fixture, private training root, build tools, reports and screenshots were
preserved. Junctions were unlinked without traversing their targets; all paths
and protected cache names were checked before deletion. Evidence:
`scratch/disk-usage-20261031.json`, `scratch/disk-cleanup-20261031.json`.

`scripts/benchmark_storage.py` now checks available space before each copy,
including a 2 GiB margin, and removes completed trials' private game copies by
default. `--keep-game-copies` retains them explicitly. Cleanup validates owned
trial paths, refuses nested shadercache/unexpected hard links and never follows
reparse points. Synthetic tests exercise junction target preservation, read-only
copies, cache protection and low-space rejection; the final real pair also
removes both copies while preserving caches/evidence. No further game runs were
needed. No launcher/release/player default changes or complete coverage claim.

## Phase 167 - Quiet preparation and portable template contracts (2026-10-31)

User observed repeated windows flashing/closing during template preparation.
Those were the offline compiler's per-profile processes, not live-game crashes.
Under the existing `GT5P_SHADER_PRECOMPILE_ONLY=1` guard, D3D windows now omit
WS_VISIBLE. Normal play remains visible. The native visibility test observes
owned windows throughout both compiler runs and confirms zero visible windows,
normal exit and the no-guest-entry guard.

`RSX_SHADER_LIBRARY_EXACT=1`, accepted only in offline mode, skips the two broad
base profiles when an explicit template/material profile is requested. The same
native test compares legacy/exact result rows: requested source identifiers are
identical, while exact mode emits only the requested profile. Ordinary library
precompilation keeps its previous default. This removes unnecessary work and
keeps the two compiler-worker/source-queue limits.

Template format 2 replaces per-install EXE/DLL binary hashes with a source
renderer contract (pinned upstream commit + normalized compatibility patch),
explicit default anisotropy/root-key/constant-buffer settings and the game ELF
hash. Actual helper/build hashes remain diagnostic report fields. Exact rebuilt
source/bytecode and current native-key checks still gate every entry, including
root signature compatibility. Independently built copies can now share a
compatible template; format 1 is rejected rather than guessed.

Identifier/numeric-only metadata can be bundled into checksum-verified text
shards, each below the repository's 1 MB text limit. Bundle names, versions,
parts, checksums and total size are bounded/validated; no shader contents enter
them. Multi-session merge deduplicates before enforcing the union cap and rejects
conflicts/incompatible generations. Tests cover malformed versions/state,
pointers, bounds, settings, duplicate conflicts and altered bundle parts.

The isolated build and runtime reverse-check pass. Native evidence:
`scratch/hidden-preparation-test-20261031/report.json` and
`scratch/pass-build/build-hidden-preparation.log`. The old interrupted run is
retained; `scratch/template-hidden-route-20261031` is the fresh restarted
preparation/paired-route experiment. It is still running at this phase: no
new live coverage or stutter claim, starter publication or player default.

## Phase 166 - Checkpoint identifier-only pipeline templates (2026-10-31)

User requested investigation of Project Pyrrhus's shared templates, then requested
wrap-up before the end-to-end experiment finished. This is an implementation
checkpoint, **not a completed/preferred player preparation path**.

Reviewed Pyrrhus patches 2031/2071/2077/2120, its template merge tool and known
issues. Useful design: identifiers plus numeric state, explicit schema/key ABI,
verified local programs, final key recomputation and deduplication. Its guest
memory scout and live-draw patch stack were not imported. GT5P already records
native descriptors and local DXBC recipes, prepares SHDS fragment profiles,
extracts CPU/GPU vertex programs, loads menu/race shader packs, and owns a bounded
priority prewarm/demand queue. The extension reuses those paths before guest
entry instead of adding a speculative concurrent translator/queue owner.

`scripts/pipeline_template.py` exports/merges local provenance into JSON containing
program SHA-256 identifiers, expected source/bytecode/native identifiers, all
recorded translation fields, canonical numeric native descriptor words and ATTR
input elements. No guest addresses, program bytes, source or compiled binaries
are in templates. Windows x64 recipe ABI, key version, game ELF, executable and
decoder hashes are pinned conservatively. Conflicting duplicate keys, unknown
fields, pointer/stage payloads and incompatible versions are rejected. Branching
VPs remain excluded: start-slot/branch context is not recorded sufficiently.

Asset lookup reads the user's local SHDS catalogue and original bounded vertex
wrappers before game boot. Preparation reconstructs both shader stages, verifies
source/bytecode identifiers and native keys, then persists ordinary recipes and
hardware-local driver blobs. `RSX_PSO_TEMPLATE_PREPARE=1` enables persistence only
in the existing guarded offline path and requires the exact current native key,
including the root signature; legacy keys are not accepted. Expected keys also
protect target/settings/layout compatibility. Default translation is explicit;
other renderer settings are not claimed compatible. Missing entries remain for
the normal asynchronous demand path. No live draw policy/default changed.

Limits: 32 MiB template, 4,096 records, 32 input elements, 32 KiB program slices,
8,192 asset containers, 1 GiB mapped container limit and a 60 s between-container
scan budget. Vertex source/code and fragment code pools each have 128 MiB caps;
fragment compilation uses the existing two-worker/64-source queue. Offline
preparation finishes/exits before a live game owns the device. Existing warmup
ownership, priority, deduplication, resident caps and shutdown remain unchanged.

Measured/checks: exported 1,494 records from retained HSR; three branching VP
records excluded. Lookup visited 601 containers (2,894,781,056 addressable bytes,
7,265 wrappers), found 210 VP and 430 FP identities in 48.93 s. This is lookup
availability, **not prepared-pipeline coverage**. The full shader/native pass was
stopped at the user's wrap-up request; no paired route/screenshot comparison ran.
No runtime compile reduction, demand-build reduction, hitch benefit, loading or
memory comparison is established. Metadata tests pass; isolated runtime builds;
strict native smoke persists one valid key and rejects an altered key; runtime
patch reverse-check passes. `pipeline_template_route.py` wires fresh preparation
into the existing paired route test; it still needs execution and visual review.

Evidence: `scratch/template-first-20261031/template-v2.json`,
`scratch/template-preparation-20261031/report.json` (stopped),
`scratch/template-native-smoke-20261031/validation.json`, `native.log`,
`scratch/pass-build/build-template.log`. Templates/caches remain ignored/local.
Next: finish reconstruction, investigate exclusions, run the paired empty-cache
route with counters/memory/screenshots, then assess first-launch integration.
No shipped starter template, launcher/default changes or stutter claim.

## Phase 165 - Prepare conditional shared convolution pipelines (2026-10-31)

The shared preparer also selects the original `Convolution_8` pair. The real
initializer `00820A28` resolves its name/bindings; the full `00820C08` wrapper
sets single-mip unnormalized 2D sampling, linear filtering and coupled source-read/
output gamma. Clamp wrapping comes from the supported initialized FrameBuffer
source. Tap count is argument ten, not gamma. Targets/depth attachments remain
explicit candidates; distinct successful RGBA8 sources/no unexpected redirects
and no later overrides remain conditions. Actual live ownership stays unproven.

576 randomized native convolution checks pass alongside 1,152 colour-correction
resource checks and earlier selection/state/input checks. Geometry, target
activation, constants and draw submission are controlled in this isolated oracle.
All 36 supported shared candidates (24 ColorCorrect, 12 convolution) create and
persist from assets, with recipe/code/driver checksums validated. Comparing the
frozen result afterwards finds two exact native-key matches among 1,497 retained
HSR links (lines 16/20), both convolution. No whole-game/stutter gain is inferred.

Evidence: `scratch/shared-convolution-prep-20261031/report.json`, `validation.json`,
`pipelines/native.log`; native oracle
`scratch/shared-pass-native-593517745aae42b098afb109bc4431b5/report.json`.
No player defaults, original-checkout changes or cache deletion/move.

## Phase 164 - Support explicit colour-only native targets (2026-10-31)

The shared rule now enumerates depth attachment as an explicit context instead
of assuming every host target has a DSV. `--depth-context both` is the developer
default; `backed` and `colour-only` restrict the set. The existing `rgba16` and
`supported` sets contain 16 and 24 conditional requests respectively with both
depth contexts. Shader compilation deduplicates the attachment variants. Actual
game ownership remains unresolved; no attachment mode is read from captures.

Offline target schema `GT5P_TARGET_V2` explicitly supplies format, samples and
depth attachment. V1 retains the original depth-backed contract. The fresh
colour-only descriptor sets DSV format UNKNOWN, disables depth/stencil and
disables depth writes, matching the production bit-27 no-DSV transform. The
material-field writer permits this case only when guest depth is disabled;
contradictory depth requests remain rejected. Existing reconstruction switches
and precompile-only guard apply; normal play is unchanged.

Twenty native descriptor/parse checks pass across supported format/sample
contexts, poisoned descriptors and malformed/contradictory inputs. Twenty
existing offline material/pass/native reconstruction checks also pass, including
zeroed native descriptors and default-off controls. All 24 shared candidates
create/persist from assets and independent state; a repeat accepts cached blobs
for all 24. Recipe, bytecode and driver checksums validate. No whole-game or
stutter gain is inferred; the shared pass's live ownership remains unproven.

The isolated runtime builds and the compatibility patch reverse-check passes.
No original checkout/runtime/process/cache changes and no cache deletion/move.
Evidence: `scratch/shared-target-native-9ddc5ba04b6a4c41b255e98495749e20/report.json`,
`scratch/shared-target-prep-20261031/report.json`, `validation.json` and
`pipelines/native.log`; build log `scratch/pass-build/build-colour-target.log`.
Next trace the shared copy/averaging passes used in exposure and post-processing.

## Phase 163 - Build the first independent shared-pass pipeline candidates (2026-10-31)

`prepare_shared_shaders.py --pipelines` now constructs complete conditional
ColorCorrect shader/native requests without captures, learned profiles, manual
bank offsets or pass names. The original named pair and sampler metadata must
declare exactly `colorMap` on unit zero, no globals and sampled mask one. Unknown
or different ownership is rejected. Explicit contexts enumerate source-read and
output gamma with supported depth-backed single-colour targets. Source must be a
successfully initialized ordinary RGBA8 2D FrameBuffer, distinct from the target;
feedback, depth/cube/volume and unexpected redirects remain excluded.

The native oracle now runs the real FrameBuffer getter-copy wrapper `00827DD0`,
full colour-correction wrapper `0081FDA8`, gamma callbacks and texture-emission/
copy chain `00823F28/00BA6CF0/00BD2660/00BD5B88/00C05D58`. All 1,152 random
descriptor/poison/identity/gamma cases match the independent transform. It forces
one mip, read gamma from the low byte of the explicit mode argument, min filter
one and mag filter two for distinct objects (one for identical objects). S/T
wrap remains inherited; the supported initializer supplies clamp. The source
descriptor provider, sampler metadata lookup, target activation, constants and
draw boundary are controlled, not claimed as independently executed ownership.

**Correction:** `0x1d7c` is anti-alias control, not shader control as labelled in
Phase 160. Its inherited low bit remains, but bit four is cleared, so it does
not enable the backend's alpha-to-coverage substitute in this pass. Fragment
export precision still comes from the authored compact descriptor. Source shape
and normalized coordinates use the already measured successful 2D framebuffer
initializer; read gamma is now explicitly overridden by this pass.

All 12 `supported` contexts rebuild shaders and create distinct persisted native
pipelines from zero native descriptors and expected key zero. Existing guarded
offline material/pass/target/input field writers are reused for independently
derived pass values; no material state is read for this shared rule. A repeat
run accepts all 12 and uses cached driver blobs. Recipe, bytecode and driver
checksums validate independently. None matches the retained HSR snapshot; actual
pass/context use and whole-game coverage remain unproven. No live performance
comparison or player/launcher/release change is made.

Resume verifies ELF/decoder/engine/context identity and marks each request pending
before native execution so stale results cannot count as a new success. Failed
outputs remain reviewable. Synthetic ownership/gamma/prerequisite checks and
bank/reconstruction regressions pass. All game-derived files remain ignored and
the original checkout/shared runtime/processes are untouched.

Evidence: `scratch/shared-pass-native-a1b5426ab1f14f1a8bd6316461e8c274/report.json`,
`scratch/shared-color-prep-20261031/pipelines/native.log` (initial creation), and
`scratch/shared-color-final-20261031/report.json`, `validation.json`,
`pipelines/native.log` (cache reuse). Next add explicit colour-only host targets
and recover more shared-pass rules, retaining unresolved ownership as conditions.

## Phase 162 - Automatically prepare shared vertex programs and derive CPU layouts (2026-10-31)

`scripts/prepare_shared_shaders.py` scans original ELF SHDS headers and bounded
name tables automatically. No capture, route visit, bank offset, pass name or
pipeline key is an input. It enumerates 46 authored pairs across five supported
banks, deduplicates original vertex slices and compiles 14 CPU vertex programs
with the production decoder/D3D compiler. Runtime source-keyed DXBC files are
written only into ignored output. Two unhandled banks are reported explicitly;
no shader cross product or guessed fragment profile is generated.

The original vertex wrapper's +4 word is emitted unchanged as the attribute
input mask by `00BDE360`: 21 poisoned synthetic and 38 authored-pair checks pass.
Under default vertex packing and no later input-mask override, an independent
layout constructor matches the production staging/layout path for all 65,536
low masks (1,048,576 input elements). Mask zero retains the production full-mask
fallback; attribute zero is always kept, active attributes are packed as float4
and inactive semantics read offset zero. This is a conditional binding fact,
not a claim of actual ownership for every draw.

The explicit offline-only `RSX_PSO_RECONSTRUCT_INPUT=1` switch applies a fresh
16-element CPU input layout from an original wrapper mask. Developer proof
`--shared-cpu-inputs` requires named original-pair selection and CPU-path samples.
Two `SimpleBias` and one `MenuShader_Color` samples rebuild shaders, replace
captured input elements, match native keys and create D3D12 pipelines. Nine
process checks pass, including erased captured element records, malformed/
missing inputs, wrong masks and switch-off controls. The erased-layout control
fails without replacement. Other translation/native descriptor state remains
explicitly captured; these are not whole independent pipeline recipes.

The isolated runtime is rebuilt and its compatibility patch passes reverse
verification. Synthetic bank enumeration/reconstruction regressions pass.
Normal play, launcher/release and player defaults are unchanged; the original
checkout and its processes/cache/runtime remain untouched. No live performance
test is run and no stutter improvement or complete pipeline coverage is claimed.

Evidence: `scratch/shared-vertex-prep-20261031/report.json`,
`scratch/shared-pass-native-214683a387794f788bc0d19d85fe9a4d/report.json`,
`scratch/input-native-427eef69545f4b2eb1b5517872a415e7/report.json`,
`scratch/shared-input-proof-20261031/report.json`, and
`scratch/shared-input-menu-proof-20261031/report.json`. Commands and remaining
scope are in [shader preparation](shader-precompile.md) and
[reconstruction](shader-reconstruction.md#automatic-shared-vertex-preparation-phase-162).
Next derive shared fragment resource/target contexts and pass overrides so these
automatically enumerated pairs can generate independent native pipelines.

## Phase 161 - Automate route discovery and native pipeline preparation (2026-10-31)

The practical workflow no longer requires finding/proving every pipeline by
hand. `scripts/train_pipeline_cache.py` drives the existing supported HSR and
Daytona routes into one private learned cache, then prepares all learned native
pipelines offline before play. It selects no individual shader names, capture
lines, material pairs or pipeline keys. The source of complete state is actual
renderer requests, explicitly separate from independent asset reconstruction.

The tool uses a copied ignored fixture, copies writable game data, rejects
redirected writable paths and links only the private copied disc directory.
It refuses another game; process cleanup targets only its owned child tree.
Cache pruning and bulk scans during route learning are disabled. No cache is
deleted or moved. An atomic report supports interruption/resume and optional
preparation-only reuse, tied to engine/fixture/route/settings identity.

Validation checks recipe envelopes/checksums, associated bytecode sizes/hashes,
grid milestones, ongoing presentation, complete native warmup acceptance,
offline guest-entry exclusion and every persisted driver blob's checksum.
The pinned offline cap is 8,192 recipes; exceeding it is an explicit failure.
Malformed/incomplete caches are retained and reported, never silently accepted.
Synthetic tests cover damaged envelopes, missing/mismatched bytecode, truncated
driver blobs, insufficient route samples and output containment.

The isolated 1080p/2x sweep visits HSR then Daytona for 60 seconds after each
grid. It learns 1,719 distinct recipes in total. Final screenshots show track,
cars and mirrors in both routes; an earlier HSR shot shows mostly HUD. These
are bounded route visits, not proof of every variant or complete visual
readiness. No paired performance comparison is made, so no stutter-reduction
claim follows. Original checkout, caches and shared runtime stay untouched.

The final offline pass accepts all 1,719 recipes with zero rejections and checks
all persisted driver blobs. A separate empty-native-cache rebuild copies only
the learned recipes/bytecode, creates and persists all 1,719 native blobs, and
confirms no guest entry. OS/driver caches remain warm; this is not a clean-driver
timing claim. The updated preparation-only resume path is also exercised.

Evidence: `scratch/pipeline-training-20261031/report.json`, route logs/shots
under `logs/`, `prepare.log`, and
`scratch/pipeline-rebuild-20261031/report.json`. Commands and limitations are in
[shader preparation](shader-precompile.md#automated-route-learning-and-preparation-developer-only).
Only the current car, supported routes and explicit settings are visited.
Expanding discovery routes/content and measuring cache reuse are the practical
next steps; independent pass reconstruction can continue separately. No
runtime, player, launcher or release defaults change.

## Phase 160 - Recover named shared shader pairs and colour-correction setup (2026-10-31)

`scripts/shader_shared_passes.py` adds bounded capture-free SHDS name-table
selection. Three embedded banks supply 38 authored pairs: 6 menu, 15 scene
effects and 17 graphics. Names join directly to vertex/fragment indices; no
cross product or capture-selected pairing is used. Unknown wrappers, malformed
tables, duplicate/unsorted names and invalid payload joins are rejected. The
texture-UI bank has an unsupported wrapper and remains excluded.

The isolated native oracle executes the original lookup/comparison/index/bind
routines on privately relocated bank tables. All 88 selection and rejection
checks pass. It also executes the full `0081FDA8` colour-correction wrapper and
real state emitters: 128 cases pass across source/target identity, explicit gamma
and mode arguments, and poisoned incoming state. It selects `ColorCorrect`,
enables colour writes, disables depth writes and front/back stencil, alpha,
depth, culling and blending tests. The shader-control packet retains an
inherited low bit. Resource providers, constants, target activation, gamma
callbacks and final draw/upload boundaries are controlled; actual texture and
target facts remain unresolved. This is not a whole-pass translation proof.

The reconstruction CLI gains explicit named-bank selection. Two `SimpleBias`
samples rebuild both programs from the named original slices, match source/
bytecode identifiers and native keys, and create D3D12 pipelines. Remaining
translation and native descriptor state is explicitly captured. These proofs
do not add independent pipeline coverage. Twenty-six synthetic bounds/selection
checks and existing reconstruction regression checks pass. No runtime/default/
launcher/release changes, no shared-checkout writes and no live benchmark runs.

Evidence and repeat commands are in
[shader reconstruction](shader-reconstruction.md#named-shared-passes-phase-160).
The next step is deriving shared texture/target context and the normal vertex
path's native input layout. Stutter reduction remains unproven.

## Phase 159 - Measure the conditional subset in live cold-cache races (2026-10-31)

Six isolated 1080p/2x/VSync HSR trials compare empty application caches with the
Phase 158 subset. Four bulk-scan trials use control/prepared/prepared/control
order; another control/prepared pair uses prepared files on demand. OS/driver
caches remain warm. Every trial starts with copied save data and its own cache;
the original checkout/runtime/processes are untouched. Runtime defaults do not
change. The script now refuses another game and cleans up only its own process.

**No consistent first-visit stutter reduction is established.** Bulk-prepared
early p99 is 82.0/84.4 ms, versus 57.5/54.4 ms controls; gaps over 50 ms are 65/66
versus 29/23. Later p99 is mixed (52.0/74.8 versus 54.3/50.6 ms). The on-demand
pair leaves early p99 essentially unchanged, 69.3 -> 69.9 ms, and improves later
p99 53.6 -> 49.3 ms / FPS 46.8 -> 50.0. One pair cannot establish a reliable gain.

Bulk startup loads 3,509-3,511 pipelines in 62.7-65.5 seconds while the guest
boots, including live-learned recipes. Only 142-144 of the 3,402 seeded keys are
marked used in prepared runs. On-demand startup loads zero upfront and reuses
files as requested. Significant new compilation remains. Workloads differ with
race progression, so compiler totals are not a controlled draw-for-draw reduction.
The first 45-second window includes the intended 30-FPS rolling start; loading
transitions are measured separately. One control has a retained unexplained
4.44-second later gap. Early screenshots show mostly HUD under all conditions;
no visual-readiness improvement is established. No cause for that appearance is
proven by these tests alone.

`scripts/test/shader_stutter.py` preserves logs/frames/screenshots and supports
both policies. Frame-metric threshold/window tests and PowerShell syntax checks
pass. Two setup trials (wrong title-ID path handling and hidden game window) were
discarded before the valid comparisons; only owned processes were stopped.
Conclusion: native-key coverage is useful provenance evidence, not a stutter
metric. Do not enable blanket startup scanning as a new player default. Target
shared critical passes/unresolved resource contexts and rerun the benchmark.
Detailed results: [shader-reconstruction.md](shader-reconstruction.md#live-first-visit-stutter-benchmark-phase-159).

## Phase 158 - Audit and prepare explicit context unions (2026-10-31)

The cheapest supported expansion is to enumerate independent conditional variants
instead of selecting one context. `--context-set rgba16` covers CCW/CW object
candidates, single/2x RGBA16 targets and active/fallback global candidates in one
preparation cache. `supported` additionally enumerates RGBA8/single. Identical
shader/state candidates merge while retaining all explicit contexts. Per-job
target sidecars preserve the selected native sample/format candidate.

The reproducible read-only variant audit freezes candidates before loading the
capture oracle. All 12 supported combinations produce 5,169 unique candidates;
the eight RGBA16 combinations produce 3,446. Whole-profile/program-prefix matches
predict 131 of 1,497 retained HSR links, versus 52 for the original context.
RGBA8 adds no matches. These predictions require native-key validation; they do
not establish live pass ownership. The comparison supplies no construction state.

Native validation confirms exactly 131 matching keys (8.75%), 79 more than the
original 52 (3.47%), with no baseline matches lost. All 3,446 requests succeed,
persisting 3,402 distinct pipelines and 204,354,804 bytes of driver blobs. The
measured developer run takes 676.9 seconds: 37.9 enumeration, 371.9 fragment
preparation, 186.0 vertex/request work and 80.4 native preparation. Native batch
metrics record 3,446 driver calls, 44 using cached blobs. Ordinary warmup then
loads all 3,402 recipes, rejecting none, in 2.7 seconds without guest entry.
These costs and coverage are for this machine/snapshot, not a first-run stutter
measurement or complete game catalogue. Intermediate developer files add storage.

Independent expansion checks cover all 24 context/cull-enable combinations and
per-job native target emission. Audit tests cover corrupted oracle inputs,
candidate immutability, link/key denominators and persisted recipe checksums.
Missing/conflicting CLI choices fail; existing profile/reconstruction tests pass.
No runtime/player defaults change and the original checkout remains read-only.
See [shader-reconstruction.md](shader-reconstruction.md#explicit-context-union-phase-158).

## Phase 157 - Prepare a capture-free conditional material subset (2026-10-30)

`scripts/prepare_material_shaders.py` now enumerates original material pairs,
derives ordinary-upload profiles and creates fresh native pipeline descriptors
without reading captures or a provenance audit. Explicit object/target/global
arguments select conditional candidates. Unknown bindings remain excluded.

Across 601 source containers, 17,861 of 132,158 material candidates reduce to 474
unique supported candidates. All 474 prepare successfully, producing 467 distinct
native pipeline keys, persistent driver blobs and ordinary warmup recipes. The
run uses 208 distinct vertex programs, 319 fragment programs and 47 fragment
profile groups. A subsequent comparison matches 52 retained HSR keys; 220 source
cache entries shared with the existing cache are byte-identical, none differ.
This comparison supplies no construction inputs. Driver blobs occupy 27,879,630
bytes on this adapter; they are local hardware/driver artifacts.

Twelve new process cases verify preparation gates, damaged code, nonzero expected
key rejection, whole-manifest validation and persisted driver-cache reuse. Twenty
existing proof cases still pass. Envelope, profile and CLI tests pass; isolated
build and runtime patch checks pass. Preparation is explicitly offline and
default-off, never enters the guest, and writes only ignored isolated output.
No original checkout, normal player defaults or release behavior changes.

This is a working developer subset preparer, not a complete player precompiler.
Live pass ownership, unresolved resource/alias contexts, full asset inventory,
launcher integration and actual first-run stutter measurements remain open.
Evidence and commands:
[shader-reconstruction.md](shader-reconstruction.md#capture-free-conditional-material-preparation-phase-157),
[shader-precompile.md](shader-precompile.md#capture-free-material-subset-developer-only).

## Phase 156 - Prove a whole independent ordinary-upload profile candidate (2026-10-30)

Developer `--independent-profile-path ordinary-uploads` builds the whole selected
translation profile from original material/control/texture facts and explicit
object/target/global candidates. It receives no captured state. Unknown sampled
facts, unsupported cube/volume/depth/stencil cases fail closed. Successful 2D
uploads, no target/depth-copy/mip aliases and no later overrides are explicit
context assumptions, not established live ownership.

Three shader/native pipeline proofs match source/bytecode/keys and create D3D12
pipelines with the independent profile and fresh native descriptor. Captures only
validate constructed state and code/key results. Another 768 native ordinary 2D
low-coordinate checks pass within the 2,304-case texture harness. Whole-profile,
unknown-context and prerequisite tests pass. No runtime/player/release changes.
This proves a supported conditional subset; complete catalogue, first-run
performance, actual pass ownership and launcher integration remain open.
Evidence: [shader-reconstruction.md](shader-reconstruction.md#whole-independent-ordinary-upload-profile-candidate-phase-156).

## Phase 155 - Derive authored compact fragment export precision (2026-10-30)

The bounded direct-pair reader supplies compact descriptor shader control from
original assets. 1,536 synthetic and 14,307 original-descriptor native checks
verify unchanged emission to shader control; all inventory descriptors select
16-bit export. The real emitter's command-space overflow path is excluded.

Developer `--material-fragment-control` rereads the original control word and
replaces export precision under explicit compact-binding/no-later-override
assumptions. Three shader/native pipeline proofs pass with fresh descriptors.
Control-source bounds, bit variation and CLI prerequisite checks pass. Other
translation/global resource facts and actual pass ownership remain open; no
runtime/player/release changes. Evidence:
[shader-reconstruction.md](shader-reconstruction.md#authored-compact-fragment-export-control-phase-155).

## Phase 154 - Construct fresh conditional native pipeline descriptors (2026-10-30)

Explicit developer `--native-target-path` selects a GPU-fetch, single-colour,
depth-backed target candidate; material and object-pass proofs are prerequisites.
The new default-off offline `RSX_PSO_RECONSTRUCT_NATIVE=1` discards captured native
state and constructs the descriptor from renderer constants, explicit target,
prepared material and object-pass fields. Target/sample profile bits are also
derived. Actual game pass ownership and remaining shader translation are open.

Three RGBA16/2x and two RGBA16/single shader/native pipeline proofs pass. A zeroed
captured descriptor still creates the expected pipeline with construction on and
fails with it off. Twenty process checks and poisoned-descriptor/target rejection
checks pass. RGBA8/single has synthetic coverage only. Isolated backend build and
runtime patch check succeed; no player/release/original-checkout changes. This
removes native descriptor state as a construction source for supported conditional
candidates, not all captured translation dependencies. Evidence:
[shader-reconstruction.md](shader-reconstruction.md#fresh-conditional-native-descriptor-construction-phase-154).

## Phase 153 - Reconstruct conditional object-pass culling and output gamma (2026-10-30)

1,536 isolated native checks recover object-wrapper entry/exit face, winding,
cull and output-gamma setup. Model draw and lighting helpers remain mocked;
live ownership and nested overrides are not established. Explicit developer
`--object-pass-path ccw|cw` combines this candidate with prepared material cull
enable and derives output gamma; capture only validates the selected candidate.

A new default-off offline switch `RSX_PSO_RECONSTRUCT_PASS=1` replaces native
cull mode/winding before key comparison and uncached D3D12 creation. Three CCW
and two CW shader/native pipeline proofs pass. Descriptor mutation/rejection
tests and twelve process checks pass, including malformed/missing/wrong state,
material prerequisite and explicit switch-off. Existing material/sampler/texture
checks pass; isolated build and runtime patch check succeed. Other translation,
target and pass fields remain captured; complete first-run preparation is open.
Original checkout/shared runtime and player/release defaults are unchanged.
Evidence: [shader-reconstruction.md](shader-reconstruction.md#conditional-object-pass-fields-phase-153).

## Phase 152 - Verify conditional initialized framebuffer cube descriptors (2026-10-30)

The environment oracle now retains the real descriptor initializer and native
format conversion. 512 controlled RGBA8 setup checks vary explicit cube/2D
creation, mip count, descriptor slot and unit. Initialized shape follows the
creation argument and survives getter/assignment/emission. Allocation remains
mocked. Poisoned incoming address tests show read gamma remains inherited.

Developer `--environment-texture-path framebuffer-2d|framebuffer-cube` requires
an explicit framebuffer sampler setup and texture reconstruction. It derives
shape/normalized-coordinate facts for the tested successful RGBA8 setup, retaining
unknown read gamma. A unit with shape known but gamma unknown remains incomplete
in sampling-state mode. No shape/path is inferred from capture.

With active dither and explicit cube setup, shape-only candidates match 1,044
retained links with no known-shape mismatch; 265 cover every sampled shape.
These are conditional shape candidates, not complete translation/pipeline
coverage. Three shader/native pipeline proofs now derive the nonzero global
environment cube bit and match source/bytecode/native creation while explicitly
retaining its read gamma. Original checkout/shared runtime, player defaults and
release packaging are unchanged. Work continues on producer context and the
remaining output/pass/target state. Evidence:
[shader-reconstruction.md](shader-reconstruction.md#conditional-initialized-framebuffer-shape-phase-152).

## Phase 151 - Derive read-gamma/coordinate bits and conditional dither texture facts (2026-10-30)

Texture constraints now include read-gamma bits and upper-unit unnormalized
coordinate flags, preserving output gamma, sample count and low-unit target/
coordinate mapping. A tighter supported-format gate excludes unsupported and
depth formats that can depend on prior binding or depth-renderer context; it
leaves the measured 160,461 local 2D bindings unchanged.

The production bind/gamma/key harness matches 2,304 synthetic cases. Another
288 real emitter checks verify dither/PCF shape, gamma and coordinate facts for
explicit active/fallback paths. Primary active dither/PCF are texel-addressed;
alternate dither and fallbacks are normalized. Other globals stay unresolved.

Under explicit active selection, known texture-bit candidates match 1,028 links,
with 16 mismatches; 122 have all sampled units covered for these selected fields.
Fallback matches 30 (26 complete). These counts do not include output gamma,
low-unit mapping or other pass state and do not establish path ownership. Three
partial shader/native pipeline proofs derive the new bits, match source/bytecode/
keys and create D3D12 pipelines. `--material-texture-state` is developer-only.
Synthetic and existing sampler/material checks pass; no runtime/player/release
changes. Work continues on global environment/shadow texture facts and remaining
pipeline state. Evidence: [shader-reconstruction.md](shader-reconstruction.md#texture-sampling-state-bits-phase-151).

## Phase 150 - Derive local texture shape translation bits (2026-10-30)

The new read-only shape audit derives supported local FORMAT dimension/cube
flags and packs independent cube/volume value/mask pairs. Global bindings,
unsupported dimension combinations and empty extents remain unknown. Gamma,
output/sample fields and unresolved units are preserved. A native DLL using
production bind assignments and shape-key helpers matches 768 synthetic cases
across 2D/cube/volume and all sixteen units under default renderer switches.

The supported inventory's 160,461 local bindings are all 2D. Same-pair known
shape candidates match 843 retained links with no known-bit mismatches; 16 have
every sampled shape known, 827 are partial and 654 lack known bindings. This does
not recover the game's actual cube/volume paths or establish unique ownership.

Developer `--material-texture-shapes` reparses the original selected definition
and replaces only known shape bits before shader translation. Two complete local
shape samples and two partial samples preserving a captured global environment
cube match shader source/bytecode/native keys and create D3D12 pipelines. Sampler
and prepared material fields are also derived; remaining translation/pass/target
state stays captured. Synthetic integrity/containment/mask/global exclusion and
existing material/sampler regressions pass. No runtime/player/release change;
original checkout/shared runtime remain untouched. Evidence and next global/
translation work: [shader-reconstruction.md](shader-reconstruction.md#asset-local-texture-shape-bits-phase-150).

## Phase 149 - Recover mirror filter overrides without guessing wrap (2026-10-30)

The isolated oracle executes the mirror scene-copy consumer `00705FC0`, real
copy/framebuffer getters, registry setter and emitter under controlled scene/
render helpers. 4,096 varied sampler/unit checks force linear min/mag filtering
while preserving incoming S/T wrap. Source sampler bytes remain unchanged;
viewport/camera changes are restored and descriptor generation updates match.
This is controlled descriptor processing, not actual scene rendering.

Developer `--mirror-sampler-path scene-copy` derives only filter-class bits
(value 8, mask 12) for the exact mirror signature. The audit/proof tools now
support partial masks within sampler lanes; wrap stays unresolved and complete
proofs reject any unknown sampled bits. Audit schema 2 reports `lane_masks`.
Synthetic CLI tests accept different wraps under the measured filter mask and
reject wrong filtering/full-key completion. Existing native checks and an
environment pipeline proof regress successfully.

The 63 asset mirror requirements have no same-pair candidate in the retained
HSR links, so complete sampler coverage remains 861/1,497. No mirror shader/native
pipeline proof or coverage gain is claimed. Runtime/player/release behavior is
unchanged, and original checkout/shared runtime remain untouched. Next recover
the live source's wrapping/ownership and remaining translation/pass/target state.
Evidence: [shader-reconstruction.md](shader-reconstruction.md#partial-mirror-scene-copy-sampler-phase-149).

## Phase 148 - Recover conditional framebuffer environment sampler setup (2026-10-30)

The isolated native oracle runs the real post-allocation texture setup,
framebuffer getter, environment descriptor assignment and emitter. Allocation
and address helpers are controlled stubs, not real allocation or scene rendering.
1,024 successful checks derive linear/clamp for one mip and trilinear/clamp for
multiple mips; 1,024 failed-allocation checks preserve sampler words. Existing
callback/emission/shadow checks pass.

Developer `--environment-sampler-path framebuffer-single|framebuffer-mipped`
requires successful setup and no later overrides; captures never select the
path. Mirror/unknown signatures remain unresolved. With active dither/LV shadow,
the mipped candidate completes sampled sampler lanes for 861/1,497 links (336
before), with 183 known-lane mismatches and 453 without known bindings. Single-mip
stays at 336. This is conditional sampler coverage, not full pipeline coverage.

Four environment-using samples rebuild source/bytecode/native keys and create
D3D12 pipelines, also replacing prepared blend/write-mask/depth fields. Other
translation/pass/target state stays captured. Synthetic signature/overlap/choice
checks and native integrity/wrong-key/material negatives pass. Original checkout,
shared runtime, normal build, player defaults and release packaging are unchanged.
Evidence and remaining mirror/ownership/translation work:
[shader-reconstruction.md](shader-reconstruction.md#conditional-framebuffer-environment-samplers-phase-148).

## Phase 147 - Recover the conditional LV shadow sampler from pass setup (2026-10-30)

The expanded native oracle verifies 1,024 synthetic dynamic descriptors and 64
absent-resource fallbacks through environment/shadow/color-shadow/mirror emit
callbacks. Supplied address/filter words are copied unchanged; absent resources
use the initialized fallback. Identifier-wide fixed sampler guesses are invalid.

Read-only tracing then found the LV shadow pass explicitly overwrites S/T wrap
to clamp and both filters to linear before assigning its descriptor. The full
local pass routine, with scene/render/resource access mocked and the real
shadow descriptor setter/color conversion retained, passes 256 varied input
sampler checks. Another 256 disabled-gate cases leave inputs untouched. Both
the shadow descriptor and its color-copy select bank register 9. This tests the
sampler setup path under controlled inputs, not actual scene rendering.

Developer `--shadow-sampler-path shadow-lv` adds only the relevant address/filter
bits for exact shadow signatures; all other pass fields remain unknown. With
active dither, same-pair candidates completely cover sampled sampler lanes for
336 links, versus 122 without this shadow variant. The conditional constraints
match known lanes on 861 links and disagree on 183; they must not be imposed on
every draw. Four car-interior samples with real shadow requirements rebuild
source/bytecode/native keys and create D3D12 pipelines with complete derived
sampler keys and prepared material fields. Remaining translation/target/pass
state is still captured. No normal game or runtime source changed. Evidence:
[shader-reconstruction.md](shader-reconstruction.md#conditional-lv-shadow-pass-phase-147).

## Phase 146 - Derive conditional dither/PCF sampler lanes and rebuild pipelines (2026-10-30)

The local oracle now executes the real dither/PCF emitters and command-building
helpers with controlled active resource providers. Fallback paths run the real
default texture initialization, descriptor copy and binding routines. Across
three identifiers, sixteen units, three resource sizes/addresses and two paths,
288 emitted sampler address/filter pairs match the independent implementation:
active nearest/repeat selects bank register 4; fallback linear/repeat selects 8.

The audit and reconstruction CLI accept explicit `--global-sampler-path` with
active/fallback choices. Only measured name/kind/identifier signatures qualify;
unknown signatures, duplicate global units and local/global overlaps stay
unresolved. The selected path is a conditional input, not inferred from capture.
Same-pair candidates fully cover sampled sampler lanes for 122 active-path or
26 fallback-path links (132 union; 16 overlap). This is not full pipeline coverage
or evidence of exact draw ownership. Active-path known-lane matches total 1,030;
14 disagree, while fallback has matching candidates for those 14 additional links.

Eight active-path and two fallback-path shader/pipeline samples rebuilt from
assets with complete sampler keys, matching source/bytecode/native keys and
creating in D3D12. Prepared blend/write-mask/depth replacement remained active.
Other translation/target/pass fields remain captured. Synthetic malformed,
overlap, branch-selection and source-integrity checks pass. No runtime or normal
game build changed. Details: [shader-reconstruction.md](shader-reconstruction.md#conditional-ditherpcf-samplers-phase-146).

## Phase 145 - Resolve global callback initialization in isolation (2026-10-30)

The new local-only `scripts/test/shader_global_registry_native.py` executes the
disc build's initializer against private ELF/BSS memory. All seven inventoried
identifiers resolve to lookup/emit callback OPDs. Negative initialization gates
leave the selected slots empty; changing the stubbed fallback result does not
change their final callback pointers. Two real lookup handlers additionally pass
ten private-memory sentinel checks, including values with the high bit set.

Dither/PCF share one lookup handler; shadow/color-shadow share another. Their
emit handlers differ. No emit callback was executed, and this does not recover
sampler registers or expand complete pipeline coverage. Structural inspection
points next to the dither/PCF emitter helper and shadow texture wrapper, still
unverified for sampler derivation. No game process, normal build or shared
runtime was changed. Details and local evidence:
[shader-reconstruction.md](shader-reconstruction.md#global-callback-initialization-phase-145).

## Phase 144 - Resolve coherent scalar aliases and inventory global requirements (2026-10-30)

The material sampler reader now accepts distinct scalar sampler names sharing a
unit only when every name binds the exact same texture-info index. Missing names
leave that unit unresolved; conflicting indices are rejected even with identical
sampler settings. Unsupported array/relocation layouts remain rejected.

The same inventory yields 160,461 resolved unit bindings, including 52,407 alias
groups, and 659 unsupported-record shader-data groups. Same-pair known-lane
candidates match 843 captured links versus 349 before; each has at least one
candidate whose known lanes agree, not necessarily agreement among all candidates.
827 links are partial, 16 complete, and 654 have no known sampled binding.
Complete coverage is unchanged; global/pass-bound units remain unresolved.

The separate SHDS 0x38 table provides global names/unit fields/kind/identifier
metadata. Reports retain the signatures for dither, environment, shadow, PCF
and mirror requirements. Identifiers are not treated as established runtime
registry addresses or used to invent texture/sampler defaults. Declared global
units are excluded from local derivation even when their unit fields overlap.

`--material-sampler-lanes` adds an explicitly partial reconstruction mode. It
reparses original bindings and derives known lanes from assets, retaining other
lanes from capture with masks reported. A character material's alpha/emission
aliases rebuilt its local sampler lane, matching shader source/bytecode and
native key and creating a D3D12 pipeline. Its global dither lane stayed captured;
the prepared material descriptor replacement was also active. The complete
sampler mode still rejects missing units.

Synthetic alias/conflict/missing/global-overlap checks and existing integrity,
output-containment and eligibility checks passed. No runtime/normal-build
changes were needed; the isolated proof never ran guest gameplay. Evidence and
next global-identifier initialization/binding work:
[shader-reconstruction.md](shader-reconstruction.md).

## Phase 143 - Derive effective sampler keys from material texture bindings (2026-10-30)

`shader_material_textures.py` reads a bounded SHDS named-sampler layout and
joins material definition keys to texture-info table indices, distinct from
image IDs. It derives sampler-bank lanes from authored filter/wrap registers.
Unsupported record fields, aliases and invalid indices are rejected; unresolved
sampled units do not receive defaults. A native differential check matched the
production sampler selector in 2,048 varied cases without game/GPU startup.

The 599-container / 1,098-model inventory supplied 72,645 accepted definition
texture bindings; 5,505 shader-data groups had ambiguous names/units and 468
had unsupported records. Of 1,497 captured links, 349 had known-lane candidates
and all matched those lanes. Only 16 were complete for all sampled units, with
333 partial and 1,148 lacking known sampled bindings. This does not establish
exact draw/image ownership or global texture-state coverage.

`shader_reconstruct.py --prepared-material-state --material-samplers` requires
complete sampled bindings from the same definition as the state proof, reparses
the original model during proof and derives the sampler key from zero. Captured
values are an equality oracle only. A trilinear-repeat car-menu material and a
trilinear-clamp car-LOD material matched rebuilt shader source/bytecode, native
keys and actual D3D12 creation, also replacing prepared blend/mask/depth fields.
Remaining cube/gamma/unnormalized/shadow and pass/target/culling fields stay
captured; no complete first-run precompiler is implied.

Synthetic reader/CLI checks passed for index identity, incomplete bindings,
malformed/ambiguous records, bounds, mismatches, input integrity and ignored
output containment/no-overwrite. No runtime changes were needed; both proofs
used the existing isolated diagnostic EXE and never executed guest gameplay.
Full results/commands and next alias/global-binding work:
[shader-reconstruction.md](shader-reconstruction.md).

## Phase 142 - Replace native descriptor fields from prepared material data (2026-10-30)

`shader_reconstruct.py --materials <audit> --prepared-material-state` reparses
material definitions/state indices and hashes the original state slice, applies
the measured preparation rule, then supplies derived blend/write-mask/depth
values to the native offline proof. Captured state is still an eligibility
oracle; unsupported stencil/mask passes are excluded.

Default-off `RSX_PSO_RECONSTRUCT_MATERIAL=1`, honored only by the guarded offline
proof, validates a bounded `material.state` file and replaces blend fields and
colour masks on active render targets plus depth comparison/write mask before
production key calculation and uncached D3D12 creation. Culling orientation and
all other descriptor/pass/texture fields remain captured. This is partial
reconstruction, not capture-free preparation or exact material ownership.

Six selected samples matched rebuilt shader source/bytecode and native keys and
created successfully: three opaque character cases, one blended character, a
blended car-menu case with depth writes off, and one opaque car interior. A valid
wrong colour mask changed the computed key and prevented creation; missing or
malformed material files were rejected. Explicit mode `0` ignored malformed
state and preserved the legacy proof. Prior truncated-recipe/damaged-code/
wrong-key checks passed; all runs confirmed guest entry was not executed.

Native unit checks cover descriptor replacement across MRTs, unchanged unrelated
fields, invalid values and unsupported stencil. Python checks cover candidate
eligibility. The isolated compile/relink and pinned-overlay reapply succeeded;
shared runtime and normal binary are unchanged. Evidence/next fields:
[shader-reconstruction.md](shader-reconstruction.md).

## Phase 141 - Reproduce material preparation and corroborate consumed bytes (2026-10-30)

The isolated runtime gains bounded/default-off `GCM_DEPTH_PROVENANCE`, with
milestone delay and record cap. It snapshots mapped depth packets and surrounding
material blocks before method processing, without guest writes. Native tests
cover disabled paths/no reads, gate timing, packet filtering, unmapped memory,
cap, JSON and refusal to overwrite an existing capture.

A 1080p/2x-MSAA HSR sample recorded 512 packets across parts of three frames,
63 addresses, all inside CALLs and all with LEQUAL in the submitted bytes. The
final window image had the racing HUD. Of the full blocks, 17 matched original
assets exactly, 242 differed only in depth words, and 253 did not match. This
places the common disagreement before renderer key generation.

Local lifted function `0x00834968` suggested material preparation. The new
independently expressed offline `prepare_state()` converts LESS to LEQUAL and
recomputes a metadata flag, preserving other modes/fields. An isolated oracle
compiled from the local lifted routine matched every word for 3,644 real and
2,048 varied synthetic blocks (5,692 checks); original generated source was
unchanged and oracle outputs stay ignored. With `--prepare-materials`, same-pair
depth candidates match all 1,164 captured links that have candidates, versus
13 before; all four checked state fields match together for 1,146 versus 9.

Prepared blocks also match 467/512 consumed full-block snapshots exactly,
versus 17 raw; 45 remain unmatched. This corroborates preparation but does not
identify a unique asset/draw owner or directly trace the live guest writer.
`shader_depth_commands.py` preserves exact/depth-only/prepared/unmatched and
invalid distinctions; synthetic parser/CLI tests passed. Remaining pass state
must not be guessed or globally overridden.

The separate backend/FIFO compile and relink succeeded; no full clean build or
performance claim is made. Shared runtime/development EXE remained untouched;
the overlay reapplied against the pinned base. Evidence, commands and next
reconstruction integration: [shader-reconstruction.md](shader-reconstruction.md).

## Phase 140 - Decode authored material state and falsify direct reuse (2026-10-30)

The isolated branch adds `scripts/shader_material_state.py`, a read-only audit
of MDL3 material definitions and their GCM state indices. The 0xA0-byte state
blocks contain three fixed RSX method packets and a return; trailing words stay
uninterpreted. The reader derives blend key, colour mask, depth bits and cull
enable, bounds all references and rejects unsupported packet layouts/enums.

The accepted-pair inventory covers 599 containers / 1,098 models and 3,644
decoded state blocks, without invalid bindings/rejected state blocks. Of 1,497
verified captured links, 1,164 have same-pair authored candidates: blend matches
1,163, colour mask 1,146, cull-enable 1,164, depth bits only 13, and all four in
the same candidate only 9. In 1,110 links where the other three fields matched,
assets specify LESS/write-on while live state is LEQUAL/write-on; another 24
show that compare difference with writes off. Do not use asset state unchanged
or substitute LEQUAL globally. Exact draw ownership and the source of the state
change remain unproven; a pass override/runtime material patch is a hypothesis.

The differential native test compiles this runtime's own key functions into a
scratch DLL. All 2,048 varied synthetic cases and 3,644 real decoded blocks
matched (5,692 checks); no game/GPU starts. Synthetic reader/CLI tests cover
malformed packets/enums/indices, extent checks, capture integrity, deliberate
depth mismatch, ignored output/no-overwrite and unchanged inputs. Shared runtime
and game build are unchanged. Full evidence/commands and next ownership/pass
analysis: [shader-reconstruction.md](shader-reconstruction.md).

## Phase 139 - Recover material-authored shader pairs (2026-10-30)

On the isolated `feature/shader-coverage-audit` worktree, the new read-only
`scripts/shader_materials.py` follows MDL3 material-data pointers into declared
SHDS vertex/fragment tables. Fragment descriptor pointers join the 0x40 table's
instruction ranges. Exact table membership, unique joins and enclosing model
bounds are required; unsupported/malformed data is rejected.

Across 601 indexed containers, 1,106 models provided 16,768 accepted material
records with direct pairs; 122 records failed shader-wrapper/fragment bounds.
Authored pairs matched 452 of the HSR snapshot's 562 distinct captured shader
pairs (80.4%). This measures structural candidate pairs, not native pipeline
coverage or a complete asset inventory. Match normalization follows the existing
vertex identity extent and fragment inline-constant rules.

`shader_reconstruct.py --materials <audit report>` reparses original material
references before choosing both shaders from the same model. A character and a
car-interior sample matched rebuilt VS/PS bytecode and native keys and created
successfully in D3D12. Rendering state is still captured, so independent
first-run preparation is not complete. No player/runtime behavior changed.

Synthetic pointer/bounds/ambiguity and CLI containment/no-mutation checks passed,
as did existing vertex checks and native negative checks for truncated recipes,
damaged bytecode and wrong pipeline keys. These used the existing isolated
diagnostic EXE; no full rebuild or race performance test was needed. Shared
runtime and development binary were untouched. Local reports and next state
extraction work are recorded in [shader-reconstruction.md](shader-reconstruction.md).

## Phase 138 - Rebuild sampled shaders from assets (2026-10-30)

On `feature/shader-coverage-audit`, `scripts/shader_reconstruct.py` finds bounded
SHDS vertex payloads, removes the observed wrapper and converts BE words to
native decoder input. The 601 indexed containers contain 7,265 bounded payloads;
211 / 216 captured vertex-input IDs have exact instruction-prefix candidates.
This is candidate discovery, not proof for all those programs.

Seven shader pairs were independently rebuilt from original asset slices:
three executable programs, three GPU-fetch car LOD cases and one GPU-fetch car
case targeting R16G16B16A16_UNORM. Generated VS HLSL and both compiled shader
identifiers matched; the PS pass used a fresh cache and matched its captured
source key too. With the captured descriptor as state oracle, all seven native
pipeline keys matched and D3D12 creation succeeded. No captured raw shader or
cached DXBC was used for shader compilation. The native proof bypasses the
application's driver-blob cache but does not clear driver-internal caches.

`RSX_PSO_RECONSTRUCT` is an opt-in offline-only proof mode; it does nothing in
normal startup without `GT5P_SHADER_PRECOMPILE_ONLY=1`. Synthetic extraction and
mutation checks passed. Native negative checks rejected malformed recipes,
changed bytecode and an incorrect pipeline key without guest entry. The updated
backend was compiled/relinked separately, preserving the shared runtime and
normal game EXE. Reports and all game-derived outputs stay ignored and local.
See [shader reconstruction](shader-reconstruction.md) for commands/evidence.

**Open:** material/pass state and shader pairing are still captured or selected
using diagnostic records. Derive those from assets/rendering rules next, before
claiming a portable catalogue or player first-run preparation.

## Phase 137 - Record shader-input to pipeline provenance (2026-10-30)

Branch `feature/shader-coverage-audit`. The runtime overlay now includes an
opt-in `RSX_PSO_PROVENANCE=<directory>` recorder; see
[shader coverage](shader-coverage.md#optional-pipeline-provenance-recorder-phase-137).
It records per-draw vertex input ranges and generated source at successful VS
compilation, then links bounded FP input snapshots, generated source, compiler
keys/flags and translation-key state to VS/PS DXBC identifiers and native
pipeline request IDs. Missing primary-VS provenance is represented explicitly.
Pending driver requests are labeled queued; recording is not creation success.

The present-thread diagnostic deduplicates pipeline/program/vertex combinations,
flushes JSONL links, and bounds link count (8192 default, configurable 1..16384).
Default-off and explicit `0` perform no output initialization/input reads in the
serializer regression. The audit verifies input/source blob hashes and joins
requests to recipe IDs and exact VS/PS identifiers, with distinct missing,
mismatched and invalid statuses. Full asset vertex/material reconstruction and
pipeline replay are still unimplemented; this does not eliminate stutters.

The patched backend was compiled in an isolated runtime and linked to a separate
test EXE using existing development objects; the normal development EXE, shared
runtime sources and their local changes were not overwritten. The regenerated
overlay preserves unrelated patch sections byte-for-byte and applies/checks in
a fresh pinned checkout. Native serializer and synthetic provenance/corruption
checks passed. Two short instrumented 1080p/2x-MSAA race samples reached racing
HUDs; a further HSR sample validates the final pre-translation snapshot change.
Local records, sources, bytecode and reports are ignored and not distributable.

The initial captures contained 1,763 HSR / 1,943 Daytona requests. The audit
caught 2 / 7 raw-FP checksum mismatches: the first implementation hashed and
wrote live guest bytes separately. The final implementation snapshots a
bounded FP on a pipeline miss and uses that snapshot for translation and
recording. Its follow-up HSR sample produced **1,497 / 1,497 verified recipe
links, zero invalid input blobs**, all with captured vertex inputs; 1,204 links
also matched fragment programs in the extracted asset catalogue. These are
pipeline request links, not unique shaders or proof of independent replay.
Four recipes created during that final run were checked separately with their
bytecode checksums and added to the previous inventory before the final join.
Evidence: audit-worktree `scratch/provenance-snapshot-hsr-20261030/audit-final.json`,
`scratch/provenance-snapshot-recipe-check/checks.json`, and the development
checkout's `scratch/pv/provenance-snapshot-hsr-20261030.*` logs/window shots.

## Phase 136 - Measure asset/shader/pipeline coverage (2026-10-30)

Added a read-only developer audit on `feature/shader-coverage-audit`; see
[shader coverage](shader-coverage.md) for commands, evidence and limitations.
Two short real race runs (High Speed Ring and Daytona, 1080p/2x MSAA) recorded
553 and 586 fragment-program files, with 484 and 535 structural matches to the
existing extracted SHDS catalogue. Inline constant changes and trailing padding
account for most matches; 69 and 51 remain unmatched. These percentages are
program-corpus coverage, not precompiled-pipeline coverage or full-race coverage.

The asset snapshot has 8,069 bounded payloads / 5,864 instruction identities;
73 payloads fail END/constant bounds. The audit walk was compared to a newly
compiled production decoder: 9,208 real inputs agreed, with the same 73 rejected.
Synthetic checks cover constant variants, unknown/malformed programs, damaged
recipe/code dependencies, checksums, profiles and membership indices.

All 49,060 accumulated recipe envelopes had expected-size DXBC dependencies
present. A 64-recipe sample additionally passed renderer checksums. Native GPU
pipeline creation/current-version compatibility was not checked. Existing
recipes, raw shader corpora and pooled profiles do not record a reliable join
from PS3 program + translation state to DXBC + native pipeline. This provenance
gap is the next implementation target; vertex/material/pass extraction remains
absent. No gameplay renderer, settings or release behavior changed. Reports and
all shader-derived data remain ignored and local.

## Phase 135 - Upgrade to pinned ps3recomp v0.18.0 (2026-10-27)

Branch: `upgrade/ps3recomp-v0.18.0`. The upstream pin is
`4e8f3ca87a3e1d87bb83b8b7e9348fe2685cd514`, v0.18.0 and upstream master
at the start of this work (542 files changed from `5244db9`). The runtime
lives in `../ps3recomp-gt5p-v018`. The old shared runtime and junction are
preserved; its source diff matched the pre-upgrade backup byte for byte.

`config/ps3recomp.json`, `scripts/setup_runtime.py` and
`patches/ps3recomp-4e8f3ca8-local.patch` reproduce the pinned base and GT5P
overlay. The patch applied to a pristine worktree, passed reverse checks,
and was recognized on repeat setup/check runs. Setup refuses unrelated dirty
checkouts and a destination inside GT5P that is not a separate checkout.

**Compatibility decisions:** retain the port's complete D3D12 renderer,
FIFO/command handling, SPURS policy scheduler, codec callbacks, optimized
SPU helpers and diagnostic-aware chained dispatcher. Merge upstream lifters,
HLE registrations, bounded memory mapping, dynamic MFC/coherency registries
and extended shader APIs around them. This does not enable Vulkan/Metal
or adopt every upstream scheduler/float implementation. Details and rollback:
[ps3recomp-upgrade.md](ps3recomp-upgrade.md).

**Integration faults fixed:** the merged SPU channel code declared process
policy counters as TLS; that linked but crashed at dispatch. The declarations
now agree with the retained policy scheduler. Pad polling mixed the old SRW
lock with the new pad mutex; it now consistently uses the pad mutex with the
SDL owner thread. Legacy volume-unit masks are converted for the new shader
API. GT5P's renderer unwraps upstream's WPOS helper before its own conversion;
otherwise its different b1 layout left `fp_alpha` undeclared in shaders.
Crash logging gained executable-relative host addresses for native faults.

The re-lift emits 50,064 PPU functions (one fewer: an interior epilogue is a
local label in its parent), 9,115 SPU functions, and 1,236 HLE handlers across
93 modules. The SPU workload registry is unchanged. All post-lift hooks were
reapplied and checked. The new generated inline memory model replaces the
older force-included shim, and uses the new coherency bitmap. Deferred
callbacks and callback stacks remain; explicit-target calls are added.
Release builds with two compiler processes fit this 16 GB machine. Derived
code, old executable/tree, logs and captures stay ignored.

**Fixtures passed:** volume textures/GPU sampling, fragment source ranges,
upper-unit coordinates/samplers/pipeline keys, depth-clear reuse, async PSO
scheduling, shader job ownership, deferred condition callbacks, SPURS
arguments, native audio math/dispatch, SDL hotplug/WASAPI recovery and debug
export gating/fault handling. Upstream's lock-line coherency fixture passed
195 assertions through the PPU store path.

**Live validation** uses 1080p, 2x MSAA, VSync and async shaders/PSOs, with
settings disabled. Acura reached its milestone at 31.6 s and rendered at
29.5 FPS (`upgrade-v018-dealer-final`). The first High Speed Ring run rendered
the race, mirror, map and HUD; its 39.0 FPS mean includes new variant
compilation and 135 seconds of retained race-prewarm processing, so it is
not a steady-state comparison.

The warmed High Speed Ring run (`upgrade-v018-hsr-warm`, bulk startup/race
prewarm off) measured 57.9 mean FPS over 61.4 s, title median 60, median
16.7 ms, p99 30.6 ms, max 200.5 ms and 2.6% over 20 ms. FIFO walk was
6.25 ms/frame (6.06 ms CPU). New DXBC compilation was zero in the sample,
though first driver-pipeline encounters remained. Phase 134's 59.1 FPS /
p99 21.5 ms was an earlier run, not a paired A/B; no speedup is claimed.

Daytona also reached actual racing: title median 58 FPS over a 20-second
smoke sample (`upgrade-v018-daytona`), with the HUD/map/mirror visible.
The opening movie rendered different frames through avcodec-61.dll at
1080p (`upgrade-v018-movie`). `shader_warmup.py` passed blocking/background
valid/damaged cases. The fixture selects recent smoke-run recipes rather
than arbitrary oldest entries from earlier root-signature generations;
its explicit damaged-input cases still verify rejection. No long race
soak or claim of fixing all existing stutters is made by this upgrade.

Two early startup checks had about 250 ms GPU-fence waits even with bulk
startup warmup off. The saved pre-upgrade executable ran normally at the
same path. After the diagnostic rebuild, startup/menu timings returned to
normal in repeated VSync runs, including with diagnostics disabled; no root
cause was established. `RSX_PRESENT_DIAG=1` logs sync interval, Present
result/call time, GPU timestamps and foreground state if it recurs. Do not
call this a proven compiler fault or a fixed deadlock.

## Phase 134 - Re-lift with the GT5 branch's lifter (2026-10-23)

The GT5 branch (BCUS98114) changed the shared ps3recomp checkout. This phase
re-lifts GT5P with it and checks that nothing regressed.

**What the PPU lifter change does here.** The PPU lift has the same
50,065 functions as before. The GT5 work's new lowerings (`stdbrx`,
`vexptefp`/`vlogefp`, `vpkuhum`) change no GT5P code. The `_cs_N`
stack-offset fix (`PPU_LIFT_CS_R1DELTA`, lift time) is the only difference:

- a lifted epilogue used to restore a callee-saved register from a snapshot
  taken at its prologue store, even when r1 had changed in between by
  something other than `addi`;
- those 3,043 restores in ten chunks now load from the guest stack, as the
  instruction does.

The two forms differ only if the stack slot was written in between. On the
GT5 branch that difference broke its boot.

**The SPU lift is unchanged.** It is byte-identical: 9,115 functions, and
`spu_workloads_bcus98158.c` has no diff. The HLE NID table gains seven
entries, the same ones the GT5 branch added: `cellGcmMapEaIoAddressWithFlags`,
`cellKbRead`, `cellKbGetConfiguration` and the debug-dump entries.

**Runtime changes GT5P picks up by default.** One: `cellFsRead` now touches
each 4 KB destination page before `fread` (`FS_READ_PRETOUCH=0` turns it
off). A `ReadFile` into an uncommitted guest page failed silently. The GT5
branch's real lwcond (`PS3_LWCOND_REAL`) and one-shot timers
(`PS3_TIMER_ONESHOT`) are opt-in and stay off here.

**Checks after a clean rebuild** (scratch/pv/relift-*):

| Test | Result |
| --- | --- |
| `winshot.ps1`, Acura dealer | Page at 33 s; it draws correctly at 30 FPS |
| `race.ps1 -FrameTest`, High Speed Ring | 59.1 FPS; median 16.6 ms; p99 21.5 ms; 1.4% late; walk 6.17 ms/frame |
| `pitshot.ps1`, Daytona Race Mode | Page at 29 s, 29.6 FPS; the crew animate |

Phase 108 measured 59.5 FPS, p99 20 ms and 1% late. The frame-test numbers
are within the run-to-run spread. None of the three logs contains a
recursion cap, a NULL `bctr`, an "indirect tail ... no lifted entry" line or
`STUCK`. The pre-relift `generated/` and exe are kept in
`scratch/gen-prerelift/` for rollback.

## Phase 133 - Anisotropic filtering (2026-10-22)

The user reported distant objects blurry, then sharp up close, and asked
about draw distance.

**The cause:** texture filtering. The title sets no anisotropy
(TEXTURE_CONTROL0 bits 4-6 are 0, for example `ctl0=0x80078000`), and the
backend's bank of 12 static samplers was plain trilinear or bilinear. Road,
grid markings, walls and boards seen at a slant took a small mip early.

**The fix:** the bank's filtered entries are `D3D12_FILTER_ANISOTROPIC`
with MaxAnisotropy `RSX_ANISO` (default 16, 1 = off). Point entries stay
point. Setting: F1 GAME > Texture filtering (Trilinear / 4x / 8x / 16x),
`game.anisotropy`.

**Measured** at 1080p:

- **Same race moment (`cap_an1` against `cap_an16`, QuickArcadeRoot+12 s):**
  the distant grid-box lines, the wall lettering and the road texture stay
  sharp.
- **Warm frame test (`anft2`):** 59.4 FPS, 1.5% late.
- **The first run after the change** rebuilds every pipeline, because the
  root signature is in the pipeline key. The cold `anft` gave 53.7 FPS,
  and a cold capture showed cars without bodies and the HUD over black.
  Both cleared on the next run.
- **Dealer (`andl`):** unchanged.

**Not changed:** the title's geometry levels of detail (model swaps by
distance). A draw-distance or LOD scale would have to be found in the
title's code.

## Phase 132 - Cockpit mirrors (2026-10-22)

**The fault.** In the cockpit view the interior and door mirrors were black,
in 8-bit as well as 16-bit.

**How the title draws them** (1080p capture `cap_cock`, Select at +22 s):

- The mirror views are drawn straight into the scene target `0x01980000`
  at their screen places: 281x147 at (0,274) for the interior mirror, 321
  draws; 211x164 at (1025,648) for the door mirror, 102 draws.
- Before them, op310/311 stamp the mirror shapes into the scene's stencil:
  colour writes off, compare ALWAYS, pass op REPLACE, ref 1 and 3
  (`ds=0x35FE6231`).
- A depth-only clear follows (op312), and the mirror draws test stencil
  EQUAL ref.

**The cause.** `rsx_stencil_mask_pass` sent every stencil-writing,
colour-masked draw to the glyph-mask stand-in target keyed by the zeta
offset. That is right for the 2D text, which the title then samples as a
texture. The mirror stamps therefore reached no stencil buffer, and every
mirror draw failed its test.

**The fix.**

- A mask pass needs the text's operations: INVERT (even-odd fill),
  INCR/DECR_WRAP (winding) or ZERO (the erase after the cover). The menu
  capture `cap_hpm` shows text using only INVERT (`0xF600C231`) and ZERO
  (`0xF6004451`).
- A first version without ZERO garbled the menu text (`mtxt`).
- `RSX_STENCIL_MASK_ANY=1` restores the old rule.
- A draw that tests stencil now keeps its zeta offset even with depth test
  off (`RSX_STENCIL_ZETA=0` old), so the stamps bind the scene's
  depth-stencil buffer.

**Checked:**

- Cockpit at 1080p (`cock2`, `cock4`): both mirrors show the view behind.
- Cockpit at 3440x1440 native (`cock3`): the interior mirror works.
- Pit, Track Select, popup and HUD text (`mtxt2`): intact.

## Phase 131 - No dither noise, no banding (2026-10-22)

The user asked to remove the dithering and fix any banding.

**What the dither is.** The title adds a signed noise to hide 8-bit banding.

- **How it is applied:** a small wrapping texture is sampled at the pixel
  position, expanded to -1..1, scaled by a program constant and added to
  the colour.
- **Where it comes from:** unit 15 in materials (105 programs) and a 16x16
  texture on unit 1 in the final tone-map pass into the display (menu
  frame `cap_hpm`, op842 `0x057B4B41`). The second is what showed on
  screen.

**The fix.**

- **16-bit colour targets (`RSX_HIGH_PRECISION`, on):** `rsx_surface_dxgi`
  maps the title's 8-bit colour targets to `R16G16B16A16_UNORM`. The range
  is the same 0..1, so blending and saturation are unchanged, and pipelines
  and targets stay consistent. Guest memory still holds 8-bit pixels:
  - the fill from guest memory converts (x 257);
  - write-backs and NV3089 readbacks copy 16-bit (512-byte rows, at most
    32 rows) and convert back (`wb_pixel_to_guest`);
  - the forced MSAA condition takes either format (`dxgi_is_rgba8_class`).
- **The title's noise neutral (`RSX_GAME_DITHER`, off when 16-bit):** a
  pixel-position sample of a small texel-addressed texture becomes
  float4(0.5), which expands to 0. A texture counts as small at 512 texels
  or fewer on units 4-15, and 64 or fewer on 0-3 (from its 1/width in
  `rsx_texscale[u].x` / `rsx_texscale_hi`). Phase 130's host-pixel noise
  sampling now covers units 0-3 too.
- **The display's last rounding (`RSX_FINAL_DITHER`, on):** draws into the
  8-bit display (one 8-bit target; the target format is in the pipeline
  key) add a static triangular noise of +-1 step from an integer hash of
  the host pixel.
- **Setting:** F1 GAME > Smooth colour (`game.smooth_colour`), restart
  needed.

**Measured.**

- **1080p Kyoto menu (`hq1` against `hq0`):** the grain is gone. Adjacent
  pixel steps of 3 or more in the dark area went from 26.1% to 14.3%,
  same mean brightness. The lamp's falloff on the wall is smooth with no
  bands (`hqcmp.png`, x4 gain).
- **Exposure meter at 16-bit:** what the guest receives matches 8-bit
  (red 13/43/95 against 13/43/96 min/mean/max, `rbq2`/`rbq0`), and it is
  valid every frame (`rbq3`). The readback debug counters now read guest
  memory, since the raw buffer layout differs by format.
- **HSR frame tests (warm):** 1080p 59.1 FPS (`hpr2`); 3440x1440 with 4x
  MSAA 57.7 FPS, 2.9% late (`hpu2`). GPU time is 3.4 -> 4.3 ms at 1080p and
  5.1-5.2 -> 5.4 ms at 3440x1440, so the FPS spread is run-to-run.
- **First run:** 42-44 FPS while the new pipelines are built.
- **Cockpit view (`cock0`/`cock1`, Select at +22 s, `PAD_HOLD_MERGE=0`):**
  the interior and door mirrors are black in 8-bit as well. An existing
  fault, open.
- **Tests:** `settings_test.ps1` and `debug_export.ps1` pass.

## Phase 130 - Race at full width, My Page labels, finer dither (2026-10-22)

The user reported three things at 4K and 3440x1440: jagged, soft distance
in races, the My Page row cut off on the right, and dithering in dark
areas.

**Race at full width.** A 4K race capture (`cap_k4race`) showed that
`0x01980000` had the race drawn into its left 2560 of 3840 columns. The
title draws the race 1280 wide (the PS3's 2x horizontal layout, read back
as a 2560x1080 texture) and stretches it to 1920. Phase 128's scaling kept
that 2/3.

- **The change:** with native scaling, a 2/3-width display surface is made
  at the full host width (`uw_host_w`, `RSX_RACE_FULLWIDTH=0` off).
- **Per-target guest size:** 1280 and 1920 guest columns now share a host
  size, so a target records the guest size it currently holds
  (`OffRT.gw/gh`, `s_zb[].gw/gh`, set by the `off_rt_get`/`zb_get`
  wrappers each frame). The per-draw viewport, depth clears, write-backs,
  readbacks and texture-over-target scales use `rt_gw()`/`rt_gh()`.
- **Depth and WPOS:** the depth texture and WPOS already went through
  `uw_host_w`, so they follow.
- **Result (`cap_k4race2`):** the scene fills the target and the final
  frame is correct. The bridge rails and fence posts are crisper.
- **Speed:** 4K 59.9 FPS (0.2% late); 3440x1440 with 4x MSAA 59.2 FPS.

**My Page label cut-off, fixed.**

- **The bug:** in `func_00768340` (`0x0076850C`-`0x00768554`) the text
  renderer turns the label strip's rectangle into the fade mask, as
  x0 = rect.x / (W/2) - 1.0. W is the screen width at +0x3C of its screen
  object (2560 at 64/27).
- **Why only ultrawide:** the menus' projection itself is right (x scale
  1/1280, offset -0.75; matrix mode 1 at `0x01720500`). Only this
  subtraction assumes the 16:9 layout fills the screen.
- **The fix:** a new required post-lift step, `scripts/ui_mask_patch.py`
  (config `ui_label_mask_func`), replaces the 1.0 with `gt5p_ui_mask_x`
  (`src/gt5p_uifix.cpp`), which returns (H * 16/9) / W: 0.75 at 64/27,
  and exactly 1 at 16:9 or 720p. `GT5P_UI_MASK_FIX=0` turns it off.
- **Result (`lblfix2`, 3440x1440):** Events and Garage show in full.
- **Tools note:** the matrix-stack store watch had missed the value: the
  copy happens in `func_00768340` itself. The memory snapshot and
  disassembly found it.

**Dither noise at host pixels.**

- **The cause:** 105 of 108 fragment programs that read WPOS use it to
  sample unit 15, a small texel-addressed noise tile (`FP_DUMP_DIR`).
  Phase 128 brought every WPOS back to guest pixels, so at 1440p/4K the
  noise grew into blotches of 1.33-2 pixels.
- **The change:** in the WPOS rewrite, a unit 4-15 sample at the pixel
  position takes the host position when the unit's `rsx_texscale_hi` 1/w
  says 512 texels or fewer. Other WPOS uses, such as screen-sized reads,
  stay in guest pixels. It only applies when `rsx_texscale_hi` is
  declared. `RSX_WPOS_NOISE_HOST=0` turns it off.
- **Result (`nzon` against `nzoff`):** fine per-pixel grain instead of
  clumps. The dither itself is the title's.

**Measured** (all three together):

- **3440x1440 borderless, 4x MSAA HSR frame test:**
  - first run (`all1`): 34.9 FPS while the changed shaders compiled;
  - warm (`all2`): 59.3 FPS, p99 22.1 ms, 1.6% late, picture correct,
    exposure readbacks valid.
- **1080p (`all1080`):** 58.5 FPS. That path is unchanged apart from the
  label patch, which is the identity there.

## Phase 129 - 4K (2026-10-22)

**What.** `video.resolution = "2160p"` (also `"2160"`, `"4k"`; F1 shows
"3840 x 2160 (4K)") is the native path of Phase 128 at
`RSX_RENDER_HEIGHT=2160`.

- **Output size:** 3840x2160, or 5120x2160 with 21:9.
- **Aspect at 21:9:** 64/27, which is 5120x2160 exactly. Only 1440p uses
  43/18.

**Limits raised in the backend.**

- `zb_get` took at most 4096 per side; it now takes 8192 (5120 wide at 4K
  ultrawide).
- The shared depth buffer and the depth copy were 2048 rows; they are now
  at least the render height (`depth_copy_h`, which the depth texture's
  `ky` uses). The two stay the same size.
- The 2048 checks on `surface_clip` are in guest units and stay as they
  are.

**Measured.** This machine's monitor is 3440x1440. The 4K backbuffer was
checked through `RSX_CAP`, and window shots are shrunk to the work area.

- **Dealer 4K backbuffer (`k4`):** 3840x2160, the same framing, finer
  detail (tyre sidewall, door seams).
- **HSR frame test, 4K 16:9, 2x MSAA:**
  - first run (`k4ft`): 56.0 FPS, 5.2% late;
  - warm (`k4ft2`): 59.2 FPS, p99 19.6 ms, 0.9% late;
  - GPU time about 4.3 ms a frame.
- **HSR frame test, 5120x2160 (`k4uwft`):** 59.3 FPS, p99 21.1 ms, 1.1%
  late. The race picture is correct in both modes.
- **Exposure meter at 5120x2160 (`k4rb`):** 60 valid readbacks a second.
- **4K ultrawide, borderless on the 1440 monitor (`k4bl`):** the output
  pass scales it down, a supersampled picture of 3413x1440 at x 13. 64/27
  is narrower than 43/18, hence the thin bars.
- **Tests:** `settings_test.ps1` and `debug_export.ps1` pass.

## Phase 128 - Native 1440p rendering (2026-10-22)

The user asked for 1440p rendered natively, with the same field of view: the
cars the same size in the window, only sharper.

**How.** The game is still told 1080p, so its layout, cameras and field of
view are those of 1080p. Stage B's horizontal scaling (Phase 125) now has a
vertical twin. `RSX_RENDER_HEIGHT=<rows>` makes `s_d3d.height` that tall
and the width follows: 2560 for 16:9, `uw_wide_w` (3440) for 21:9.

- **Display-class surfaces:** full height, of display width or the race
  scene's 2/3. They are made `rs_hw` x `rs_hh` (`uw_host_w/h` in
  `off_rt_get` and `zb_get`), and `uw_guest_w/h` undo it.
- **When scaling is on:** `rs_on()` = native ultrawide or a render height.
  With neither, every helper is the identity, so 1080p and 720p are
  unchanged.
- **The y twins of stage B's x scaling:**
  - the per-draw viewport and scissor;
  - depth-clear rectangles;
  - write-backs and NV3089 readbacks (host rows `hy..hy+hh`, guest row r
    read from `(y + r) * ky - hy`);
  - the guest height of a target sampled as a texture;
  - the depth copy's `ky`.
- **WPOS:** y is scaled back to guest pixels through `rsx_alphatest.w`,
  which was unused.
- **Settings:** `video.resolution = "1440p"` sets `RSX_RENDER_HEIGHT=1440`.
  `GT5P_RENDER_NATIVE=0` keeps Phase 127's 1080p render with the bicubic
  upscale.

**Measured** on the 3440x1440 monitor:

- **Dealer, 21:9 borderless (`n1440uw`):** rendered 3440x1440 with no output
  pass. The framing matches the upscaled shot, and the wheel spokes and
  panel lines are visibly finer.
- **Dealer, 16:9 (`n1440`):** 2560x1440, correct.
- **HSR frame test, 21:9 native, 2x MSAA:**
  - first run (`n1440ft`): 38.6 FPS with stalls up to 959 ms while new
    shaders compiled (the WPOS text differs); GPU about 4.5-5 ms;
  - warm (`n1440ft2`): 58.7 FPS, median 16.6 ms, p99 20.1 ms, 1.0% late.
  - The race framing matches the upscaled run exactly, and the HUD is
    crisp.
- **Exposure meter (`nrb`):** 60 valid readbacks a second, none zero.
- **Pit, Track Select, menu popup (`nrt`), opening screens, F1 page:**
  correct.
- **1080p 16:9 frame test (`n1080ft`):** 59.1 FPS, unchanged.
- **Tests:** `settings_test.ps1` and `debug_export.ps1` pass.

## Phase 127 - Borderless fullscreen and 1440p output (2026-10-22)

The user asked for a borderless fullscreen option, and for 3440x1440 and
its 16:9 equivalent, 2560x1440. This machine's monitor is 3440x1440.

**Output pass (backend).** The swap chain can now differ from the render
size.

- **How it works:** when the sizes differ, `render_targets[]` are offscreen
  images at render size, in COMMON between frames like swap chain buffers.
  After the frame's last transition, `output_present` draws one into the
  swap chain buffer, with the bars cleared black.
- **Filter:** Catmull-Rom bicubic from nine bilinear taps through s15 (the
  bank's linear/clamp sampler). `RSX_OUTPUT_FILTER=linear` uses bilinear.
- **Shape:** the picture keeps the render size's shape (the ultrawide
  aspect when anamorphic) and is centred in `s_out_vp`.
- **Switches:**
  - `RSX_OUTPUT_SIZE=WxH` sets the window's client size.
  - `RSX_WINDOW_MODE=borderless` makes a `WS_POPUP` window over the primary
    monitor, with the swap chain at the monitor's size.
  - `RSX_OUTPUT_PASS=0` keeps the old DXGI stretch.
- **Unchanged default:** with equal sizes nothing changes (720p/1080p
  windowed).
- **Overlay mouse:** `rsx_d3d12_output_rect` gives the picture's rectangle
  in the client, and the F1 page maps the mouse through it.
- **Too-large windows:** a windowed client too big for the work area
  (3440x1440 on this monitor) shrinks proportionally. Windows had clipped
  its height to 1421 instead.

**Ultrawide aspect as a parameter.** `RSX_ULTRAWIDE_ASPECT` (default 64/27)
replaces the hard-coded 64/27, 4/3 and 0.75:

- `uw_wide_w` for the native width;
- `uw_host_w` by `s_d3d.width / s_gw`;
- `uw_frac()` = (16/9) / aspect for the edge stretch, the pillarbox and the
  scissor widening.

**Settings.**

- `video.resolution` takes `"1440p"`. The game is told 1080p
  (`gt5p_present.cpp` and `main.cpp` check `>= 1080`), and the output size
  is 2560x1440, or 3440x1440 with 21:9.
- With 21:9 the three aspect constants get 43/18 (`0x4018E38E`) and the
  backend `RSX_ULTRAWIDE_ASPECT=2.3888889`, so a 1080-high render is
  2580x1080.
- `video.window = "windowed" | "borderless"` sets `RSX_WINDOW_MODE`.
- On the F1 page, the VIDEO page has a new Window row and Resolution has
  2560 x 1440. A page holds five rows, so Shader compile indicator moved to
  the GAME page. `settings_test.ps1` now also saves Window and reverts it.

**Measured** on the 3440x1440 monitor, 2x MSAA where noted:

- **Dealer, 1440p 21:9, windowed and borderless** (`r1440uw`, `bl1440uw`):
  rendered 2580x1080, shown 3440x1440, correct proportions; a crop is
  clean.
- **Dealer, 1080p 16:9 borderless** (`bl1080`): picture 2560x1440 at x 440,
  black bars.
- **HSR frame test, 1440p 21:9 borderless** (`bl1440ft`): 58.7 FPS, median
  16.6 ms, p99 27.3 ms, 1.8% late. That is the same as 2560x1080, and the
  race is correct.
- **Pit, Track Select, menu popup** (`blrt`): centred, and the dims reach
  the edges at the 43/18 fraction.
- **Tests:** `settings_test.ps1` and `debug_export.ps1` pass.

**Not done:** native 1440 rendering, meaning the title's full-screen targets
made 4/3 taller as well as wider. It would extend stage B's horizontal
scaling to y everywhere it applies: viewports, scissors, depth clears,
readbacks and WPOS.

## Phase 126 - Ultrawide: scene cameras and opening screens (2026-10-22)

The user reported, in 21:9: the opening text and the Sony and Polyphony
logos stretched, and the main menu background, dealer page and pit
stretched too.

**Scene cameras.** The menu background, dealer and pit cameras have their
own 16/9, separate from the race camera's display block.

- **The candidates:** the ELF holds eleven 16/9 floats. Searching TOC
  pointer loads followed by an `lfs` from the exact address found five
  readers:
  - `func_000156D0`, the UI aspect;
  - `func_005E3180`, which passes 16/9 to a perspective call (`0xB20A48`);
  - `func_005E51D0`, which returns it;
  - `func_005E8020`, which passes `0x01280924` to the camera setter
    `0x00814E00`;
  - `func_00814C60` and `func_008150E8`, a camera object's defaults.
- **Narrowed by pokes** (`GT5P_POKE_BOOT`, dealer window shots): only
  `0x01280924` changes the dealer. A wheel seen from any angle cannot be
  wider than tall, which made "stretched" measurable.
- **Pit memory snapshots** (`GT5P_MEMSNAP`): the pit's camera object
  (vtable `0x0125B350`, field of view 37.85, near 0.2, far 2000, aspect at
  +0x10) is still 16/9 after poking the other constants. With `0x01280924`
  poked it holds 64/27. The menu's camera (same class, field of view 33.2)
  does too.
- **The fix:** that address is `scene_camera_aspect_16_9_float` in
  `config/targets.json`. `GT5P_ULTRAWIDE=1` patches it with the other two
  constants; `GT5P_ULTRAWIDE_CAM=0` leaves it alone.
- **Left 16/9:** the default camera object (`func_00814C60`) and an object
  with vtable `0x012610B8` keep 16/9. Nothing visible needed them.
- **An earlier claim corrected:** Phase 125's dealer check judged crispness,
  not proportions, and Phase 122's dealer reading was wrong as well. The
  dealer page was stretched all along.

**Opening screens.** The copyright, Sony and Polyphony screens are one draw
each: a 6-vertex quad into the display surface, sampling a 1920x1080 linear
texture in main memory (`RSX_CAP` at frame 300).

- **The fix:** such a draw (the edge-stretch conditions, plus a sampled
  display-sized texture that is not in local memory) gets
  `vp_posoffset.w = -0.75`. The vertex epilogue then moves vertices at clip
  x = +-1 to +-0.75, so the image is pillarboxed at 16:9.
- **Excluded:** render targets live in local memory, so full-screen
  post-processing passes are not touched.
- **Switch:** `RSX_ULTRAWIDE_PILLAR=0` turns it off.

**Measured** at 1080p, native 21:9:

- **Opening (`uwlogo2`):** the three screens are centred at 16:9 with black
  sides. The movie is unchanged.
- **Pit, menu (`uwrt3`):** crew and car have correct proportions.
- **Dealer (`uwdeal3`):** the whole car fits, and the wheels are not wider
  than tall.
- **HSR race (`uwrace4`):** correct, median 53 fps over 30 s with MSAA 2.
- **Tests:** `debug_export.ps1` passes.

## Phase 125 - Ultrawide stage B: native-width rendering (2026-10-22)

**Why.** Stage A spread a 1920-wide frame over 2560 pixels, and races are
drawn 1280 wide by the title. A 1:1 crop of HSR was visibly soft across.

**What it does.** `RSX_ULTRAWIDE=2`, the default for the 21:9 setting;
`GT5P_ULTRAWIDE=anamorphic` keeps stage A.

- **Two sizes:** the swap chain and `s_d3d.width` are 2560x1080, while
  `s_gw x s_gh` keeps the title's 1920x1080 display.
- **Which targets widen:** full-height surfaces of display width, or of the
  race scene's 2/3 of it, are created 4/3 wider (`uw_host_w` in
  `off_rt_get` and `zb_get`). `uw_guest_w` undoes it, so a width that is
  already widened passes through unchanged.
- **Draws stay in game units.** Scaling happens only at D3D12:
  - per-draw viewport and scissor are computed against the target's guest
    width, then multiplied by kx;
  - depth-clear rectangles are scaled the same way;
  - the shared depth buffer and its copy are at least the host width
    (`depth_copy_w`).
- **Guest-unit comparisons now use `s_gw`/`s_gh`:** sub-viewports, the edge
  stretch, display-by-size, depth-surface notes, display-sized textures and
  the small-viewport test.
- **Textures over targets:** a texture placed over a widened target uses the
  target's guest width for its scale and origin.
- **Pixel-exact copies:** NV3089 readbacks (the exposure meter) and small
  write-backs copy the widened box and take column `(x + c) * kx` per guest
  column. Two scratch surfaces, `0x02A80000` and the meter's `0x02EC0000`,
  also receive full-screen draws and so are widened.
- **WPOS:** fragment programs reading it get x scaled back to guest pixels
  through `rsx_fogstate.w`, a lane that was unused. The shader text is
  rewritten in native mode only, so other runs keep their cached shaders.
- **No guest-memory fill:** a widened target is not initialised from guest
  memory, since the row layouts differ.
- **The F1 page:** no squeeze in native mode. The page spans the
  backbuffer, centred, and the Options tag sits at the corner of the 16:9
  area.

**Measured** at 1080p/2x MSAA.

- **Readbacks (`uwN2`):** the meter readbacks are valid every frame
  (`RSX_BLIT_READBACK_DBG=3`: about 57 a second, none zero).
- **Tour (`uwT4`):** menu, popups, Track Select, pit, Driving Options, grid,
  race, pause and the F1 page are all correct. One frame showed the mirror
  black just after it appeared; later frames were fine.
- **Dealer (`uwD1`/`uwD2`):** native is crisper; wheel spokes and panel lines
  are sharper in a crop.
- **Frame test (`uwNFT`):** 58.2 FPS, median 16.7 ms, p99 32.4 ms, 3.3%
  late. GPU time is about 4 ms a frame in both modes, so the difference from
  anamorphic (59.0 FPS, 1.6% late) is the CPU-bound walk's run-to-run
  variation.
- **The first native run** compiles new shaders (WPOS) and recreates
  targets: 24 FPS that once.

**The My Page label cut-off, traced further (not fixed).**

- A memory snapshot on the menu holds the text renderer's constant block
  (`c[128]`-`c[131]`) at `0x0139A700`. The label mask is at `0x0139A730`:
  -0.835156, -0.4, 0.854473, -1.95652.
- `func_00768340` writes it on every text draw by calling `0xBC8150` ->
  `0xBC8088`. That pair copies the top 4x4 of a GL-style matrix stack (base
  `0x0171FD00`, index at +0x10D0, table at +0x10C0) into the block.
- So the strip widget pushed the wrong origin onto that stack earlier.
  Next: watch the stack slot for `0xBF55CCCD` to find the push and the
  arithmetic that leaves out the 0.25 centring offset.
- **Regressions:** 16:9 at 1080p (`n169`) is unchanged at 60 fps, and
  `settings_test.ps1` and `debug_export.ps1` pass.
- **Not covered:** the tunnel itself in native mode. The scripted drive hit
  a wall first; the meter readback is the evidence instead.

## Phase 124 - Ultrawide step 4: the Aspect ratio setting (2026-10-22)

- **The setting:** F1 VIDEO > Aspect ratio (16:9 / 21:9 ultrawide) takes
  effect after a restart. The settings file key is
  `video.aspect = "16:9" | "21:9"`; it sets `GT5P_ULTRAWIDE=1`, which still
  wins when set by hand. F8 reports show `ultrawide=`.
- **Checked:**
  - A settings file with only `resolution = "1080p"` and `aspect = "21:9"`
    (`uwSet`): both constants were patched and the window was 2560x1080.
  - `settings_test.ps1` now also saves and reverts the new row (Vsync is one
    row further down) and passes. `debug_export.ps1` passes.
- **Other resolutions:** 720p with 21:9 makes a 1707x720 window by the same
  route, but it has not been looked at.

## Phase 123 - Ultrawide step 3: menus centred, full-screen layers widened (2026-10-22)

**Menus lay themselves out.** The display block's set A aspect
(`0x0138D2B0`) is what the menus' 2D layout reads.

- Set at 21:9 before the menus load (a kept `GT5P_POKE` at `CursorRoot`), the
  game centres every menu at 16:9 proportions inside the 21:9 frame. That
  covers My Page, Track Select, Race Mode, the pit, Driving Options, the
  starting grid and the loading logo.
- Set A takes its value from `func_000156D0`, through `func_007AE2A0`, from a
  second 16/9 constant at `0x0126AE5C`. No other code reads it.
- That address is now `ui_aspect_16_9_float` in `config/targets.json`.
  `GT5P_ULTRAWIDE=1` patches both constants at load; `GT5P_ULTRAWIDE_UI=0`
  leaves menus stretched.
- Other 16/9 constants are read by functions around `0x5C1000`-`0x675000`.
  Their use is unknown; the screens checked so far do not need them.

**Full-screen 2D layers.** Laid out to the 16:9 width, the popup dimming,
the menu's bottom shading bar and the page fades covered only the middle 3/4
and left the sides bright. RenderDoc (`uwdim`) shows those draws end exactly
at clip x = ±0.75.

- **The fix:** in ultrawide mode only, the vertex shader epilogue
  (`rsx_vp_decompiler.c`) moves vertices on ±0.75 to the screen's edge, for
  draws the backend marks in `vp_posoffset.w`. Other runs keep their cached
  shaders.
- **What gets marked** (`vp_record_cb`):
  - a draw into the display surface (`rt_off` 0, where the 2D layer is drawn)
    or a display-sized target;
  - depth test off, colour written, stencil test off (bit 0 of the stencil
    key), so not the text's glyph-outline passes;
  - no sampled unit wider than 16 texels (`rsx_fp_texture_mask`, cached per
    program; leftover bindings do not count).
- **Scissor:** these layers are also scissored to the 16:9 area
  (240,0,1440x1080). That scissor, and only one exactly that size and place,
  is widened at replay. A first version widened any marked draw's scissor and
  blacked out the race: the rear-view mirror's box drew over the whole
  screen.
- **Switches:** `RSX_ULTRAWIDE_EDGES=0` turns this off.
  `RSX_ULTRAWIDE_EDGEDBG=1` logs the candidate draws.

**Measured** at 1080p/2x MSAA, from 2560x1080 window shots:

- Tour `uwT3` (menu, Arcade, Daytona pit, Driving Options, grid, race,
  pause) and menu popup `uwE6`: the dimming and fades cover the full width,
  and the text is intact.
- HSR race `uwR`: correct, with the HUD centred by the game.
- HSR frame test (`uwFT`): 59.0 FPS, median 16.6 ms, p99 24.5 ms, 1.6% late,
  walk 7.0 ms.

**Follow-ups.**

- **Opening movie** (`uwMov`): already correct. With the UI aspect patched
  it shows pillarboxed at 16:9 with black bars.
- **F1 page and Options tag:** painted 3/4 as wide in ultrawide, so the
  swap chain's stretch restores their shape.
  - `paint_ax()` reads `RSX_ULTRAWIDE`. The world transform and the
    device-space helpers (`vgrad`, `stadium` with elliptical ends,
    `shaded_tri`, the tag's icon) take the factor; the mouse uses
    `s_scale_x`.
  - The full page spans the whole backbuffer with its layout centred
    (`s_paint_ox`), so the dimmed scene reaches the window's sides.
  - The tag sits in the corner of the game's centred 16:9 area.
  - `settings_test.ps1` (16:9) still passes.
- **My Page label cut-off, diagnosed (`uwdim3`, RenderDoc):**
  - The labels (draw 965, program `0x0507F3C1`) multiply by a 1480x4 fade
    mask at `TEXCOORD2.zw`. The vertex shader computes that coordinate as
    (position - `c[131].xy`) x `c[131].zw`.
  - The game sets the mask origin to `c[131].x` = -0.835. The icons' shader
    gets the correct -0.585 (in `c[128]`). The label value is the strip's
    left edge (pixel 211) scaled by 0.75 and converted to clip space without
    the 240-pixel centring offset, so u passes 1.0 at clip x 0.335 (guest
    1280).
  - The value is computed in the game's text path. A fix means finding that
    code; not done.

**Known issues.**

- **My Page icon row:** the labels end at guest x ~1280, so "2P Battle" is
  cut and "Events" is missing; the icons themselves draw. The cut sits at
  1706 x 0.75, which looks like a label fade mask placed by scaled
  coordinates without the centring offset. That is the game's own aspect
  handling, not a scissor; the row's scissor (398-1521) is right.
- **Still stretched at first:** the F1 page (the port's overlay, drawn into
  the 16:9 backbuffer) and the opening movie. Both were fixed later in this
  phase; see Follow-ups.

## Phase 122 - Ultrawide step 2, stage A: anamorphic 21:9 (2026-10-22)

**What it does.** `GT5P_ULTRAWIDE=1`, which needs `GT5P_RESOLUTION=1080p`:

- `main.cpp` writes 64/27 into `aspect_16_9_float` at load. It first checks
  the word holds 16/9, and does nothing otherwise.
- It sets `RSX_ULTRAWIDE`, so the backend makes the window 21:9 (2560x1080
  for 1080p).
- The backbuffer stays 1920x1080. DXGI's default stretch scaling spreads it
  over the window, which undoes the squeeze the 21:9 aspect gives the
  title's picture.

The renderer is otherwise unchanged, so the cost is unchanged: the HSR race
ran at a median 59 fps.

**Measured** at 1080p/2x MSAA, from 2560x1080 window shots:

- **HSR race (`uwA`):** correct 21:9 geometry. The gauges are round and the
  boards keep their proportions. The scene fills the width and the race HUD
  sits centred. Fence posts and barriers reach both edges, so there is no
  culling at the sides.
- **Acura dealer page (`uwD`):** the cars have correct proportions across
  the full width.
- **Main menu (`uwM`):** the 3D background is correct. Its 2D (popup, icon
  row, text) is stretched by 4/3, because menus lay out at 16:9 whatever the
  aspect. That is step 3.

**Limits of stage A.**

- Horizontal detail is the 16:9 frame's: 1920 samples spread over 2560
  pixels. Races are already drawn 1280 wide by the title.
- The F1 page and the opening movie are stretched too.
- Native-width rendering, where the full-screen targets are created 4/3
  wider, is stage B, the quality step. No new readings are needed for it.

## Phase 121 - Ultrawide step 1: where the game's aspect ratio lives (2026-10-22)

The user wants a 2560x1080 (21:9) mode. The plan is in
[plan-ultrawide.md](plan-ultrawide.md); this is step 1, finding where the
game's 16:9 comes from and what it drives.

**Race render target.** At 1080p a race draws its scene into `0x01980000`
with a 1280x1080 viewport (2x MSAA, pitch 10240; depth at `0x02420000`), and
the game stretches it to 1920 itself. Widened for 21:9 that becomes about
1707x1080.

**The camera.** A new capture filter, `RSX_CAP_VPFULL=1`, keeps only draws
whose scissor covers the whole target, so the rear-view mirror's camera is
left out. With `RSX_CAP_VPC=01980000` it gives the main race camera's
view-projection rows. Their lengths are x 1.2988 and y 2.3091, a ratio of
0.5625 (9/16), which is a vertical field of view of 46.8 degrees.

**In memory** (`GT5P_MEMSNAP` mid-race, searched for floats):

- The camera keeps the same two scales at `0x01398518`/`0x01398520`,
  followed by its view matrix.
- A display block starts at `0x0138D294`. It holds the display size
  1920x1080, then set A (size at `0x0138D29C`, aspect at `0x0138D2B0`) and
  set B (size at `0x0138D2A4`, aspect at `0x0138D2AC`). Both aspects are
  16/9.

**What each aspect drives.** A new diagnostic, `GT5P_POKE=<milestone>+<ms>:addr=value`,
writes guest words at run time; a leading `!` keeps rewriting one.

- Writing 64/27 into `0x0138D2AC` alone mid-race turns the camera's ratio
  into 0.4219 (27/64), with its vertical scale unchanged: a wider view and
  the same vertical field of view. The race HUD and the mirror camera re-lay
  themselves out for 21:9 too, pulled toward the centre by 3/4.
- Writing `0x0138D2B0` alone changed nothing visible. Its role is unknown.
- The crowd and barrier boards still drew to the outer edges of the
  squeezed image. That is the region a 16:9 culling frustum would drop, so
  culling probably follows the projection. This is not proven until the
  frame is really drawn wide.

**Who sets it.** A store watch at boot (`PPU_WWATCH=0138D290`) names the
writers:

- `func_007AE548` calls `func_0081DE00` (set A) and `func_0081DE10` (set B)
  once, early in boot. Set A is also written from `0x007AE2B8`.
- The value comes from a table chosen by a mode byte at `[0x01720F00]+0x2B`,
  read through `0x00BC5A58`. Mode 1 gives 4/3 (`0x1287DE0`), mode 2 gives
  16/9 (`0x1287DD0`, the case in practice) and anything else gives 1.0
  (`0x1287DD8`).
- The mode byte is presumably cellVideoOut's aspect: 1 is 4:3 and 2 is 16:9
  in the SDK. A widened code scan finds no other reader of the table.

**The patch.** A load-time poke, `GT5P_POKE_BOOT=01287DD0=4017B426` (new in
`main.cpp`), writes 64/27 before the game runs.

- The game's own setup then gives the camera 21:9 (ratio 0.4219) and the
  race HUD lays itself out centred.
- The main menu's 2D layout stays at the full width, so menus will need the
  renderer's pillarboxing.
- `0x0138D2B0` stays 16/9; it is written through another path.

The address is now `aspect_16_9_float` in `config/targets.json`.

## Phase 120 - Rebindable keyboard keys (2026-10-22)

**Follow-up: the Options tag's Select.** The "SELECT  PC settings" tag on
the game's Options screen is the port's own overlay, not a game texture,
so the replacer never saw it.

- **What it shows:** the tag now draws the Select button of the device in
  use.
  - A DualShock 4 shows Share and a DualSense shows Create
    (`playstation4_button_share`, `playstation5_button_create`).
  - Xbox shows View, Switch shows −, and the keyboard shows its bound key.
  - A PS3 pad, or no known pad, keeps the "SELECT" pill.
- **How:** cellPad now also exposes SDL's controller type for port 0
  (`g_pad_device_type`). `gt5p_glyphs_select_icon()` renders the icon with
  the glyph resampler as premultiplied BGRA, and `paint_hint` AlphaBlends it
  just left of the label. The tag is re-pushed when
  `gt5p_glyphs_select_id()` changes, after a new device, style or binding.
- **Checked:** runs `sel-*` at 1080p showed Create (Auto, with the user's
  DualSense), View, − and a Backspace keycap (`PAD_KEYMAP=select=Backspace`).

The user asked for the keyboard's keys to be changeable, since a keyboard
has far more keys than a pad has buttons.

- **cellPad:** `s_kbd_map` is now a mutable table of all 16 buttons, with
  L3/R3 included and unbound by default. `pad_keyboard_set_vk(btn, vk)`
  rebinds while running; the poll skips unbound entries.
- **`src/gt5p_keymap.*`:** holds the button table (settings key, label, pad
  bit, default) and the bindable keys, each with name, virtual-key code and
  Kenney art.
  - Bindable keys: letters, digits, arrows, Enter, Tab, Space, Backspace,
    Shift, Ctrl, Alt, Insert, Delete, Home, End, PageUp, PageDown and the
    punctuation keys.
  - Left and right Shift/Ctrl/Alt read as one key. Escape and F1-F12 are
    refused, because the port uses them.
  - It also parses and formats `PAD_KEYMAP` (`cross=Z,circle=X,...`).
- **Settings file:** a new `[keyboard]` section (`cross = "Z"` ...) goes to
  `PAD_KEYMAP`, which wins over the file. `gt5p_keymap_init()` applies it at
  start-up, before the glyph module loads its art.
- **F1 page:** a new Keyboard tab shows two columns of eight bindings.
  - Cross or Enter waits for a key. Escape or Circle cancels.
  - A key another button had swaps onto the old key, and the status line
    says so. Left/Right jump between the columns.
  - A Defaults button restores the original keys.
  - The page's own navigation keys stay fixed; they only drive the page.
- **Prompts:** a rebinding sets a flag. The glyph watcher reloads the
  keyboard art and bumps a cache generation, which keys the keyboard style's
  cache. Old entries are kept, not freed, so an upload in progress never
  reads freed bytes. The listed textures then upload again. The extra key
  art takes `assets/glyphs/kenney/` to 89 PNGs (234 KB).
- **Checked:**
  - `keys_t` posts keys to the page against a scratch settings file:
    - Cross K: saved.
    - Circle K: saved, and Cross took X.
    - F1 while waiting: refused.
    - Escape: left the binding unchanged.
    - R3 Comma: saved.
    - Defaults: restored Z and None.
  - `keyslive` ran with `PAD_KEYMAP=circle=K,right=L,left=J,cross=I` and
    SDL off, so the keyboard was pad 0, and sent real key events. K closed
    the menu popup, L and J moved along the tabs and I opened a page. The
    prompt read "I Enter".
  - `debug_export.ps1` passes. It now builds `gt5p_keymap.cpp`, with two
    more stubs.

## Phase 119 - Button prompts for the controller in use (2026-10-22)

The user asked for the prompts to follow the connected controller, using
Kenney's Input Prompts pack (CC0). The art used is in
`assets/glyphs/kenney/` (73 PNGs at 128 px, 197 KB, with Kenney's licence).

**Where the game's prompts come from.** A RenderDoc capture of Options
(`glyph720`) showed that the Cross beside "Enter" is drawn from its own
52x52 DXT5 texture. It is not a font glyph and not part of an atlas. Dumps
of every small texture uploaded on the main menu, Options, the dealer, the
pit and a paused race found no other button symbol. GT5P shows only "Cross
Enter" there. The race pause bar uses plain icons. The one other place is
Options > Change Button Assignments. Its whole DualShock diagram (L1/R1/L2/R2,
the face buttons, SELECT/START, the D-pad and the sticks) is one 460x720 DXT5
texture (capture `btnasg`).

**How they are replaced.**

- **Backend:** `vp_upload_tex_slot` hashes each 2D texture of up to
  1024x1024 that it uploads (FNV-1a 64 over the whole mip chain). It offers
  the texture to a replacer callback (`rsx_tex_set_replacer`), which may
  return bytes of the same size and layout to decode instead.
  - The texture cache re-uploads a managed texture when the replacer's
    generation changes (`rsx_tex_replace_invalidate`).
  - `RSX_TEX_REPLACE=0` turns the hook off.
  - `RSX_TEX_REPL_DUMP=<dir>` writes each distinct texture larger than 16x16
    as `<hash>_<w>x<h>_<fmt>.dds` (game-derived: keep it in `scratch/`).
- **Port (`src/gt5p_glyphs.cpp`):** the table is `assets/glyphs/textures.txt`.
  Each line is a hash, a size and the cells, one cell per button.
  - For a listed texture the port decodes the DXT5 and clears each cell's
    button. The button is found by a flood from the cell's centre at alpha > 40,
    widened by two texels.
  - It draws the style's art fitted to where the button was, or into a given
    box. Labels baked into the picture ("SELECT", "START") are cleared.
  - It then encodes back to DXT5, mips included, so the format and size never
    change. Results are cached per texture and style.
- **Device (cellPad):** `g_pad_device_family` records what port 0 is played with.
  - With SDL, it comes from `SDL_GameControllerGetType` (an optional import),
    or from the controller's name.
  - XInput means Xbox.
  - Otherwise it is the keyboard, unless the keyboard is off. A `PAD_HOLD`
    script does not count as a device.
  - `pad_keyboard_vk()` exposes the key bound to each button, so the keyboard
    art names the real binding.
- **Styles:** Auto maps the device to a style:
  - Xbox and other pads get Xbox art.
  - Switch pads get Switch art. SDL reads them by label, so Cross shows A.
  - The keyboard gets keycaps of the bound keys.
  - A PlayStation pad, or nothing at all, keeps the game's art.

  A watcher thread re-resolves the style every 250 ms; a change re-uploads
  the listed textures. D-pad arms and sticks keep their shape on pads.
- **Switches:**
  - `GT5P_GLYPHS=auto|playstation|xbox|nintendo|keyboard` chooses the style.
  - `GT5P_GLYPHS=0` turns the feature off.
  - The F1 page has INPUT > Button prompts, which applies live, and the
    settings file has `input.button_prompts`.
  - `GT5P_GLYPHS_DBG=1` logs changes. `GT5P_GLYPHS_CYCLE=<ms>` steps through
    the styles, for tests.
  - F8 reports state the setting, the style in effect and the device family.

**Measured.**

- **Detection:** with the user's DualSense connected, the log reads
  `port 0: DualSense Wireless Controller (type 7, family 3)`, and Auto keeps
  the game's art.
- **Forced Xbox (`gx2`, 1080p):** "A Enter" appears top right, and the
  diagram shows LT/RT/LB/RB, Y/X/B/A and View/Menu.
- **Cycling on the assignment page (`gx3`):** the page switched live through
  PlayStation, Xbox, Switch (ZL/ZR/L/R, A/B/X/Y, -/+) and keyboard (1/2/Q/W,
  arrows, S/A/X/Z, Tab/Enter), then back to the game's own art.
- **Speed:** the 1080p/2x HSR frame test gave 59.3 FPS, median 16.7 ms, p99
  19 ms and 0.7% late, the same as before.
- **Tests:** `debug_export.ps1` (its stubs gained the two new symbols) and
  `settings_test.ps1` pass.

**Follow-up: spacing and highlight rings.** The user reported two problems
on the assignment page. The new icons crowded each other, and the red
selection outline kept the PS3 button shapes.

- **What the outlines are:** each button has its own highlight texture,
  14 in all. L2/R2 are 116x72, L1/R1 are 116x52, the D-pad arms are 60x60
  pentagons, the face buttons are 52x52 circles, Select is 48x32 and Start
  is 52x36. Each is drawn centred over its button at the diagram's scale.
- **Mapping:** moving the cursor through all 24 rows with
  `RSX_TEX_REPL_DUMP` (run `hl1`) gave each texture's button. Each texture
  first uploads when its row is selected.
- **Spacing:** the diagram's cells now take `inset=6`, so the art is fitted
  6 texels inside the button's own area.
- **Rings:** `outline:<button>@<box>` lines name the ring textures. For each
  one the port draws the art where the diagram has it, shifted into the
  ring's frame. It fills holes, such as see-through letters, by a flood from
  the border. It then draws a ring 1 to `ring=N` texels outside that
  silhouette, in the original's red.
- **Select and Start:** these now sit on their own buttons instead of over
  the cleared labels, because their rings are only 32 and 36 texels high.
  They are sized to fit those rings.
- **Checked:** runs `hl2-xbox` and `hl2-keyboard` walk every row. The rings
  trace LT/RT/LB/RB, the face buttons, the keycaps and the arrow keys, and
  the letters stay white.

**Limits.**

- The assignment page's help line still names PS3 buttons ("Assign controls
  to the L2 button"). That is game text, not a texture.
- The keyboard is still only used when no controller is connected. Its art
  shows only in that case or when forced.
- Prompt textures not seen yet are not listed. Add one by dumping with
  `RSX_TEX_REPL_DUMP` and adding a line to `textures.txt`; no rebuild is
  needed.

## Phase 118 - Tunnel lighting fixed: the exposure meter's readback (2026-10-22)

**Fixed.** The High Speed Ring tunnel is lit (lamps, beams, blown-out exit)
and the exposure adapts outdoors, as in the user's RPCS3 screenshot.
`tunnel118g`: 1080p/2x, 150 s, median 60 FPS; dealer and Kyoto menu shots
unchanged. The investigation that got there follows the fix.

- **The cause.** The title meters exposure itself (`0x008064E8`, every
  frame on scene object + `0x288`): it copies the scene into a 128x128
  corner of surface `0x02EC0000`, reduces it in place (`fp 0x057B6001`,
  then `0x057B5E01`, 8-tap averages, alpha 0) to a 16x8 block at row 80,
  and blits that block (NV3089, 1:1, local `0x02F60000` pitch 8192) into a
  three-slot ring in main memory (scene + `0x260`, `0x200` bytes a slot),
  read two frames later. From it the meter sets a target at `+0x248` and
  enables the smoother `0x008062D8` (`+0x254`), which drives the scale
  `+0x65C` behind the exposure global. Our blit copied guest memory, which
  never holds a GPU-only surface, so the meter always found no data and
  left adaptation off: exposure stayed at its base 0.4.
- **The fix** (ps3recomp): a 1:1 32-bit NV3089 blit out of local memory
  that overlaps a surface drawn this frame now records a readback in
  command order (`rsx_d3d12_note_blit_read`); replay copies that rectangle
  from the target, and the next frame start writes it into the surface's
  guest memory, where the next blit picks it up (one frame later than on
  hardware; the ring already allows two). `RSX_BLIT_READBACK=0` off;
  `RSX_BLIT_READBACK_DBG=1|2|3` logs (3: per second, valid/zero/stale
  counts); `RSX_BLIT_READBACK_NOWRITE=1` copies without writing.
- **A trap found on the way.** Draw records are reused across frames and
  filled field by field: a record slot that held a readback kept the flag
  when reused for a draw, so random draws were skipped and copied instead
  (it removed the meter's own second pass, and garbage readbacks swung the
  exposure between white and black). New draws clear the flag.
- **Also fixed: the car's reflection probe had no depth test.** Colour
  targets that are not window-sized never got the shared depth buffer, so
  the probe's sky (drawn last) covered everything, tunnel included. Such a
  target now gets its own depth buffer, keyed by the guest depth surface,
  when its draws test depth (`RSX_RT_OWN_DEPTH=0` off). `ZB_MAX` is 12.
- **Follow-up: the car still reflected sky in the tunnel** (user screenshot).
  The car samples the probe through a real cube copied from the six face
  targets at the first draw of a frame that samples it. That draw comes
  while face 0 is being rendered (objects in the probe sample it too); the
  bound face was skipped and the cube marked done, so face 0 kept a view from
  outside the tunnel indefinitely. Faces are now tracked per frame and a
  skipped one is copied at the next sampling draw (`RSX_CUBE_RT_ONCE=1`: one
  pass, as before). Capture `tunrefl118b`: all six faces show the tunnel and
  the roof reflects its light strips; dealer cars unchanged; race 60 FPS.
- New diagnostics: `RSX_RT_WB_SIDE=<n>` (write back regions up to n x n),
  `RSX_SKIPDBG_FP=<fp>` (why a program's draws are left out),
  `GT5P_WATCH=addr>off` (follow a pointer),
  `scripts/diag/rdoc_smalldraws.py`.

### The investigation

Retained captures
(`graphics94-manual_frame{6819,10164,10650}`) plus two driven 1080p/2x HSR
races (`scratch/pv/tunnel118a`, `tunnel118b`; tunnel at shots 90-135 s).

- **The wall shader** (draw 489): light = `v7.rgb * c0 + v7.w * c1`, times
  sRGB-decoded albedo, times `c4`, then fog. `v7` is attribute 13 passed
  straight through, four half floats (descriptor `0x143`, stride 28), so
  (1.69, 0.89, 0.26, 0) is a real HDR value: orange lamp light, no sky.
- **`c4` is the main view's exposure**, (0.4, 0.4, 0.4, 10), in every draw
  of all four captures, tunnel included (`scripts/diag/rdoc_expo.py`).
  Live, the global `0x015FA284` alternates per view between (0.04, w 0),
  (0.4, w 10) and (1, 1): fixed values the whole race (`GT5P_WATCH`).
- **`c0` is a per-draw value the title chooses** (`scripts/diag/rdoc_vlit.py`):
  outside the tunnel these programs get the sun colour (1.09, 1.01, 0.9) or
  0.8; tunnel pieces get 0.01 or 0.006, even on a shader that gets 0.8 on
  another draw in the same frame. So the near-black is the title's own
  numbers (0.01 x 0.4 x albedo 0.08), not a decode or upload fault seen so
  far.
- The exposure function (`0x007132C0`, helper `0x00712E28`) is in its
  clamped regime, where exposure is proportional to the colour at
  `object+0xB30`, set through `0x00712B18` from `0x00702950`: a product of
  scene fields `+0x65C`, `+0x668`, `+0x674`. That input does not change in
  the tunnel.
- **The car's cube probe**: six 256x511 targets, each a 256x256 face with
  its mip chain stacked below; the 4x4/2x2/1x1 levels are written back
  (`RSX_RT_WB`). The 1x1 averages are nonzero and live, but barely change
  inside the tunnel (`15191C` vs `161A1D` outside), and one face is
  `0D1725` for the whole race. Whether the title meters exposure from these
  is not established.

The user's RPCS3 screenshot then showed the tunnel lit and its exit blown
out: adaptation. A store watch on the exposure fields led to the meter
above (EV `0x01390EB4`, set only by a script binding at `0x00362668`, is
the course's base and stays 0). Pixel-count reports were ruled out
(`GCM_REPORT_FULL=0` changes nothing; the race reads zcull statistics).

## Phase 117 - Opening the settings in a race pauses it (2026-10-22)

The user asked that opening the settings during a race open the game's pause
menu. Start pauses a race (a small bar: retry, Continue, exit) and Start
again resumes it, so the page must know whether the race is already paused.
No screen script is read when pausing.

**Finding the pause state.** New diagnostics: `GT5P_MEMSNAP=<milestone>+<ms>,...`
(or F9) saves every committed page of guest memory to `scratch/memsnap/`
(~950 MB each; delete after), and `scripts/diag/memsnap_diff.py --a ... --b ...
[--c ...] [--ptrs]` lists the words that are constant within each state but
differ between them; `GT5P_WATCH=addr,...` logs changes to words live, and
`race.ps1 -ExtraHold` adds presses to the drive. Two snapshots per state
caught frame-flipping words (`0x0138D1D0` toggles every frame); four per
state across two pauses left an object whose word at +8 past its vtable is 7
paused, 3 running. Its vtable `0x0124C290` is `mListBox` (rtti.json): the
pause bar's icon list. Of the ~13 mListBox objects in a race, two have 3 at
+4: the pause bar, and on the starting grid the grid's menu (7 shown there,
gone once racing). The objects are on the heap at different addresses each
boot, so the page scans guest memory (0x20000000-0x40000000) for the vtable
when it opens.

**Behaviour.** A race is RaceRoot until another screen root other than its
layers (OnboardMeterRoot, QuickArcadeRoot, DLSGadgetRoot) is read. Opening
the page in a race with a kind-3 mListBox present but none shown (racing)
presses Start for the title for 150 ms through cellPad's new
`g_pad_inject_buttons` (passes even while the title's input is blocked);
shown (grid menu or already paused), or none found, presses nothing. Closing
leaves the game on its pause bar. `GT5P_SETTINGS_PAUSE=0` disables it; the
vtable is `menu_listbox_vtable` in config/targets.json (via main.cpp,
`GT5P_LISTBOX_VTABLE`). `GT5P_SETTINGS_TOGGLE_AT=<milestone>+<ms>,...` opens
or closes the page at those times for scripted runs.

Verified on High Speed Ring (`race.ps1 -Tag pause8`): grid open pressed
nothing; open while racing paused the race (timer frozen, pause bar after
closing); open while paused pressed nothing and it stayed paused. Other race
modes with a different race root are untested and never count as racing.
A stray Start a few seconds after a scripted one appears in race drives
regardless of this change (seen before it existed); not investigated.

## Phase 116 - Settings page as one of the game's settings popups (2026-10-22)

The user sent the game's "Steering Settings" popup (closed and with a list
open) as the target look, and reported that the big title and the button
labels did not fit. Measured from their screenshot: flat grey-28 panel,
grey-76 rules, labels grey 190 right-aligned, value boxes near-black
(0, 4, 0) with a (99, 101, 107) underline and values at grey 204, square
drop-down buttons (black edge, glass face, white triangle; the selected
row's has a (168, 0, 0) ring), grey-96 dotted rules between rows; the open
list is grey 204 with grey-51 text, grey-127 separators, the highlighted
entry a (154, 181, 206) -> (222, 244, 250) gradient, a short grey dash before
the current value.

The page is now that popup: "PC Settings" centred at the top, then a
section bar (the Options screen's style, with L1/R1 knobs) that pages
through Video, Shaders (split off Video: cache, background compilation,
preload, pipelines, race preparation), Input, Game, Performance and Debug,
then the rows, the help, and Restart/Close pill buttons. Cross/Enter opens a
row's list placed so the current value sits on its box; Up/Down, Cross picks,
Circle/Esc closes it. Left/Right still step values; L1/R1 (Q/W, Page Up/Down)
or Left/Right on the bar switch pages. Button labels are now centred in the
pills (the quit popup too). Restart-pending and environment notes sit in the
row's empty left side. `GT5P_SETTINGS_UI_ALPHA` now sets how far the scene
around the popups is dimmed (default 186, as the game).

Checks: `settings_test.ps1` (updated for pages, adds a shot with a list
open) and `-Legacy`, `quit_confirm.ps1` pass; shots at 720p and 1080p.

The arrow cursor now copies the game's (from the user's crop, ~28 x 42
pixels at 1080p): a bevelled arrowhead with a tail on its left, the left
face dark with a lighter rim, the right face bright at the tip greying
towards the notch, a thin grey outline and a black edge outside it so it
reads over the light lists. Drawn as shaded triangles with 4x4 edge
coverage in device pixels.

## Phase 115 - Settings page in the game's own style; Escape asks before quitting (2026-10-22)

The user asked for the page to look exactly like an in-game menu, and for a
confirmation before Escape quits.

**Measured from the game's 1080p screens** (Options, and its "Exit the
Options menu?" Confirmation): the popup dims the scene to about 27% (grey 20
-> 5), its panel is flat grey 28 with a dark header gradient (45 rule, then
2 -> 21), a grey-76 rule above the buttons; the pill buttons are 236 x 56
pixels with a black rim, a 3-pixel red ring (237, 0, 0) when focused, and a
glass face (123/125/140 fading to 57 at the middle, then near-black rising
to ~60 at the bottom); the Options screen is black lifting to grey 24 at the
bottom, a grey-180 rule under its big grey title, section bars with grey-70
rules over a 3 -> 34 gradient, text at greys 132-212. Layout units are those
pixels over 1.5.

**The page** is now full screen after the Options screen: the GT header,
a large "Settings" title over its rule, Video / Input / Game / Performance /
Debug section bars with end knobs, a dotted rule between the columns, the
selected row as the game's red-ringed pill, the help centred below, and
Restart / Close as the game's pill buttons between its two bottom rules
(arrow cursor on the focused one). Prompts top right. Left/Right move
between the buttons; Up/Down treat them as one stop. Opaque by default
(`GT5P_SETTINGS_UI_ALPHA` < 255 lets the scene through its black).

**Escape** in the game window now shows a copy of the Confirmation popup,
"Quit Gran Turismo 5 Prologue?", Cancel focused: Left/Right, Enter/Cross,
Esc/Circle cancels, mouse on the buttons. OK posts WM_CLOSE (the normal exit
path). The backend calls `rsx_d3d12_on_escape` (ignoring auto-repeat) and
closes at once only when it is unset or returns 0. `GT5P_ESC_CONFIRM=0`
restores the immediate close; `GT5P_QUIT_UI=1` asks at start (tests). The
window's close button still closes at once.

**Transparency:** text drawn over clear areas (the Options tag) picked up
the magenta colour key at its antialiased edges. Images are now painted
twice, clear parts black then white; the black pass is the premultiplied
colour and the difference the transmitted fraction, so edges are exact.
Fonts use greyscale antialiasing.

Checks: new `scripts/test/quit_confirm.ps1` (Escape asks, Cancel keeps the
game, OK exits; passes at 1080p); `settings_test.ps1` with and without
`-Legacy`; `debug_export.ps1`; a driven Options visit shows the tag cleanly.

## Phase 114 - Settings page drawn in the game's picture; reachable from the game's Options (2026-10-21)

The user asked for the F1 page to be part of the game's menus. Two steps,
both measured live at 720p:

**1. The page is drawn into the frame.** It was a GDI window kept over the
game window. Now `gt5p_settings_ui.cpp` paints the same layout with GDI into
a 32-bit bitmap at the backbuffer's scale (layout units are 1280 x 720
pixels, so 1080p is a 1.5x world transform), converts it to premultiplied
BGRA, and hands it to the backend (`rsx_d3d12_overlay_set`). The conversion
is a colour key outside the rounded panel (clear), the panel's plain
background at alpha 236 (`GT5P_SETTINGS_UI_ALPHA`), everything drawn on it
opaque. The backend uploads it when it changes (three upload buffers in turn)
and blends it with a premultiplied-alpha triangle over the backbuffer just
before the present barrier (`overlay_present`, SRV slot 22, `vp_root_sig`'s
point/clamp s0; 1:1 pixels). It shows in fullscreen and in window captures.
Keyboard and mouse are read with `GetAsyncKeyState` while the game window has
the focus; keys posted to the page's hidden window still work (tests). The
window's Escape no longer closes the game while the page is up, nor for
600 ms after (the page closes itself on Escape). Restyled after the game's
own popups: dark grey glass, a grey selection bar with a red rim.
`GT5P_SETTINGS_UI_LEGACY=1` or `RSX_OVERLAY=0` keeps the old window.
Limitation: the page updates only when the game presents frames (a long
loading stall freezes it too).

**2. The game's Options screen offers it.** Entering Options reads
`OptionRoot.gpb` (then `DLSGadgetRoot.gpb`); leaving through its "Exit the
Options menu?" prompt reads `TopRoot`/`TopMenuTemplate` again (measured with
`GT5P_SETTINGS_UI_DBG=1`, which now prints each screen script). cellPad has a
second listener for every file the title opens (`g_pad_screen_hook`). While
Options is up and the page is closed, a "SELECT  PC settings" tag sits in the
screen's empty bottom-right corner, and Select (Tab on the keyboard) opens
the page; the game showed no reaction to that Select. `GT5P_OPTIONS_HINT=0`
removes both. Closing the page now keeps the title's pads at rest until every
button is up: before, the Circle that closed it would have reached the game
as a new press and opened its exit prompt (checked: it does not).

Checks: `scripts/test/settings_test.ps1` (overlay; shots now of the game
window) and `-Legacy` both save every change; `debug_export.ps1` passes; a
driven run showed the tag, Select opening the page, Circle closing it with
the game still on Options, and the tag gone after leaving Options.

## Phase 113 - Black barrier fixed: stale pipeline blobs, then source saturation by default (2026-10-21)

The user asked for the tunnel lighting next, suspecting shadows and the
black barrier. Phase 94's barrier trace needs fragment source saturation
(`RSX_FP_SOURCE_RANGE=2`), which streaks the road (user-confirmed on every
saturating variant below; mode 0 looks right).

- RPCS3's decompiler (read for behaviour, not copied) applies the three
  source precision modifiers (SRC1 bits 19-27; 4 = saturate, before ABS,
  negation last) to temporaries and constants only: input registers take
  none (COL0/COL1 are always saturated). Ours applied them to inputs too.
  Modes 1/2 now skip input operands. The road still streaks, so that was
  not the cause; kept because it matches the reference.
- `RSX_FP_SATLOG=1` (new): saturation requests are MUL src1 (123), LG2 src0
  (116), MAD src0 (56), MUL src0 (32), MAD src1 (8); all temporaries.
- `RSX_FP_SAT_OPS=<mask>` (new, 1 MUL, 2 LG2, 4 MAD, 8 rest): only MUL
  saturation streaks the road.
- `RSX_FP_SAT_PROG=<m>,<lo>,<hi>` (new): bisection by a hash of the
  program's first 64 bytes (logged as hash16/hash64). Four rounds of
  window-shot comparisons narrow it to bucket 6 of 16: three programs.
- RenderDoc (`scratch/rdoc/satroad_frame6804.rdc`, MUL saturation on): the
  main road draw (event 5395) saturates N.L before a multiply, but N.L is
  0.33-0.52 at every traced road pixel, so the road surface is unchanged.
  The candidate is a reflective/specular overlay program (guest fp
  0x075F5AC1, dump under ignored `scratch/fpd113/`) that squares
  `saturate(x)` of a reflection term and multiplies by it again: without
  saturation a negative term squares to a positive highlight, so mode 0
  may be the one adding light. Which is right needs the RPCS3 reference:
  the next step is the same program's draw in
  `scratch/rdoc/rpcroadreplay_frame187.rdc` and its term at a road pixel.
- Also seen in this capture: render target 36843 holds an old 1280-wide
  frame with garbage on its right, the likely source of the replay's noise
  strip (Phase 109).

**Continued: the road streaks are not the clamp's arithmetic.** A finer
hash (`hash64`) isolates one program, guest fp 0x0B998E81, the main road
material (event 5395 in the capture): saturation alone (MUL only, that
program only) reproduces the streaks; the other two bucket-6 programs do not.
Its only text difference is `h[2].xyz *= saturate(h[3].x)`, where h[3].x is
the normal map's N.L.

- `RSX_FP_SAT_VIS` (new, diagnostic): 1 shows a saturated source that was
  negative as 50, 2 one above 1, 3 spells the clamp `min(max(x,0),1)`, 4
  replaces the program's colour with its first saturated source (red 0..1,
  green negative, blue above 1, white NaN). Mode 4 paints the whole road
  solid red: N.L is inside 0..1 everywhere, no NaN. Yet modes 1 and 2
  (identical results for in-range values) came out smooth, and mode 3 and
  plain `saturate` streaky.
- With an empty cache folder (`RSX_SHADER_CACHE=scratch/cold113`), plain
  saturation was smooth on both the cold and the warm run; on the main
  `shadercache/` it was streaky with warmup off, with recipes and race
  prewarm off (`RSX_PSO_RECIPES=0 RSX_RACE_PREWARM=0`) and with the race pack
  off (`RSX_SHADER_PACK=0`). The DXBC files, driver blobs (the hash covers
  both shaders' bytecode) and the pack are all keyed by full text or
  bytecode, and the library and fp profiles are not read in play, so no
  stale entry has been identified. Frame rate does not track it either.
- RenderDoc captures are not representative (the user notes they run
  differently): their composites showed no streaks in either mode.

**Solved: stale native pipeline blobs.** `RSX_PSO_DISK=0` (no driver
pipeline blob cache) on the main cache made saturation smooth at 216 km/h.
The blob key (`guest_pso_hash`) covered pipeline state and both shaders'
bytecode but left out the root signature, which holds the static sampler
bank, and that bank has changed across builds (Phase 78 and later). So a
pipeline whose shader bytecode matched one first built in an older build
got that build's blob, with its sampler setup, and the road sampled with
the wrong wrap. That explains every observation: saturated variants were
first built in Phases 94/97; the conditional spellings compile to new
bytecode (no blob), `min(max(x,0),1)` compiles to the same bytecode as
`saturate`; an empty cache folder has no blobs. The Phase 97 conclusion
that saturation streaks the road was this artefact.

- The serialized root signatures are hashed when created and folded into
  the blob key (`RSX_PSO_KEY_RS=0`: the old key). Old blobs stop matching;
  nothing is deleted. Recipes recorded under the old key are still accepted
  (`guest_pso_recipe_hash_ok`), and the pipelines they create are looked up
  under the new key.
- **Fragment source saturation is now the default** (`RSX_FP_SOURCE_RANGE`
  unset = 2; `=0` legacy; `=1` all ranges, experimental). The user confirmed
  on a fresh-cache run that it fixes both the black barrier and the road.
  Verified on the main cache with warmup on: smooth road at 207 km/h, menu
  set 2236 and race set 3040 prepared. Tunnel interior still dark (user).
- Tests: `fp_source_range.ps1` (unset now expects saturation only; all four
  modes pass, 240 lanes each), `pso_async.py` (stub for the recipe check),
  `debug_export.ps1`.

The earlier contradictions in this phase are kept above for the record. The user's rolling-start shot
shows the streaks along the pit straight at 120 km/h from a trackside
camera, so they are a texture-like artefact, not speed blur.

Mode 3 of `RSX_FP_SOURCE_RANGE` (also skip texture-fetch operands) is a
diagnostic only. The default stays 0. Tunnel lighting itself is not changed
yet (Phase 94: material constant 0.01 times exposure 0.4).

## Phase 112 - Dealer page: SPU dispatch measured, no cheap win (2026-10-21)

Goal: cut the Ferrari dealer page's render workloads (0/1, ~29 ms of CPU a
lane pass at 30 FPS) toward 60 FPS. Measured before changing anything:

- `SPU_IBHIST=1` (new): ~1.2 million indirect branches a second, nearly all
  indirect calls (bisl through a register) to a few geometry routines of
  body b01376080 (0xB240, 0x10EE0, 0x10C18, 0x103E0, 0x10418); full drains
  ~130,000 a second. The fast-path resolve, timed with rdtsc, is ~34 cycles
  including the timer pair: about 1% of lane CPU. A per-call-site target
  cache would save at most that, against the overlay/residency cases it
  must get right; not built. The Phase 110 sample shares for
  `spu_indirect_branch`/`spu_lookup_fast` (11%) do not match this timing;
  treat per-function runtime shares from the sampler with caution.
- Interrupts: ~2.5% (Phase 111).
- `SPURS_KERN_STAT=1`: both workloads already run on 5 lanes each (ready 5,
  maxContention 5), so ~10 SPU lanes share 6 cores / 12 threads with the
  title's PPU threads. The page is bound by total CPU throughput, not
  scheduling or lane count.

So the remaining lever is faster lifted SPU code across the board (60% of
the lane time is body b01376080, spread over ~10 routines): register
promotion within lifted functions, or native replacements of several of
those routines. Both are larger projects; not started. Diagnostics kept:
`SPU_IBHIST=1` (targets, full-drain return pcs, fast-path cycles).

## Phase 111 - Native sorted walk in the race workloads; SPU interrupt cost (2026-10-21)

**The race's sorted insertion runs natively.** Body 0x0133A700, blocks
0x43E0/0x43E8/0x4420 (Phase 110): walk a list in descending order of the
float key at +60, next index the halfword at +66 (0xFFFF ends it), 68-byte
nodes from r13, new key in r12; stop when the new key is greater (fcgt).

- `src/gt5p_spu_native.c` finds the stopping node natively and sets r7 to
  the node one step before it; the lifted code then takes the last step and
  the final test, so every register ends as before, and nothing is written.
  Local-store reads follow rotqby's wrap within a quadword.
- `scripts/spu_native_patch.py` inserts the call at the top of the lifted
  blocks named in `spu_native_hooks` (`config/targets.json`). Required after
  every SPU lift or `--chain`; `--check`, `--restore`.
- `GT5P_SPU_NATIVE`: 0 off, 1 on (default), 2 check: compute natively,
  change nothing, compare with where the lifted walk stopped at 0x4420.
  Two 30 s race runs in check mode: about 2.5 million walks each run's
  final windows, 0 mismatches. `GT5P_SPU_NATIVE_STATS=1` counts.
- Walks average ~90 nodes (~120,000 nodes a pass). A/B within one boot
  (`SPU_EXP_AB=1`, gate since removed): byte-wise reads 10.8-11.8 -> 9.4-10.3 ms;
  with single unaligned loads 10.7-11.9 -> 8.8-9.8 ms a pass (~18%). The
  walk is still a third of the workload: it is latency-bound pointer
  chasing, natively or not; only a different algorithm would remove it.
  Frame test 59.0-59.3 FPS (at its ceiling).

**SPU interrupt cost on the dealer page.** `SPU_IRQTRACE=1`: the interrupts
are list stall-and-notify (event 0x2), not tag updates as Phase 110 said: a
pair per job, at 0x2D38 (job manager, depth 0; its iret runs one call deeper
and unwinds to the driver) and 0x2328 (depth 1; iret at depth 2, unwinds to
the taking frame, then a drain restart). `SPU_IRQSTAT=1` now also stamps
cycles: handler ~17,500 cycles an interrupt (take to iret restore), longjmp
~5,000 cycles each, two per interrupt; ~9,400 interrupts/s on this visit's
cars. About 2.5% of render-lane CPU in all, under 1% in unwinds. Reworking
the iret path (non-unwinding jumps, no longjmp) is not worth its risk for
that; left alone. The dealer's remaining runtime share (Phase 110: 40%) is
mostly ordinary call/return dispatch (`spu_indirect_branch`,
`spu_lookup_fast`, `spu_drain_call_impl`) and DMA copies, outside interrupts.

## Phase 110 - SPU profile: where hand-written replacements would pay (2026-10-21)

Prompted by another port's report of a 25x gain from replacing one SPU
occlusion job with a native routine. The question: which GT5P SPU code, if
any, is worth that treatment. Measured on the current build (Phase 109).

**Ferrari dealer page, 1080p/2x** (`dealer.ps1 -Moves DOWN,RIGHT,RIGHT,RIGHT,RIGHT
-Enter`, `GT5P_SAMPLE=16 GT5P_SAMPLE_GRAIN=16 GT5P_SAMPLE_WID=1
SPURS_LANE_CYC=1`). 30 FPS; render workloads 0 and 1 take 28-30 ms a lane
pass, so this page is SPU-bound (60 FPS needs under ~16 ms). Workload 1's
samples, all rounds summed (11,195):

- 60% job body b01376080: 0xF8C0 18%, 0xF620 8%, 0x10EE0 6%, 0x4844 6%,
  0xD388 5%, 0x10C18 4%, 0xB3E0 4%, 0xB240 4%, then smaller ones.
- 40% runtime: `mfc_do_transfer` 8%, `spu_indirect_branch` 7%,
  `spu_drain_call_impl` 5%, `spu_lookup_fast` 4%,
  `spu_irq_regs_maybe_restore` 3%, `spu_restart_dispatch` 3% (its longjmp's
  unwind), `spu_rdch` 2%, `spu_shlqby` 2%, `spu_fi` 1%.

`SPU_IRQSTAT=1` (new): about 33,000 SPU interrupts a second on this page,
~310 per lane pass, each ending in two longjmps (iret to the taking frame,
then a drain restart), and ~420,000 indirect branches a second resolved on
the slow path while a handler's registers were saved. The interrupts are
the job manager's tag-update events: our DMA completes at once, so each
armed tag update interrupts at the next dispatch. An experiment letting
handler-time branches take the fast path (except to the interrupted pc)
measured within noise in an A/B in one boot (paired windows within 0.5 ms
of 31-33 ms) and was removed. The counters themselves cost ~5 ms a pass
(atomics); leave them off for timing.

**Race, HSR frame test** (`GT5P_SAMPLE_WID=5`). Workloads 5/6 take ~11 ms a
pass. Workload 5's samples (6,587): 90% body 0x0133A700, 9% runtime.

- 0x43E8 (with its head 0x43E0) 40%: a walk along a list of 68-byte nodes
  linked by 16-bit index, comparing a float key at +60 against the inserted
  one: a sorted insertion, O(n) per insert. 0x554C 14%, 0x66B8 8%, 0x19498
  6%, 0x196B0 5%, 0x69B0 5%.
- `spu_fi` 7%: the reciprocal-estimate interpolation, a called four-lane
  scalar loop.

**`spu_fi` vectorised.** Same arithmetic with SSE2: the step's 2^(exp-140)
is built from bits while exp >= 14 (lower exponents take the scalar form),
y's 2^-19 is a constant, multiply and subtract stay separate. 0 differing
words in 20 million random and edge-exponent operands, with IEEE and with
FTZ/DAZ (scratch test against `spu_fi_scalar`). Race workloads 5/6:
11.0-11.4 ms -> 10.0-10.5 ms a pass; frame test 59.4 FPS, 1.1% late.
`-DSPU_FI_SCALAR` builds the old form.

**Where a replacement would pay, in order:**

1. The race's sorted insertion at 0x0133A700+0x43E8: 40% of the frame's
   critical-path workload in a dozen instructions. A native loop over the
   local store (or a different insertion structure producing the same
   order) should take most of that away. Gains go to race headroom; the
   frame test is already at its ceiling.
2. The dealer's interrupt traffic: ~310 interrupts a pass, each with two
   longjmps and 2 KB of register save/restore. Returning from an iret
   without the longjmps, or not raising a tag-update interrupt the handler
   provably does nothing with, is a runtime change that helps every WWS job.
3. Body b01376080 (geometry): the time is spread over ten routines, so no
   single rewrite takes much; better served by general lifter work (hot
   leaf loops with registers in locals) than one-off replacements.

A replacement must be our own code describing the behaviour (addresses, not
transcribed lifted or decompiled code), behind a switch, with a check mode
comparing its output memory against the lifted routine.

Tools: `SPU_IRQSTAT=1`; `SPU_EXP_AB=1` flips `g_spu_exp` every
`SPURS_LANE_CYC` window for an A/B in one boot (`abcyc.py --key exp`); read
`g_spu_exp` only from code under test.

## Phase 109 - Hood-camera audio (SPU denormals), controller during tests, replay ghosting report (2026-10-21)

**Controller during tests.** A `PAD_HOLD` script used to replace port 0
outright, so a controller did nothing during a scripted run. Now a connected
controller and the focused window's keyboard are merged over the script:
buttons ORed, the controller's sticks used where the script leaves them
centred, triggers and pressures the larger of the two. `PAD_HOLD_MERGE=0`
restores script-only input. A 20 s 1080p/2x HSR run still drives into the
race (59 FPS median), with no controller pressed.

**Replay ghosting (open).** Two F8 reports from process 34220 (Phase 108
build) catch the post-race replay: the frame is about four overlaid copies of
the scene a few frames apart, and a ~225-pixel strip at the right edge is
noise. Its FIFO walk is ~22 ms a frame against ~9 ms while racing; 28 FPS.
The log has an `[RT] evict slot 7 (off=0x1100000 1920x1080)` shortly before.
Hypothesis, untested: the replay's frame blend samples earlier frames by
address, and they resolve to stale targets or to unwritten guest memory.
Whether it predates Phase 108 is not checked (`RSX_HOT_METHODS=0
RSX_IMM_MASK=0 RSX_FPK_FAST=0` would tell).

**Audio cutting out in the hood camera: fixed.** A scripted 1080p/2x
frame test (default camera) with `AUDIO_RATE=1 SPURS_JC_STATS=1`: 2 underruns
in 60 s, 0% silent blocks, 3,189 jobs/s, chain busy 81-92%. With the user
switching to the hood camera during the same test (the controller merge
above): 2,000 jobs/s at 0.47 ms each instead of 0.28, chain 96-97% busy,
35-42% of blocks silent, about 6 underruns a second.

`GT5P_SAMPLE=4 GT5P_SAMPLE_GRAIN=16` on the job thread: one lifted function,
image j65DD2F53 block 0x1E8, was 40% of its samples in the hood camera (9%
before the switch). It is a per-sample IIR filter: one float read from local
store, five multiply-adds, written back, then a backward branch. (`SPURS_JC_SAMPLE`
stopped reporting when the view changed; the per-thread sampler did not.)

- First guess, the dispatcher trip on the loop's backward branch: the chain
  pass in `lift_spu_jobs.py` now makes backward transfers within an image
  direct tail calls too, with the dispatcher's interrupt check inline, never
  for a branch to 0 (a job's end, which only the dispatcher notices).
  `SPU_CHAIN_BACK=0` at lift time leaves them alone; at run time
  (`g_spu_chain_back`, also cleared by `SPU_FAST=0` or a per-step diagnostic
  switch) it sends them back through the dispatcher. 2,883 transfers. Hood
  camera: no change (0.47 ms a job, block 0x1E8 still 2,003 samples of 4,764).
- The cause: denormals. The filter's state decays toward zero; x86 handles
  denormal floats with microcode assists, the SPU's single-precision unit
  flushes them to zero. `runtime/spu/spu_fpmode.h` sets MXCSR flush-to-zero
  and denormals-are-zero at the start of every host thread that runs SPU
  code (SPURS kernel, workload groups, pool lanes, policy-module workers, job
  chains, raw SPUs, async SPU threads); never on PPU threads. `SPU_FTZ=0`
  leaves MXCSR alone. Hood camera: 3,190 jobs/s, 0.26-0.29 ms each, chain
  82-92% busy, **0 underruns and 0% silent blocks** for the whole run; block
  0x1E8 313 samples. The default camera's job thread: 86-87% -> 76-78% of a
  core.

Backward chaining kept on its own merit: default-camera A/B frame tests
(`SPURS_LANE_CYC=1`): workloads 5/6 lane time 11.0-11.5 ms (on) against
12.4-13.3 ms (`SPU_CHAIN_BACK=0`); frame test 59.1 FPS / 0.9% late against
59.3 / 1.4%, walk 6.25 against 6.28 ms. `pso_async.py` and `debug_export.ps1`
pass.

## Phase 108 - FIFO walk: hot methods first, fewer copies (2026-10-21)

`RSX_DRAWPROF=1` (new) times the walker's draw recording by stage with the
TSC and prints ms and calls per frame every 5 s. Draw recording is
2.3-2.5 ms of a 7-11 ms walk: upload 1.0 (half of it `vgpu_finish`, the
raw-vertex copy), constants 0.40, texture snapshots 0.25, the rest below
0.2 each. The other ~5 ms is command handling. Present-thread samples with
library samples credited to callers (`GT5P_SAMPLE_DLL` unset) show method
dispatch about 19% of busy time, the walker loop 16%, and memcpy/memset in
several callers.

- **Hot methods first** (`RSX_HOT_METHODS=0` off). Immediate vertex data
  (3F/2F/4UB/4F) and transform constants are about a third of the ~215,000
  data words a frame, and sat 60-80 tests deep in
  `rsx_process_method_impl`'s chain, behind its debug switches. They are now
  handled first, same effects minus their debug prints, while none of the
  switches that watch them is set. No earlier handler in the chain claims
  those ranges (checked against every constant it tests).
- **Immediate vertices copy only read attributes** (`RSX_IMM_MASK=0`, or
  `RSX_VTX_MASK=0`, copies all). Each immediate vertex copied all sixteen
  attribute registers (256 bytes) at emit and again at read. Both now copy
  only the vertex program's inputs, the rule the vertex buffers already use.
- **Fragment constants without a 32 KB clear** (`RSX_FPK_FAST=0` off). Every
  draw zeroed a whole `rsx_fp_constant_block` (2048 slots, 32 KB) before
  collecting a program's few inline constants: 16-29 MB a frame.
  `rsx_fp_collect_constants_to` writes the first `FP_CB_CONSTS` straight
  into the constant buffer, same count and error result. Constants 0.84 ->
  0.48 us a draw.

| Frame test (1080p/2x, HSR) | FPS | Late | p99 | Walk |
| --- | --- | --- | --- | --- |
| Hot/imm off (same build) | 59.0 | 1.0% | 20.1 ms | 7.75 ms |
| Hot methods + imm mask | 59.2 | 1.6% | 21.6 ms | 6.65 ms |
| + fragment constants | 59.5 | 1.1% | 20.1 ms | 6.66 ms |

Frames are now at the ceiling in this test: median 16.6 ms, and FPS and late
share sit within noise of each other. Walk per frame is the number to watch.
HUD, mirror, track map, loading list and Ferrari dealer (30 FPS) draw
correctly; game speed 1.015 over 40 s of shots.

**Left in the walk:** `vgpu_finish` copies ~2.9 MB of raw vertices a frame
(0.65 ms). Texture snapshots copy a volatile texture again at every draw
that binds it (0.3 ms). The vertex cache compares (`vraw_cmp`) and the
walker loop's per-header overhead remain.

## Phase 107 - Inline guest memory access; chained SPU job bodies (2026-10-21)

With the pacer pad gone, full rendering still had 7-9% of frames over 20 ms.
`rtsplit.py` on a full-rendering timeline: the render thread's CPU was 14.1 ms
a frame, against 8.5 ms with draws dropped, and it often was not running.
Keeping host threads off the guest CPUs (`PS3_HOST_AVOID_PPU=1`) changed
nothing measurable (58.1 FPS, 6.6% late, CPU 13.4 ms).

**Guest memory accessors.** Sampling the render thread (g20) put 24% in
`vm_read32`, 13% in `vm_write64`, 10% each in `vm_write32` and
`spu_coh_is_reserved`, and 5% in `vm_read64`: about 65% of its time was
calls to the out-of-line accessors, against a few percent in game code. Main
and g21 looked the same. `GT5P_VM_INLINE` (Phase 54's step 5a, set aside when
SPU dispatch set the pace) is now **on by default**. Render thread CPU 14.1
-> 5.8 ms a frame, p99 ~30 -> 24.4 ms, walk 11 -> 7.5 ms. The late share did
not move (6.8%): the render thread now spent ~9 ms a frame in spin waits.
`-DGT5P_VM_INLINE=OFF` builds the old way; `VM_INLINE=0` at run time sends
every access out of line. The exe is 176 MB.

**The race's one-SPU workloads.** Lining up the render thread's spin-wait
sleeps (timeline `Q`) with workload passes: each frame it waits for workload
5 or 6 to end, then kicks the other and prepares the flip. Those are WWS job
lists with maxContention 1 (forcing two lanes made no difference and was
removed), and a pass took 14-17 ms of lane CPU (`SPURS_LANE_CYC=1`), against
4.2 ms in Phase 101. That pass was the frame's critical path.
`GT5P_SAMPLE_WID=<wid>` (new) profiles one workload's SPU code across pool
lanes (lanes publish the workload they run in `g_spurs_tid_wid`;
`GT5P_SAMPLE` now takes up to 16 threads). Workload 5 runs job body
`0x0133A700`. 26% was one two-block loop (`0x43E0`/`0x43E8`, a walk along a
list of 68-byte nodes ordered by a float key), and 17% the dispatcher between
lifted blocks: every block, even a fall-through, returned to it.

`lift_spu_jobs.py` turns forward transfers into guaranteed tail calls for job
images, but it never did so for job bodies. It now does for bodies too
(`SPU_CHAIN_BODIES=0` at lift time to skip; `--chain` applies it to an existing
`generated/`): 3,410 transfers, 1,066 in `0x0133A700`. Backward transfers still
pass the dispatcher. Workload 5/6 passes 17 -> ~6 ms in racing (13 ms in an
earlier, heavier window); render lists 3.4 ms.

| Frame test (1080p/2x, HSR) | FPS | Late | p99 |
| --- | --- | --- | --- |
| Phase 106 | 57.7-58.1 | 7.1-8.8% | 28-34 ms |
| + inline accessors | 57.7 | 6.8% | 24.4 ms |
| + chained bodies (2 runs) | 58.9-59.0 | 3.0-3.2% | 26.6-27.7 ms |

Game speed 1.006 (HUD timer over 40 s of shots). The rolling start stays at
30 FPS (two seconds at 22-27), then 59-60. Ferrari dealer 25 FPS. Tests:
`pso_async.py`, `shader_warmup.py`, `debug_export.ps1` pass.

**Next.** The FIFO walk is 10-12 ms a frame (draw recording, Phase 105) and
now the largest serial item. Backward SPU transfers (loops) still use the
dispatcher, and the patched spin waits sleep 0.5 ms when asked for 0.1.

## Phase 106 - The title's frame pacer copies slow frames; skip its pad (2026-10-21)

The user asked why the race still missed 60 FPS with every draw dropped
(`RSX_VTX_SKIP=1`: 58.5-58.8 FPS, 3.5-5.4% of frames over 20 ms).

**Where late frames come from.** A no-draw timeline (`nd-tl`, 10 s): 523
frames took one vblank, 18 two and 14 three, in clusters. In a three-vblank
frame the walker sat idle for 37 ms: the render thread (`PDI:1:200c3b40`,
guest tid 20, the one calling `cellGcmSetPrepareFlip`) slept in `usleep(37381)`
before submitting. `PS3_USLEEP_LONG=<us>` (new) logs long sleeps with their
guest return address. Every long render-thread sleep returns to `0x00B24AF4`.

**The pacer** (`func_007AF300`, once per frame on the render thread; read
from the disassembly, not decompiled into this repo):

- It keeps the render loop's elapsed time for the last four frames (fields
  `+0x148..+0x160`; timer at `+0x168`, restarted after the pad).
- The target is `[+0x1C] x 16683 us` (one 59.94 Hz vblank per unit).
- If the longest of the four reaches the target, it sleeps until the
  current frame has lasted that long, capped at 50,049 us (`0x00B24AA8`,
  sleep until an offset from the timer's start).

So one slow frame is copied onto the following ones: a 40 ms hitch becomes a
run of ~40 ms frames. On a console frame times vary by microseconds and this
rarely fires. Here it fires on ordinary jitter.

**What the render thread does per frame.** New timeline events: `C` at each
prepare flip (the thread's CPU time and wall time since its previous one) and
`Q` for each sleeping step of a patched spin wait. `scripts/diag/rtsplit.py`
splits each frame (`nd-tl3`, 880 frames, no draws):

| | Wall | CPU | Syscall waits | Pacer pad | Spin waits | Not running |
| --- | --- | --- | --- | --- | --- | --- |
| Normal frames (mean) | 16.6 | 8.5 | 5.0 | 0.6 | 2.3 | 0.2 |
| Late frames (range) | 20-37 | 8-15 | 0-10 | 0-22 | 0-11 | 0-13 (25 frames) |

The render thread's CPU never exceeded 15 ms. Late frames were a spin wait on
SPU progress, an occasional preemption, or a vblank wait, and then the pacer
padding.

**Skipping the pad** (`PS3_USLEEP_SKIP_LR=<hex lr>` returns at once from sleeps
from that call site; the address is `frame_pacer_sleep_lr` in
`config/targets.json`, set by default from `main.cpp`; `GT5P_PACER_PAD=1` keeps
the title's padding):

| Frame test (1080p/2x, HSR) | FPS | Late | p99 |
| --- | --- | --- | --- |
| No draws, pad | 58.5-58.8 | 3.5-5.4% | 26-39 ms |
| No draws, no pad | 59.3 | 1.6% | 24.2 ms |
| Full, pad (Phase 105) | 54.8-55.7 | 13.6-15.4% | 41-45 ms |
| Full, no pad (3 runs) | 57.7-58.1 | 7.1-8.8% | 28.5-34.1 ms |

Game speed is unchanged: the HUD timer advanced 39.48 s across 40 s of shots
(0.99; Phase 102 measured 0.97). The race clock follows the title's timer
service. The rolling start still runs at 30 FPS, and more steadily (30 almost
every second, against 24-30 with the pad). Ferrari dealer 24 FPS. Tests:
`debug_export.ps1`, `pso_async.py` pass.

**What remains** (full rendering, ~7-9% late): the walker's draw recording
(~5.6 ms, Phase 105) delays the render jobs, SPU spin waits stretch the
render loop, and guest threads are occasionally preempted.

## Phase 105 - Frame-time test, walker CPU split, NOP-loop parks (2026-10-21)

Steps 1-3 of [plan-60fps.md](plan-60fps.md), as the user asked.

**Frame-time test (step 1).** `race.ps1 -FrameTest` drives High Speed Ring
with a moving car, waits 45 s (past the rolling start), and reads 60 s of
per-frame records the present thread writes with `GT5P_FRAME_LOG=<csv>`
(Unix ms, walk wall ms, walk CPU ms). It prints frames, FPS, median, p99,
max, the share of intervals over 20 ms (a missed vblank) and the walk per
frame, to `scratch/pv/<tag>.frames.txt`. `-SampleDelay` moves the window. Use
it as the pass/fail number, not title-bar FPS. Run-to-run spread is wide at
the same build (51.6-55.5 FPS, 15-30% late): AI cars and crashes change the
scene. Compare walk ms/frame, which moves far less, and repeat runs.

**Walker CPU split (step 2).** The present thread now times each FIFO walk
with `QueryThreadCycleTime` as well as wall time (only when F3/`present-prof`,
the frame log or the timeline is on); the timeline `R` event carries both and
`tl.py` prints them. Result: the walk is CPU work, within 2% of wall time in
every run. It is not parked waits. Baseline at this phase's start: 51.6-51.9
FPS, 27% late, p99 46-49 ms, walk 11.9-12.5 ms/frame. Working set 2.68 GB.

**Walk made cheaper (step 3).**

- *Method fast path* (`GCM_WALK_FAST=0` off). 3D methods on subchannels 0/1
  with no per-word debug switch set translate their IO address once per
  1 MB page and read guest memory directly, instead of an IO translation, a
  dozen switch checks and a `vm_read32` per word. Headers touching
  `GET_REPORT` keep the general path. Walk 12.5 -> 10.0-10.6 ms/frame;
  53.4-56.7 FPS, 10-20% late.
- *NOP-loop parks* (`GCM_NOP_PARK=0` off). `GCM_WALK_STATS` counted 100-160
  million method headers per 5 s in late race windows, all but ~20M of them
  `0x00000100`: `NV4097_NO_OPERATION` with no arguments. `GCM_NOPRUN_DBG=1`
  (new) shows they come in runs of 31, each closed by a JUMP back to the
  run's start: the SPU jobs park the walker on a 128-byte block (31 NOPs and
  a JUMP) at a ring's write head and overwrite the block to release it. The
  walker recognised only a JUMP to itself as a park, so it lapped these
  blocks ~5,500 times a frame. The JUMP back over an all-NOP block is now a
  park like the self-JUMP, with the same wake, timeout and stuck rules. NOP
  headers fell from ~130M to a few hundred per 5 s.
  The time gained is small (walk 10.2 -> 9.8 ms in a same-build A/B), because
  a NOP lap is cheap; the real gain is that the walker no longer spins
  through guest memory the jobs are writing.
- *Failed: skipping NOP runs.* Scanning a NOP run in one step made the walker
  lap these blocks fast enough to burn its whole word budget per pass. The
  circling watchdog then resynced to `put` and dropped the SPU lists: 3 FPS.
  Removed. Prefetching the FIFO 512 bytes ahead gained nothing; removed.
- `has_display` scans the frame's draws backward (it scanned all of them
  forward at every present).

**What the walk is now.** `RSX_PROF` (now also ranks by count) and a
same-build run with `RSX_VTX_SKIP=1` (every draw dropped) split it: walk
9.8 -> 4.2 ms/frame without draws, 58.8 FPS, 3.5% late. So **draw recording is
~5.6 ms of the walk**: `DRAW_INDEX_ARRAY` costs ~2.8 us a call, ~1,800 calls a
frame. `RSX_VTXSTAT`/`PERF`: uploads ~2 ms/frame (indexed triangles 1,500
calls/frame, GPU-fetch region setup in `vgpu_finish` 0.32 s per 5 s), per-draw
constant snapshots (`vp_record_cb`) ~1.5 ms, the rest record bookkeeping.
Immediate-mode vertex words (0x1500-0x1508, 0x18C0/C4) are the most numerous
methods (~23M per 5 s) but cheap each. The sampler under-attributes the
backend here (its draw functions show ~10%); trust the drop test.

**Also in this phase.**

- The resident pipeline limit is 8192 (was 4096): menus keep ~1,450 and the
  race set ~4,050 more; `race-prewarm` now reports `rejected=0`.
- Menus and dealerships get their own shader pack,
  `shadercache/menu-shaders-v1.pack`, loaded at the first script load and again
  after a race. Second run: 318 shaders read in 0 ms, 538 hits, 0 new.
- `GT5P_SAMPLE_DLL=1` keeps samples landing in DLLs (no unwind);
  `GT5P_SAMPLE_TOP` now also applies to per-thread tables.
- Checks: Acura (24-30 FPS) and Ferrari dealer pages draw with the NOP park;
  `pso_async.py`, `shader_warmup.py`, `debug_export.ps1` pass.

**Next for 60.** The walker's remaining CPU is draw recording: make
`vp_record_cb` copy only changed constants, and cut per-draw upload and
record work. Run in the frame test, the title alone (draws dropped) is
already at 58.8 FPS with 3.5% late; the render-list jobs (step 4) are the
other half.

## Phase 104 - What the memory really is; per-frame buffers sized to use (2026-10-21)

The user asked why the port needs about 5 GB when the PS3 has 512 MB.
A committed-memory map of the process in a High Speed Ring race (1080p/2x,
private 3.86 GB, working set 2.84 GB) shows:

| Allocation | Committed | Notes |
| --- | --- | --- |
| Guest address space | 948 MB of a 4 GB reservation | PS3 main/RSX memory plus emulator regions |
| Per-frame upload buffers | ~730 MB | Constants 198 MB, raw vertices 256 MB, vertices 128, fragment constants 102, indices 32, descriptors 12 |
| Their Phase 101 GPU copies | ~730 MB | Same sizes again; see below |
| ~40-55 allocations of 15 MB | ~0.6-0.8 GB | 1080p 2x MSAA surfaces: GPU resources |
| Lifted code image | 202 MB | Image-backed |
| One 1 GB mapped view | 1024 MB | NVIDIA's own on-disk shader cache (`AppData\Local\NVIDIA\DXCache\*.nvph`), file-backed |

**Private bytes overstate RAM.** A standalone D3D12 probe on this machine
(RTX 4060): every default-heap allocation adds its size to process private
bytes but nothing to the working set. This held for committed buffers, ones
created without zeroing, explicit heaps and render targets. A 512 MB
upload buffer adds 512 MB to both. The driver reserves page-file backing for
GPU allocations. So the GPU copies and render targets cost commit charge, not
RAM; `RSX_VRAM_FRAME=0` drops private by about 700 MB but frees no RAM worth
the GPU time. The working set is the figure that matters. F8's memory line now
leads with it.

**Per-frame buffers sized to measured peaks (step 1):**

- `RSX_DRAW_CAP` (default 6144, up to 12288): constant slots are draw indices,
  so the constant, fragment-constant and descriptor buffers follow the draw
  cap. Peaks: race 2627-3484 draws, Ferrari 3077-3336. Record arrays keep
  12288 entries.
- Raw vertex bytes per half: 48 MB (was 96; `RSX_VTXGPU_MB`). Peaks 11-28 MB;
  a full region falls back to CPU conversion.
- Race: working set 2842 -> 2592 MB, private 3.86 -> 3.33 GB, GPU copies 1240 ->
  476 MB. Median 56 FPS, unchanged; Ferrari 25 FPS. 3 of 3 boots then reached
  the dealer page; one earlier boot hung just after the opening dialog (the
  rare start-up hang of Phase 22's kind; not reproduced).

What is left is mostly irreducible here: the emulated PS3 memory (948 MB),
the remaining upload buffers (~480 MB), code, the driver and caches.

## Phase 103 - Race-start stalls: cold shader reads, race shader pack (2026-10-21)

Two F8 exports from process 13624 (10:07:42 and 10:09:00; build with Phase
102). The first covers the grid and race start: present gaps of 1292, 1235,
1013, 689 and 655 ms, almost all of each in the walker's wait for the replay
thread ("submit"). Only 377 MB of RAM was available, private memory was
4.05 GB, and there were 3.5M page faults (4.4M at the second export). The
second export is mid-race: median 16.7 ms, a few 50-100 ms gaps whose time is
mostly guest idle.

- During the race start the replay thread's time per frame went 2-3 ms ->
  22 ms -> 97 ms, with its pipeline cache growing from 448 to 1496 entries in
  about 15 s. Its CPU use was only 28% of a core in the snapshots: it was
  blocked, not busy.
- **Race preparation was turned away by the resident cap.** The menu set
  (1449) and race set (3922) are 5371 pipelines against a 4096 cap; startup
  prepares the menu set first, so `[race-prewarm] finished: ready=2715
  rejected=1207`. `RSX_PSO_RACE_EVICT=1` releases resident pipelines outside
  the race set at race loading: ready=4020, rejected=0, but the extra recipes
  cost 12.6 s of loading in file reads, and the race was not smoother than
  the control. It is off by default.
- **The stall was cold shader reads on the replay thread.** Each first
  sighting of a pipeline hashes the generated HLSL and reads its DXBC from
  `shadercache/<key>.dxbc`, one file per shader (53,881 files). Cold reads cost
  4.9 ms each, warm ones 0.06 ms. `[pso-time]` in a bad window: "260 misses:
  hlsl 48 ms, dxbc 1042 ms". With a few hundred MB free, nothing stays in the
  OS file cache. The rejected pipelines themselves were built on the worker
  and only delay individual draws.
- **New: race shader pack (`RSX_SHADER_PACK`, default on; `=0` off).** While a
  race runs, every shader looked up is kept in memory with its bytecode. When
  the race ends, or after 10 s without a new shader (so a killed or crashed
  process keeps it), it is written to `shadercache/race-shaders-v1.pack` on a
  separate thread, and shutdown also writes it. The next race loading reads it in one
  sequential read and lookups check it first. This race's shaders are kept
  first, older ones up to `RSX_SHADER_PACK_MB` (default 64). Memory: about
  20 MB during a race, freed when it ends.
- Measured (High Speed Ring, 1080p/2x, warmup on): learning run 9113 ms of
  shader reads on the replay thread over the run, pack of 1571 shaders /
  20.6 MiB; next run read it in 15 ms and spent 790 ms. The learning run's
  worst race-start window (58 presents in 5 s) did not recur. This machine
  had more free RAM than the user's, so cold reads there cost more.
- F8 reports add a "Race shader pack" line (shaders, hits, new).

Open: menus and dealerships still read shaders per file (same cost, smaller
sets); a combined pack or pipeline-key cache could cover them. The 1207
turned-away race recipes still build on the worker at the race start.

## Phase 102 - Race slow motion, vblank clock, upload memory (2026-10-21)

The user drove a race at 1080p/2x and exported five F8 reports (process 1236,
06:50-06:51, `logs/debug/`): hiccups on the grid, pauses in the rolling start,
and a race that felt "consistently slow" and rubber-banded. The user also
confirmed that **the rolling start is meant to run at 30 FPS**; Phase 101's
"30 FPS lock" in the introduction is the title's design, not a defect.

### The race played in slow motion (fixed)

`race.ps1 -RaceShots <n>` saves a window shot every n seconds; the HUD race
timer against the shots' file times gives game time per real second. With
guest threads on two CPUs (`PS3_PPU_CORES=topo`) the race clock ran at
**0.38 to 0.55** of real time in several runs, also while the timeline showed
50-60 presented frames a second. So the clock is not frame-locked: the title
advances its simulation on a timer, and that timer ran late.

- Guest PPU threads were confined to logical CPUs 2 and 4. Their demand
  summed to about 180% (render thread 57-62%, PDI:1:200c3b80 35-74%, the
  thread named "Main Thread" 60-88%).
- "Main Thread" (guest priority 2048, host IDLE) is the title's timer service:
  its loop at `0x913270` locks the timer list (`+0x1068`), reads the time and
  fires expired entries from a ring (`0xD897A8`/`0xD89804`, `0x912908`), and
  polls again. It runs only when no other guest thread wants a CPU.
- Three CPUs (`PS3_PPU_PRIO_SCHED=3`): ratio 0.97. Both hardware threads of
  the same two cores (`PS3_PPU_CORES=3C`, four logical CPUs): 0.98, and the
  render lanes keep their four spare cores.
- New default **`PS3_PPU_CORES=topo-ht`**: topo's two physical cores with all
  their hardware threads (on a CPU without SMT, cores until three logical
  CPUs). Default run: 9.900 -> 49.916 s of race time in 41.23 s, **0.97**.
  `PS3_PPU_CORES=topo` restores Phase 91's placement.
- Ferrari dealer visits: topo-ht 24.3/15.9/7.0 fps, topo 6.3/25.1/8.5. The
  low visits in both are first sightings of a car pair building native
  pipelines on the worker (50-115 ms each), not the placement.

Not tested: whether a rubber-band feel remains with real driving; the user's
next exports will show it.

### Vblank on its own thread

The vblank/flip tick shared the present thread with the FIFO walk, and a race
frame's walk is 13-17 ms in one call, so no vblank fired during it. The
title paces on the vblank handler. Wakes of its vblank-driven workers were
2-37 ms apart (mean error from a multiple of 16.68 ms: 3.2 ms), with late ticks
fired back to back. `GT5P_VBLANK_THREAD` (default on; `=0` old ticker) moves
`cellGcmTickVBlank`/`cellGcmTickFlip` to a time-critical thread (timer to
0.4 ms, then spin). Ticks are now 16.68 ms apart (max deviation 0.24 ms) and
416 of 482 worker wakes are 17 ms apart. It did not change the race clock by
itself (0.55 on, 0.54 off) or the rolling start's 30 FPS. Timeline event `V`
marks ticks (`tl.py`).

### Upload memory (1 GB less)

The reports show 394-441 MB of RAM available; the game held 4.8 GB private
(3.3 GB resident) in a race on this 16 GB machine. Paging is a plausible cause
of the 120-600 ms "present" gaps, not a proven one: those gaps were under the
250 ms hitch-snapshot threshold, and no retained snapshot is from the race.

- Per-buffer peaks (new F8 line and `[present-thread]` suffix): race vertex
  slots 1.2 MB, Ferrari 4.9 MB, of 320 MB per half; indices 2.19M of 4M; raw
  vertices 28 MB of 96; draws 3484 of 12288.
- The generic vertex buffer is now `RSX_VPVB_MB` per half, default 64 with
  GPU vertex fetch on (320, the old size, with `RSX_VTX_GPU=0` or
  `RSX_VPVB_MB=320`). Race private memory 4.8 -> 3.8 GB, working set 3.26 ->
  2.75 GB. Its VRAM mirror shrinks by the same 512 MB.
- F8 reports now include process private memory, working set, page faults
  and system commit.

### Ruled out / not adopted

- `PS3_PPU_RESERVE` (process default CPU set excluding the PPU CPUs):
  whole-core reservation made render lanes 25% slower (18.6 vs 14.9 ms);
  logical-only matched the old placement. Removed.
- The rolling start's serial chain (vblank -> render list 13.4 ms -> walk
  tail 3.4 ms -> wid3/wid2 -> flip at about 23 ms) is the title's 30 FPS
  design, so it was left alone.
- Vblank handler delivery does not coalesce (`GCM_PUMP_DBG=1`, now printed
  every 600 deliveries): 7138 deliveries for 7157 ticks.

Open: race windows of 40-56 FPS remain (presents 199-282 per 5 s). With the
clock fixed these judder but no longer slow the race. A stretch of 26-34 FPS
right after the timer starts (render lists 12-13 ms) is probably the rolling
start; confirm with the user's next exports.

## Phase 101 - Toward 60 FPS in races: SPURS dispatch, guest spin waits, frame buffers in VRAM (2026-10-20)

The user asked for a consistent, smooth 60 FPS in races. Not reached yet; this
phase removes three measured limits. All tests are 1080p/2x HSR with preload on,
`race.ps1` (scripted: the car stops against a wall, so 40-s FPS medians are
noisy and not driving benchmarks). The timeline windows (`PS3_TIMELINE`, same
start each run) are the comparable numbers.

The user's latest F8 exports (process 1592) already showed the shape: in
33-ms frames the renderer was idle 20-23 ms waiting for guest commands, so the
guest side, not the renderer, set the pace there. `race.ps1 -Cpu` now reports
per-thread CPU named from the log; `scripts/diag/rdoc_gputime.py` sums
RenderDoc per-event GPU time by target and kind.

### 1. One-SPU workloads ran on the SPURS kernel thread

The kernel ran any workload that wanted one SPU inline, synchronously. GT5P's
race workloads 5/6 (one SPU, 13-15 ms a pass) therefore held the kernel: the
render list (wid0), kicked meanwhile, waited until wid5 ended (one frame:
kicked at 4.35 ms, dispatched at 12.25 ms). Mean kick-to-dispatch was 1.4 ms
for the render lists and 4.6 ms for wid2/3. One-SPU workloads now go to their
lane pool like the others (`SPURS_SINGLE_ASYNC=0` restores inline). After:
kick-to-dispatch about 0.01 ms for every workload; timeline mean frame 25.8 ->
19.1 ms.

### 2. Guest spin waits starved the main thread

Every guest PPU thread runs on two host CPUs (`PS3_PPU_PRIO_SCHED=2`) with
guest priority mapped to host priority. Main Thread is guest priority 2048,
host IDLE. The render thread (PDI:1:200c3b40, 640, NORMAL) waits for the render
list in `func_00BAB5C8`: a bare loop over `func_00BA8838`, which returns
whether queue 3's minimum per-SPU progress reached a target, with no syscall.
`func_00BA97B0` contains the same wait inline. On the console the SPUs finish
in a few ms; here the spin held a guest CPU for most of a frame, and Main
showed 10-11 ms per frame "blocked" in `sys_mutex_unlock` (syscall 104, which
cannot block: it was waiting for CPU). Three guest cores
(`PS3_PPU_PRIO_SCHED=3`) cured Main (0.74 ms/frame) but left lanes three spare
cores and slowed them (wid0 9.7 ms, wid5 18 ms), so it was not adopted.

`scripts/spin_patch.py` (new required post-lift step, after `setjmp_patch.py`;
`--check`, `--restore`, idempotent) adds a call to `gt5p_spin_pause`
(`src/gt5p_spin.cpp`) on the back edge of each loop listed under `spin_waits`
in `config/targets.json`: 32 pauses, 32 yields, then 100-us high-resolution
sleeps (`GT5P_SPIN_SLEEP_US`, `GT5P_SPIN_YIELD=0` pauses only). After: Main's
unlock stall 4.05 -> 0.83 ms/frame, Main 77% of a core; wid0 passes 7.5 -> 5.1
ms, wid5 12.2 -> 4.2 ms; the render worker g21 57% -> 28% CPU; process CPU
4.96 -> 4.74 cores; timeline mean frame 19.1 -> 17.5 ms (about 57 FPS). In the
introduction all four render lanes now share each pass (before, three were
left out of most passes).

### 3. Per-frame buffers were read from system memory

GPU time in the rolling-start introduction was 12-15 ms per frame and did not
change at 720p without MSAA (`fps60-720`) or with per-pixel MSAA shading
(`RSX_SSAA=0`, `fps60-nossaa`). A RenderDoc capture of an introduction frame
(`scratch/rdoc/fps60-intro_frame3139.rdc`, `fps60-intro.gputime.txt`) puts
13.6 of 17.7 ms on the scene target: 1710 draws of about 400 indices, about
8 us each, no expensive draw. The per-frame vertex, index and constant buffers
and the cross-frame vertex cache were upload heaps (system memory), fetched
across PCIe by every draw. This machine reports no GPU upload heap support
(`RSX_GPU_UPLOAD=1`, opt-in, falls back), so the backend now keeps
video-memory mirrors with the same layout (1240 MB) and fills exactly what each
frame wrote with one copy-only command list submitted before the frame
(`RSX_VRAM_FRAME=0` restores system memory). After: introduction GPU time
5.8-10.4 ms per frame, later windows 3-5 ms (from about 6). Shots of the
introduction, HSR race, Daytona race and dealership render correctly.

### Where it stands

- The introduction still presents exactly 150 frames per 5 s (30 FPS lock)
  even at 5.8 ms GPU time. Its render list passes are 13.6-14.6 ms (four lanes
  of 10-14 ms work), the FIFO walk is 16.9 ms per frame, and Main again shows
  5.7 ms unlock + 2.4 ms mutex stalls. That is the next target.
- Later race windows run 47-58 FPS. The audio job chain is the heaviest single
  thread (about 80% of a core); then the render thread, FIFO walker, Main and
  the replay thread. About 4.8 of 6 physical cores are busy.
- The frame start still drains the GPU before replay (no CPU/GPU overlap).
- `PS3_PPU_PRIO_SCHED=3` and `GT5P_VM_INLINE` remain unadopted; the latter was
  measured when SPU dispatch set the pace and may deserve a new measurement.

## Phase 100 - Review fixes: bounded preparation, recipe pruning, staging memory, audio notifications (2026-10-20)

A review of the commits since Phase 74 found problems in the shader-preparation
work and two memory/latency costs. The user asked for those fixed and for the
open rendering bugs (source ranges, depth ownership, tunnel, road streaks,
rims) to be left alone; none of those changed.

### Startup preparation crowded out the race set

With **Preload known shaders** on, the Phase 99 background pass loaded the menu
set and then every recipe on disk in directory (hash) order until the 4096
resident cap was full. The user's cache held 6029 recipes, so the cap filled
with an arbitrary subset; race loading then rejected race recipes that were not
already resident, and the paused startup pass resumed during the race.
Phase 98's clean result (1059 ready, 0 rejected) was measured with startup
preload off, so the user's combination had not been re-tested.

- Startup now prepares the learned menu set, then the learned race set, and
  stops. `RSX_SHADER_WARMUP_SCAN=1` restores the directory scan as a last phase.
- Race loading cancels an active startup pass instead of pausing it.
- Demand (draw-miss) pipelines no longer enter the resident prepared set; the
  renderer's own cache already holds them. Long sessions used to fill the set
  with them too. `RSX_PSO_RETAIN_DEMAND=1` restores retention.
- `RSX_PSO_RESIDENT_MAX` (64..4096, default 4096) lowers the resident cap.

### Recipes were never pruned

Recipes from older shader generators can never match again but were kept and
counted. The worker now marks each recipe used once per run (refreshing the
modified time of the recipe and its two bytecode files); reused bytecode is
touched when a new recipe shares it. At worker start, recipes and bytecode not
used within `RSX_PSO_RECIPE_KEEP_DAYS` (default 14) of the newest recipe are
deleted. The window is measured from the newest recipe, so a break from
playing deletes nothing. Both indexes are then compacted: entries without a
recipe and duplicates go, the rest are ordered newest use first, capped at 4096.
A damaged recipe, or one whose bytecode is gone, is deleted when read, so the
next creation records it again (recording skips an existing recipe). `=0`
disables pruning and use marks. On this cache nothing was old enough to prune
(oldest recipe 2026-10-19); the index backup from before the first run is in
`scratch/index-backup-20261020/`.

### Texture staging kept a second copy of every texture

Every texture slot kept its upload-heap buffer (system memory) for life. Phase
76 doubled the slots to 1024 and Phase 78 made buffers hold mip chains. A slot's
staging buffer is now freed at frame start (after the existing full GPU wait)
once it has not uploaded for `RSX_TEX_UPLOAD_KEEP` frames (default 120);
animated and streamed textures keep theirs while they change, and a later
re-upload recreates it. `RSX_TEX_UPLOAD_KEEP=0` keeps every buffer. F8 reports
live staging MiB, resident count/cap and recipe use marks.

### Audio thread polled the default device

Since Phase 77 the mixer thread asked Windows for the default endpoint every
500 ms, a cross-process call on the pacing thread. It now registers an
`IMMNotificationClient`; with a stream open it queries only after a reported
default/state/add/remove change. With no stream (no device, failed open) it
still retries every 500 ms, and it polls as before if registration fails.
`AUDIO_HOTPLUG_POLL=1` restores polling. Underrun counts were not re-measured.

### Smaller items

- The SPURS argument comment now records the conflicting LittleBigPlanet note
  the Phase 92 change deleted (the new layout is the hardware one).
- AGENTS.md's ps3recomp file counts were stale (62 and 58; 63 now).
- The review's "unused `by_hand`" was wrong: it still gates the missing-root
  message box. Left unchanged.

### Validation

- `scripts/test/pso_async.py` (WARP): the five existing checks plus two new
  ones, race loading cancelling an active startup pass, and maintenance pruning
  a 20-day-unused recipe and bytecode, dropping dangling/duplicate index entries
  and ordering newest-first. All seven pass.
- `scripts/test/shader_warmup.py` (real exe, copied records): blocking 3/0 and
  2/2; background 4/0 (menu, then race set with one reuse) and 3/1; the
  background damaged case asserts the invalid recipe was never scanned.
- `scripts/test/hotplug.ps1`: controller cases, plus WASAPI cases with new
  notification checks (no endpoint query while streaming until a change; a
  capture-side change is ignored). The real mixer thread registered without
  falling back to polling. `debug_export.ps1` (all cases) and the F1 page pass.
- 1080p/2x HSR races with preload on, private memory sampled every 2 s
  (`scratch/pv/fix100-*`). Old behaviour restored by switches (`fix100-old`):
  startup 36.7 s, 880 rejected over the cap; mean/peak private 3589/3907 MB.
  New defaults repeated after the cache caught up (`fix100-new2`): startup
  9.3 s, 0 rejected, race gate 2586 ready; mean/peak 3324/3541 MB. Both 51 FPS
  medians. The first new run (`fix100-new`, 37 FPS) learned 665 new 1080p race
  states mid-race, which the later runs then had prepared; those FPS medians
  are not controlled benchmarks. The race shots render normally.

## Phases 99 and earlier

In [progress-archive.md](progress-archive.md) (moved unchanged on 2026-11-06, Phase 226).
