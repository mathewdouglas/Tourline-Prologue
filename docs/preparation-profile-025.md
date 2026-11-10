# Fresh 0.2.5 test-build preparation profile

Measured 2026-11-10, at the user's request, with the extracted
`tourline-prologue-v0.2.5-test-d989d9c-windows-x64` package. This profiles that
package, rather than rebuilding or substituting the current branch's engine.

## Setup and result

The packaged engine and helper hashes match `release.ini`:

- Engine: `6d2e3a3e554869c7b861a1fcb2eb8677dc30099f1b0057db47b320c0172bdcf0`.
- Helper: `b9bdc5a262b9728c48c823ef8fa65bceae14a0aa05beb110689d21f193eb7077`.

The frozen helper runs under `run_locked.py`, with a new private storage directory,
`--no-reuse`, copied ELF and copied player settings. Settings are 1080p, 21:9,
8x MSAA, smooth colour on and anisotropy 16. Compiler selection is unset, using
the package's DXC default. Profiling uses `GT5P_PREPARE_SHADER_PROFILE=1`,
`GT5P_PREPARE_NATIVE_PROFILE=1` and `PS3_VERBOSE=0`. Cleanup offers are disabled
for this diagnostic. No gameplay runs alongside it, and no real player cache,
selection or save is used or changed. The original settings file's hash is
unchanged after the run.

Hardware: NVIDIA RTX 4060, 12 logical CPU processors. The default-template vertex
pass and enumeration use 10 compiler workers. The additional ultrawide vertex
pass uses two workers, as specified by that translation path in this build.

**Exit 0, 978.308 seconds wall (16 minutes 18 seconds).** Default native preparation
and ultrawide preparation each pass 12,669 requests with
`native_counts = [12669,12669,12669,0]`. Catalogue enumeration prepares
24,522/24,522, zero failures and zero reused jobs. MSAA mapping covers 6,497
source rows and creates 5,840 distinct pipelines, with
`native_counts = [5840,5840,5840,0]`. Selection is published only in the private
storage. The interpreter stage is skipped: this exact engine reports no
interpreter-class preparation support; its inspection costs about three seconds.

This is a fresh **application** cache, not a cleared Windows/driver cache or a
machine-cold boot. Output is on the worktree's drive. These are one-run diagnostic
timings with profiling enabled, not a controlled speed comparison or a promised
speedup on another PC.

## Wall-time breakdown

Status is sampled every 0.1 seconds. The following groups partition the whole
run without double-counting. They are approximate stage boundaries, not separate
CPU measurements. The helper sometimes leaves its previous `Complete` status
visible during subsequent setup work; that interval is included in setup below.

| Group | Seconds |
| --- | ---: |
| Native pipeline creation, persistence and process overhead, all three passes | 245.7 |
| Default and ultrawide template fragment passes | 200.1 |
| Verification/finalization, including fresh-process native lookup | 172.2 |
| Catalogue shader batches, excluding separately counted asset reads | 145.1 |
| Native input generation, initial metadata and between-stage setup | 105.8 |
| Asset lookup, archive verification and reads across the stages | 82.3 |
| Default and ultrawide template vertex passes | 24.3 |
| Interpreter-stage inspection, then skipped | 2.8 |
| **Total** | **978.3** |

Detailed sampled intervals include default native creation 66.7 s, ultrawide
native creation 145.3 s, MSAA native creation 33.7 s, default fresh-process lookup
22.8 s, ultrawide verification/finalization 63.6 s and MSAA verification/finalization
82.6 s. The latter labels cover subsequent work until the next status update,
including final table/membership/pack work; do not attribute their full duration
to a single checksum or directory scan without finer instrumentation.

The enumeration report measures 164.76 s including its asset lookup;
`compile_seconds` is 136.69 s. The complete MSAA report measures 162.25 s, including
input generation, native creation and its persistence check.

## What the internal counters show

Each template fragment pass launches 30 engine processes for 7,354 unique
requests, using 256-request batches. The two passes together spend 185.25 s
inside their child-process lifetimes, but only 55.23 s inside the instrumented
shader batches. **130.02 s is outside those batches**, including engine/device
startup and shutdown and other process-level work. This is not all OS process
creation time. Fragment worker compiler-call durations sum to 483.43 s across
parallel workers; that sum must not be added to wall time.

Native creation counters, excluding the separate lookup-validation pass:

| Pass | Driver calls, s | Blob persistence, s | Recipe persistence, s |
| --- | ---: | ---: | ---: |
| Default | 11.66 | 23.75 | 18.28 |
| Ultrawide | 74.09 | 24.92 | 24.48 |
| MSAA 8x | 5.38 | 11.10 | 10.45 |
| **Total** | **91.13** | **59.78** | **53.21** |

Persistence totals **112.98 s**. Driver work is important for the ultrawide pass,
but is not the only native-stage cost. The shared bytecode transport is active:
native batches report zero individual code reads and use their memory/bundle
hits. Reimplementing that optimization would not address this run's bottleneck.
The report's checksum statistics use the native backend, with zero Python
fallback calls; those statistics are captured before the final MSAA stage and
must not be presented as a complete-run checksum total.

## Next work suggested by this profile

1. Keep the fragment-preparation engine alive between bounded batches, or group
   launches while retaining the current sub-batch checkpoints and cancellation
   behavior. The measured 130 s outside the two template passes' shader batches
   makes this a stronger first target than increasing compiler-worker counts.
2. Batch durable native-cache persistence and investigate bounded parallel native
   creation, keeping per-entry checksums, GPU/driver validation and crash-safe
   publication. Persistence accounts for 113 s; driver calls account for 91 s.
   These are measured costs, not guaranteed removable time.
3. Instrument verification/finalization more finely. Avoid repeated validation of
   unchanged files within one exclusively owned preparation when equivalent proof
   can be retained, while still checking every new persisted result and keeping
   the independent fresh-process lookup. Do not simply remove validation.
4. Reuse verified original program bytes across the default, translated and
   enumeration stages within the same bounded read session. Asset work totals
   82 s here; archive/ELF identity and change detection must remain intact.
5. Let the additional ultrawide vertex pass use the same bounded auto-worker
   policy as the other paths. It currently uses two workers, but its entire
   17.4 s wall interval is only a small part of the full preparation.

No performance implementation or player default is changed by this profiling
work. Before/after acceptance should use another fresh private cache, the same
package/settings and equivalent validation, with driver-cache history stated.

Private evidence is under `scratch/p235`: `run.json`, `validation.json`,
`timeline.json`, `report.json`, `summary.json`, `helper.out`, `helper.err`,
`interp-pipelines.json` and `profile.html`. Native/fragment logs remain inside
the private generation named by `validation.json`. The analysis checks that
all main-stage counts succeeded before producing its summary.
