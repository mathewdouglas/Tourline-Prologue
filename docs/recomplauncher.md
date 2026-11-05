# RecompLauncher integration

[RecompLauncher](https://recomplauncher.com/game/tourline-prologue) installs releases from
GitHub and reads `recomplauncher.json` beside the program
([developer guide](https://github.com/elripalda/RecompLauncher/blob/main/docs/DEVELOPERS.md)).
Ours is [launcher/recomplauncher.json](../launcher/recomplauncher.json); the release packager
puts it at the root of the player ZIP, beside `tourline-prologue.exe`. As the game is already
listed, the next release carrying it is enough.

## What it does

- **Play starts `tourline-prologue.exe`**, not `runtime/gt5p.exe`. The Tourline launcher keeps
  doing storage selection and locks, release/ELF verification, setup, the preparation offer,
  managed restarts and pipeline-tool handoffs. There is no `game` section: our launcher asks for
  and verifies the disc folder itself, so RecompLauncher does not ask a second time.
- **Settings (level 2)** edit `gt5p_settings.toml` in place: resolution, aspect, window mode,
  MSAA, V-Sync, texture filtering, skip movie and button prompts, plus Smooth colour and Preload
  known shaders under Advanced. Keys are `section/key`; RecompLauncher changes only those lines,
  and reads the file again after the game closes, so F1 changes show on its page.
- **`config.new`** writes the launcher's first-run preset (720p, 2x MSAA, background shader
  work, `[meta] defaults_version = 1`) when RecompLauncher starts the game before our launcher
  ever ran. `launcher.cpp` writes the same preset; keep the two in step.
  `defaults_version = 1` stops the 0.2.4 one-time migration from undoing a Preload choice made
  in RecompLauncher before the first start.
- **Folders:** Open Storage Folder and Open Logs buttons; `logs` also lets RecompLauncher attach
  the newest log to a crash report.

## Relocated storage

The manifest's paths are fixed, but players can move storage (`Change storage.cmd`,
`--set-storage`), which RecompLauncher cannot read from `storage.ini`. Rewriting the manifest
from the storage scripts would not hold: every update replaces `recomplauncher.json`, and
RecompLauncher edits the settings file *before* it starts our launcher, so the first start after
each update would edit the wrong file.

Instead the launcher keeps a directory junction, `%LOCALAPPDATA%\GT5PRecomp\selected-storage`,
pointing at relocated storage ([storage_link.h](../launcher/storage_link.h)). The manifest uses
the file under that junction when it exists and the default folder otherwise. The junction is:

- created or retargeted after a successful storage change;
- checked on every launch, which repairs links for players who moved storage before this
  version, and removes a stale one when `storage.ini` no longer names a folder;
- never made for `GT5P_USER_DIR` runs, never replacing a real folder of that name, and never
  pointed at network paths (junctions cannot target them).

Failures are logged to `logs\storage-link.err` and never stop the game.
`GT5P_STORAGE_LINK=0` leaves the link alone. While relocated storage is disconnected the junction
dangles, so RecompLauncher falls back to the default folder; our launcher then refuses to start
until the drive returns, as before.

## Not done yet

- **Guided first-time setup (level 3):** a `game` section plus a noninteractive import
  (`prepare` hook) that takes the disc folder and an `EMAIN.ELF` or RPCS3 path, validates it as
  setup does today and prints `progress` lines. Until then the Tourline setup dialogs appear on
  first Play.
- **Big Picture:** the first-run storage picker and setup dialogs need a mouse;
  `RECOMPLAUNCHER_MODE=bigpicture` could pick borderless and skip the picker.
- **Keyboard bindings:** RecompLauncher's `bindings` names (Return, Space) must be mapped to ours
  (`names`) before exposing `[keyboard]`.
- **`saves`:** left to RecompLauncher's write detection; listing paths needs the same link.

## Checks

```
python scripts/test/recomplauncher_manifest.py
python scripts/test/player_package.py
cl /nologo /std:c++17 /EHsc /DUNICODE /D_UNICODE scripts\test\storage_link_probe.cpp
scripts\release\build_launcher.cmd <out>
python scripts/test/storage_link.py --probe storage_link_probe.exe --launcher <out>\tourline-prologue.exe
```

The first reimplements RecompLauncher's TOML line editor and checks every choice against the
game's saved layout, the accepted values and the keys `gt5p_settings.cpp` reads. Before a release,
also add the build in RecompLauncher's Developer tools ("Add a build") and read its check.
