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

Filled in after the Windows workflow completes.
