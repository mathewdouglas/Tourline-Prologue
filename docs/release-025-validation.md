# 0.2.5 release validation

The release runner was stopped when the main build queued. On 2026-11-11 its
existing listener was restarted without changing runner configuration. Main
commit `e52b1f7` passed the complete cold build, validation, packaging and upload
in [run 42881053387](https://github.com/mathewdouglas/Tourline-Prologue/actions/runs/42881053387).

The first tag build reused that cache but failed the launcher lifecycle fixture:
after it installed a synthetic preparation helper returning not-selected, the
DXC migration offer appeared before the child-start assertion. The retained
fixture reproduced this failure. The lifecycle fixture now explicitly disables
unrelated preparation offers with `GT5P_PREPARE_OFFER=0`; production behavior is
unchanged. The corrected lifecycle suite passes, and all 26 dedicated first-run,
DXC offer and cleanup cases pass separately with the tag build's launcher/probe.
Both checks ran through the shared validation lock.

The initial `v0.2.5` tag had not published a release. It was corrected to include
this test isolation fix before publication. Earlier published versions are
unchanged. Remaining feature work is recorded under 0.2.6 in the roadmap.

## Published release

[Release workflow 42889828538](https://github.com/mathewdouglas/Tourline-Prologue/actions/runs/42889828538)
passed both the Windows build/upload and hosted publication jobs. The final
immutable `v0.2.5` tag names `1696885a93e6285ef3eafa3caf7c34f209b17e4c`.
[The public release](https://github.com/mathewdouglas/Tourline-Prologue/releases/tag/v0.2.5)
contains the authored summary and detailed release notes, player ZIP and checksum.

An independent download of both public assets passes SHA-256, ZIP CRC, unique
paths, version, engine/helper executable hashes, all 71 helper files against the
build manifest, and the RecompLauncher manifest. Both preparation commands and
DXC DLLs are present; game inputs, saves and caches are absent. The ZIP contains
309 files and is 103,925,151 bytes.

SHA-256:
`c25835bfce94097c11dd1b72bd6eb3f2921d39e7189db688ff5c64b60dc8ef55`.

Local evidence: `scratch/release025/published-validation.json`, downloaded ZIP
and checksum. Verification ran through `run_locked.py` under label
`release025-public-verify`. These distribution checks do not add new gameplay,
other-GPU or controller hardware acceptance beyond the evidence in the release
notes. The runner remains online for future jobs.
