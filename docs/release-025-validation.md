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

The initial `v0.2.5` tag had not published a release. It is corrected to include
this test isolation fix before retrying publication. Published versions are
unchanged. Remaining feature work is recorded under 0.2.6 in the roadmap.
