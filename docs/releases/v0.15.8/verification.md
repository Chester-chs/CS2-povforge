# v0.15.8 verification

## Scope

Expand the reel editor after Continue; expose Style only in Highlights; expose
Victim perspective in every reel mode except whole-match recording; select
individual kills and insert victim replays inline or explicitly at the end.

## RED checkpoint

Commit `739607d` on `codex/camera-simulation` adds the initial regression cases.
Executed `.venv/Scripts/python.exe -m pytest tests/test_inline_replays.py tests/test_workspace_browser.py -q`:
**6 failed**, caused by missing inline placement/selection helpers and the existing
700px editor at a 1920px viewport. No production code had changed at that point.

## Behavior and evidence

| User guarantee | Verification |
| --- | --- |
| Editor fills the desktop workspace | Real HTML browser geometry at 1920px; native WebView2 maximized preview |
| Style only in Highlights | Browser mode switching; event request payload and backend style filtering |
| Victim toggle works in each reel mode | Browser checks across all modes; event/duel pipeline routing |
| Choose individual real kills | Browser checkbox and submitted selection checks; compressed-source identity; forged/unselected entries cannot trigger capture |
| Insert after kills and resume | Real FFmpeg composition: 80 main frames plus two 23-frame replays = 126 frames; red/blue pixel samples verify placement |
| Matching replay sound | Source has 440 Hz, victim capture 880 Hz; final replay audio measures 440 Hz |
| Preserve event/duel order | Ordered source spans route each encounter without regrouping A/B during assembly |
| Keep ending placement | Existing ending-replay integration tests explicitly select `placement: end` |
| Preserve independent preferences | Style import, mixing, reset, save and reload tests; camera choice remains independent |

## Validation boundaries

No CS2/HLAE game process was launched and no owner game settings were changed.
Game capture was mocked; generated video/audio was rendered with real FFmpeg.
The native preview used an isolated fake API and state directory; the installed
user application was not manipulated. Demo summary cache version remains 4.

Python compilation and JavaScript syntax checks passed. Director simulation:
25 assertions passed. No configured type/lint commands or installed coverage,
Ruff or Pyright are available; no coverage percentage is claimed. Targeted input
review confirmed that selection strings only filter known parsed victim events;
they do not supply a capture target, path or shell command. UI names use x-text.

Final test and release results are recorded in HANDOFF and the release CI run.

## GREEN results

Full local regression: **350 passed in 160.86s**. After collection, three more
selection-security cases were added; the full inline target passed **12 tests in
13.10s**, including these cases and compressed-source identity. Relevant old
effects/first-person contracts passed **31 tests in 44.81s**. Browser/payload
checks passed **3 tests in 6.51s**. No production changes followed the final suite.
GitHub release CI also runs the complete collected suite before packaging.
