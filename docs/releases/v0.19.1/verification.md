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

- Source: `b7b44d40821acd5a2e7db0deac70467f3752b7cd` (main), manual dispatch
  `release: v0.19.1`.
- [Release](https://github.com/Chester-chs/CS2-povforge/releases/tag/v0.19.1)
  published 2026-10-27T21:20:54Z; public, latest, both assets uploaded.
- [Windows workflow](https://github.com/Chester-chs/CS2-povforge/actions/runs/40584861866):
  **409 passed, 24 skipped in 110.99s**. Build, bundled FFmpeg, smoke, installer,
  incremental update, native WebView2 window and uninstall checks passed.
- Installer: 139386926 bytes; SHA-256
  `4706ebc53ee574b17adead5308224c57e8e2e520aed93ba607ef8f31e2e0d67f`.
- Portable ZIP: 218466417 bytes; SHA-256
  `793ea24b93c2bc5ecf93a1e3d48123904a8f59e0b035e056bae4fc67cc0ac8ae`.
