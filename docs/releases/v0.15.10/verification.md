# v0.15.10 verification

Scope: hide the entire victim replay section in head-to-head mode, and ignore
saved opt-ins for duel jobs without mutating preferences used by other modes.
The AI style editor request remains planning only; no layout/API changes for it.

RED: targeted frontend/backend regression returned 2 failed, 2 passed before
implementation. The full affected target also reproduced both browser visibility
failures (4 failed, 11 passed). Checkpoint: ae2e03b.

GREEN: event request, inline replay pipeline, real browser visibility/preference
retention and independent camera/style choice checks: 16 passed in 28.19s.
Switching back to kill POV restores the checked victim preference. Backend duel
jobs disable victim replay even if older specs/prefs requested it. Other modes
continue passing the existing replay and composition cases.

JS syntax and diff checks passed. All game capture is mocked or replaced by
synthetic clips. No CS2/HLAE game process was launched; game settings unchanged.
Unchanged code reuses the v0.15.9 suite/installer evidence. Release CI runs the
whole suite and install/update/uninstall checks. Coverage/type/lint tools remain
unavailable as recorded in the preceding release; no such result is claimed.

Existing event selection and A/B video regression: 18 passed in 9.12s.
