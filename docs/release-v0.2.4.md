# Tourline Prologue v0.2.4

This update greatly widens optional shader preparation, makes it cheaper to
compile, and fixes a dealership loading freeze and analog trigger pressure.

**Run preparation again after updating.** The renderer's generated shader text
changed, and that text is the cache key, so shaders prepared with v0.2.3 are not
reused. Your old cache is left in place but goes unused; normal launching still
works without preparation.

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

  End-to-end preparation of the full v0.2.4 starter plus enumeration on a
  fresh cache has not been measured on the final build. Expect it to take
  longer than v0.2.3's preparation, because it covers far more.
- **Template format 3:** pipeline templates now store only shader and state
  inputs, so future renderer changes no longer need the starter re-issued.
  Older helpers cannot read format 3; keep the launcher, runtime and helper
  from the same ZIP together.

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
