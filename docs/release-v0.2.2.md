# Tourline Prologue v0.2.2

Default-translation shader preparation now writes local menu and race bytecode
packs before those pipelines are first used. The runtime already loads this
pack format. 720p and 1080p at 16:9, including the first-run preset, use the
bundled observed plan. Higher resolutions and 21:9 keep the previous
preparation path and do not receive that plan.

One ordered High Speed Ring comparison, with the unpacked window first, showed
fewer long frames when packs were present. The race window moved from 37.7 to
49.4 frames per second, and the 99th percentile frame interval from 121.7 ms
to 44.1 ms. Shader compiles did not fall. The packed window also had warmer
operating-system and driver caches, so this is not a reversed-order proof and
not a promise that hitches are gone. The reported mirror reflection change is
still unexplained.

`RSX_SHADER_PACK=0` disables runtime pack use and keeps every cache file.
An existing unpacked preparation is left in place. The next default-translation
run uses a new generation and can import verified work from the previous one.

This release also includes preparation behavior that v0.2.1 did not publish:

- After the first successful file setup, the launcher offers **Prepare now**
  or **Skip and play**. Closing the offer skips preparation. The offer does
  not repeat on later launches. `GT5P_PREPARE_OFFER=0` disables it.
  **Prepare shaders.cmd** still prepares or resumes at any time.
- Saved settings choose the preparation translation. 21:9 adds ultrawide
  variants. 16:9 above 1080p adds scaled fragment variants. 720p and 1080p
  16:9 stay on the default set, which is the set that receives shader packs.
  `GT5P_PREPARE_TRANSLATION=default` keeps default-only preparation.
- Optional preparation compiles vertex shaders in bounded batches.
  `GT5P_PREPARE_VERTEX_BATCH=0` restores serial compilation.
- **Restart** on the in-game settings page exits the old game and lets the
  launcher start the replacement. `GT5P_LAUNCHER_RESTART=0` restores the
  previous path. Both the new launcher and the new engine are required.

Optional preparation still reads the game folder already configured for play.
No separate GT.VOL extract is required for BCUS98158 v03.00. The preparation
window matches the in-game PC Settings menu. The starter remains 2,892 observed
pipeline records. `GT5P_PREPARE_REUSE=0` disables reuse. `GT5P_PREPARE_NATIVE_HASH=0`
selects the Python checksum fallback. `GT5P_PREPARE_UI=0` restores the Windows
dialog.

Extract the complete ZIP into its own folder, close the game and launch
**tourline-prologue.exe**. Existing selected storage, saves and settings remain
compatible. Cancellation keeps completed work; repeat the same option to resume.
Only successful verified preparation changes the selected cache.

Preparation remains optional. It may take several minutes and uses additional
local disk space. The starter covers observed routes and supported renderer
settings, not every car, track section, camera or pass. Uncovered pipelines
and different settings continue through normal demand compilation.

Use `tourline-prologue.exe --no-prepared` to launch with the ordinary cache
without deleting any cache. Keep previous installation folders for binary
rollback. The package contains no game data, executable dump, keys, raw shaders
or game-derived cache contents. Shader bytes, generated source and GPU binaries
stay on the user's machine. Your own supported game files are required.
