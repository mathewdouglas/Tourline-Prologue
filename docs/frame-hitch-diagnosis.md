# Frame-level hitch diagnosis

The two targets are the first close/reflected car LOD (especially in the mirror)
and the camera handoff from rolling start to gameplay. Treat them independently.
Prepared keys and five-second PSO summaries cannot identify their critical paths.

`patches/ps3recomp-frame-hitch-trace.patch` is a separate developer diagnostic
overlay for the Phase 192 provenance runtime, after its normal compatibility and
coverage patches. Apply/build only in a private runtime/output. It is not part of
the packaged renderer or preparation compatibility contract. Set
`RSX_HITCH_LOG=<fresh-ASCII-output.csv>` to enable it; unset, empty or `=0` is the
rollback. Existing output is refused. It neither waits for new pipelines nor
changes async draws, warmup membership, queue priority or cache contents.

The trace writes at most 32,768 batch rows, with a 64 KiB stdio buffer and a flush
every 120 rows. It enables existing PERF probes, suppressing their periodic text
and counter resets while tracing. This has measurement overhead: compare runs
with the same instrumentation. It logs no shader source, programs, texture bytes
or per-draw lines. Keep all trace files and screenshots private/ignored.

Rows distinguish offscreen batches from display batches and carry precise Unix
and monotonic QPC timestamps, total replay time, Present time, foreground state,
previous GPU timing and cumulative render-stage/counter snapshots. Render stages
overlap: texture handling is inside SRV/prepass work, and prepass is inside replay.
VS/constants/vertex recording can run concurrently with replay. Do not add these
times or call the remaining interval guest CPU time. Driver and compiler counters
include asynchronous completions during the interval; they do not measure a
frame's blocking driver/compile time.

Successful DXBC file-read timing includes allocation and memory-cache insertion.
It excludes failed opens, shader packs, native driver-blob reads, cache writes and
guest filesystem work. Texture allocation timing covers the uploader's default/
staging resource block; texture decode timing covers its ordinary 2D/cube decode,
excluding the separate volume/mip paths. Upload counts/bytes are source work,
not measured PCIe bandwidth or proof of GPU-copy completion. Allocation counts
are calls/attempts, including a failed creation if one occurs. Additional counters split replacement hashing,
upload-resource Map, copy/barrier command recording and uploader SRV creation.
They do not include guest model streaming. Unknown streaming/model work remains
unknown. Recording-thread stage snapshots can straddle adjacent replay batches.

Run the existing private HSR route with `-IntroShots -FrameTest -SampleDelay 0`
and explicit engine/game/output/cache paths. `-RequireForeground` activates the
owned game at the grid and rejects loss of foreground during intro/sampling.
The backend trace independently records foreground for every batch. The script
now writes `<tag>.shots.json` with the actual start/end of each PrintWindow/PNG
operation; one-second sleeps are not exact screenshot timestamps. Screenshot
overlaps must be flagged, and a shot is only a rendering sample.

```powershell
# The command must synchronously join all its children, including cleanup.
powershell -NoProfile -File scripts/test/isolated_validation.ps1 `
  powershell -NoProfile -File <private-owned-route.ps1>

python scripts/diag/frame_hitches.py <backend.csv> `
  --window <tag.window.json> --shots <tag.shots.json> `
  --output <new-analysis.json>
