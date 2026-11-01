# Tourline Prologue v0.2.1

Optional shader preparation now reads the game folder already configured for
play. A separate GT.VOL extraction or second asset copy is no longer required
for the supported BCUS98158 v03.00 disc build.

- New preparation window matches the in-game PC Settings menu. Its title is
  **Tourline Prologue**, with real per-step status, cancellation and verified
  resume. `GT5P_PREPARE_UI=0` restores the Windows dialog.
- The starter expands to **2,892 observed pipeline records**, adding verified
  Fuji Speedway F candidates to the existing menu/High Speed Ring/Daytona set.
  Both shader stages and native pipeline keys are verified locally.
- Preparation can reuse verified shaders and driver hints from the previously
  selected cache when templates or helper generations change. Every native
  pipeline is still recreated and checked. `GT5P_PREPARE_REUSE=0` disables reuse.
- Native checksum acceleration reduces repeated verification overhead, with a
  Python fallback. `GT5P_PREPARE_NATIVE_HASH=0` selects the fallback.
- Packed game reads are bounded and verified against the supported game files.
  The legacy `--prepare-assets <folder>` path remains available.

Extract the complete ZIP into its own folder, close the game and launch
**tourline-prologue.exe**. Existing selected storage, saves and settings remain
compatible. After ordinary setup, run **Prepare shaders.cmd** if you want
preparation. Cancellation keeps completed work; repeat the same option to resume.
Only successful verified preparation changes the selected cache.

Preparation remains experimental and optional. It may take several minutes and
uses additional local disk space. The starter covers observed routes and
supported renderer settings, not every car, track section, camera or pass.
Uncovered pipelines and different settings continue through normal demand
compilation. Consistent gameplay stutter reduction has not been established.

Use `tourline-prologue.exe --no-prepared` to launch with the ordinary cache
without deleting any cache. Keep previous installation folders for binary
rollback. The package contains no game data, executable dump, keys, raw shaders
or game-derived cache contents. Shader bytes, generated source and GPU binaries
stay on the user's machine. Your own supported game files are required.
