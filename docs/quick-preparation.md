# Short preparation for the current settings

The foreground **Prepare shaders** action prepares the observed menu and race
set: 3,546 of the starter's 12,669 inputs. It uses the saved resolution/aspect
translation and MSAA mapping, retains shader/native/persistence proofs and
cancel/resume checkpoints, and selects a separate generation only on success.
Catalogue enumeration and interpreter pipelines are left to full preparation.
The interpreter remains off by default.

This is a coverage choice, not a promise that every first encounter is smooth.
Unseen cars, dealerships, tracks and state variants can still compile on demand.
The plan is observed coverage, not a list of every pipeline in the game.

`Prepare shaders.cmd`, F1 > Debug > Prepare shaders and accepted startup offers
use the short path. **Prepare all shaders.cmd** (launcher `--prepare-full`,
helper `--full`) retains the full starter, catalogue and interpreter stages.
`GT5P_PREPARE_QUICK=0` restores the previous foreground full preparation.

With background preparation enabled, a short completed generation counts as
ready for startup offers, but not as full completion. On the next game launch,
the existing idle-priority helper reuses its checked shader/driver results and
continues the broader preparation, pausing during races. It skips the redundant
race-first stage when a current short generation is selected. The current game
keeps its selected short cache; the full result is selected for the next launch.
`GT5P_PREPARE_BACKGROUND=0` disables that continuation.

Older completed full preparations still count as full. No old generation is
deleted or invalidated merely by adding this mode. The optional old-cache cleanup
offer is scheduled after full completion, not after replacing a broad cache with
a smaller short result. Settings changes make the short readiness check false;
its cache stays on disk and normal demand compilation remains available.

The subset and adapted plan are deterministic, pinned to the shipped template
and stored privately beside the generation. Unknown plan inputs are rejected.
The full preparation token is unchanged; the short token also includes its scope
and settings. The library preparation API retains its existing full behavior.

Current limits: the implementation retains the existing default native proof
before the additional ultrawide/scaled pass; it does not yet avoid every native
pipeline outside the player's mode. Automatic translation has the existing
anisotropy-16/high-precision requirements. Other settings/overrides fall back to
the existing default translation policy. Shader coverage, renderer defaults and
runtime patches are unchanged.

Measured acceptance is recorded in progress Phase 235; the full-profile baseline
and its caveats are in [preparation-profile-025.md](preparation-profile-025.md).
