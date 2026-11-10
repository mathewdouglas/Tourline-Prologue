# Controls polish test build (previous host-preset candidate)

This candidate predates the native mapping link described in [controls-polish.md](controls-polish.md).
It remains available for comparison; it does not implement the linked Yes/No option.

Local Windows x64 test ZIP built from `feature/controls-polish` implementation
head `8dc4b5423dba09d4322890882704bcf6cdf67bdb`. No tag or release.

Artifact (ignored):
`scratch/controls/test-build-8dc4b54-final/tourline-prologue-v0.2.5-controls-test-8dc4b54-windows-x64.zip`

Size: 103,896,746 bytes; 309 files.
SHA-256: `a4ba42935381738e2b0c43e5c187ae99fad0911c946ec8f780526651574a680f`.
Engine SHA-256: `3d991a9e3a1c128cdf67b8abe2d4a90b09bb9caf082042397cbaae17789409f6`.

This retains the verified [0.2.5 background preparation test package](test-build-025-background.md)
launcher, helper, DLLs, assets and licenses. It substitutes the privately relinked
controls engine and current RecompLauncher manifest, updates release.ini's engine
digest, and adds TEST-CONTROLS.txt. The frozen helper is byte-identical to the
verified base; no helper logic changed for input controls.

Packaging ran through the mandatory machine-wide lock. Base ZIP SHA-256 matched
the recorded value before reading it. ZIP CRC, duplicate paths, every copied or
replaced payload hash, release engine/helper digests, all 70 helper-manifest files,
and the 16-setting RecompLauncher manifest passed. No game data, player settings,
saves or caches are included. Evidence and the local packaging script are under
`scratch/controls`; native and game/F1 validation of this engine is recorded in
[controls-polish.md](controls-polish.md). This packaging pass did not repeat the
base package's offline preparation or physical driving acceptance.

Extract the entire ZIP into a fresh folder and run **tourline-prologue.exe**.
F1 > Controls provides response/dead-zone settings; F1 > Feedback provides optional
effects. Change the desired setting, then choose Restart. Keep Modern controls
Off if R2/L2 are already assigned in the game. That preset targets the standard
Cross-throttle / Square-brake layout. Feedback defaults Off; tactile acceptance
and Xbox hardware testing remain open. Existing caches are preserved, although
the changed engine may require a new preparation generation.
