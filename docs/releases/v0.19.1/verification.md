# v0.19.1 verification

Scope (owner request): Auto matchmaking is a sidebar mode peer (6th entry after
Highlights) with its own main page instead of a Settings tab; first-use notes
("注意事项") are the first sidebar entry, open automatically until the user
acknowledges them (`prefs.notes_seen`, can only be set true), and hold the
recording and auto-matchmaking notes. No recording/queue/watcher logic changed.

## Local evidence (Linux, headless Chromium)

- Full suite: 412 passed, 14 failed, 7 skipped; the 14 are the same
  environment-only FFmpeg/Windows-process failures as the v0.18.1 baseline.
- New browser tests: auto mode is the sixth `.modes` tab, not a Settings tab,
  selection/visibility switch correctly, choices post to `/api/auto-mm`;
  first use opens the notes page, notes entry is the first sidebar child above
  the modes, acknowledging stores `notes_seen` and the notes stay closed after
  reload. Theme text audit covers the auto and notes pages.
- Screenshots checked at 1920 and 900 px.

## Published package

Filled in after the Windows workflow completes.
