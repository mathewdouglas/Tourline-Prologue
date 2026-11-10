# Release roadmap to 1.0

High-level plan for Tourline Prologue releases from 0.2.5 to 1.0, agreed with
the maintainer on 2026-11-05. GT5 is a separate project and is out of scope here.
Each release has a theme, its main features, and an exit test that says when it
is done. Order follows dependencies: a smooth, stable D3D12 base first, then
hardware and platforms, then features that need high frame rates.

Detailed plans live beside this file:
- [plan-60fps.md](plan-60fps.md)
- [plan-vulkan.md](plan-vulkan.md)
- [plan-ultrawide.md](plan-ultrawide.md)
- [plan-input-glyphs.md](plan-input-glyphs.md)

Evidence for finished work goes in [progress.md](progress.md).

| Release | Theme | Headline |
| --- | --- | --- |
| 0.2.4 | Preparation | 12,669-pipeline starter, catalogue enumeration, freeze and trigger fixes |
| 0.2.5 | Polish | Hitches, render-target bugs, controls polish |
| 0.3.0 | Smooth | Locked 60 FPS, no compile stutter on a prepared install |
| 0.4.0 | Wheels | Steering wheels with force feedback, sim-rig telemetry |
| 0.5.0 | Vulkan | Vulkan backend on Windows at parity with D3D12 |
| 0.6.0 | Linux | Native Linux build, Steam Deck |
| 0.7.0 | Unlocked | Frame rate above 60, HDR, upscaling |
| 0.8.0 | VR | OpenXR cockpit view with head tracking |
| 0.9.x | Extras and freeze | Photo mode and smaller features, then release candidates |
| 1.0 | Complete | Full playthrough acceptance on every supported platform |

## 0.2.5 - Polish

- **Hitches:** finish hitch attribution (stopped at `3d8673d`). Then ship the
  measured fixes for car, reflection and rolling-start camera hitches, including
  texture retention (`RSX_TEX_LRU`) if the numbers hold.
  Status (Phase 221, branch `feature/hitch-texture-lru`, not merged): texture retention, a texture
  pool/staging ring, a 4-thread race prewarm and a persistent fast pipeline lookup are defaults in the main
  patch; High Speed Ring race-start frame 370-407 -> 113 ms on a prepared cache. Remaining: first-time
  texture creation and the first launch before the lookup table is learned.
  Phase 223: preparation also creates the multisampled pipelines at the player's MSAA count (driver only,
  shared shaders); 21:9 8x High Speed Ring excess 3.7-4.5 s -> 0.6 s, worst frame 386-842 -> 161-170 ms.
  Phase 225: background preparation is the launcher default when nothing current is prepared (no offer):
  race pipelines first, copied into the live cache (next race loading screen prepares them), helper paused
  during races, full preparation selected next launch. Empty-cache HSR first race with ~2.5 min of menus
  first: excess 10.5-11.1 s -> 3.5-4.5 s; straight to the race: unchanged (10.3 s), later races benefit.
  Phase 226: the race stage's finished shaders and blobs are copied in while it runs, and the helper pauses at
  the race start (grid preview Start press) instead of the loading screen: straight to the race 11.2 -> 3.2-3.9 s.
  Phase 231: DXC can also prepare the player cache and is packaged with pinned DLLs/notices. Phase 232 combines this work with the race-pack/loading bar and makes DXC the user-requested default
  (`RSX_SHADER_COMPILER=fxc` rollback). Synthetic GPU comparisons exceed the numeric threshold; fixed-frame
  and other-GPU rendering checks remain open. See [dxc-preparation.md](dxc-preparation.md).
  Phase 233 adds a one-time DXC migration offer and optional old-generation cleanup
  after successful preparation, with the recoverable size displayed and Keep as
  the default. Background completion defers cleanup to the next launch.
  Phase 235 makes foreground preparation a settings-focused menu/race step (3,546 inputs), with full
  preparation retained explicitly and in the background. Fresh 1080p/21:9/8x wall time is 199 s versus
  978 s for the full baseline on the dev PC; coverage is intentionally smaller. Old caches remain intact,
  and cleanup waits for full completion. See [quick-preparation.md](quick-preparation.md).
  Phase 236 adds a launcher-owned background status (Preparing / Paused during race), deferred
  completion notice and Ready for next launch state, with no engine/cache identity change.
  `GT5P_PREPARE_BACKGROUND_INDICATOR=0` hides the UI independently of work and race pausing.
- **Render-target lifetime:** one investigation into targets reused by address
  after a scene change:
  - the yellow menu glow after a race;
  - the black menu slabs after the Race Mode page;
  - the replay showing overlaid frames, and its missing controls.
- **Controls polish:**
  - trigger response curve and dead zone in F1;
  - one-step "modern controls" (R2/L2 driving);
  - DualSense adaptive triggers at a fixed resistance, through SDL;
  - Xbox trigger rumble.
  Development implementation on `feature/controls-polish`: F1 Controls/Feedback,
  settings-neutral trigger shaping, a standard-layout host preset, and opt-in SDL2
  fixed DualSense resistance / game-signal Xbox trigger vibration. SDL3 is deferred;
  a connected DualSense accepts enable/clear API requests, but tactile and driving acceptance remain open. Arbitrary custom game
  assignment rewriting remains open. See [controls-polish.md](controls-polish.md)
  for exact switches, native evidence and hardware/transport gaps.
