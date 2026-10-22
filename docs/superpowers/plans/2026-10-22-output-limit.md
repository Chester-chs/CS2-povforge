# 1080p output limit implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Limit all newly produced recordings and videos to 1920 x 1080 and 60 fps, and remove the extra upscale copy.

**Architecture:** Normalize recording settings at configuration and pipeline boundaries. Normalize reused clips when cutting/composing, including cached parts. Retain parsing of the old upload setting only so existing configuration files remain usable.

**Tech Stack:** Python, FFmpeg, Alpine.js, pytest.

**Spec:** User request of 2026-10-22, item 1: maximum 1080p, 60 fps; no 4K output.

## Global constraints

- Never change persistent CS2 settings.
- Preserve old videos and reusable source recordings on disk.
- Keep ordinary first-person highlights and optional victim replays.
- Work sequentially; other requested features are tracked separately below.

## Review focus

- Saved preferences containing 2160/120 and upload_4k must migrate safely.
- TOML settings and programmatic callers must also respect the ceiling.
- A cached recording or composed part above the ceiling must not leak into a new output.
- Mixed cached resolutions/frame rates must produce compatible joined clips.
- Lower-resolution screens and explicitly smaller output must remain supported.

### Task 1: output settings and legacy migration

Files: povforge/media.py, hlae.py, config.py, gui/server.py, gui/static/app.js, gui/static/index.html; tests/test_output_limits.py and tests/test_gui.py.

- [x] Add failing tests for 4K/120 legacy configuration, saved preferences, screen fitting and recording settings.
- [x] Add bounded output sizing and recording normalization; disable legacy upscale and remove UI/progress controls.
- [x] Run `.venv/Scripts/python.exe -m pytest tests/test_output_limits.py tests/test_gui.py -q`.

### Task 2: encoding and cached media

Files: povforge/compose.py, extras.py, reel.py, pipeline.py; tests/test_output_limits.py, tests/test_effects.py.

- [x] Add an FFmpeg test that uses an oversized 120 fps source and verifies the plain output size/frame rate.
- [x] Cap cut/composition output and invalidate incompatible cached parts; remove upscale production.
- [x] Verify new media with ffprobe and run related composition/reel tests.
- [x] Update README and example configuration, then run full regression tests before reporting completion.

## Other requested work (not implemented by this plan)

- Reference effect window: preview, select time range, describe desired effect, propose supported implementation, explicitly apply after user confirmation. Approved in chat.
- Reference example: BV1LHpY62EdG at 01:43, red effect around knife. Reproduce download/analysis separately; do not substitute a global filter for object tracking.
- Background music: analyze the full track and align with Demo kill times. Approved in chat.
- Kills/deaths chronological reel and opposing-team duel reels: clarified and implemented in the separate event-reels plan.

## Execution ledger

- Initial checkout clean at d00eeb9; current workspace reused. No recording or CS2 launch is needed to validate output limits.
- Reference download reproduced failure with yt-dlp 2026.08.19; latest official release is 2026.10.21. Investigate with isolated updated downloader before changing analysis behavior.

- Implemented and verified: 6 output tests passed, including actual FFmpeg normalization of oversized/120 fps cached clips and composition parts, legacy migration and small-screen fitting. English/Chinese documentation updated.

- Final integrated verification: 255 pytest tests passed, Node syntax and git diff whitespace checks passed. See event-reels ledger for combined release/real-device limitations.

- Release verification found a test-fixture dependency on the actual Windows display: passing None invoked display discovery, while the assertion assumed unknown resolution. Injected unknown and 1280x720 display results explicitly; all 7 targeted size tests passed. Production display behavior was unchanged.
- Final release recheck after fixture correction: 255 tests passed in 116.22 s; director simulation, JavaScript syntax and staged diff checks passed.
