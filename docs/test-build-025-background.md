# 0.2.5 background preparation test build

Private Windows x64 test package, built on 2026-11-10 from branch `0.2.5`,
source commit `6de70051e112128a04270080ed35b1f0a1101c71`. No release or tag.

Artifact (ignored, local):
`scratch/test-6de7005/tourline-prologue-v0.2.5-test-6de7005-windows-x64.zip`.
Size: 103,894,959 bytes; 308 files.

SHA-256:
`25033c34aba9bd81d78374831b5ffa07c04d3af0805af5127d7ef5b4859f930b`.

This combines settings-focused quick preparation, continued full background
preparation, the launcher status and deferred completion notice, race pausing,
and the native opening-movie setting link. It includes the RecompLauncher
manifest and current DXC runtime DLLs. Import the ZIP into RecompLauncher or
extract it into a fresh folder and run `tourline-prologue.exe`.

The engine and launcher were rebuilt from current host sources and the pinned,
patched runtime using read-only reference generated PPU objects. The helper was
frozen from current scripts. The interpreter remains default-off; this normal
player build uses the main runtime patch without experimental overlays.

All build and validation processes used the shared validation lock. Packaging
passed ZIP CRC, duplicate-path, manifest, version, engine/helper SHA-256 and every
helper file hash check. No game data, saves or player caches are included. The
helper's 8 hashing and 9 volume-reader checks, both executable icon checks and
the RecompLauncher manifest test passed. Local evidence and build input hashes
are in `scratch/test-6de7005/`.

The extracted production helper and engine passed the frozen 32-record quick
preparation fixture in 152.29 seconds: eight interrupted fragment results were
reused, all native requests passed, cancellation preserved the old selection,
cached/rollback runs reused their work, and full background completion selected
a new generation while preserving the quick cache. Evidence:
`scratch/t237/validation.json`. Command (inside `run_locked.py`):
`scripts/test/player_fragment_checkpoint_native.py --quick`, with helper and
reference install from this ZIP, original assets read-only, output `scratch/t237`.
This is a bounded offline check on one GPU, not a full preparation timing.

Player checks: prepare the short set, launch the game, observe the background
status in menus, enter a race and confirm the paused status, then return to menus
to allow work to continue. Successful background completion should display its
notice followed by the ready status. See [background-preparation-status.md](background-preparation-status.md)
for details and rollback switches. This artifact is for interactive acceptance;
it does not establish new full-game rendering or hitch results.
