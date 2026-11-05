# Player hitch attribution

This investigation uses `ab77487` (12,669 starter records, fragment sample
sharing and preparation enumeration on, interpreter fallback off). It measures
one machine/save/scripted route per condition. It does not establish whole-game,
multi-GPU or randomized causal acceptance.

## Method and denominators

The machine is an i5-12400F (12 logical processors), RTX 4060, driver
32.0.16.1088. All game runs use 1080p/16:9, 2x MSAA, default SSAA, VSync,
normal async shader/PSO policy, `PS3_VERBOSE=0`, `GT5P_NO_SETTINGS=1` and
`FS_HIDE=grim/file/contents`. Interpreter fallback is explicitly off.

Cold means an empty **application** cache. OS and NVIDIA driver caches are
preserved and uncontrolled. Prepared means current source-helper template,
native verification, menu/race shader packs and default shader enumeration.
Warm means a second process using that route's post-play prepared cache.
It does not mean every possible driver object was already resident.

A private backend is compiled from upstream plus the current main patch, then
`patches/ps3recomp-frame-hitch-trace.patch`. The overlay remains separate and
default-off (`RSX_HITCH_LOG=<fresh ASCII CSV>`; unset/empty/`0` disables it).
The private engine links only this object and the current present-thread object
ahead of the read-only reference objects. No main patch, player default,
starter, tag or release is changed.

`GT5P_HITCH_HOST_LOG=<fresh CSV>` independently enables bounded host submission
stage snapshots (unset/empty/`0` off). The backend trace now includes exact
D3DCompile/guest-PSO/DXBC-read elapsed time **on the replay thread**, separate
aggregate compiler/driver work across threads, and pending vertex/fragment-or-PSO
replay omissions plus recording-time vertex omissions. An omission is a draw
count, never an invented duration. The sync timers cover their instrumented
cached-compile/guest-pipeline paths, not every built-in renderer shader.

All tests, builds, links, preparation resumes and game routes use
`C:\tmp\gt5p-testlock\run_locked.py`, with `tasklist` process preflight. Original
game/runtime/build directories stay read-only. Saves and ELF are copied into
private roots; the original disc folder is a read-only VFS input. No junctions
are created for game data. Owned game processes are joined in cleanup.

The analyzer joins offscreen batches to the next display batch. Tables include
intervals strictly greater than 20 and 50 ms. These are rendered display-batch
endpoints, not independently measured scanout. Dealership pages intentionally
run at about 30 FPS: most >20 ms intervals there are ordinary cadence, so their
excess is also measured against 33.367 ms. Races use 16.683 ms. The grid-to-end
window includes intended 30 FPS rolling-start frames; the standard FrameTest
sample begins 45 seconds after grid arrival and lasts 60 seconds.

Screenshot/PNG intervals and background intervals are excluded from primary
timing tables and counted separately. Images are rendering samples, not proof
that no omission occurred between shots. Both conditions use the same probes;
measurement overhead remains. Cancellation can leave a killed writer's final
unterminated row: only explicit `--allow-incomplete-tail` drops that row and
records the discarded byte count. Interior corruption and counter resets reject.

## What the accounting can establish

The ranked wall partitions sum to long-interval wall time, **not** to causal
excess above the frame budget. Texture handling includes lookup, allocation,
decode and upload command recording. Allocation/decode/etc. subcounters are
contained in that time and must not be added again. Pipeline lookup includes
translation, file checks, queueing and cache lookup; direct replay-thread compile,
driver creation and successful DXBC reads are broken out. Other prepass excludes
its nested texture/SRV/PSO stages. GPU fence waiting, Present and remaining replay
are separate. Stage-snapshot overlap/clipping is reported explicitly.

Outside replay is an unresolved mixture of command production, guest PPU/SPU
work, recording, waits, scheduling, file/model streaming and pacing. It is not
measured guest CPU. The separate host ledger distinguishes FIFO wall/estimated
CPU, submission, FIFO-kick idle waits, pump, vblank/flip calls and residual host
time. It runs concurrently with replay and must not be added to that ledger.
Idle includes normal cadence; it does not independently prove a FIFO starvation
bug. Guest PPU/SPU critical-path attribution needs further producer instrumentation.

Background D3DCompile and driver-creation totals can exceed one frame's wall
time. They are reported as correlations, not assigned milliseconds of a hitch.
They may cause CPU/driver contention, which these probes do not isolate. A
previous-batch GPU timestamp is likewise a useful signal, not proof that the
current interval is GPU bound. Pack/native-blob/guest-file reads and exact texture
eviction-versus-first-upload causes remain distinct unmeasured questions.

## Reproduction

Use a VS x64 environment for the build. Every command below needs the common
`python C:\tmp\gt5p-testlock\run_locked.py --label <name> --` prefix. Check
`tasklist /FI "IMAGENAME eq gt5p.exe"` before each run; never stop another agent's
game. Repository Python is `.venv\Scripts\python.exe`.

```text
python scripts/test/hitch_private_build.py
python scripts/test/hitch_attribution.py
python scripts/test/hitch_capture.py dealer cold
python scripts/test/hitch_capture.py hsr cold
python scripts/test/hitch_capture.py daytona cold
python scripts/test/hitch_prepare.py --budget 120
# Resume the preceding command, one locked invocation at a time, until code 0.
python scripts/test/hitch_capture.py <dealer|hsr|daytona> prepared
python scripts/test/hitch_capture.py <dealer|hsr|daytona> warm
```

