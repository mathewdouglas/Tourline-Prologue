# Controls polish (development 0.2.5)

Implemented on `feature/controls-polish`, based on the required unpublished
`82fd3370dcb3a75b8cf0087366e2125b93e3cf3b` base. No main merge, tag or release.
The existing Phase 218 partial-pressure fix remains in place.

## Player controls

F1 has a **Controls** page and a **Feedback** page. Response, dead zone and
feedback changes require a restart; Modern controls applies live once the game
has loaded its profile. RecompLauncher exposes the five restart-based choices;
Modern controls is in F1 because it reads and changes the game's current mapping.
Its first-run preset stays unchanged. Existing files retain linear response,
zero dead zone and no new effects. Custom game mappings stay intact until a player
explicitly chooses Yes or No.

| TOML key under `[input]` | Environment override | Values / default |
| --- | --- | --- |
| `trigger_deadzone` | `PAD_TRIGGER_DEADZONE` | Integer 0..20 percent; default 0. F1 offers 0/2/5/10/15/20. |
| `trigger_curve` | `PAD_TRIGGER_CURVE` | 0 Linear (default), 1 Gentle, 2 Quick |
| `modern_controls` | `PAD_MODERN_CONTROLS` | Last observed game mapping (not a boot command); F1 No / Yes changes the four assignments |
| `adaptive_triggers` | `PAD_ADAPTIVE_TRIGGERS` | false / 0 by default; true / 1 requests fixed DualSense resistance |
| `trigger_rumble` | `PAD_TRIGGER_RUMBLE` | false / 0 by default; true / 1 forwards game motor levels to supported trigger motors |
| `sdl_rumble` | `PAD_SDL_RUMBLE` | false / 0 by default; true / 1 forwards game motor levels to SDL body motors |

`PAD_CONTROLS_POLISH=0` disables all six runtime additions, independently of saved
values. `GT5P_NATIVE_CONTROLS=0` disables only the native mapping link. For Modern
controls, an explicit `PAD_MODERN_CONTROLS=1` is a one-shot startup request for the
modern mapping; `=0` requests the four defaults. It is not continuous enforcement.
Other individual `=0` overrides restore their defaults. Environment values win over
the file and F1 reports the individual overrides. `PAD_NO_SDL=1` retains XInput /
keyboard fallback. `PAD_PRESS_FORCE_FULL=1` is the older Phase 218 rollback and
intentionally defeats partial pressure; leave it unset for these controls.

The dead zone and curve affect both real controller triggers in the SDL2 and
XInput paths, before script/keyboard injection. Stick response is unchanged.
The dead zone removes `floor(percent * 255 / 100)` byte steps, then rescales the
remaining travel to 0..255. With normalized pressure x, Gentle is x squared and
Quick is 2x minus x squared (integer rounding). Both are monotonic and retain full
pressure at full travel. The default bypasses shaping, including the previous
backend-specific digital thresholds. When shaping is chosen, nonzero shaped
pressure sets the digital bit; a zero value clears it so injection fix-up cannot
turn a suppressed input into full pressure.

**Modern controls follows the game's player-one SIXAXIS assignments.** Yes means
R2 accelerate, L2 brake, Cross gear up and Square gear down. F1 detects this exact
mapping even when it was selected through the game's Options screen. Choosing No
restores Cross accelerate, Square brake, R2 gear up and L2 gear down. A custom
mapping displays No; choosing No explicitly from its dropdown restores these four
defaults even if No was already displayed. Steering, other buttons, wheels, other
play modes and player two stay unchanged. No host button alias remains, so physical
menu buttons and pressure channels retain their normal meanings.

The link waits for profile load, validates the pinned native controller layout,
then changes only four pressure-action bytes and clears the four corresponding
digital actions, matching the game's own assignment representation. Getter,
setter and profile-load hooks serialize mapping access with the input poll. No
save-file offsets or checksums are patched. Use the game's normal Save to persist
the mapping; the TOML boolean is only an observation and never silently reapplies
an old preset at boot. Unknown targets or unavailable layouts receive no writes.

## Feedback and lifecycle

Effects run on the existing SDL owner thread. Guest `cellPadSetActDirect` publishes
a packed atomic motor command rather than touching an SDL handle. The normal
large motor becomes low-frequency body / left trigger level; the small on/off motor
becomes high-frequency body / right trigger level. Body and trigger vibration are
independent opt-ins. This is the game's existing vibration signal, **not** ABS,
engine RPM, wheel slip or other invented telemetry.

