# Recording options and workspace verification

Journeys derived from the user's requests in this conversation.

| Guarantee | Evidence | Result |
|---|---|---|
| App output remains 1080P, old high-resolution selections migrate, FPS uses presets | test_output_limits.py, test_gui.py, test_gui_security.py | RED then GREEN |
| A player can choose a persistent folder, cancel without changes, or restore the ID folder | test_gui_security.py | RED (missing endpoint) then GREEN |
| A first recording creates its destination directory | test_gui.py::test_job_config_names_the_videos_folder | RED then GREEN |
| Selected-round totals follow player/round changes; duel totals count mutual encounters separately | test_selection_stats.py | RED (missing totals) then GREEN |
| Mode order keeps highlights last | test_workspace_browser.py | RED then GREEN |
| Browser layout supports full-screen columns, narrow windows and readable help spacing | test_workspace_browser.py | GREEN |

Checkpoints: 00358ba (quality, folder, totals RED); 800b4dc (layout test);
6fe0dd2 (mode order RED); 731f85c (directory creation RED).

Commands run: `.venv/Scripts/python -m pytest -q --tb=short` (340 passed in
277.80s); affected tests after final refinements (31 passed); browser-specific
check (passed); `node --check povforge/gui/static/app.js`; `node tests/director_sim.js`
(25 assertions passed); `git diff --check`.

Native WinForms/WebView2 preview used an isolated fake API, never the real App or
game discovery. Normal/maximized appearance and the white slider track were
visually checked. Real CS2 recording was not run. Coverage tooling is not installed;
no percentage claimed. Type-check/lint commands are not configured. Release CI
checks the full final suite, build, installation, incremental update and native host.