```

The validation wrapper owns `Local\Tourline-Prologue-Isolated-Validation`, fails
immediately if busy, preflights existing game/preparation/launcher processes and
releases only its own handle in `finally`. An abandoned mutex can be acquired;
process preflight still applies. Never terminate another thread's processes.

The analyzer joins offscreen batches into subsequent display intervals, validates
finite/monotonic clocks and cumulative counters, and flags foreground/shot
overlaps. It rejects malformed/truncated rows by default. If owned-process cleanup
killed a buffered writer, `--allow-incomplete-tail` explicitly drops only the final
unterminated row and reports the discarded byte count. It never repairs interior
rows. A complete prefix is useful timing evidence but is not a final coverage
snapshot, successful shutdown proof or complete-session counter total.

## Texture and race-prewarm hitch fixes (default since Phase 221)

Phase 221 folded three changes into the main runtime patch and made them the default.
The earlier separate overlays (`ps3recomp-texture-slot-lru.patch`, and the Phase 221
`ps3recomp-texture-alloc-pool.patch` experiment) are removed. Each keeps a rollback switch:

| Switch | Default | Rollback | What it does |
| --- | --- | --- | --- |
| `RSX_TEX_LRU` | on | `=0` | When the 1,024 texture slots are full, evict the least recently used unreferenced slot instead of the first unused one. Empty slots still win, exact dirty/replacement hits reuse their own slot, a slot used by this batch is never evicted. |
| `RSX_TEX_POOL` | on | `=0` | A texture evicted because its slot changes shape is parked (at most 512 entries / `RSX_TEX_POOL_MB`, default 256) and reused by a later texture with the identical resource description. Staging data goes through one persistently mapped upload buffer (`RSX_TEX_RING_MB`, default 64, `0` off) reset after the per-batch GPU drain, instead of a new committed upload buffer per texture; an upload that does not fit uses the old per-slot buffer. `[tex-pool]` stats every 5 s. |
| `RSX_RACE_PREWARM_THREADS` | 4 | `=1` | The race prewarm reads the race index once and prepares it on n below-normal helper threads (2..8); the pso-worker keeps serving demand jobs. `[race-prewarm] finished ... threads=n` and a per-stage split (recipe/bytecode/driver-blob reads, driver call). |
| `RSX_PSO_FAST_LOOKUP` | on | `=0` | Persistent map from a session-independent draw key to the native pipeline hash (`warmup-v1/fp-lookup-v1.bin`, epoch-tagged); a first-in-process miss whose pipeline is resident skips HLSL/DXBC rebuilding. |
| `RSX_TEX_PLACED` | on | `=0` | Textures are placed in 64 MB pre-made default heaps (first fit, coalescing; `RSX_TEX_HEAP_MB`, `RSX_TEX_HEAP_MAX`, `RSX_TEX_HEAP_PRE`) instead of one committed resource each. |

Why: each new texture upload made two committed resources (texture plus its own staging
buffer), about 1 ms together, so a frame where about 190 textures appear for the first time
(race start, the +7 s camera change) spent 150-200 ms in `CreateCommittedResource`. The race
prewarm (on by default for players) prepared about 4,000 learned race pipelines one at a time;
each costs about 15 ms of small-file reads (recipe, bytecode, driver blob in directories of
16k-39k files), so it took 66-69 s, the 30 s loading gate timed out and the race started while
it was still filling (about 1,000 draws then waited for pipelines).

`scripts/test/texture_slot_policy_native.py --runtime <tree>` still compiles the production
slot-selection loop and checks both modes. Evidence and limits: progress.md Phase 221.

## Bounded texture eviction experiment (historical, Phase 199)

The text below describes the Phase 199 overlay before it became the default in Phase 221.

`patches/ps3recomp-texture-slot-lru.patch` is a separate, default-off runtime
experiment. `RSX_TEX_LRU=1` selects the least recently used slot among textures
not referenced by the current batch. Unset/`=0` restores first-unused eviction.
Empty slots still win; exact dirty/replacement-generation hits reuse their own
slot; a slot already used by this batch cannot be evicted. Source checksums,
shape identity, per-frame ownership, descriptor capacity, GPU waits and upload
retention stay in the existing paths. No new worker or resource slot is added.

The hypothesis is narrower than prewarming all car models: first-unused eviction
can replace recently useful textures while older menu/scene resources remain,
causing more allocation/upload work as a new close-car working set arrives.
Recency cannot eliminate genuine first uploads or a working set larger than the
existing cap. It can change resident byte sizes within that cap; measure memory
and rendering as well as allocation counts. Keep it explicit until broader
acceptance supports a default change.

`scripts/test/texture_slot_policy_native.py --runtime <private-runtime>` compiles
the actual production selection loop with fake resource handles. It checks both
modes, same-batch protection/exhaustion, empty preference, hit recency, dirty and
replacement-generation handling, incompatible shapes and deterministic ties.
This checks selection semantics, not GPU lifetime or final rendering. Live routes
and window-only screenshot inspection remain necessary.
