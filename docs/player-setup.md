# Player ZIP and first-run setup

The current port version is **v0.2.3**, recorded in the root `VERSION` file. Player ZIPs
include `port_version=0.2.3` in `release.ini`; its separate `version=03.00` field
identifies the supported disc build. ps3recomp v0.18.0 is the runtime dependency,
not the port release version. CI names ZIPs `tourline-prologue-v0.2.3-windows-x64-<commit>.zip`.

## Short foreground preparation (0.2.5 development)

`Prepare shaders.cmd`, F1 and accepted offers prepare the 3,546 observed menu/race
inputs for the saved settings. `Prepare all shaders.cmd` retains full preparation;
`GT5P_PREPARE_QUICK=0` restores the previous foreground behavior. A short cache
counts as ready for offers, but full background preparation still continues on
the next game launch, reusing its results and skipping the race-first step.
Cleanup waits for full completion. See [quick-preparation.md](quick-preparation.md).

## Background preparation (Phase 225, replaces the offer by default)

When no completed preparation made by this release is selected, the launcher no longer asks. It starts the
helper beside the game (`GT5P-Prepare.exe --background --live-cache <the cache this run uses>`) at idle
priority in its own kill-on-close job, logging to `logs/prepare-background.out/.err`:

1. **Race stage:** the bundled plan's 2,113 race pipelines are prepared and proven like any preparation,
   then copied into the cache the game is using and added to its race list. The next race loading screen
   prepares them (about 90 s after launch on the 12-thread development PC). While the stage runs, its
   finished shaders and driver blobs are copied in every few seconds already (Phase 226; complete files
   only), so a race started before the stage finishes still finds most shaders on disk.
   `GT5P_PREPARE_BACKGROUND_TRICKLE=0` copies only at the end.
2. **Full stage:** the ordinary full preparation, reusing the race stage; selected only when it completes,
   so the next launch uses it.

