# POVForge handoff — 2026-10-20

## Current agreed scope

The owner cancelled camera imitation and third-person recording. Highlight
reels always use the selected player's first-person view. Keep the separate
optional victim replay switch, off by default: record all main highlights,
then append victims' first-person views in the main reel's kill order. Never
interleave these replays. Style imports and preset changes preserve this choice.

Reference-video editing styles (pace, transitions, grading, effects and titles)
remain supported. Legacy follow/orbit/wide preferences are ignored. Custom
camera math, camera-style detection and map collision extraction were removed.

## Project and recording flow

Repository: https://github.com/Chester-chs/CS2-povforge

Python application with an Alpine.js UI. `pipeline.py` parses the demo, records
and publishes whole-match POVs. `reel.py` selects kill moments, records any
requested victim clips in one additional session per demo, then composes the
main moments followed by replays. `camera.py` now only normalizes legacy
preferences, plans real victim events and renders ending replays.

`hlae.py` validates all extra clips as first-person and caches them using source,
settings and director signatures. `director.js` seeks and locks the requested
player in native first person; it rejects third-person requests and stops if
the target changes during recording. Missing target information must never
silently substitute another player's view.

`effects.py` keeps kill effects on the main highlights. `style.py` handles
reference editing styles. `gui/static/app.js` owns the independent victim
checkbox and migrates saved camera preferences.

## Settings safety

Do not change the owner's persistent CS2 settings. Preserve `settings_guard`
backup/restoration, including startup failure, cancellation, temporary CFGs and
owner-process locking. Restoration must finish after CS2 exits before reporting
successful recording. Do not launch CS2 just to run the automated tests.

## Verification and historical sample

Run `python -m pytest -q` and `node tests/director_sim.js`. FFmpeg integration
tests check actual frame colours, ordering and audio timing. Recording tests
use a fake external game and real isolated settings files.

Earlier on 2026-10-20, real Dust2 round 21 recordings covered first-person-only
and first-person-plus-victims output. All 52 audited CS2 settings files matched
their pre-test bytes. Local evidence remains under
`packaging/dist/camera-real-test-final/` (ignored by Git). These tests preceded
the final removal of third-person code; the simplification was tested without
relaunching CS2. Old camera-test ZIPs are historical and are not this source
revision's build.

Version is 0.15.0. A source push does not publish an installer. The Windows
workflow builds releases on version tags or manual dispatch. The owner has
authorized publishing this feature update to GitHub.

## 2026-10-22 feature update

- All new output is capped at 1920x1080 and 60 fps. Legacy high-resolution
  preferences migrate; cached oversized clips/parts are normalized. No extra
  4K upload copy is produced.
- New content modes: deaths only, kills plus deaths, and opposing-player
  duels. Solo events always use the selected player's first person in round
  order. Duels include mutual kills only, each encounter A then B, with a swap
  control. Duel mode does not append a third victim replay. `reel_events.py`
  validates selections before recording and keeps actual kill anchors separate
  from deaths. Exit events belong to the round just played.
- Reference import now previews the source, accepts a selected time range and
  effect description, displays a supported partial proposal, then requires an
  explicit Apply. Common editing effects are template approximations. The
  supplied Bilibili example could not be downloaded in this environment;
  object-tracked knife rings are unsupported, not silently approximated by a
  full-screen filter.
- Optional music synchronization selects a continuous excerpt from the full
  song using onset strength, energy and the final Demo kill timeline. It does
  not identify a semantic chorus or guarantee every kill lands on a beat.
- Automated verification: 255 tests passed; browser UI and real Demo event
  parsing were checked; FFmpeg tests verify actual output/order. New event
  modes have not been recorded in live CS2. No persistent CS2 settings were
  changed during this update.
