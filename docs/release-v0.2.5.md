# Tourline Prologue v0.2.5

## Summary

Shader preparation now happens by itself while you play, shaders compile much
faster, and races hitch far less. Controllers get trigger tuning, a one-step
modern layout and optional feedback.

**New**

- **Background shader preparation:** with nothing prepared, the launcher
  prepares shaders beside the game at low priority, race shaders first. It
  pauses while you race and shows a small status in the corner.
- **Short "Prepare shaders":** the foreground step now prepares the menu and
  race set for your settings only, and the rest continues in the background.
  **Prepare all shaders.cmd** keeps the full preparation.
- **Faster shader compiler (DXC):** guest shaders are compiled with Microsoft's
  DirectX Shader Compiler instead of the older FXC.
- **Controls:** trigger dead zone and response curve, one-step modern controls
  (R2 accelerate, L2 brake), optional DualSense trigger resistance, optional
  trigger and body vibration, and a vibration test, all in F1.
- **RecompLauncher support:** a manifest lets RecompLauncher start the game and
  edit its settings.
- **Race loading bar** under the logo while race shaders load.

**Gains measured on the development PC** (High Speed Ring; one PC, one GPU)

- First race with nothing prepared, started straight away: time lost to long
  frames 11.2 s -> 3.2-3.9 s (with FXC, before the compiler change).
- Shader compile time for that race's 1,075 shaders: 85 s -> 32 s with DXC.
- Prepared cache, race start frame: 370-407 ms -> 113 ms.
- Prepared cache at 21:9 with 8x MSAA: time lost to long frames 3.7-4.5 s -> 0.6 s.
- Short preparation: 199 s against 978 s for the full one (1080p, 21:9, 8x).
- With eight busy background programs: 23.4 FPS -> 59.5 FPS in the frame test.

**Fixes**

- "Skip opening movie" now uses the game's own option instead of pressing a button.
- Controller vibration never reached the game (a capability reply of the wrong
  size); Bluetooth DualSense body vibration now works when enabled.
- A stop when F1 drew its Debug page.
- Multisampled pipelines are prepared at your own MSAA setting, not only 2x/4x.

**After updating**

- Shaders prepared by v0.2.4 are not reused: the compiler changed, and with it
  every shader key. The first launch offers preparation once; skipping it is
  fine, because background preparation then does the work while you play.
- Old caches are kept. After a successful full preparation the launcher offers
  to remove older ones and shows the space they use; the default is to keep them.

The rest of this page gives the detail, the switches that turn each change off,
and the limits of what was measured.

## Background preparation

When no completed preparation made by this release is selected, the launcher no
longer asks. It starts the preparation helper beside the game at idle priority.

1. **Race stage first.** The 2,113 race pipelines of the bundled plan are
   prepared and proven exactly as in a normal preparation. While that runs,
   each finished shader and driver file is copied into the cache the game is
   using, every few seconds, so a race started early already finds most shaders
   on disk. When the stage completes, the next race loading screen loads the
   whole set.
2. **Full stage.** The ordinary full preparation follows, reusing the race
   stage. It is selected only when it completes, so the next launch uses it.

