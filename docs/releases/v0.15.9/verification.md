# v0.15.9 release verification

UI and replay behavior and local/native/FFmpeg evidence are recorded in
[the feature verification](../v0.15.8/verification.md).

The v0.15.8 CI run 40030178920 passed 330 tests and skipped 22, but failed the
remaining browser check with PermissionError reading DevToolsActivePort. No
installer was produced or published. The failed tag was retained unchanged.

RED checkpoint `5a3cfb3`: two simulated browser startup cases fail with the actual
sharing violation, before any fix. GREEN: `pytest tests/test_browser_startup.py
tests/test_cdp.py tests/test_workspace_browser.py -q --tb=short` passed all five
in 14.70s. Tests cover temporary locks, partial and invalid port data, a single
readiness snapshot (no second read race), bounded failure and profile cleanup,
plus real Edge/Chrome local FACEIT and application UI behavior.

The fix retries only browser startup file readiness within its existing timeout;
it does not alter game capture, the replay implementation or game settings.
Unchanged feature code reuses the successful 350-test local regression and the
12-test inline selection/media target. Release CI runs the whole current suite.
No CS2/HLAE game process was launched. Type/lint/coverage availability remains as
recorded in the feature verification; no unsupported check is claimed.
