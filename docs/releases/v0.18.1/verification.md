# v0.18.1 verification

Scope: interface/folder UX only. Folder rules and preflight moved to Settings →
Saving & folders; the recording panel shows the task's actual destination
(duel = player A, several players = multi-player folder, matching
`videos_folder`); new-install default output `Videos/职业选手POV`; sidebar and
recording panel scale at 1440/1800/2300px; toolbar/toast follow sidebar width;
library mode chips with counts; library search icon fixed. No recording,
parsing, cache, queue or game-settings code changed. No CS2/HLAE launch.

## Local evidence (Linux, headless Chromium)

- Baseline before changes (b7f29a9): 401 passed, 14 failed, 7 skipped.
- After changes (5ca60f9): 401 passed, 14 failed, 7 skipped. The same 14
  tests fail before and after: FFmpeg-filter, Windows-process and replay
  composition cases that depend on the Windows CI toolchain, not the UI.
- Updated/added UI assertions: by-player switch and preflight live in Settings;
  duel shows one destination (A); multi-player reel shows the multi folder;
  Settings lists known player folders; mode chips count per folder/search and
  treat unlisted modes as existing videos; new-install default folder.
- Theme text audit now covers the Saving & folders tab (four theme paths).
- `node tests/director_sim.js` passed.
- Screenshots checked at 1280, 1920 and 2560 px wide (reel editor, Settings,
  video library).

## Published package

Filled in after the tagged Windows workflow completes.