- **Smaller items:**
  - texture-load warning indicator;
  - keyboard alongside a connected controller;
  - an opt-in F1 entry for the shader interpreter. Status: its pipelines are now prepared ahead of use
    (Phase 220, branch `feature/interp-pipeline-prep`, not merged): startup step plus a separate helper stage.
    Phase 224 adds that budget (GPU-time adaptive, `RSX_SHADER_INTERP_BUDGET`); on the dev PC empty-cache
    hitching is the same with the interpreter off, on or capped, so the F1 entry is a visual choice, not a smoothness one.
- **Build speed:** CI cache keyed on lifter inputs, plus a persistent Ninja
  directory.
- **Exit:** the listed bugs are fixed or explained, and there are no new hitch
  regressions on the reference routes.

## 0.3.0 - Smooth

- **Locked 60 FPS:** in races and dealerships at 1080p on the reference PC.
  Dealerships are limited by the SPU render jobs today (22-30 FPS); see
  plan-60fps.md.
- **No compile stutter:** on a prepared install. Enumerate native pipelines as
  well as shaders. Close the remaining coverage axes: sampler lanes, sRGB, other
  resolutions and MSAA modes.
- **Benchmark suite:** fixed routes covering menu, dealership and three tracks,
  cold and warm, with pass/fail frame-time thresholds (p99, % of frames over
  16.7 ms). These become the acceptance test for every later release.
- **Exit:** the suite passes on the reference PC. The README status changes from
  "partly playable" to "playable".

## 0.4.0 - Wheels

- **Wheel input:** support common USB wheels such as Logitech G29/G920/G923,
  Thrustmaster T-series and Fanatec in PC mode. Either present them to the game
  as the wheel it natively supports (Driving Force GT class), or map their axes
  to the game's steering input with full rotation range.
- **Force feedback:** translate the game's own force-feedback commands to the
  host wheel through SDL haptics or DirectInput. Add per-wheel strength and
  rotation settings in F1.
- **Pedals and shifter:** separate axes for throttle, brake and clutch. H-pattern
  shifter and handbrake buttons.
- **Telemetry output:** speed, RPM, gear, g-forces and slip, read from game
  memory, for SimHub, dashboards and motion rigs.
- **Exit:** at least three wheel families tested with force feedback, and a
  telemetry consumer shown working.

## 0.5.0 - Vulkan

- **Backend:** a Vulkan backend on Windows beside D3D12 (plan-vulkan.md).
  - Shaders: the same generated HLSL compiled to SPIR-V with DXC.
  - Same pipeline-key and preparation model, with a Vulkan pipeline cache.
- **Parity:** every rendering fix tracked by a D3D12 rollback switch has a
  Vulkan equivalent or a documented gap.
- **Exit:** the 0.3.0 benchmark suite passes on Vulkan within 10% of D3D12, with
  no visual differences on the reference routes. D3D12 stays the Windows default
  unless Vulkan is better.

## 0.6.0 - Linux

- **Native Linux build:**
  - runtime threading, file and timing layers ported from Win32;
  - SDL input and audio;
  - Vulkan only.
- **Launcher and preparation helper:** port both. Package as an AppImage or
  Flatpak.
- **Steam Deck:** verified, with controller-first defaults, 800p and 40/60 Hz
  presets, and suspend/resume.
- **Exit:** benchmark suite and full-feature checks pass on one desktop Linux
  distribution and on Steam Deck.

## 0.7.0 - Unlocked frame rate

- **Above 60 FPS:** the game simulates at a fixed rate, so frames above 60 need
  presentation decoupled from simulation. Either interpolate object and camera
  transforms between simulation ticks, or run the render path at display rate
  with extrapolated cameras. Physics and game logic stay at their native tick.
  This is the riskiest engineering item before VR; prototype it in 0.6.x.
- **Display options:**
  - 120/144/165 Hz;
  - VRR/G-Sync;
  - frame cap.
- **HDR output:** scRGB or HDR10 from the 16-bit render targets already in use.
- **Upscaling:** FSR, with DLSS optional, for 4K and high refresh.
- **Exit:** stable 120 FPS on the reference PC with correct game speed, and no
  physics or timing drift against the 60 FPS path.

## 0.8.0 - VR

- **OpenXR on D3D12 and Vulkan:**
  - stereo cockpit and bumper views from the race camera, with head tracking;
  - world scale from car dimensions;
  - menus on a virtual screen.
- **Requires 0.7.0:** headsets need a steady 90 Hz or more.
- **Comfort:**
  - recentre;
  - horizon lock option;
  - menus out of the stereo path.
- **Exit:** a full race in VR at headset refresh on the reference PC and one
  standalone-tethered headset, with no stereo artefacts in the cockpit.

## 0.9.x - Extras and feature freeze

- **Candidate extras, chosen by demand:**
  - photo mode and free camera;
  - replay export to video;
  - triple-monitor surround (the ultrawide work generalised);
  - HUD scale and position;
  - higher-resolution texture packs, loaded from the user's own files;
  - Discord rich presence;
  - accessibility (colour-blind HUD options, input remapping everywhere);
  - controller layouts per device.
- **0.9.x freeze:** after the first 0.9 release, only fixes. Release candidates
  run the full acceptance matrix.

## 1.0 - Complete

- **Full playthrough:** every mode, track and car class in GT5 Prologue on
  Windows (D3D12 and Vulkan) and Linux. No open crash, freeze or rendering bug
  above minor.
- **Preparation:** whole-game coverage measured, not just observed routes.
- **Install and update:** documented, with old caches handled automatically.
- **Exit:** the acceptance matrix passes on all platforms. README status:
  "complete".

## Tracking

When a release ships, mark its row done here, keep the evidence in progress.md,
and move unfinished items forward explicitly rather than dropping them.
