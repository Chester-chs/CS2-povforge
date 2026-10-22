# Targeted reference effect implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Preview a reference, select a time range, describe the wanted effect, inspect a supported proposal and explicitly apply only that effect.

**Architecture:** Keep source preparation and bounded segment analysis in child CLI processes. Serve a browser-compatible preview from a temporary session through an opaque token with HTTP range support. Filter the analyzer result to the requested effect; unknown or object-tracked requests produce an unsupported result, never a substitute global filter.

**Tech Stack:** Python, FFmpeg, Alpine.js, pytest.

**Spec:** User-approved flow on 2026-10-22: preview, time selection, description, proposal, then apply. Example is a red ring around a knife at 01:43 in BV1LHpY62EdG.

## Global constraints and review focus

- No persistent CS2 settings changes, no reference audio copied into the user's reel.
- Clearly separate download failure, analysis failure and unsupported visual effects.
- Only explicit Apply changes the reel. A proposal applies a partial patch so unrelated effects remain intact.
- Reject invalid/out-of-range timestamps and large analysis windows; clean temporary media on failure and application shutdown.
- User descriptions are data. Do not execute them or claim semantic object tracking from keyword classification.

### Task 1: analysis and capability reporting

Files: povforge/reference.py, style.py, cli.py; tests/test_reference.py.

- [x] Write failing tests for unknown/knife effects, partial patches, timestamps and download diagnostics.
- [x] Deduplicate style definitions only after checking identical ASTs; retain the live final downloader.
- [x] Prepare capped preview media and analyze a selected segment, preserving original frame rate for repeated-frame detection.
- [x] Keep supported effect results as a proposal. Mark unrecognized requests explicitly.

### Task 2: window and media transport

Files: povforge/gui/server.py, gui/static/app.js, gui/static/index.html, gui/static/app.css; tests/test_reference.py.

- [x] Add prepare/analyze endpoints and token-scoped preview with byte-range streaming.
- [x] Add modal preview, range controls, description, effect family selector and an explicit Apply button.
- [x] Prevent stale async results from replacing another source; retain the proposal when closing the modal without applying.
- [x] Validate via HTTP and browser UI, then run full regression tests.

## Execution ledger

- Download fails with both installed yt-dlp 2026.08.19 and isolated latest 2026.10.21; Bilibili public metadata returns HTTP 412. This environment has not retrieved the example. Local upload remains a necessary test route.
- Ruling: knife-bound rings need tracking/segmentation/occlusion handling absent from this project. The window will explain this accurately; this work does not claim that complex effect has been recreated.

- Implemented preparation/range HTTP transport/proposal/modal/explicit Apply. Browser verified a one-off synthetic flash is recognized, remains unapplied until Apply, and stays editable after reload.
- Review fixes: selected analysis accepts one occurrence; native preview can play beyond selected range; unnamed applied settings survive reload; reference subprocess launch/register is atomic with shutdown and child trees are stopped. Regression tests passed.
- style.py repeated definitions were AST-compared before deduplication; final live fetch retained. Reviewer independently checked preservation.

- Final integrated verification: 255 pytest tests passed, Node syntax and git diff whitespace checks passed. See event-reels ledger for combined release/real-device limitations.
