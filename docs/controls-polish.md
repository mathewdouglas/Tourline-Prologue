# Controls polish (development 0.2.5)

Implemented on `feature/controls-polish`, based on the required unpublished
`82fd3370dcb3a75b8cf0087366e2125b93e3cf3b` base. No main merge, tag or release.
The existing Phase 218 partial-pressure fix remains in place.

## Player controls

F1 has a **Controls** page and a **Feedback** page. All new values require a
restart. RecompLauncher exposes the same six choices; its first-run preset stays
unchanged. Existing files default to linear response, zero dead zone, the game's
own assignments and no new effects. No save or game assignment table is edited.

| TOML key under `[input]` | Environment override | Values / default |
| --- | --- | --- |
| `trigger_deadzone` | `PAD_TRIGGER_DEADZONE` | Integer 0..20 percent; default 0. F1 offers 0/2/5/10/15/20. |
| `trigger_curve` | `PAD_TRIGGER_CURVE` | 0 Linear (default), 1 Gentle, 2 Quick |
| `modern_controls` | `PAD_MODERN_CONTROLS` | false / 0 by default; true / 1 enables the standard-layout host preset |
| `adaptive_triggers` | `PAD_ADAPTIVE_TRIGGERS` | false / 0 by default; true / 1 requests fixed DualSense resistance |
| `trigger_rumble` | `PAD_TRIGGER_RUMBLE` | false / 0 by default; true / 1 forwards game motor levels to supported trigger motors |
| `sdl_rumble` | `PAD_SDL_RUMBLE` | false / 0 by default; true / 1 forwards game motor levels to SDL body motors |

`PAD_CONTROLS_POLISH=0` disables all six runtime additions, independently of saved
values. Individual `=0` overrides restore each default. Environment values win over
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

**Modern controls is a standard-layout preset, not a universal assignment editor.**
It makes R2 supply Cross pressure and L2 supply Square pressure during the existing
RaceRoot / QuickArcade race scope. That gives R2 throttle / L2 brake with the game's
standard Cross-throttle / Square-brake assignments. Original face buttons remain
available, including pause-menu confirmation; R2/L2's old digital functions are
suppressed in that scope. F1 uses physical buttons. Other screens keep their input.
Turning it Off restores the original host mapping. Modes with different screen
roots need acceptance. The preset does not detect arbitrary in-game assignments:
players who already assigned R2/L2 in the game (as in Phase 218) should keep it Off
and use the response/dead-zone controls directly. A one-step rewrite of arbitrary
custom game assignments remains a gap; no unverified save offsets are written.

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
  endpoint/reference values, race/menu preset routing; **255** actual big-endian
  guest trigger packets plus modern partial Cross/Square packets survive Phase
  218 fix-up. Mock outputs verify packet flags/unused bytes, motor levels,
  400-ms renewal, stop/resume, failure suppression and missing exports.
  Real SDL virtual devices verify neutral disconnect, **five** replacements keeping
  their port and **three** worker reconnects. Master rollback and no-SDL XInput
  fallback pass. These are synthetic/native checks, not physical feedback proof.
- `scripts/test/controls_settings.py <native probe>`: **four** production C++ parser
  save/reload cases cover defaults, opt-ins, invalid types/ranges, environment
  precedence and original-file preservation. Probe compiled from the real settings
  and keymap sources; no guest/game execution.
- `scripts/test/recomplauncher_manifest.py`: **16 settings / 19 keys** pass all
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

Hardware acceptance should cover both existing in-game R2/L2 assignments with the
preset Off and standard Cross/Square assignments with it On, pressure sweeps,
menu/pause navigation, normal close, F1, focus loss and reconnects. Effects stay
default-off until those results exist. Full release packaging and a long race/hitch
comparison were not run for this input-only change.
