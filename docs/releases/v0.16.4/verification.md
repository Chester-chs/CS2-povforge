# v0.16.4 verification

Journeys were derived directly from the user's request. No external plan was used.

| Guarantee | Evidence |
| --- | --- |
| Public recording options show a one-line switch and no historical-player paths | Real isolated-browser test in `test_player_folder_navigation.py` |
| Whole-match/reel destinations follow selected players, including both duel players | Same browser test; custom path retained, match-list return hides stale players |
| Sidebar folders expand/collapse, filter contents and return to all videos | Same browser test against configurable fake library API |
| Windows case/slash variants group together, similar prefixes stay separate, custom/empty/legacy folders work | Node evaluation of actual app.js in `test_player_folder_navigation.py` |
| Folder, mode and search filters combine; folder text is black/white in light/dark | Node assertions and browser computed styles |
| Default kill padding is 5s/3s; overlapping multi-kills remain continuous and boundaries are clipped | `test_reel_timing_defaults.py` |
| Highlight rounds retain the entire first-to-last-kill interval | Mocked `_cut_points` using real default config |
| Preflight uses the same 5s/3s solo/highlight windows | Node app.js assertions compared to backend window results |

RED: the new target ran and failed 6 tests in 9.51s. Folder grouping was absent,
the public panel showed two historical players, and default cuts still used
4s/1.5s. Checkpoint: `2b4bac3`. GREEN: the same target passed 6 tests in 2.55s;
checkpoint `9950af3`.

Affected regression command (local Chrome override only, private temporary profiles):

```powershell
.venv/Scripts/python.exe -c "from pathlib import Path; from povforge import cdp; import pytest; cdp.find_browser=lambda:Path('C:/Program Files/Google/Chrome/Application/chrome.exe'); raise SystemExit(pytest.main(['tests/test_player_folder_navigation.py','tests/test_reel_timing_defaults.py','tests/test_workspace_browser.py','tests/test_preflight_browser.py','tests/test_theme_text.py','tests/test_text_contrast.py','tests/test_event_reels.py','tests/test_first_person_reels.py','tests/test_highlights.py','tests/test_recordings.py','tests/test_recording_details.py','tests/test_event_reels_frontend.py','tests/test_gui.py','-q','--tb=short']))"
```

Result: **88 passed in 32.35s**, including all-view light/dark/auto text audits,
eight accent variants, recording requests and existing destination/capture logic.
`node --check`, Python compilation and `git diff --check` passed.

Full local regression ran 376 cases: 374 passed and two failed in 200.28s. Both
failures were old timing expectations: the Node preflight fixture still expected
4s/1.5s, and the synthetic camera-composition fixture expected a 5.5s main clip
instead of all 6s available under the new 3s tail. Updated explicit expectations
to the independently calculated 5s/3s intervals and 6s + 1.15s ending replay. The
same fixture still verifies the blue victim replay by decoding an actual frame.
No production change was needed. Re-running both affected test files plus the
new feature tests passed **17 tests in 23.03s**. Valid results for unchanged code
from the full run are retained; the release workflow runs the entire suite again.

Private 1920×1080 browser previews of the public panel, selected-player page and
light/dark folder library were visually inspected. These use fake API data and
temporary browser profiles, separate from the installed app and user settings.

Coverage, Ruff and Pyright are not installed locally; no coverage percentage,
type-check or lint pass is claimed. Recording tests use mocks; development never
launched CS2/HLAE or changed game/Steam settings. Explicit Highlight pace choices
still override default timing; whole-match timing and actual capture behavior
remain outside this task's live verification.