DualSense uses SDL's controller-specific effect API, only for SDL PS5 type 7. The
47-byte payload sets only the two trigger flags and requests fixed resistance on
both triggers (mode 1, start 0, force 110, following SDL's official test example).
It is not vehicle-dependent. Mode 5 clears resistance. Unsupported/missing effect
APIs retain normal input. A failed adaptive request is reported once and suppressed
until device replacement. Xbox trigger vibration is gated by SDL's capability query;
XInput alone cannot supply trigger-motor output.

Output is suppressed while F1 blocks game input, while unfocused, or after 250 ms
without a host input poll. Vibration requests last 1,000 ms and renew every 400 ms;
inactive output clears queued levels so old vibration does not resume on focus
return. Disconnect clears queued state before another device can occupy the port.
`cellPadEnd` clears the poll heartbeat and requests. Normal CRT exit joins the owner
and requests zero output. Forced termination, process crashes, failed disconnect
writes and actual controller firmware behavior are **not** hardware-validated;
persistent adaptive resistance may require reconnecting or power cycling the pad.

Bluetooth DualSense effects enter SDL's enhanced-report mode, which can affect
DirectInput in other applications until the controller is power cycled. This is
shown in F1 help. USB and Bluetooth both require physical acceptance. Xbox driver,
firmware and transport determine trigger-motor capability; unsupported output does
not disable controller input or the existing XInput fallback.

## SDL2 versus SDL3

Keep SDL2 for this change. `scripts/get_sdl2.ps1` pins 2.30.9; CMake copies SDL2.dll,
release CI seeds it, and the player package requires it and the SDL notice. The new
APIs are optional dynamic exports, so an older DLL can still read controllers.
Trigger rumble exists since SDL 2.0.14, SendEffect since 2.0.16, and the trigger
capability query since 2.0.18. No new DLL or license bundle is needed.

Official references checked 2026-11-10:

- [SDL2 trigger rumble](https://wiki.libsdl.org/SDL2/SDL_GameControllerRumbleTriggers)
  and [capability query](https://wiki.libsdl.org/SDL2/SDL_GameControllerHasRumbleTriggers).
- [SDL2 SendEffect](https://wiki.libsdl.org/SDL2/SDL_GameControllerSendEffect),
  [official PS5 example / effect layout](https://github.com/libsdl-org/SDL/blob/release-2.30.9/test/testgamecontroller.c),
  and [PS5 backend](https://github.com/libsdl-org/SDL/blob/release-2.30.9/src/joystick/hidapi/SDL_hidapi_ps5.c).
- [PS5 enhanced reports](https://wiki.libsdl.org/SDL2/SDL_HINT_JOYSTICK_HIDAPI_PS5_RUMBLE).
- [Windows RawInput backend](https://github.com/libsdl-org/SDL/blob/release-2.30.9/src/joystick/windows/SDL_rawinputjoystick.c)
  combines Windows APIs for controller features; capabilities still depend on the
  selected driver. No global Xbox driver override is forced here.
- [SDL3 migration guide](https://wiki.libsdl.org/SDL3/README-migration): function
  renames (GameController to Gamepad), changed success return conventions,
  instance-ID discovery and lifecycle/thread requirements make this an ABI port,
  not a DLL rename. SDL3 would also require fetching, staging, package/notice and
  hotplug/virtual-controller harness changes. Audio is WASAPI in this Windows
  build, but the runtime's optional SDL2 audio backend is another migration surface.

SDL3 can be assessed later against real devices and transport-specific gaps. No
migration or claim of better Xbox/DualSense hardware compatibility is made here.

## Validation and reproduction

Every game, build and test below ran through:

```
C:\GT5P-CI\venv\Scripts\python.exe C:\tmp\gt5p-testlock\run_locked.py --label NAME -- <command>
```

All sources/build outputs/caches/saves used for native/game validation live under
this worktree's ignored `scratch/controls`. The source runtime is a clean pinned
4e8f3ca8 export plus the main patch and regenerated controls overlay. Shared CI,
runtime checkouts, original input/cache and saves were read-only. No generated PPU
code was compiled. The engine was relinked from retained reference PPU objects,
with changed runtime and settings consumers recompiled privately.

- `powershell -NoProfile -File scripts/test/controls_polish.ps1 -Runtime <private runtime> -Sdl <read-only SDL2.dll>`:
  **16,128** monotonic response cases (21 dead zones x 3 curves x 256 pressures),
  endpoint/reference values; **255** actual big-endian
  guest trigger packets survive Phase 218 fix-up. Mock outputs verify packet flags/unused bytes, motor levels,
  400-ms renewal, stop/resume, failure suppression and missing exports.
  Real SDL virtual devices verify neutral disconnect, **five** replacements keeping
  their port and **three** worker reconnects. Master rollback and no-SDL XInput
  fallback pass. These are synthetic/native checks, not physical feedback proof.
- `scripts/test/controls_settings.py <native probe>`: **four** production C++ parser
  save/reload cases cover defaults, opt-ins, invalid types/ranges, environment
  precedence and original-file preservation. Probe compiled from the real settings
  and keymap sources; no guest/game execution.
- `scripts/test/recomplauncher_manifest.py`: **15 settings / 18 keys** pass all
  choices and preserve other file values; first-run preset unchanged. Actual
  RecompLauncher app acceptance remains open.
- `scripts/test/controls_patch.py`: clean pinned main + controls apply, setup
  `--check`, and all **four** independent renderer-overlay apply checks pass.
  Input-only overlay leaves the renderer contract and starter unchanged. CI's
  private runtime identity includes overlay bytes; the helper bundles the referenced
  patch. The main compatibility patch was not edited. The overlay is regenerated with
  `git diff --binary` against a staged main-patched clean export; its normalized
  final cellPad.c SHA-256 is pinned in `config/ps3recomp.json`.
- `scripts/test/controls_private_build.py`: private native engine + decoder build
  passes. Existing format/toml literal warnings remain; no new compile error.
- `scripts/test/controls_ui.ps1`: real game F1 navigation and persistence of dead
  zone 2%, Gentle and Modern On, with all feedback defaults Off; PrintWindow
  inspection checks Controls and Feedback layout. Private settings/cache/save
  fixture; this is boot/settings acceptance, not a driven-race comparison.
- Initial native SDL inventory: **0 controllers**. A later discovery found **one
  DualSense Wireless Controller**, SDL type 7. Optional `controls_polish.ps1
  -Hardware` sent fixed resistance for **350 ms**, then cleared it: both SDL API
  calls returned **0** (success); trigger-rumble capability was **0**, as expected
  for a DualSense. This is a real-device API smoke test, not tactile acceptance;
  its USB/Bluetooth transport was not established. No Xbox was detected.
  Full-travel feel, actual motor response, unplug during an effect,
  focus/overlay/exit clearing on hardware, USB/Bluetooth, wireless Xbox adapters,
  Steam Input/DS4Windows and DualSense Edge remain unverified.

Hardware acceptance should cover the modern and default game assignments, pressure sweeps,
menu/pause navigation, normal close, F1, focus loss and reconnects. Effects stay
default-off until those results exist. Full release packaging and a long race/hitch
comparison were not run for this input-only change.

## Native mapping follow-up (2026-11-10)

The previous test ZIP's race-only host alias is superseded by the native mapping
link above. Measured default native action pairs for Cross/Square/L2/R2 are
4/5/10/9; modern is 9/10/5/4, with digital action zero on these channels.
Per-build addresses are pinned in `config/targets.json` and compile only into
`gt5p_controls.cpp`, avoiding any generated PPU rebuild. The runtime overlay
provides the pad-poll and screen callbacks; the main runtime patch is unchanged.

`controls_mapping.cpp` exercises the production bridge against private big-endian
memory: Yes/No, game-side edits detected without a host request, explicit default
restoration from a custom No mapping, unrelated bytes preserved, five malformed
layouts rejected before writing, and deferred profile load / disabled requests.
These are synthetic native checks, separate from game and hardware acceptance.

Real-window native acceptance used `controls_ui.ps1 -Mapping`'s route on a private
fixture: F1 Yes shows the four modern assignments in the game's dialog (including
the highlighted Cross / Shift Up field); changing Cross to Shift Down in-game
makes F1 show No. Explicitly choosing the already-displayed No restores all four
defaults, confirmed in the game's dialog, while the other displayed bindings stay.
A custom 10/10/5/4 tuple survives the game's save and reload without a host command.
A separate normal game Save after the F1/native 9/10/5/4 tuple completes successfully
(`GAME_P2.DAT` 6,840 bytes, private fixture). Fresh parser/native/overlay checks pass;
the current SDL inventory is zero controllers. No new tactile or driving claim is made.
Fresh-process reload of that modern save also passes: with a new PC settings
file (default false), F1 shows Yes and the native tuple is 9/10/5/4 without any
host mapping request. This confirms persistence uses the game save, not a TOML
preset replay. Evidence: `scratch/controls/native-mapping/{accept,save.log,reload}`.
