# Review fixes and first-use documentation

**Goal:** Fix R1-R5 from the 2026-10-23 read-only review, preserve current behavior outside the approved mode change, and explain installation and recording to new users.

**Authority:** User approved the review recommendations and implementation. Latest mode clarification: retain kill events, kills + deaths, and duels; remove deaths-only. Preserve traditional highlights and whole-match POV.

**Architecture:** Keep the Python/Alpine architecture. Share the Job lock between manual restoration and recording startup. Validate ordinary raw-take completion before cache reuse. Validate event coverage against the POV cutoff before recording. Resolve image paths and validate HTTP listener authority. No new dependency.

**Constraints:** Do not launch CS2/HLAE, access or change real game settings, push, publish or install an update. Tests use fake games, temporary settings and synthetic media. Leave changes local and uncommitted for review.

**Release follow-up:** After the implementation report, the owner explicitly authorized committing and pushing these changes to GitHub and updating the installer. This supersedes the implementation-phase no-push/no-publish constraint. Release as v0.15.1 through GitHub Actions; do not install locally, launch CS2/HLAE or access the owner's game settings.

## Tasks and regression gates

- [x] R1: `gui/server.py`, `gui/static/index.html`; add isolated handler tests for busy jobs, running games, safe restoration, and startup serialization. Watch failure then pass.
- [x] R2: `hlae.py`; add interrupted/corrupt/short ordinary take retry tests and successful reuse. Use isolated files and fake external recording only. Watch failure then pass.
- [x] R3 and modes: `reel.py`, `reel_events.py`, GUI mode/preview; distinguish traditional `kills` highlights from chronological `kill_events`. Remove `deaths`, preserve `kills_deaths` and `duel`. Exclude unsupported posthumous kill perspectives before recording with clear feedback. Verify preflight and output order. Watch failure then pass.
- [x] R4/R5: `gui/server.py`; resolve thumbnail paths, validate actual listener Host for GET/POST and Origin for POST. Use session CSRF token for POST and update frontend transport/pagehide. Test legitimate UI requests, traversal/junctions, bad Host/Origin, missing/wrong token and existing media preview. Watch failure then pass.
- [x] Rewrite `README.md` and `README.zh-CN.md` for first-time users: product, direct release download, requirements, initial setup, output modes, real vs output duration, troubleshooting and optional CLI. Remove fixed 28-to-16 minute example and developer handoff content from user-facing overview.
- [x] Run isolated full regression, Node simulation/syntax, diff checks; fresh independent review of all local changes; address substantive findings and update HANDOFF.

## Review focus

- Manual restoration must not race Job.start or run while cancellation is cleaning up.
- A failed raw take must not poison retries or be promoted to a complete clip.
- Every accepted event must fit its own player's recorded perspective; delayed grenade/fire kills must not trigger impossible recording.
- Normal browser startup, preview playback, heartbeat/pagehide and preference writes must work with stronger HTTP checks.
- Both READMEs must describe the same available modes and distinguish video duration from wall-clock processing time.

## Execution ledger

- Baseline: a501c4659b586926d260ce495e3cc6582d3f4cac, clean feature checkout. Reusing current checkout per session authorization; no worktree or publication needed.
- Design authority: the approved audit report plus explicit user corrections above. No additional design approval requested for already-authorized fixes.
- Ruling: chronology uses `kill_events` so legacy `kills` specifications continue to mean traditional selected-round highlights.
- Compatibility cost if this choice were reversed: existing saved specs would silently change editing behavior. Keeping the legacy name avoids that migration.
- R1 red: 5 failures, 1 pass; focused green: 22 passed, including startup/restore serialization and cancellation.
- R2 red: incomplete, unreadable and short takes reproduced the retry bug. Final validation is separated from muxing: malformed media is discarded; output errors retain valid raw media. Both Python PermissionError and FFmpeg CalledProcessError are covered.
- R3 red: 7 failures before the mode/filter change; initial event/planning/replay regression: 38 passed. Event counts and duel lists share the posthumous filter. No pipeline change was needed because invalid events are removed before planning.
- R4/R5 red: 9 failures before path/authority/token changes. Real local HTTP tests verify normal thumbnails, traversal and Windows junction rejection, hostile Host/Origin, token rejection and authenticated shutdown. JS transport test verifies token bootstrap, writes and pagehide keepalive.
- Pre-review full regression: 281 passed in 137.46 seconds. Director simulation: 25 assertions passed; JS syntax and diff checks passed.
- Independent final review found two P2 follow-ups: validated raw footage was still discarded on subprocess output failures, and v3 inspection cache could retain old posthumous counts. Both were reproduced with failing tests and fixed; focused regression: 46 passed in 18.03 seconds.
- Independent reviewer rechecked both deltas and ran 8 focused tests: all passed. Final verdict: no outstanding actionable findings. No deferred minor findings.
- Documentation and final report will distinguish automated validation from live recording. No CS2/HLAE launch or real game-settings access is part of this change.
- Final full regression: 284 passed in 115.08 seconds with `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp .test-tmp/review-full-final` and isolated `POVFORGE_STATE`. JS syntax and diff checks passed. All changes remain uncommitted on `codex/camera-simulation`; no push, merge, installer build or release. Retain this plan as the local review record.
