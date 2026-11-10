# Background preparation status

The launcher shows a small, click-through status at the bottom left of the game
while its background preparation helper is running:

| Status | Meaning |
| --- | --- |
| Preparing shaders in background | The helper is running, including its asset checks and preparation stages. |
| Shader preparation paused during race | The watcher has suspended the helper's processes for racing. |
| Shader preparation complete / Ready for your next launch | The helper has exited successfully. Its full cache is selected for the next launch. |
| Shaders ready for next launch | The quieter status after eight visible seconds of the completion notice. |
| Background preparation incomplete / You can keep playing | The helper exited unsuccessfully; this never masquerades as success. |

Completion and incomplete notices are hidden while the race event is set.
Completion waits until that event clears on returning to menus. Minimizing or
switching away hides the overlay and does not consume its eight visible seconds.
The ready status stays in menus for the remainder of this launcher session.
Settings restarts retain the helper and notification state; the overlay follows
the new game window. Quitting still cancels at a checkpoint and preserves work.

Race pausing remains on by default: the renderer arms at loading, sets the event
at grid Start (or its existing timeout), and clears it in menus. Results and
replays remain in that race interval. With the pause rollback off, the event is
still observed for notification deferral, but the helper continues running and
the status correctly remains Preparing rather than Paused.

Controls:

- `GT5P_PREPARE_BACKGROUND_INDICATOR=0` hides the new status/notification only.
- `GT5P_PREPARE_BACKGROUND_PAUSE=0` disables race suspension only.
- `GT5P_PREPARE_BACKGROUND=0` disables background preparation, as before.

The existing Compiling shaders / Loading shaders badges still describe the
renderer's own work. This indicator describes the separate preparation helper;
it does not guess a whole-job percentage from stage-local counts. It is not a
modal dialog, takes no input/focus, and creates no taskbar entry. It appears only
over the foreground, non-minimized game launched by this launcher.

Implementation is in `launcher/background_preparation_ui.h` and the existing
launcher watcher. The watcher reads the owned helper's exit status, not an
intermediate Complete line in `prepare-status.txt`. No engine/runtime, template,
prepared-cache identity, shader key or helper selection/publication rule changes.
Only the launcher needs rebuilding. View transitions are recorded in
`logs/prepare-background-status.txt` for the current helper session; existing
pause and preparation logs remain available.

Validation is recorded in progress Phase 236. It includes native pause/resume,
restart ownership, deferred completion, failure and indicator rollback checks,
plus real-game window integration with a controlled timed helper. That last
check validates presentation, not a new full-preparation speed or hitch claim.
