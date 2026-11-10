# Controller vibration follow-up (development 0.2.5)

On `feature/controls-polish`, based on the required unpublished 0.2.5 base.
No main merge, tag or release. The player reported no race vibration with a
Bluetooth DualSense after enabling SDL controller vibration and restarting.

## Findings and changes

1. **Guest capability response overflow.** `cellPadGetCapabilityInfo` used the
   64 button-data codes as its word count. The capability ABI is 32 words / 128
   bytes, independently documented in [PSL1GHT's pad header](https://github.com/ps3dev/PSL1GHT/blob/master/ppu/include/io/pad.h).
   The disc game's manager at `0x00B4F4C8` reserves a 128-byte stack buffer,
   calls the capability import at `0x00B4F888`, then copies 128 bytes. The old
   256-byte write cleared nearby local state, including its buffer pointer.
   A private native driver probe observes actuator capabilities **0** before
   the fix and **0x1f** after it. The actuator method at `0x00B4E360` rejects
   output without bit 4. The runtime now writes exactly 128 bytes and the header
   reflects that ABI. No game code or generated PPU source was changed.
2. **Bluetooth feedback mode.** Enabling SDL body vibration or DualSense
   resistance now requests SDL's enhanced PS4/PS5 reports before controller
   discovery. Bluetooth DualSense rumble needs these reports; the previous
   input-only hints did not enable them. This follows the
   [SDL PS5 hint documentation](https://wiki.libsdl.org/SDL2/SDL_HINT_JOYSTICK_HIDAPI_PS5_RUMBLE)
   and [pinned SDL 2.30.9 backend](https://github.com/libsdl-org/SDL/blob/release-2.30.9/src/joystick/hidapi/SDL_hidapi_ps5.c).
   Feedback remains opt-in; ordinary input with all feedback off does not request
   enhanced reports. Explicit SDL environment hints retain their precedence.
3. **F1 test and diagnostics.** Feedback has **Test controller vibration**.
   With SDL body vibration enabled for the current launch, this requests a
   250 ms player-one body-motor pulse on the SDL owner thread. It is independent
   of race events and the game's vibration option. Only this explicit pulse can
   run while F1 blocks ordinary game output; focus loss, disconnect, timeout or
   shutdown clears it. It never drives the trigger motors or creates telemetry.
   Status distinguishes disabled/restart-required, absent controller, API error,
   focus cancellation and SDL acceptance. Acceptance is not a claim that a person
   felt the pulse. The ordinary rumble API's first error is now logged per device,
   and controller discovery logs body/trigger capabilities and the enabled state.

The game's own **Options > Hardware > Vibration Settings > Vibration Function**
must also be On for race effects. The private fixture already had it On, confirmed
visually; this preference is not rewritten. Existing mappings/settings, fallbacks,
modern controls and feedback defaults are preserved. New F1/manifest help explains
the game option, restart and Bluetooth report mode. SDL2 remains; no SDL3 change.

## Switches

| Switch | Behavior |
| --- | --- |
| `PAD_SDL_RUMBLE=1` / `[input] sdl_rumble=true` | Forward the game's body motors, after Restart; existing default false. |
| `PAD_SDL_ENHANCED_REPORTS=0` | Omit the new PS4/PS5 enhanced-report request. It cannot undo a controller mode already enabled; power cycle is needed for that. |
| `PAD_FEEDBACK_TEST=0` | Disable only the new F1 pulse. |
| `PAD_FEEDBACK_TRACE=1` | Bounded per-second guest actuator counts/levels plus SDL body result logs; default off. |
| `PAD_CAPABILITY_INFO_FIX=0` | Diagnostic legacy response-size rollback, reproducing the previous 256-byte guest overwrite. Default is the correct 128 bytes; this is not a normal player setting. |
| `PAD_CONTROLS_POLISH=0` | Existing controls/SDL-feedback master rollback, including the F1 pulse and enhanced-report opt-in. The independent capability ABI correction remains enabled. |

Extended reports can affect DirectInput in other programs until the pad is power
cycled, as documented by SDL. F1 and RecompLauncher help disclose this when opting
into vibration. Unsupported APIs/devices keep their ordinary input path.

## Validation

Every build, test and game launch uses the mandatory `run_locked.py` wrapper.
Outputs, source exports, logs, saves and caches are private under
`scratch/controls/vibration`; shared sources/CI/game input/saves are read-only.
Changed host/runtime objects were relinked against retained reference PPU objects;
no generated source was rebuilt. Both input files are clean pinned-source overlay
outputs with normalized hashes in `config/ps3recomp.json`; the main patch is intact.

- `scripts/test/controls_polish.ps1`: the production capability function writes
  the big-endian actuator flag and exactly 128 bytes for **all seven ports**,
  preserving guard bytes everywhere else. The rollback reproduces the old extra
  128-byte overwrite. Production guest actuator bytes reach SDL spies correctly.
  Pulse tests cover its exact 250 ms duration/body-only levels, timed stop,
  F1-blocked ordinary output, focus loss, no device, expiry, failure and switches.
  Hint tests cover opt-in, neutral defaults and both report/master rollbacks.
  Existing **16,128** pressure cases, **255** guest trigger packets, mapping tests,
  virtual disconnect/**five** replacements/**three** worker reconnects and XInput
  fallback pass. Synthetic tests are separate from physical acceptance.
- Real game baseline and corrected High Speed Ring wall-contact routes use the
  same private save/cache and input schedule, with player-one Vibration Function
  already On. A private diagnostic host wrapper observes capability **0 -> 0x1f**.
  Baseline: no calls reach the runtime actuator function. Corrected: **721 nonzero
  requests** reach it (first recorded low-frequency level **5,397**, high **0**).
  The driver wrappers are scratch-only and are not in the player engine. Body
  output stays disabled during this later race probe, respecting deferred tactile
  testing. This proves guest command flow, not a driving/physical-feel acceptance.
- Real-window F1 inspection confirms the four-row Feedback layout. With
  `PAD_FEEDBACK_TEST=0` the status explains that the test is disabled. The game
  Vibration Function is visibly On.
- One Bluetooth DualSense reports SDL body capability **1** and trigger-motor
  capability **0**. The player felt two short body pulses from the standalone
  SDL probe. Both rumble calls returned **0**. `SDL_GetError` also reported
  `Unexpected controller element crc`; that string did not stop the pulses they felt.
- The in-game F1 **Test controller vibration** button, with SDL vibration already
  enabled for that launch, focused the settings window and logged
  `[pad-feedback] port 0 SDL body low=24576 high=24576 result=0 test=1`.
  The page showed "SDL accepted the test." The first attempt pressed nothing
  because the game window could not be focused. `scripts/test/feedback_ui.ps1`
  now foregrounds the settings overlay, which belongs to the same process, so F1
  stays open. This is SDL acceptance of that F1 action on the body motors the
  player had just felt. A following race launch was not started after a test
  window was reported stuck white and then closed.

Remaining physical acceptance: collision and kerb vibration during a race,
strength and timing, focus/F1/exit clearing, and reconnects. The corrected HSR
route delivered **721** nonzero guest requests with body output disabled, so
those commands were not forwarded to the controller. USB DualSense, DualSense
Edge, Xbox trigger/body motors, Steam Input and DS4Windows remain unverified.
No invented ABS, wheel-slip, RPM or other vehicle signal is used.

A later play of that package stopped during startup with a null read. The fault
was F1 drawing the Debug page: Debug export has no environment name, and the
modern-controls label passed it to `strcmp`. The vibration path was not on the
faulting stack. Rows with no environment name are now skipped by that check.

Local test ZIP, head `79ecafc`, is recorded in
[test-build-controls.md](test-build-controls.md). It is not a release.