Example read-only analysis (fresh output filename):

```text
python scripts/diag/hitch_attribution.py <tag>.trace.csv --host <tag>.host.csv --window <tag>.window.json --shots <tag>.shots.json --period sample --allow-incomplete-tail --output <tag>.analysis.json
```

Use `--period grid` for the introduction plus sample; use
`--budget-ms 33.3667` for the dealership. `--include-contaminated` is diagnostic
only and must not silently replace the primary table.

A cold async run can omit most geometry while a prepared run draws it. Their
texture/GPU/replay workloads are then different: a faster incomplete frame is
not a rendering or performance win. Cache conditions are ordered observations,
not matched-frame ABBA trials. AI traffic and camera phase can differ despite
identical input schedules and save seeds.

## Initial cold dealership measurement

The three visits reach ACURA, ASTON MARTIN and BMW. The save fingerprint is
`9161393d2439d6104c34c54a352717cf5140106727c62a6cf675ee61ba2d5d02`;
the diagnostic engine SHA-256 is
`a13c500f0570a457ffdbc04d3bd9567d71820586c3540ef6d4dedd8d5a288f88`.
The application cache begins with zero DXBC files and ends with 410.

There are 2,456 accepted display intervals, zero background exclusions and
25 screenshot-overlap exclusions. The complete trace prefix stops 1.162 s before
the observed window end (87.469 s of accepted intervals); it is below the row cap. Median is 33.410 ms, p99 135.248 ms, maximum
344.485 ms. Stage clipping is zero. The 2,066 intervals >20 ms total 80.989 s,
with 13.061 s of excess above the 33.367 ms showroom budget. The 222 intervals
>50 ms total 17.838 s.

| Rank / measured wall category | >20 ms intervals: seconds / share | >50 ms intervals: seconds / share |
| --- | ---: | ---: |
| Outside replay (unresolved producer/pacing/recording/scheduling) | 65.297 / 80.6% | 13.561 / 76.0% |
| Other replay | 5.581 / 6.9% | 1.190 / 6.7% |
| Other prepass | 4.230 / 5.2% | 0.823 / 4.6% |
| Texture handling | 2.070 / 2.6% | 0.536 / 3.0% |
| Pipeline lookup excluding instrumented direct costs | 1.969 / 2.4% | 0.604 / 3.4% |
| Replay-thread successful DXBC file reads | 1.003 / 1.2% | 0.995 / 5.6% |
| Present call | 0.804 / 1.0% | 0.123 / 0.7% |
| GPU fence wait | 0.036 / <0.1% | 0.006 / <0.1% |
| Specialized compile on replay thread | 0 / 0% | 0 / 0% |
| Guest driver PSO creation on replay thread | 0 / 0% | 0 / 0% |

The >50 ms row ranking is outside replay, other replay, DXBC reads, other
prepass, pipeline lookup, texture handling, Present, GPU wait. These are wall
occupancy shares, not a proven division of the 10.430 s of excess in that set.
Background correlations for those same backend intervals are 271 compiler
completions / 115.093 s accumulated D3DCompile elapsed time, and 682 driver
calls / 2.282 s accumulated driver time. Neither can be added to the table.
Possible compiler/driver contention is not isolated by this observation.
Texture allocation accounts for 190.425 ms of the texture-handling time,
with 243 allocation attempts; decode is 2.384 ms. These are contained subcosts.

The separate host ledger has 231 submission intervals >50 ms totaling 18.142 s:
FIFO 5.371 s (estimated on-CPU 4.911 s, contained), FIFO-kick idle 12.326 s,
submission 0.407 s, pump 0.006 s and residual host work/scheduling 0.032 s.
Vblank/flip calls on this thread are zero because the separate vblank thread
is active. Idle is not proof that guest CPU or SPU work caused the delay.
The host and backend interval sets differ and these totals are not additive.

In the accepted showroom intervals >20 ms, pending omissions are 315 replay vertex,
342,889 fragment-or-PSO and 619,394 recording-time vertex draws. The BMW +68 s
shot visibly lacks the foreground Concept 1 Series body panels. The ACURA
+20 s and ASTON MARTIN +40 s shots contain cars, wheels and floor reflections.
The BMW +78 s shot shows the foreground body panels recovered. This establishes
a visible missing-geometry problem separately from hitch time;
it does not prove every dark pixel is caused by a pending shader.

Evidence: `scratch/hitch/routes/dealer-cold/{context.json,analysis-v2.json,visual.json}`,
`dealer-cold.{trace.csv,host.csv,frames.csv,window.json,shots.json,out,err}` and
`route.log`. The private game copy was removed after the route.

The first HSR cold attempt is excluded: `race.ps1 -RequireForeground` rejected
focus moving to T3 Code during intro shot 7, before the FrameTest window.
Evidence stays in `scratch/hitch/routes/rejected-hsr-cold-focus/`; its game copy
and populated private cold cache were removed, so the retry starts empty.
No timing or cache-warmth result from that attempt enters the accepted tables.

The second HSR cold attempt is also excluded: foreground moved to T3 Code just
after `race000`, before a completed FrameTest. Evidence is under
`scratch/hitch/routes/rejected-hsr-cold-focus2/`; its cache/game copy are removed.
The user subsequently confirmed that the game can remain foreground for race
captures. Strict focus checks remain enabled.
