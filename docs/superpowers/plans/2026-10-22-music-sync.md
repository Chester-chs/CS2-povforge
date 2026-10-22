# Demo-driven music synchronization implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Let users supply a whole song and optionally choose its starting point automatically so actual Demo kill times land near strong beats, prioritizing multi-kill sequences in louder passages.

**Architecture:** Analyze the full audio track locally using FFmpeg and NumPy. Optimize one continuous music excerpt against the final video timeline, accounting for intro cards, slow motion and overlapping transitions. Keep round chronology and game audio intact. Report alignment statistics instead of claiming every kill matches exactly.

**Tech Stack:** Python, NumPy, FFmpeg, Alpine.js, pytest.

**Spec:** User confirmed on 2026-10-22: use Demo kill times, with the full supplied song as the source.

## Global constraints and review focus

- No CS2 launch or persistent settings changes.
- Music sync is optional and kept separately from imported visual presets.
- Silence, missing beats, a short song, no kills and decode errors must have explicit fallback behavior.
- Respect real timestamps after effects; do not use only the first/last kill-effect scope.
- Bound analysis time/memory and preserve full-song analysis for ordinary music tracks.

### Task 1: analyze and select

Files: povforge/music_sync.py; tests/test_music_sync.py.

- [x] Write failing tests for synthetic beats, silence, dense-kill/high-energy preference and insufficient song duration.
- [x] Implement audio analysis and a deterministic bounded search of music offsets; return offset and timing errors.
- [x] Run `pytest tests/test_music_sync.py -q`.

### Task 2: integrate with final timeline and UI

Files: povforge/effects.py, gui/static/app.js, gui/static/index.html; tests/test_music_sync.py.

- [x] Test final kill times with slow motion, cards and cross-fades.
- [x] Add optional music_sync setting and retain it when changing visual presets.
- [x] Select music offset after rendering determines real section lengths; log fallback and measured match counts.
- [x] Verify an FFmpeg output with synthetic audio and rerun effects regressions.

## Execution ledger

- Ruling: first implementation optimizes a continuous song excerpt, preserving original event order. It does not claim exact synchronization of every shot or infer the artistic chorus from loudness alone.

- Implemented and verified: 6 music tests passed, including real FFmpeg audio output, stronger later song excerpt selection, effects-adjusted timing and explicit short/silent/no-kill fallbacks.

- Final integrated verification: 255 pytest tests passed, Node syntax and git diff whitespace checks passed. See event-reels ledger for combined release/real-device limitations.
