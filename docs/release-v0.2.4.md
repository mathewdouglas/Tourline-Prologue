# Tourline Prologue v0.2.4

This update greatly widens optional shader preparation, makes it cheaper to
compile, and fixes a dealership loading freeze and analog trigger pressure.

**Run preparation again after updating.** The renderer's generated shader text
changed, and that text is the cache key, so shaders prepared with v0.2.3 are not
reused. Your old cache is left in place but goes unused; normal launching still
works without preparation. The first launch of this version **offers** it once
(see [First-launch offer](#first-launch-offer)).

## Wider shader preparation

- The starter now has **12,669 verified pipelines across 3,446 programs**
  (v0.2.3: 5,669 across 1,881). The 7,000 additions come from a content sweep;
  every one passed fresh shader, native-pipeline and persistence checks.
- Preparation now also **enumerates the game's shader catalogue** from your own
  GT.VOL/ELF: about 22,300 fragment and 2,240 vertex compiles, independent of
  what anyone has played. `GT5P_PREPARE_ENUMERATE=0` skips this stage.
  - Expected gain: fewer shaders compiled during play. In one cold High Speed
    Ring start (720p, 2x MSAA), the first 20 seconds served about 950 shaders
    from the enumerated cache and compiled 205, against 375 compiles with an
    empty cache. Median frame rate in that window was 29 against 20 FPS, and
    the scene drew instead of showing a black view.
  - This is one route on one machine. Native driver pipelines are still created
    on first use, so it is not a zero-stutter claim.
  - Cost: roughly 220 MiB more disk.

## Cheaper shaders, faster preparation

- **Sample sharing:** single-sample and multisample variants of a fragment
  program now compile to one shader. Distinct pixel shaders in the starter fall
  from 6,965 to 3,592, and enumeration fragment jobs from 34,355 to 22,282.
- **Simpler shader text:** looped vertex fetch, right-sized fragment registers
  and lazy sRGB helpers produce the same shader output, checked bit for bit on
  the GPU for all 1,120 vertex programs, for less compiler work. In-game GPU
  time is unchanged within 5%.
- **Preparation pipeline:** compiler workers scale to the CPU (four on 8+
  logical processors), bundled bytecode replaces thousands of file reads, and
  verifying an existing cache falls from about 30 s to under 2 s.
- **Measured on this machine:**

  | Stage | Before | v0.2.4 |
  | --- | --- | --- |
  | Catalogue enumeration | 1,028 s | 262 s |
  | Full v0.2.3-sized (5,669-record) preparation | 731 s | 336 s |

- **End to end, measured:** one full fresh preparation of the shipped
  12,669-record starter plus enumeration, through the frozen helper on this
  machine (i5-12400F, 6 cores / 12 logical processors, so four compiler
  workers; original GT.VOL and ELF read in place; empty storage), took
  **579 s (9.7 minutes)** and about 0.96 GiB of disk:

  | Stage | Seconds |
  | --- | --- |
  | Start-up, game archive check, asset reads (before each of the two phases) | 49 |
  | Vertex shaders (627) | 23 |
  | Fragment shaders (12,669 records) | 124 |
  | Native pipelines (inputs, create, lookup, verify) | 127 |
  | Shader packs | 3 |
  | Catalogue enumeration (24,522 jobs) | 253 |
  | **Total** | **579** |

  A PC with fewer than eight logical processors uses two compiler workers
  (about 1.4 times as long on this machine in earlier measurements), and a slower
  CPU takes longer again; the launcher's estimate therefore says "about 10 to 20
  minutes" with eight or more logical processors and "about 20 to 40 minutes"
  with fewer. Only the first number was measured here; the others are scaled.
- **Template format 3:** pipeline templates now store only shader and state
  inputs, so future renderer changes no longer need the starter re-issued.
  Older helpers cannot read format 3; keep the launcher, runtime and helper
  from the same ZIP together.

## Shader preload is on by default, with its own indicator

- **Preload known shaders** (F1 > Shaders, `video.shader_warmup`) now defaults
  to **On** for a new settings file: while the game starts and the movie plays, the
  recorded menu pipelines (then the race set during loading) are prepared in the
  background. A settings file that already says `shader_warmup = false`
  (the v0.2.3 default wrote that line) keeps its value; switch it on in F1 or
  delete the line. `RSX_SHADER_WARMUP=0` still turns it off. The default applies
  through the settings file; a bare engine run with `GT5P_NO_SETTINGS=1` is
  unchanged.
- **"Compiling shaders" now means a draw is waiting.** Before, the badge also lit
  for the whole background preload, because the preload held the same busy count
  and its driver calls went through the same counter. The backend now counts
  preload work (startup warmup, the blocking scan, race preparation) apart.
  `RSX_SHADER_INDICATOR_LEGACY=1` restores the old combined counting.
- **"Loading shaders"** is a second, smaller and dimmer badge for that preload
  work, **off by default** (F1 > Game > Shader preload indicator,
  `video.preload_indicator`, `GT5P_PRELOAD_INDICATOR=1`). It sits in the same
  corner and never shows together with "Compiling shaders".

## First-launch offer

On the first launch of this version, **after** setup is complete and before the
game starts, the launcher offers optional shader preparation in the same styled
dialog the post-setup offer uses. It says what preparation does, that it is
optional and can reduce stutter, and the estimated time for your processor count
(see above). **Prepare now** runs the existing preparation window, with the same
cancel and resume behaviour; **Skip and play**, closing the dialog, cancelling or
a preparation failure all continue to the game. Either way the answer is recorded
in `prepare-offer-<version>.done` in the launcher's storage, so it is not asked
again for this version, and **F1 > Debug > Prepare shaders** and
**Prepare shaders.cmd** stay available.

- Fresh installs get this through the existing post-setup offer; the two never
  appear in one launch.
- Nothing is asked if a completed preparation made by this release is already
  selected (the helper's read-only `--check-selected`, which compares a
  fingerprint of engine, decoder and bundled inputs recorded when the selection
  was written). Shaders prepared by v0.2.3 do not count.
- `GT5P_PREPARE_OFFER=0` disables the offer; `--no-prepared` skips it for that
  launch without recording an answer.

## Fixes

- **Dealership logo freeze:** repeated dealership visits (often around the
  fifth, for example Mazda) could stop on the logo while audio continued. A
  Windows thread-join race left finished threads occupying the 64-slot guest
  thread table until no new thread could start. In a 315-second automated
  repeated-dealer run, the old build filled the table and the fixed build kept
  recycling threads. `PS3_PPU_JOIN_WAIT_HOST=0` restores the old behaviour.
- **Analog L2/R2:** with accelerate and brake assigned to R2/L2 in the game's
  own **Options > Change Button Assignments**, the triggers now give partial
  throttle and brake across their whole travel. Previously they jumped to 100%
  after about 9% of travel. `PAD_PRESS_FORCE_FULL=1` restores the old
  behaviour.

## Not in this release

- The shader interpreter fallback stays off. It cuts draws left out while
  shaders compile by about 97%, but has not improved worst-case frame times.
- Car, reflection and rolling-start camera hitches are not claimed solved.

## Install

Extract the complete ZIP into a separate folder and run
**tourline-prologue.exe**. Existing storage, saves and settings are kept. Use
your own supported BCUS98158 v03.00 disc files; no game data or shader or
driver cache is supplied. `tourline-prologue.exe --no-prepared` bypasses a
selected preparation.
