# Event reels implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, followed by one existing reviewer.

**Goal:** Add chronological first-person deaths, kills plus deaths, and opposing-player duels.

**Architecture:** Keep the existing highlight path. Resolve new modes to validated Demo event windows before any recording. Reuse matching full recordings or record the bounded event span per player/round. Build chronological solo windows, or A then B for each duel. Keep only real kill timestamps as effect/music anchors.

**Tech Stack:** Python, demoparser2, FFmpeg, Alpine.js, pytest, Node.

**Spec:** User confirmation on 2026-10-22: deaths always use the selected player's first person; duels include only mutual kills between opposing players, each encounter A then B, with a swap control.

## Global constraints / review focus

- Never change persistent CS2 settings; preserve original highlights and optional victim replays after the main reel.
- Validate opposing teams per round, including halftime side swaps; unknown sides cannot authorize a duel.
- No empty/invalid event selection may launch recording. Reject same-player and same-team requests.
- Merge overlapping solo windows without duplicating kills; keep duel pairs together in chronological order.
- Cache identity includes event selection; preserve cancellation through the existing recorder subprocess flow.
- Round boundaries, player death, actual recording starts and clip duration bound cuts. Deaths are not kill/music anchors.

### Task 1: event model and validation

Files: povforge/reel_events.py, reel.py, gui/server.py; tests/test_event_reels.py.

- [x] Write and run failing tests for solo chronological kills/deaths, death-only, enemy duels, team swaps, teamkills and absent players.
- [x] Implement event selection and optional ReelItem mode/opponent serialization, preserving defaults.
- [x] Expose validated opponent encounters in Demo inspection and preserve mode fields in queue persistence.
- [x] Run event model and existing reel tests; expect PASS.

### Task 2: recording and cutting

Files: povforge/pipeline.py, reel_events.py, reel.py; tests/test_event_reels.py.

- [x] Write failing tests for event cache identity, exact A/B order, clip boundaries and overlapping solo windows.
- [x] Add optional event tick trimming and route new modes through existing recording, effect and publication mechanisms.
- [x] Run targeted integration tests; expect PASS, including a real FFmpeg synthetic reel.

### Task 3: UI and verification

Files: gui/static/app.js, index.html; tests/test_event_reels_frontend.py; README.md, README.zh-CN.md.

- [x] Write a failing Node test against the real Alpine factory for chronological selection, enemy filtering, swap and request serialization.
- [x] Implement content selector, per-demo opponent picker, swap and chronological editing restrictions.
- [x] Verify browser UI and complete the full pytest suite; update docs and reviewer ledger.

## Execution ledger

- Pre-flight: server inspection feeds frontend candidates; queue must retain mode/opponent to child CLI; event windows supply actual kill anchors to the existing effect/music pipeline.
- Ruling: add death-only alongside kills plus deaths, matching the explicit request to compile every death. Default remains legacy highlights.
- Ruling: implement inline on the existing feature branch; no new worktree, merge, push or release during this task.

- Task 1/2/3: implemented. Initial 8 backend tests and Node UI test failed for absent functionality, then passed. Current event suite: 12 passed, including actual FFmpeg colour/order inspection.
- Review fixes: exit events use real round_start boundaries; last-kill event must be strictly inside a clip; fallback drops old round spans before assigning a new context. Each defect was reproduced by a failing regression before correction.
- Actual Demo inspection: Dust2, 13 rounds; Mann3n/m0NESY yielded 7 mutual-kill encounters and 14 ordered POV windows. Browser confirmed opponent filtering, round order and swap. No CS2 launch; real post-death camera remains unverified.

- Final verification: `.venv/Scripts/python.exe -m pytest -q` -> 255 passed in 247.42 s; `node --check povforge/gui/static/app.js` and `git diff --check` passed. Existing reviewer rechecked boundary/cache/shutdown fixes: no unresolved important findings.
- Remaining limits: no live CS2 recording of the new modes; no semantic music-chorus detection; Bilibili sample retrieval blocked and knife-bound tracking effect unsupported. No GitHub push or installer release performed for these changes.
