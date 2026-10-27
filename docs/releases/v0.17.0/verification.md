# v0.17.0 verification

Scope: persisted queued tasks, weapon filters with continuous mixed streaks,
and in-library playback with finished-video event seeking. Journeys came
directly from the user's request. No CS2/HLAE launch or game/Steam setting edit
was performed. No additional runtime dependency was introduced.

## TDD checkpoints

| Behavior | RED evidence | GREEN evidence |
| --- | --- | --- |
| Restart restores tasks paused with original options | 5 failed; b9f3d68 | 55 related tests passed; b0916d5 |
| Weapon filtering preserves merged mixed sequences and queue/spec payloads | 8 backend + 1 Node failed; ec9f4d0 | 33 passed in 26.43s; b0c9cdb |
| Source/output indexes and private Range playback | 5 failed; 4ca9f93 | 17 passed in 1.94s; 909332a |
| Recovery notice, weapon controls, actual video seeking | 1 browser failed; 833f7c0 | Real synthetic-video browser journey passed; 7d39f26 |
| Retained-kill labels and exhausted recovered queue | 2 failed, 5 passed; f4ad2ba | 7 passed in 0.89s; 4333125 |
| Victim replay choices follow retained kill windows | 1 failed, 7 passed; 62b7727 | 13 passed in 1.69s; 623a221 |
| Missing Demo leaves remaining recovered tasks resumable | 1 failed, 7 passed; ebb39a5 | 51 queue/lifecycle/GUI tests passed in 2.92s; 126051b |

Checkpoint commits are on the current branch and retained in the task sequence.

## Guarantees

- `test_queue_recovery.py`: no startup recording; queued/running task recovery;
  saved selections/options/effects; remove/clear/retry persistence; corrupt or
  unsupported snapshots cannot launch tasks; failed atomic replacement keeps
  the previous file. A later assertion exercises real job preparation with a
  mocked process launcher: saved 120 FPS is used while current 60 FPS app
  preferences remain saved. All test storage is isolated.
- `test_weapon_filter.py` and `test_weapon_filter_frontend.py`: normalization,
  invalid-input rejection, queue/spec round trips, merged 5s/3s windows,
  mixed-weapon preservation, unrelated-window exclusion, duel A/B order,
  estimates, labels, displayed weapons and replay choices agree. Highlights
  retain the entire matching first-to-last-kill round sequence.
- `test_video_index.py`: actual seek origin, inline replay offsets, intro,
  slow motion, overlap timing, source weapon/death metadata, publication and
  stale/malformed index handling. Indexes remain outside work-file cleanup.
- `test_library_player_http.py`: CSRF and Host boundaries, opaque handles,
  exact and suffix byte ranges, invalid-range rejection, unknown/outside-path
  rejection, and invalidation when a registered file changes.
- `test_library_player_browser.py`: generates a real H.264/AAC test video,
  renders the production frontend, opens the player, waits for completed seeks
  to kills/deaths and Previous/Next targets, verifies playback stops on leaving,
  and checks 900px overflow plus readable dark-mode text. The fake API serves
  byte ranges like the production stream endpoint.
- `test_reel_cameras.py`: a real synthetic composition has a kill marker at 4s
  and ending replay at 6s; the existing frame-color assertion still verifies
  the replay content. The HLAE recorder is mocked.
- `test_theme_text.py`: includes the player in 18 views/states across light,
  dark and both automatic-theme paths (72 audits), plus 16 accent/theme cases.

## Runs

Full regression:

```powershell
.venv/Scripts/python.exe -c "import platform; platform.machine=lambda:'AMD64'; from pathlib import Path; from povforge import cdp; import pytest; cdp.find_browser=lambda:Path('C:/Program Files/Google/Chrome/Application/chrome.exe'); raise SystemExit(pytest.main(['-q','--tb=short']))"
```

**397 passed in 184.92s**. Subsequent additions for live preference preservation
and filtered replay selection passed a 13-test target. Final completed-seek
browser/filter/recovery target: **9 passed in 4.89s**. Valid results for unchanged
code are reused; the release workflow runs the full suite again.

The local test process overrides platform.machine after a Windows WMI resource
error during import. This affects only test-process hardware discovery. Browser
tests use private Chrome profiles because the local Edge startup is unreliable;
production browser/native-window selection is unchanged.

`node --check`, Python compilation and `git diff --check` pass. Coverage, Ruff
and Pyright are not installed locally; no coverage/type/lint pass is claimed.
Private 1920px light/dark player previews were visually inspected. Native
controls and event navigation remain usable at 900px.

## Scoped security review and limits

New playback sessions require the existing same-origin CSRF-protected POST.
Media GETs enforce Host checks and accept only random, expiring handles for
known library files, never a raw client file path. Handles are bounded to 16
and file size/mtime signatures are checked. Indexes are bounded JSON, stat-bound
and rendered with text bindings. Task JSON is validated, bounded, flushed and
atomically replaced. No commands, secrets, accounts or external API calls were
added. Existing whole-match/cancellation/settings-protection behavior is reused.

Recovery covers queued tasks, not an unsubmitted editor draft or resuming at
the exact interrupted frame. Missing/invalid recordings still need recording.
Legacy videos can play without indexes; legacy cached recordings may expose
only the kill events available in their existing metadata. Codec support is
provided by the embedded browser, with a system-player fallback. Live game
capture has not been exercised in this task, per the user's constraints.
