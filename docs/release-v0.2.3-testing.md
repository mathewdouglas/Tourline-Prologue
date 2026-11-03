# Testing the private v0.2.3 candidate

This candidate is for local acceptance before publication. Extract its entire ZIP
into a separate folder and use its **tourline-prologue.exe**. Keep the engine,
launcher and preparation helper from that ZIP together. Existing storage, saves
and caches can be reused; do not delete any cache to run these checks.

Use **RC3** (`tourline-prologue-v0.2.3-rc3-windows-x64.zip`); it supersedes the
earlier RC1, budget-only and RC2 copies. SHA256:
`6e21d4f19220767195d0d157195f937c58685eb1f19cd293832bf1b4fbf4a00b`.
The starter has 5,669 records. Full default preparation/native persistence,
checkpoint/collection lifecycles, F1 handoffs, settings restarts and one foreground
High Speed Ring visual route have passed on the development PC. Your test checks
the actual player experience and your storage/settings before publication.

1. Launch normally with your existing storage. Check the menu, garage and a
   dealership. Confirm your settings and save still load.
2. Run the same High Speed Ring race you normally use. Check nearby cars,
   reflections, rear-view mirror and the rolling-start handoff. Note the car,
   resolution/MSAA and approximate race time if a hitch or missing draw occurs.
   Existing hitches are not claimed fixed by this release.
3. Open **F1 > Debug > Prepare shaders**. The game should close before the
   preparation window opens. Cancel once, then rerun **Prepare shaders.cmd** to
   resume. A completed run should prepare the starter and keep normal launch
   available. Launch the game again afterward.
4. Open **F1 > Debug > Collect pipelines** with supported collection settings
   (720p or 1080p, 16:9, anisotropy 16, smooth colour enabled). The game should
   restart into collection. Visit a few dealerships or other scenes, then close
   the game. Verification should start afterward, showing its current stage.
5. Cancel verification once and close its result window. Run **Resume pipeline
   verification.cmd**, or start **Verify last collection** from F1 Debug.
   Successful verification should show verified/pending totals and a share-file
   path. Pending records are allowed; they are not silently accepted. Share only
   the named metadata template, never the private recorder or cache directories.
6. Change a video setting and use the normal settings restart. Check that only
   one game remains and that the saved setting applies to the replacement.

Record any failure together with the candidate ZIP checksum and the relevant
storage logs. Keep interrupted caches and verification files for diagnosis.
No upload, release tag or publication happens through these local tool actions.
