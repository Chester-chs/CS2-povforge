# v0.18.0 verification

Scope: recording preflight, named recording presets, local diagnostic export,
and optional completed-video sample checks. Journeys were derived from the
agreed remaining feature list. No CS2/HLAE launch or game/Steam setting edit
was performed. No runtime dependency was added.

## TDD checkpoints

| Guarantee | RED evidence | GREEN evidence |
| --- | --- | --- |
| Named profiles exclude destinations/identities; storage/environment checks; diagnostic redaction; video samples and cached reports | 11 failed; d917907 | 11 passed in 16.74s; f1eb281 |
| Authenticated routes, native-picker cancellation, library allowlist and quality/queue serialization | 5 failed; fdb9d2d | 27 related checks passed in 12.07s; 6b6caea |
| Real frontend profile/check/diagnostics/quality journey | 1 failed; 0861d4d | 3 browser/frontend checks passed in 9.44s; 0dd1134 |
| Queue preflight tolerates conditions owned by the current recording; new theme states | 1 failed; ba9d670 | 7 HTTP/theme tests passed in 12.98s; 45c4082 |
| Oversized quality reports preserve previous file; sample decoding errors are not called clean | 2 failed; cebd694 | 7 passed in 1.47s; 3ecee83 |
| Worker thread startup failure releases pending reservation | 1 failed, 1 passed; 4951643 | 10 quality/queue tests passed in 2.91s; 44078bc |
| Malformed preflight selections are rejected before probing | 1 failed; 8c09123 | 6 HTTP tests passed in 4.67s; 268017c |

Checkpoint commits remain on the working branch. Native-window test fixture
now supplies the new checker close interface. The browser fixture waits for
check submission before delivering the completed result, eliminating a race
where its delayed response removed the finding immediately before clicking.

## Verification

Initial full local regression: **414 passed, 2 failed in 591.88s**. Both failures
were the test fixture issues above. After their corrections and final boundary
checks, **35 related tests passed in 29.84s**, including the real native WebView2
host, synthetic-video checks, all new HTTP routes and the player journey.
Valid results for unchanged code are reused. The release workflow runs the
entire final suite again before packaging.

Command used for the full local run:

```powershell
.venv/Scripts/python.exe -c "import platform; platform.machine=lambda:'AMD64'; from pathlib import Path; from povforge import cdp; cdp.find_browser=lambda:Path('C:/Program Files/Google/Chrome/Application/chrome.exe'); import pytest; raise SystemExit(pytest.main(['-q','--tb=short']))"
```

The local test process uses the previous WMI workaround and private Chrome
profiles; production browser/native-window discovery is unchanged. Native
window testing uses an isolated fixture page, not the user's installed app.

- `test_record_profiles.py`: same-name replacement, invalid names/modes/weapons,
  applying options without changing current destinations or launching jobs.
- `test_preflight_checks.py`: writable ancestors for not-yet-created folders,
  low free space, permission errors, file/directory collisions, environment
  states. Disposable probes do not create player folders or modify game files.
- `test_diagnostics.py` / HTTP: paths, Steam IDs, names, email, URL queries and
  credential lines are redacted; unique local JSON exports; cancel writes
  nothing; client-supplied output paths are ignored.
- `test_video_quality.py`: real synthetic H.264 black/static video, missing
  audio, missing/invalid video metadata, sample offsets, stale cache rejection,
  bounded reports, worker deduplication, startup failure, owned decoder timeout
  cleanup. No gameplay recording is involved.
- `test_quality_queue.py`: checks reserve the queue before the next job;
  per-task automatic-check choice survives later preference changes.
- `test_recording_tools_http.py`: all mutations require same-origin CSRF;
  manual checks accept only known library movies and reject active recording;
  listing performs no mass decoding. Bad preflight selections return 400.
- `test_recording_tools_browser.py`: actual production UI actions for save/apply,
  unchanged output destination, blocked submission, local diagnostic export,
  check status and timestamp navigation; 900px overflow check.
- `test_theme_text.py`: 20 views/states across light, dark and both Auto paths
  (80 audits), including expanded preset inputs, preflight findings and quality
  results; existing 16 accent/theme button-contrast checks remain.

Python compilation, `node --check` and `git diff 06f4811 --check` passed.
Coverage, Ruff and Pyright are not installed locally; no coverage/type/lint pass
is claimed. Private 1920px light/dark preflight and quality previews were viewed.

## Security and practical limits

Profile values are validated and whitelisted, bounded to 20 names, and saved
using existing atomic preferences. They contain no destinations, player IDs,
API keys or executable commands. Diagnostics use a native folder choice and
exclusive unique-file creation; nothing is uploaded. Recent log data is bounded
and conservatively redacted. Users can inspect JSON before sharing.

Preflight is advisory for free-space capacity (512 MiB hard floor, under 8 GiB
warning); it cannot predict every raw capture's size. Startup repeats storage
checks using saved task options. Existing recording/cancellation settings
protection remains unchanged. No new game-start path was introduced.

Quality checks sample at most 45 seconds, downscaled to 320px at 5 FPS; format
and audio metadata are checked separately. FFprobe and each sample decoder have
timeouts, run without a shell, and can only be killed through their owned process
handle. Black/freeze detections are possible issues, including intentional still
shots; absence of a finding is not whole-video validation. Reports are bounded,
atomically saved separately from work files and tied to video size/mtime.
Checks run serially before the next queued recording and never delete videos.
Legacy videos can be checked manually without reparsing their Demo.
