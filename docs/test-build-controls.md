# Controls polish test build

Current local Windows x64 test ZIP from `feature/controls-polish`, head
`79ecafc80a0ce6c8f545a7d02ecc330d40517082`. No main merge, tag or release.

Artifact (ignored):
`scratch/controls/test-build-79ecafc-final/tourline-prologue-v0.2.5-controls-test-79ecafc-windows-x64.zip`

Size: 103,903,698 bytes; 309 files.
SHA-256: `74d8c47d5280b305ac99968095350e75712b723f85caccb818678344f17e9c00`.
Engine SHA-256: `c97b9005cf4226f44e4d947dfa0ec36ac79c70db3d85ee8bead610fa9936acfd`.

Extract the entire ZIP into a fresh folder and run **tourline-prologue.exe**.
This build adds the vibration follow-up on top of the native modern-controls link:
the 128-byte capability response, Bluetooth enhanced reports when feedback is
enabled, and F1 **Test controller vibration**. A Bluetooth DualSense player felt
two probe pulses. The F1 button logged `low=24576 high=24576 result=0 test=1`.
Race strength and timing still need a play test. Turn on the game's Vibration
Function as well, then Restart after enabling SDL controller vibration.

Packaging used the locked wrapper. The verified 0.2.5 launcher, helper, DLLs,
assets and licenses are retained. The engine and manifest are replaced, and
`release.ini` carries the new engine digest. Base SHA-256, ZIP CRC, unique
paths, every payload hash, release engine/helper hashes and all 70 helper
manifest files pass. The 15-setting manifest passes. No game data, settings,
saves or caches are included. Evidence is `validation.json` beside the ZIP.

The `1c7cb3e` ZIP below predates the vibration fixes.

## Previous native-mapping package

Updated local Windows x64 test ZIP from `feature/controls-polish`, implementation
head `1c7cb3e4bfddeca0b9d6bd4417a2804a4634a018`. No main merge, tag or release.

Artifact (ignored):
`scratch/controls/test-build-1c7cb3e-final/tourline-prologue-v0.2.5-controls-test-1c7cb3e-windows-x64.zip`

Size: 103,900,219 bytes; 309 files.
SHA-256: `c7c452b7517bf8b745e95f4e31fe61a6ac4750619401a23fad499a9902eb6ac0`.
Engine SHA-256: `d2a0520c78598220ea2235f2b0ef5d182fb902fabcbb58cbbcac22ac0284858c`.

Extract the **entire ZIP into a fresh folder** and run **tourline-prologue.exe**.
F1 > Controls > Modern controls applies live after profile load:

- **Yes:** R2 accelerate, L2 brake, Cross gear up, Square gear down.
- **No:** restore Cross accelerate, Square brake, R2 gear up, L2 gear down.

The option follows the game's actual player-one SIXAXIS mapping, including changes
made in Options. Custom layouts show No; explicitly choosing No restores these
four defaults. Other bindings and player two stay unchanged. Use the game's normal
Save to retain assignments. A PC settings observation never forces an old mapping
at boot. Modern controls is in F1; its old static RecompLauncher toggle is removed.

Response/dead-zone and optional Feedback settings still require Restart. Feedback
defaults Off. `GT5P_NATIVE_CONTROLS=0` disables the native mapping link without
changing assignments; `PAD_CONTROLS_POLISH=0` disables all controls additions.

Native mapping safety tests, 16,128 response cases, 255 guest pressure packets,
virtual hotplug, parser/manifest and clean pinned-patch checks pass. Real-game F1,
in-game assignment edits, explicit defaults and game Save/reload pass. No new
physical driving or tactile acceptance is claimed. SDL2 remains; SDL3 is deferred.
See [controls-polish.md](controls-polish.md) for evidence and remaining device gaps.

Packaging ran under the required machine-wide lock. The verified
[0.2.5 base package](test-build-025-background.md) launcher/helper/DLLs/assets/licenses
are retained; the engine and manifest are replaced, release.ini's engine digest
updated, and TEST-CONTROLS.txt added. Base SHA-256, ZIP CRC, unique paths, every
payload hash, release engine/helper hashes and all 70 helper-manifest files pass.
The 15-setting / 18-key manifest passes separately. No game data, player settings,
saves or caches are included. The unchanged frozen helper's offline preparation
was not repeated for this input-only update. Existing caches are retained; the
engine change may require a new preparation generation.

The previous `8dc4b54` ZIP remains available under
`scratch/controls/test-build-8dc4b54-final/` for comparison. Its host-only preset is
superseded by this native mapping link. Packaging evidence and the local script
are under `scratch/controls/native-mapping` and the artifact's `validation.json`.
