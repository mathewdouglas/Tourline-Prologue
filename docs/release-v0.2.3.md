# Tourline Prologue v0.2.3

This update expands optional shader preparation and adds player controls for
learning and verifying pipelines from your own play sessions.

- The starter now contains **5,669 verified observed pipelines**, including
  dealership and subsequent player collection, with matching original-program
  lookup maps. Observed menu/race warmup membership is retained; newly added
  keys without observed membership stay on the demand path. Coverage is partial.
- Preparation retains completed additional-translation fragment chunks through
  cancellation. Resume checks saved work before reuse. Smaller chunks provide
  progress between compiler jobs; normal compiler limits remain unchanged.
- Retained preparation generations no longer hit the old fixed 100,000-entry
  scan limit. The bounded scan allowance now follows catalogue capacity and
  retained generations, keeping link and ownership checks in place.
- Offline preparation explicitly flushes batch-completion output before the
  engine exits. Completion/native-key checks remain strict; incomplete runs
  retain their work and do not select an unverified cache.
- Bounded parallel reads reduce cached preparation overhead. One local full
  4,450-record pair measured 261.34 seconds with serial reads and 202.52 seconds
  with four readers. This is a cached preparation result on one machine, not a
  first-time compilation or gameplay performance guarantee.
- F1 **PC Settings > Debug** provides **Collect pipelines**, **Verify last
  collection** and **Prepare shaders**. Each action closes the current game
  before the launcher starts the requested tool. Preparation/verification leave
  the game closed afterward; launch normally to play again.
- Collection verifies after play against your original game files, reconstructing
  both shaders and checking exact native pipelines in a separate local cache.
  A window styled like the precompiler shows progress, cancellation and results.
  **Resume pipeline verification.cmd** continues interrupted verification.
- Only successfully verified metadata is exported as a shareable template.
  Unresolved records remain private and pending. Nothing is uploaded automatically;
  maintainer acceptance is still required before adding records to the starter.

Extract the complete ZIP into a separate folder and run **tourline-prologue.exe**.
Keep the matching launcher, runtime and preparation helper together. Existing
storage, saves, settings and caches are retained. Preparation remains optional;
normal launching is available without it. Use your own supported BCUS98158
v03.00 disc files; no game data or shader/driver cache is supplied.

Collection currently supports the documented default 720p/1080p 16:9,
anisotropy-16, smooth-colour context. Automatic preparation selects supported
saved translation modes; this does not enumerate every resolution, MSAA mode,
car, course or camera. Driver pipelines are prepared locally for your GPU.
Verification can take minutes, especially for newly discovered programs.

Normal asynchronous rendering policy is unchanged. The texture-retention
experiment remains outside the shipped runtime patch. Car/reflection and
rolling-start camera hitches are not claimed solved; prepared key coverage
does not guarantee first-draw readiness or zero stutter.

For troubleshooting, `GT5P_PREPARE_IO_WORKERS=1` restores serial preparation reads,
`GT5P_PREPARE_FRAGMENT_CHUNK=4096` restores larger additional-translation chunks,
`GT5P_OFFLINE_FLUSH=0` restores historical offline exit flushing,
`GT5P_PIPELINE_TOOLS=0` disables F1 tool handoffs, and
`GT5P_COLLECT_VERIFY_UI=0` uses console verification. These controls preserve
existing caches. `tourline-prologue.exe --no-prepared` bypasses selected preparation.