While a race runs (from the race start until the next menu, results and replays included) the helper's
processes are suspended; the game signals this through `GT5P_RACE_EVENT`, which the launcher creates. The
race start is the first Cross or Start press at least 1 s after the race loading screen (the grid
preview's Start), or 45 s after it (`GT5P_RACE_SIGNAL_CAP_MS`); `GT5P_RACE_SIGNAL_AT=loading` pauses from
the loading screen instead (Phase 225).
A settings restart keeps the helper; quitting stops it at a checkpoint (`prepare.cancel`), and the next
launch resumes. `logs/prepare-background-pause.txt` records the pauses.

- `GT5P_PREPARE_BACKGROUND=0` restores the one-time offer below. `GT5P_PREPARE_BACKGROUND_PAUSE=0` never
  pauses. `GT5P_PREPARE_BACKGROUND_WORKERS=<2..12>` sets the compiler workers (default half the logical
  processors). `GT5P_PREPARE_OFFER=0`, `GT5P_PREPARE_VOLUME=0` and `--no-prepared` start nothing.
- A current full preparation is remembered in `prepare-full-current-<port version>.txt` with its
  selection/settings/compiler identity, so later launches skip the helper check.
- Tests: `scripts/test/launcher_background_native.py` (13 scenarios against the probe),
  `scripts/test/background_preparation.py`. Measurements: docs/progress.md Phase 225.

## First-launch preparation offer, preload default and indicators (v0.2.4)

Shaders prepared by an earlier version are not reused by v0.2.4 (the shader text
is the cache key), so the **first launch of v0.2.4** offers preparation once,
after setup and before the game starts, in the same dialog as the post-setup
offer. It gives a broad time estimate for your processor count: **about 10 to 20
minutes** with eight or more logical processors (four compiler workers), **about
20 to 40 minutes** with fewer (two). One full preparation measured on a 12-thread
i5-12400F took 579 s (9.7 minutes), 0.96 GiB; see the
[v0.2.4 notes](release-v0.2.4.md#cheaper-shaders-faster-preparation). Your time
depends on your PC.

- **Prepare now** runs the existing preparation window (cancel and resume as
  before); **Skip and play**, closing the dialog, cancelling or a failure all
  start the game.
- The answer is recorded in `prepare-offer-<port version>.done` in the launcher
  storage, so the offer is not repeated for that version. A fresh install gets
  the post-setup offer instead, which records the same marker; both never appear
  in one launch.
- Nothing is asked when a completed preparation made by this release is already
  selected: the helper's read-only `GT5P-Prepare.exe --check-selected` (exit 0
  prepared, 3 not prepared) compares the fingerprint recorded in
  `prepared-identity.txt`. If the helper cannot answer, nothing is offered and
  nothing is recorded.
- `GT5P_PREPARE_OFFER=0` disables the offer; `--no-prepared` and
  `GT5P_PREPARE_VOLUME=0` skip it for that launch. **Prepare shaders.cmd** and
  **F1 > Debug > Prepare shaders** remain available.
- Tests: `scripts/test/launcher_first_run_native.py` (20 scenarios against the
  probe), `scripts/test/rc024_launcher_e2e.py` (real launcher, helper and
  engine).

**Preload known shaders** (F1 > Shaders) now defaults to On in a new settings
file; an existing file that says `shader_warmup = false` keeps false. "Compiling
shaders" lights only for work a draw is waiting on; background preload is counted
separately and can show a smaller **"Loading shaders"** badge (F1 > Game >
Shader preload indicator, `video.preload_indicator`, `GT5P_PRELOAD_INDICATOR=1`,
off by default). `RSX_SHADER_INDICATOR_LEGACY=1` restores the combined counting.

## Shader enumeration in development builds

Optional **Prepare shaders**, the first-run **Prepare now** choice and F1
**Debug > Prepare shaders** now also prepare asset shaders after the existing
template stages. The new **Enumerating shaders** step handles 36,595 fragment
and vertex jobs using your original GT.VOL and ELF. No catalogue, unpacker or
extra asset copy is needed. The package includes 2.62 MiB of metadata before ZIP compression;
shader bytecode is generated locally. Published v0.2.3 is unchanged.

This adds preparation time and local cache space. On the development machine a
full first preparation took about 10.5 minutes for the template stages, and the
enumeration step added about 24 minutes of shader compilation (36,473 of 36,595
shaders; the rest are left to normal in-game compilation) and about 220 MiB of
disk. Repeating the preparation re-checks rather than rebuilds. Your time depends
on your CPU. Development builds now default to logical processors minus two compiler workers
(2 to 10, limited by free RAM; `GT5P_PREPARE_COMPILER_WORKERS=legacy` restores four or two) and larger
compiler launches (`GT5P_PREPARE_ENUMERATE_BATCH=256` restores the old size). On the development machine the
enumeration step alone then took about 8 minutes instead of about 17 (measured in isolation with the template
stage's cache present; the full first preparation was not re-timed). Cheaper generated shader text (looped vertex
fetch and sized fragment registers, default since Phase 215) brings the same
enumeration step to about 4.4 minutes and the template stages' shader work from about 4.2 to about 2.6 minutes
(consecutive runs, rollbacks with `GT5P_PREPARE_VFETCH_LOOP=0` and `GT5P_PREPARE_FP_REG_SIZE=0`; see
[de-specialized shader text](coverage-enumeration.md#de-specialized-shader-text-phase-215-now-default)). Details:
[player enumeration acceptance](coverage-enumeration.md#packed-player-acceptance-2026-11-04-12669-record-starter).
Cancel/close/Escape retains completed chunks. Repeat preparation to resume;
completed bytecode is checked before reuse. The previous selected cache stays
available until preparation succeeds. Individual shader rejections are reported
and left to normal demand compilation. Native pipeline creation still uses the
starter templates and the runtime worker, so preparation cannot remove every hitch.

Set `GT5P_PREPARE_ENUMERATE=0` before launching the preparation command to restore
the previous template-only preparation path. Existing caches are retained;
switching modes can therefore leave more than one generation on disk. Enumeration
currently adds default-translation shaders; the existing settings-aware template
preparation still handles its supported additional translation modes.

## Pipeline tools in v0.2.3

F1 **PC Settings > Debug** offers **Collect pipelines**, **Verify last collection**
and **Prepare shaders**. Each closes the game before starting its owned tool.
Collection verifies against your own original files after play; cancellation
keeps resumable work. Only verified metadata becomes shareable, and nothing is
uploaded automatically. The starter contains 5,669 verified observed pipelines;
coverage remains partial. See [v0.2.3 notes](release-v0.2.3.md) and
[contribution instructions](pipeline-contributions.md).

Development Phase 212 expands the source starter to 12,669 verified pipelines
(3,446 programs: 622 VP / 2,824 FP). It is not part of the published v0.2.3 ZIP.
See [progress](progress.md) for the fresh frozen preparation and remaining limits.

## Shader packs in v0.2.2

Default-translation preparation writes local menu and race bytecode packs from
the bundled observed plan after native preparation. That translation is 720p
and 1080p at 16:9, including the first-run preset. `native-scaled` and
`ultrawide-native` do not use the plan. `RSX_SHADER_PACK=0` disables runtime
pack use and does not delete caches. An older unpacked generation stays on
disk; the new generation can import it. See [v0.2.2 notes](release-v0.2.2.md).

v0.2.2 offers **Prepare now** or **Skip and play** immediately after successful
first-run file setup, before starting the game. Closing the offer skips
preparation. Cancelling preparation waits for the owned helper to finish
cancelling, then starts the game; completed work remains available for resume.
A preparation failure is reported and normal play remains available. The offer
does not repeat on ordinary configured launches. Run **Prepare shaders.cmd**
any time later to prepare or resume. `GT5P_PREPARE_OFFER=0` disables the offer.
v0.2.1 kept the manual command only.

## Optional shader preparation in v0.2

The sections below record what v0.2 and v0.2.1 shipped. v0.2.2 keeps those
paths and adds the behavior in the section above.

Complete ordinary setup, close the game, then run **Prepare shaders.cmd**
(`tourline-prologue.exe --prepare`). v0.2.1 includes the Phase 178 path reading the
original `USRDIR/GT.VOL` from the game folder already configured for play. No
additional volume extraction, unpacker installation or second asset copy is
needed. The helper is self-contained and requires no player Python/compiler
installation. The older v0.2 package uses its earlier unpacked asset selection.
See [v0.2.1 notes](release-v0.2.1.md).

Direct preparation supports the verified BCUS98158 v03.00 volume. It verifies
the complete original volume and game executable, derives its read parameters
from that executable, then decodes only the required containers in memory.
Game files stay read only. Parameters/keys and decoded assets are not distributed. The existing
`--prepare-assets <folder>` option, or `GT5P_PREPARE_VOLUME=0`, selects the legacy
unpacked-asset flow if needed; unknown volumes fail safely rather than guessing.

v0.2.1 includes the Phase 181 standalone preparation window styled after the
in-game PC Settings menu. It displays the helper's current phase and real counts
for that step; uncounted steps use an animated bar. Counts are not overall progress
or an estimated completion time. `GT5P_PREPARE_UI=0` restores the Windows TaskDialog;
failure to create the new window also falls back to that dialog. Its window
title is **Tourline Prologue**. Preparation stays optional.

Cancel, Escape or closing the window requests cancellation and keeps the window
open until its owned helper exits. Repeat the preparation option to resume
the same metadata/helper generation. Original assets are reverified, completed
shader bytecode is checked, and native pipelines are recreated/checked locally.
The launcher owns the helper and its child processes in its existing Windows
job; cancellation stops only owned preparation work. Successful completion
atomically selects `prepared-cache.txt`, a storage-relative pointer to
`preparation/<generation>/shadercache`. Existing ordinary and older generation
caches remain intact. Storage relocation preserves this relative selection.

v0.2.1 preparation can reuse verified shaders and driver-cache
hints from the previously selected generation when metadata or engine identity
changes. It still verifies original assets and creates/checks every native
pipeline. `GT5P_PREPARE_REUSE=0` disables this optimization. Reuse leaves older
cache generations intact. See
[incremental preparation](shader-precompile.md#incremental-preparation-across-template-updates-phase-176).

v0.2.2 defaults to vertex compilation batches inside optional preparation:
unset or `GT5P_PREPARE_VERTEX_BATCH=1` uses at most two owned compiler workers.
`GT5P_PREPARE_VERTEX_BATCH=0` restores serial compilation. v0.2.1 did not include
this switch. See
[vertex batching](shader-precompile.md#exact-vertex-batching-phases-183-184).
It changes offline preparation speed, not coverage or the game's draw policy.

v0.2.2 also offers explicit additional translation preparation.
`GT5P_PREPARE_TRANSLATION=ultrawide-native` adds native ultrawide variants;
`native-scaled` adds the scaled fragment mode used by native 1440p/4K.
Explicit `default` keeps default-only preparation. These explicit modes do not
infer settings or generate every MSAA/pass combination. v0.2.1 did not include
them. See [translation modes](shader-precompile.md#additional-local-translation-modes).
v0.2.2 defaults an unset `GT5P_PREPARE_TRANSLATION`
to `auto`, choosing from saved launcher settings: 21:9 adds ultrawide variants,
while 16:9 native 1440p/4K adds scaled
fragment variants. Supported file values are checked against the production
settings parser. Unsupported overrides/settings fall back to default preparation
with a reason in the report. Settings changed during a pass prevent publishing
its selection. Explicit `GT5P_PREPARE_TRANSLATION=default` restores default-only
preparation; `=auto` is equivalent to leaving it unset. This is
translation selection, not complete MSAA/pass coverage; see
[automatic selection](shader-precompile.md#automatic-selection-from-launcher-settings-development-phase-187).
`GT5P_PREPARE_REUSE_HANDOFF=0` rolls back the development optimization that avoids
rereading shaders just verified/copied during an incremental update.

The next launch uses that cache, retaining demand compilation for missing keys.
`tourline-prologue.exe --no-prepared` uses the ordinary cache for that launch without deleting
anything. Failure/cancellation leaves any prior selection intact. Logs are
`logs/prepare.out` and `logs/prepare.err`; phase/checkpoint reports are inside the
generation directory. Preparation is experimental, partial and optional.
One High Speed Ring comparison had fewer long frames with shader packs. That
is not whole-game coverage or a guarantee that stutter is gone.

## Restarting after settings changes

v0.2.2 fixes **Restart** on the F1 settings page: the old game exits, then the
launcher starts its replacement with the saved settings. The launcher keeps
storage ownership throughout and closes the old process group before starting
the next one. This avoids the old launcher's shutdown also killing a replacement
spawned by the game. The fresh child reads settings again without inheriting
renderer variables derived by the previous game process. The fix requires both
the updated launcher and engine; replacing only the launcher beside an older
release engine is insufficient. v0.2.1 did not include it.

`GT5P_LAUNCHER_RESTART=0` restores the legacy direct-spawn path for diagnosis;
unset/1 uses managed restart when launched through the updated launcher. Direct
engine launches retain their existing behavior.

The package also contains `preparation/GT5P-Prepare.exe`, its Python runtime and
licenses, the production vertex decoder, and validated template/location JSON.
The frozen tool loads the system D3D compiler explicitly, matching the game's
compiler search rather than accepting a freezer-selected SDK DLL. Metadata is
validated before packaging; only build-manifest-listed standalone tool files
are included. No game-derived cache is distributed.

Implementation branch: `feature/player-setup`, based on the v0.18.0 upgrade.
Worktree: `../GT5P-player-setup`. The shared working tree, runtime checkouts,
generated sources and existing build were left alone. Initial implementation
was written while Claude was active. With Claude paused, the launcher was
compiled and tested on 2026-10-29 as recorded below. Those original implementation
notes predate the v0.1 release; v0.2 candidate acceptance is recorded in the
latest progress phase.

## Player experience

1. Extract the entire ZIP and launch **tourline-prologue.exe**.
2. Choose the default storage folder or an empty folder on another drive,
   including an external SSD. Then select the extracted disc dump, or its
   `PS3_GAME` directory. The launcher
   checks `PARAM.SFO` for BCUS98158 / VERSION 03.00 and requires `GT.VOL` and
   `TV.DAT`. Selecting an ISO is not supported.
3. If a matching decrypted `USRDIR/EMAIN.ELF` is present, it is reused. Otherwise
   select an existing decrypted ELF or choose an installed RPCS3 executable.
   The RPCS3 option copies `EMAIN.SELF` into the private import directory and
   invokes `rpcs3.exe --decrypt <copy>`; it never writes into the original dump.
   If CLI decryption fails, the dialog points at its logs and offers the manual
   RPCS3-decryption path on the next attempt. RPCS3, firmware and keys are not
   bundled, downloaded or configured by this launcher.
4. The ELF must match the release's SHA-256. A verified private copy and the
   selected dump path are saved. Later launches skip setup while they remain
   valid. A missing/moved/wrong-version dump reopens setup.
5. Continue using **tourline-prologue.exe**. It starts `runtime/gt5p.exe` internally. Players
   do not need Python, a compiler, the repository, junctions or developer batch
   files. The initial preset is 720p, 16:9, 2x MSAA with async shader/pipeline
   compilation; existing settings are not overwritten. F1 changes game options.

This is one visible launch entry point with two executables internally. A
separate setup-only executable adds no benefit: `tourline-prologue.exe --setup` changes the
installation path without duplicating startup logic. The engine EXE alone is
still a developer entry point and does not load the launcher's saved selection.

## Files and persistence

The release contains only these selected files:

```text
tourline-prologue.exe                 native /MT launcher, no managed runtime required
release.ini              schema, target, ELF digest and engine digest
START-HERE.txt
Change storage.cmd       reopen the storage chooser with the game closed
LICENSE.txt
runtime/gt5p.exe
runtime/SDL2.dll
runtime/avcodec-61.dll
runtime/avutil-59.dll
runtime/swresample-5.dll
runtime/<app-local MSVC runtime DLLs>
assets/glyphs/...         distributable glyph art and its license
licenses/...             dependency notices and matching source/build information
```

It excludes the ELF/SELF, PARAM.SFO, ROM volumes, savedata, gamedata, existing
settings, shadercache, logs, firmware, keys, and RPCS3. The ELF's digest is
metadata, not the file. The package script never recursively copies a build or
third_party directory. ZIP inputs are explicit; assets are limited to PNG/text
and checked for expected content; v0.2 additionally permits schema/checksum-checked
template metadata. EXEs/DLLs must be native Windows x64 PE files.

Mutable files live in the user-selected storage folder, initially defaulting
to `%LOCALAPPDATA%\GT5PRecomp`:

- `setup.ini`: selected dump path, written atomically after successful setup.
- `input/EMAIN.ELF`: verified personal copy; never part of a release.
- `gamedata`, `gt5p_settings.toml`, `shadercache`, `logs` and copied glyph assets.
- `imports`: private per-attempt RPCS3 input/output; contains personal game data.
  These import directories can be removed by the player with the game closed
  after setup; do not remove the verified `input/EMAIN.ELF`.
- `logs/play.out`, `logs/play.err`: latest game run; `logs/decrypt.*`: latest
  helper run; `logs/setup.err`: last setup/launch failure.

No existing developer save is imported automatically. A player can transfer
their save into their private `gamedata` with the game closed. Updating the ZIP
does not overwrite user data. An exclusive user-directory lock prevents a
second launch. A Windows job owns only the child the launcher created; killing
the launcher cannot leave its game running and then allow a duplicate launch.

The binaries remain wherever the player extracts the ZIP. To install on an
external SSD, extract the entire player folder there, then choose a separate
empty storage folder on that drive during first setup. Original disc files
remain in their selected location. Existing configured profiles keep their
location until the user chooses to change it.

Double-click `Change storage.cmd` (or run `tourline-prologue.exe --choose-storage`) with the
game closed to change storage. Saves/settings/cache/imports are copied and
SHA-256 verified before atomically changing the remembered location. The
original profile is retained as a backup. Nonempty and nested destinations
are rejected, as are linked source files/directories. A failed copy leaves the
original selected and may leave an incomplete destination for inspection;
choose another empty destination before retrying. Large caches can take time
to copy and verify. This is a copy-and-switch operation, not deletion.

A small `storage.ini` locator and `storage.lock` remain under Local AppData's
`GT5PRecomp` folder. A missing external drive produces a reconnect message
without changing that selection or silently creating a fresh profile.

Options:

| Option | Effect |
| --- | --- |
| `--setup` | Select a different dump; cancellation keeps the old selection |
| `--open-data` | Open user data in Explorer, including while the game runs |
| `--choose-storage` | Open the storage chooser, copy/verify existing data and remember the new folder; exit without starting the game |
| `--set-storage <folder>` | Same relocation to a named empty folder without dialogs; errors go to stderr/logs |
| `--check` | Validate release/config/dump/ELF without dialogs or launching a child; exit 0/1 |
| `GT5P_USER_DIR=<folder>` | Separate writable user-data location/profile |
| `GT5P_LAUNCHER_HOME=<folder>` | Override the small locator/lock directory for isolated testing |
| `GT5P_STORAGE_PICKER=0` | Skip the automatic first-run/setup storage chooser |
| `GT5P_LAUNCHER_SETUP=0` | Suppress automatic interactive setup and report missing/invalid configuration |

The game receives the existing `GT5P_ROOT`, `GT5P_SETTINGS`, `GT5P_GAME_DIR`,
`PS3_VFS_ROOT` and `PS3_GAMEDATA_ROOT` overrides. Its working directory is user
data, so ordinary cache/log writes work even if the install folder is read-only.
Glyph art is copied from the ZIP into that working directory on launch.
`GT5P_USER_DIR` overrides the remembered choice and suppresses the storage
chooser; unset it before using the relocation options. Check mode never
changes the remembered storage location.

The only game-source integration change is the direct `PARAM.SFO` lookup in
`src/main.cpp`: an absolute game directory must not be prefixed by the writable
VFS root. The runtime's cellFs already handles absolute mappings. This fix
must be included in the engine build packaged with the launcher.

The engine still has ANSI/path-length limits. The launcher rejects paths that
cannot round-trip through the system code page, or exceed its conservative
length limit, with a visible error instead of a white-window failure. Full
Unicode/long-path support across the runtime is separate work.

## Maintainer build and packaging (when Claude is idle)

First integrate the small main.cpp fix with Claude's completed changes. Build
the game normally for **BCUS98158** in Release/RelWithDebInfo using its matching
local decrypted ELF. The packager relies on the maintainer supplying that same
ELF; it cannot reconstruct the game's compiled input from an arbitrary EXE.
Do not package while the game build is writing outputs.

Build only the launcher from an **x64 Visual Studio Developer Command Prompt**:

```bat
scripts\release\build_launcher.cmd C:\GT5P-release\launcher
```

The launcher uses Win32 dialogs, COM, CNG SHA-256 and a static C++ runtime.
It has no game/runtime linkage and is deliberately outside the shared CMake
game target; adding/changing it cannot invalidate lifted game-code chunks.

Prepare a notices directory containing these exact text filenames:

- `SDL.txt`: SDL license/distribution notice from the bundled SDL build.
- `FFmpeg-LGPL.txt`, `FFmpeg-GPL.txt`: full applicable license texts.
- `FFmpeg-SOURCE.md`: exact bundled FFmpeg version, binary origin, matching
  corresponding source location, patches and build instructions/configuration.
  Use the actual bundled DLL build, not an unrelated newer source tree.
- `ps3recomp-LICENSE.txt`: pinned runtime's license.
- `MSVC-NOTICE.txt`: applicable notice for app-local redistributable DLLs.

Use the x64 redistributable DLL directory matching the game's compiler, not
debug CRT DLLs or arbitrary copies from System32. Required: msvcp140.dll,
vcruntime140.dll and vcruntime140_1.dll. Known companion DLLs are also included
when present. Review dependency notices/source availability and runtime DLL
dependencies before publishing; the script checks presence, not their legal
or version correctness. It performs no dependency downloads.

```powershell
python scripts/release/build_preparer.py `
  --runtime C:/path/to/pinned-patched-runtime `
  --output C:/GT5P-release/preparer
python scripts/release/package_player.py `
  --build-dir C:/path/to/completed/build `
  --launcher-exe C:/GT5P-release/launcher/tourline-prologue.exe `
  --preparer-dir C:/GT5P-release/preparer/dist/GT5P-Prepare `
  --elf C:/path/to/matching/EMAIN.ELF `
  --vc-runtime-dir C:/path/to/VC/Redist/MSVC/version/x64/Microsoft.VC143.CRT `
  --notices-dir C:/GT5P-release/notices `
  --output C:/GT5P-release/tourline-prologue-windows-x64.zip
```

Python is needed by the maintainer only. The packager refuses overwrite,
wrong-target/debug builds, non-ELF inputs, missing dependencies and asset links.
It detects changes to copied inputs and verifies the ZIP's actual engine digest
before committing the final filename. Only the named ZIP should be attached
to a GitHub release, never input/, gamedata/, shadercache/ or scratch/.

## Local validation (2026-10-29)

The x64 MSVC Release `/MT` launcher compiles with `/W4` and no warnings.
Compilation found missing `shellapi.h` declarations and two BOM-byte cast
warnings; both are fixed. Option parsing now precedes path initialization,
so `--check` also suppresses error dialogs for early initialization failures
and unknown options, regardless of option order.

Local binary (historical v0.1 name): `../GT5P/scratch/launcher-validation-20261029/build/GT5P.exe`.
`dumpbin /dependents` lists only Windows DLLs (USER32, SHELL32, ole32,
bcrypt, COMCTL32, KERNEL32); no MSVC redistributable is required by the
launcher itself. The engine's DLL requirements are unchanged.

Passed `scripts/test/player_package.py`: wrong-target/debug-build rejection,
missing/non-PE dependencies, invalid ELF/assets, strict ZIP allowlist,
private-input exclusion, engine/ELF digest binding and existing-ZIP preservation.
These use synthetic metadata, not a distributable game ZIP.

Passed `scripts/test/launcher_native.py` against the compiled launcher and an
independently compiled `launcher_probe.cpp` stand-in child:

- Missing/moved setup, wrong title/version, truncated SFO, missing volume,
  wrong engine/ELF digest and unknown options fail without dialogs in check mode.
- Both disc-root and PS3_GAME selections normalize; paths with spaces reach the
  child as one argument, with correct working directory and environment.
- Saved configuration launches without setup, stdout/stderr logs are captured,
  assets copy into private data and original synthetic dump files are unchanged.
- Initial 720p settings are created; subsequent launches preserve user settings.
- Duplicate launch is blocked while a child runs. Terminating the launcher
  terminates its owned child (verified through a Windows process handle), and
  another configuration check can acquire the released lock.

To reproduce from an x64 VS Developer Command Prompt after building the launcher:

```bat
cl /nologo /std:c++17 /O2 /W4 /MT /EHsc /Fo"C:\GT5P-release\launcher\probe.obj" /Fe"C:\GT5P-release\launcher\probe.exe" scripts\test\launcher_probe.cpp
python scripts\test\launcher_native.py --launcher C:\GT5P-release\launcher\tourline-prologue.exe --probe C:\GT5P-release\launcher\probe.exe
python scripts\test\player_package.py
```

Logs are in `../GT5P/scratch/launcher-validation-20261029/`. The probe and
synthetic fixtures are test inputs only and never belong in the player ZIP.
These initial checks used no game/emulator. The local assembly follow-up below
also validates a real dump and exercises the engine integration.

Interactive testing could not proceed: the Computer Use native helper reported
`failed to connect native pipe` after retry and session reset. Folder selection,
cancellation and the RPCS3 helper dialog remain unverified; this is not evidence
that those UI paths passed.

### Local assembly follow-up

The standalone compiler output is **not a runnable player installation**.
Launching it without its siblings produces the missing `release.ini` error.
Use the complete local test folder instead:
`../GT5P/scratch/launcher-validation-20261029/player/GT5P.exe` (historical v0.1 name).
It includes the hash-bound `release.ini`, engine, SDL/FFmpeg/MSVC DLLs and
glyph assets. Keep the folder together. No game data is bundled in it.
This is a local test assembly, not a public release ZIP with reviewed notices.

Validation against the actual disc found an incorrect SFO check: this dump has
`VERSION=03.00` and `APP_VER=01.00`. The launcher now validates `VERSION`,
and the synthetic SFO fixture represents both fields independently. The native
suite passed again, and `--check` against the real dump/private ELF returned 0.

Compiled only the feature branch's `src/main.cpp` into a scratch object and
linked a separate engine against the existing completed v0.18.0 build objects.
The main worktree's sources, objects and `build/gt5p.exe` were not replaced.
The compile/link retained pre-existing format/unused-option/imported-DllMain
warnings; the launcher itself builds without warnings.

An isolated profile launch through the assembled launcher logged the correct
`BCUS98158` title from the absolute SFO path and reached CursorRoot,
GTLogoTransition and ConfirmDialog boot milestones. The owned launcher was
then terminated; this was a short boot-path smoke check, not menu/race visual
acceptance. Logs/private test profile remain in `real-dump-check/`, outside
the `player/` folder. The player's default first-run profile was not configured
by this check. Interactive folder selection, decryption and deployment checks
still remain.

### Custom storage validation (2026-10-29)

Rebuilt the launcher with the first-run storage chooser and relocation options;
MSVC `/W4` reports no warnings. Native integration checks pass for a custom
path containing spaces, verified migration of saves/settings/cache/private ELF,
retention of the original profile, remembered launching, a second relocation,
refusing nonempty/nested/installation destinations, and blocking relocation
while the owned child runs. A simulated unavailable external path fails without
recreating the directory or changing the locator. Packaging fixtures pass with
the additional explicitly selected `Change storage.cmd` file. The installed
local `player/` folder has the rebuilt launcher and shortcut; no real user
profile was relocated. The new TaskDialog/folder-picker clicks still require
interactive acceptance because the Windows automation helper was unavailable.

## Acceptance checks still required before publishing

Do these in an isolated user-data directory on a spare Windows machine/Ally,
after Claude's testing is finished. The local checks above cover the compiled
launcher with synthetic fixtures; the table also includes the interactive,
real-game, decryption and deployment cases that remain unverified.

| Check | Required result |
| --- | --- |
| Build launcher /MT x64 | No missing declarations/link symbols/manifest errors |
| Fresh extracted ZIP, no developer tools | Folder picker opens before any game window |
| Valid disc root and PS3_GAME selections | Both normalize correctly; ELF digest accepted |
| Wrong title/version, ISO, missing VOL/DAT, wrong ELF | Clear failure; no game launched |
| Cancel folder/ELF/RPCS3 picker | Clean exit; original setup remains valid |
| Existing ELF and RPCS3 helper paths | Both work; original dump hashes unchanged |
| Second launch | No setup dialog; game reaches menu using saved paths |
| Move dump / change release ELF digest | Setup shown again; no stale launch |
| Settings/save/cache/log persistence | Writes only to private user directory |
| Different drives and paths with spaces | Direct PARAM.SFO initialization reports BCUS98158 |
| Unsupported Unicode/long path | Clear path error before starting the engine |
| Read-only install folder | Works with writable Local AppData |
| Duplicate launch / terminate launcher | One owned game; no unrelated processes affected |
| `--open-data` while running, `--check` without config | Explorer opens; check fails without dialogs |
| Game early exit / helper failure | Visible error and readable logs |
| ZIP inspection | No game data, secrets, personal settings or driver cache |
| Packager interrupted / inputs changed | No final ZIP; existing releases untouched |

The release flow is intentionally not wired to automatic GitHub publishing
until these checks pass. Generated game code is not available to a public
source-only CI runner; a maintainer prepares the completed game binary locally.
