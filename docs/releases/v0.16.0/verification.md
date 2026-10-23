# v0.16.0 verification

Journeys came from the user's request: see the expected result before recording,
find finished videos, and see the weapons used in each round in all five modes.
The cancelled AI editor is not included.

## TDD evidence

| Guarantee | Test target | RED | GREEN |
| --- | --- | --- | --- |
| Timed weapon events, POV exclusions, round lengths, optional cache upgrade, durable catalog and selection estimates | test_recording_details.py, test_recordings.py, test_preflight_frontend.py | 6 failed; 1240af2 | 6 passed in 0.87s; 23f582a |
| Real UI shows estimates and weapons; library search, English and responsive layout | test_preflight_browser.py, test_workspace_browser.py | Missing .preflight reproduced in private Chrome; 59b0622 | 3 passed in 8.17s; e7a8976 |
| Bad history does not crash; profile uses job-start FPS; suicide classified as death | test_recordings.py, test_preflight_frontend.py | 3 failed, 3 passed; 99b4fba | 8 passed in 1.06s including details; 18646df |
| Multi-demo history keeps actual map names for search | test_recordings.py | 1 failed; f8f8e35 | 43 passed in 2.15s including existing queue tests; d6cb65d |
| Malformed optional map entries do not block completed jobs | test_recordings.py | 1 failed, 1 passed; 764e7d4 | Final affected target: 62 passed in 11.49s |

All checkpoints are on the active task branch and reachable from HEAD. A backend
fixture was corrected to give the attacker a living POV; its original accidentally
killed that attacker before the event. No production code was deleted for RED.

Affected checks after implementation: **66 passed in 19.80s**. These include the
real HTTP Host rejection for /api/library, queue clearing and disk persistence,
profile sampling, legacy cache reuse and upgrade, Node selection calculations,
and the actual Alpine frontend in private Chrome.

Full local regression: **362 passed in 459.83s** before the last small catalog
hardening. Final affected target (recordings, details, Node selection, browser,
existing queue and HTTP security): **62 passed in 11.49s**. Final release CI runs
the complete final collection; valid earlier results are reused for unchanged code.

Python compileall, app.js syntax and git diff checks passed. Director simulation
passed all 25 assertions without launching the game. Private-browser screenshots
of the whole-match page, kill page, library and dark theme were produced; browser
assertions verify 1920px layout and absence of horizontal overflow at 900px.

Local Edge exited at startup; browser validation used installed Chrome with its
own temporary profile. No user's existing browser tab, installed PovForge window
or native window was controlled during these checks.

## Limits and safety

- No CS2/HLAE launch or game/Steam settings edits. Capture calls in tests are mocked
  or use synthetic/placeholder footage. No live recording claim.
- Estimates use default round bounds and chronological merged windows, including
  both duel POVs. Optional replay/style time is excluded and explained in both
  languages. No measured-PC estimate is invented before three compatible samples.
- Catalog writes/probes are optional and bounded; failure does not fail a video.
  Listing neither probes every old file nor reparses Demos. Unknown metadata stays
  unknown, and moved/deleted files are labelled without changing them.
- Names/events render with Alpine x-text. No generated HTML, arbitrary command,
  upload, API Key, AI service or new file-serving route was added.
- Coverage, Ruff and Pyright are unavailable locally; no coverage percentage, lint
  or type-check result is claimed. Release CI runs final tests and packaged-app
  install/update/uninstall checks separately.
