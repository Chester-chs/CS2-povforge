# v0.20.0 verification

Scope: record each player with their own look. `pro_settings.py` parses the
structured tables of a prosettings.net player page (allow-listed cvars only);
`demo.player_crosshair` reads the player's crosshair share code from the demo;
`hlae.for_player` applies per-player window size (4:3 recorded at 1440×1080),
fit (stretch/pad) and console commands inside the recording session;
`mux_take` stretches or letterboxes takes to the 1920×1080 video. Looks are
cached for a week in `player-looks.json`; per-player link/off overrides in
prefs. Quality cache keys change only when a look is used.

Tests (`tests/test_player_look.py`): FalleN fixture → 1440×1080 stretch,
viewmodel/crosshair/bob/HUD commands, visitor comment codes ignored, mouse and
graphics settings not applied; command allow-list rejects injection; launch
uses the window size; real FFmpeg stretch to the video size with square pixels;
job config round-trip; cache/offline/off/404 handling; duel records both
players' looks; recording-panel UI.

Local full suite: 420 passed, 14 failed, 7 skipped (the same 14 environment
failures as earlier releases). Not checked in real CS2: whether demo playback
draws the observed crosshair with `cl_show_observer_crosshair 2` /
`apply_crosshair_code`, and the `cl_hud_color` value mapping.

## Published package

- Source: `687114fb81e9e1ddc19ec3d4d89ad924ddc20b19` (main), manual dispatch
  `release: v0.20.0`.
- [Release](https://github.com/Chester-chs/CS2-povforge/releases/tag/v0.20.0)
  published 2026-10-27T22:20:21Z; public, latest, both assets uploaded.
- [Windows workflow](https://github.com/Chester-chs/CS2-povforge/actions/runs/40592860933):
  **416 passed, 25 skipped in 120.67s**. Build, bundled FFmpeg, smoke, installer,
  incremental update, native WebView2 window and uninstall checks passed.
- Installer: 139418744 bytes; SHA-256
  `ed9c1ec8b189373d989935d52db3841cd7f06a4f9a7ab0a6bfb5870f8272c5f0`.
- Portable ZIP: 218481904 bytes; SHA-256
  `4c01037034c7a2630ef266c250e9ca12c26e5e8a309d9a70e733ddbfa9b40a72`.
