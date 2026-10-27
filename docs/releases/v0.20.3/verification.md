# v0.20.3 verification

Published 2026-10-27T23:53:14Z from 6e1e4b2 via workflow 40604106147
(426 passed, 29 skipped); Setup and portable assets uploaded. v0.20.2 was never
published: its run (40601354733) was cancelled at the owner's request and left a
draft release with that tag.

Contents: victim replays 3 s before death + 1 s after (owner request), with no
footage of another player after the death: the director ends the take when the
camera leaves the dead victim (why=after_death), hlae stores that tick in
shot-cuts.json, and _prepare_shots drops everything from 0.3 s before it. Also the
v0.20.2 fix: a missing music file is a readable "Error:" instead of a cli_main crash.

Checks: director_sim.js scenarios (camera leaves after death, stays, lost before
death); render tests with real FFmpeg for the cut, early tail and pre-death loss;
recording-contract test for shot-cuts.json. No CS2 launch; the real after-death
camera behaviour of CS2 still needs the owner's recording to confirm.