- **Paused while racing.** The helper's processes are suspended from the race
  start (the grid preview's Start press, or 45 s after the loading screen) until
  you are back in a menu. Results and replays count as racing.
- **Status.** A small click-through status at the bottom left says *Preparing
  shaders in background*, *Paused during race*, then *Ready for your next
  launch*. A failure says *Background preparation incomplete*; you can keep
  playing.
- **Quitting** stops the helper at a checkpoint; the next launch carries on.
  A settings restart keeps it running.

Measured on an empty cache, High Speed Ring, 1080p, 2x MSAA, one run per case,
before the compiler change below:

| Case | Time lost to frames over 50 ms |
| --- | --- |
| No helper | 12.0-12.8 s |
| Helper, race started straight away | 3.2-3.9 s |
| Helper, about 90 s in the menus first | 3.0-3.6 s |
| Full preparation selected (next launch) | 0.36 s |

Switches: `GT5P_PREPARE_BACKGROUND=0` restores the one-time offer;
`GT5P_PREPARE_BACKGROUND_PAUSE=0` never pauses;
`GT5P_PREPARE_BACKGROUND_TRICKLE=0` copies only when the race stage is done;
`GT5P_RACE_SIGNAL_AT=loading` pauses from the loading screen;
`GT5P_PREPARE_BACKGROUND_INDICATOR=0` hides the status;
`GT5P_PREPARE_BACKGROUND_WORKERS=<2..12>` sets the compiler workers.
More: [player-setup.md](player-setup.md),
[background-preparation-status.md](background-preparation-status.md).

## Short preparation

**Prepare shaders** (the startup offer, `Prepare shaders.cmd` and F1 > Debug)
now prepares the observed menu and race set, 3,546 of the starter's 12,669
inputs, for your saved resolution, aspect and MSAA. It keeps every proof and the
cancel and resume behaviour.

- A fresh run at 1080p, 21:9, 8x MSAA took 199 s on the development PC; the full
  preparation took 978 s at the same settings.
- It covers less on purpose. Cars, dealerships and tracks outside the observed
  set still compile on first use, and the background helper continues with the
  full preparation on the next launch.
- **Prepare all shaders.cmd** runs the full preparation up front.
  `GT5P_PREPARE_QUICK=0` makes the foreground step full again.

More: [quick-preparation.md](quick-preparation.md).

## DXC shader compiler

Guest vertex and pixel shaders now compile with Microsoft's DirectX Shader
Compiler (v1.8.2502, shader model 6.0) in the game and in preparation. The two
DLLs ship in `runtime\` with their licenses in `licenses\`.

- **Compile time:** the 1,075 shaders one empty-cache High Speed Ring race
  compiles took 84.8 s with FXC and 32.1 s with DXC, single-threaded, with no
  failures. Worst single shader: 419 ms -> 122 ms.
- **In play, empty cache, no helper:** time lost to long frames 11.2-12.2 s ->
  6.6-6.8 s; frame test 56 -> 58-59 FPS.
- **Caches:** the compiler is part of every shader key, so FXC and DXC caches
  never mix. Existing FXC caches stay on disk.
- **Rollback:** `RSX_SHADER_COMPILER=fxc` (set it for the launcher, so the
  helper matches). Turning the shader interpreter on also keeps FXC.

Limits: checked in play on one PC with an NVIDIA RTX 4060. A synthetic GPU
comparison of both compilers on the game's shaders found small numeric
differences in last-bit arithmetic that exceed its strict threshold; no missing
or wrong surfaces were seen in play. Other GPU vendors are untested. If
something looks wrong, try the FXC rollback and report it.
More: [dxc-preparation.md](dxc-preparation.md).

## Fewer hitches

All on by default; each has a switch that restores the old behaviour.

- **Textures:** recently used textures are kept, and textures are created from
  a pool with a shared upload ring (`RSX_TEX_LRU=0`, `RSX_TEX_POOL=0`).
- **Race loading:** the known race pipelines are created on four threads inside
  the loading screen, 66-69 s -> 15-16 s, and read from one pack file
  (`RSX_RACE_PREWARM_THREADS=1`, `RSX_RACE_PREWARM_PACK=0`). A thin bar under
  the logo shows the wait (`GT5P_RACE_LOAD_BAR=0`).
- **Pipeline lookup:** a saved lookup table finds prepared pipelines without
  rebuilding their keys (`RSX_PSO_FAST_LOOKUP=0`).
- **Your MSAA setting:** preparation also creates the multisampled pipelines at
  the sample count in your settings (`GT5P_PREPARE_MSAA_MAP=0`). At 21:9 with
  8x MSAA: time lost to long frames 3.7-4.5 s -> 0.6 s, worst frame
  386-842 ms -> 161-170 ms.
- **Shader bundle:** shaders are read from one bundle file instead of one file
  each (5-6 ms per open). On a second launch at 21:9, 8x: frames over 100 ms
  23 -> 5, worst 985 -> 203 ms (`RSX_DXBC_BUNDLE=0`).
- **Process priority:** the game runs at above-normal priority. With eight busy
  background programs the frame test went from 23.4 FPS (worst 510 ms) to
  59.5 FPS (worst 72 ms) (`GT5P_PRIORITY_CLASS=normal`).

On a prepared cache at 1080p, 2x MSAA, High Speed Ring: race start frame
370-407 ms -> 113 ms, the camera change seven seconds later 299-317 ms ->
106 ms, and a 60 s frame test peaks at 28.9 ms.

Still there: one to two seconds of 30-80 ms frames right after a race starts
while the graphics driver raises its clock, and first-time texture creation.

## Controls

F1 has new **Controls** and **Feedback** pages. Existing settings files keep
their behaviour: linear triggers, no dead zone, no new effects.

- **Trigger dead zone and response** (0 to 20 percent; Linear, Gentle, Quick)
  for L2 and R2. Restart to apply.
- **Modern controls:** Yes sets R2 accelerate, L2 brake, Cross gear up and
  Square gear down in the game's own button assignments; No restores those four
  defaults. Other custom assignments are left alone.
- **DualSense trigger resistance** at a fixed strength, **trigger vibration**
  on supported controllers, and **SDL body vibration**. All three are off by
  default and need a restart.
- **Test controller vibration** in F1 > Feedback sends one short pulse.

For vibration in races, the game's own **Options > Hardware > Vibration
Settings > Vibration Function** must be On as well.

Limits: a Bluetooth DualSense was felt vibrating and the package was accepted
in play. The feel of DualSense trigger resistance and Xbox trigger vibration
has not had hands-on acceptance.
Switches: `PAD_CONTROLS_POLISH=0` turns all of it off; individual settings are
in [controls-polish.md](controls-polish.md) and
[controller-vibration.md](controller-vibration.md).

## Updating from v0.2.4

- **One-time preparation offer.** Even with background preparation on, a
  configured install is offered DXC preparation once
  (`GT5P_PREPARE_DXC_OFFER=0` to skip the question).
- **Old cache cleanup.** After a successful full preparation the launcher
  offers to remove older completed preparations, showing the space freed. Keep
  is the default. The selected cache, unfinished work, the ordinary cache and
  saves are never touched (`GT5P_PREPARE_CLEANUP=0`).
- Keep the launcher, `runtime\` and `preparation\` folders from one ZIP
  together.

## Other changes

- **Skip opening movie** now sets the game's own boot option, the same one as
  Misc > Other > Opening Movie (`GT5P_NATIVE_OPENING=0` presses Cross as before).
- **RecompLauncher:** `recomplauncher.json` beside the launcher lets
  RecompLauncher start the game and edit its settings. See
  [recomplauncher.md](recomplauncher.md). Not tested inside every
  RecompLauncher version.
- **Shader interpreter (still off by default):** its pipelines can be prepared
  ahead of use, and it limits its work by GPU time. On the development PC it
  did not change empty-cache hitching.

## Fixes

- **Controller vibration:** the game was told the controller had no vibration
  motors, because a capability reply was written at the wrong size. It now gets
  the correct reply.
- **Bluetooth DualSense:** body vibration needs enhanced reports, which are now
  requested when a feedback option is enabled.
- **F1 Debug page:** drawing a row with no environment name could stop the game.

## Known problems

- After returning to the main menu from a race, the menu scene can show flat
  bright yellow lights, black slabs can appear after the Race Mode page, and
  the replay can show overlaid frames with its controls missing. These are
  older than this release and are planned for v0.2.6.
- First use of cars, tracks and dealerships outside the prepared set still
  compiles shaders and can hitch.
- Dealership pages run at 22 to 30 FPS.

## Not in this release

Moved to v0.2.6: the render-target problems above, a texture-load warning, the
F1 entry for the shader interpreter, the keyboard beside a connected
controller, and faster CI builds.
