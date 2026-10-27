# v0.20.1 verification

Owner report (2026-10-27): victim perspective on + "at the end" produced no
victim footage; chosen background music was missing from the reel.

Findings on the owner's PC (read-only):
- reels/reel-2.json had `camera.victim: true, selected: []`; the picker was empty
  because the inspection cache for the Inferno MM demo had `duels: []`.
- Cause: player "Seeking Heaven" disconnected from round 4; demoparser2 returns
  `team_num = NaN` for him, and `int(NaN or 0)` raised in `round_sides`, which the
  inspector swallowed, so the whole match lost its sides.
- The finished reel's audio matched the raw clip (corr 0.998, gain 0.99): no music
  and no game-audio lowering, i.e. `mix_sound` found no file at the music path.

Changes: NaN-safe side/scoreboard parsing; `sides_error` logged and kept in the
inspection result; inspection cache v5; `effects.check_music` stops a reel with a
missing track before recording (auto MM drops the track instead); victim replays
are a single switch (legacy `selected` dropped in normalize_camera, picker removed).

Checks:
- Fixed code against the owner's real demo on his PC: duels 0 -> 130; round 11
  lists NiKo's 5 kills, matching victims.json ticks; per-round headshots non-zero.
- New tests: test_round_sides_disconnect.py, test_music_missing.py; selection tests
  rewritten for the single switch. Local Linux suite: only the 14 pre-existing
  environment-dependent failures (same set before and after the change).
- No CS2 launch, no game-setting changes.

Published 2026-10-27T22:52:29Z from d91024f via workflow 40596988101
(422 passed, 25 skipped), Setup and portable assets uploaded. Two earlier
attempts (run 40595343504) failed only test_first_use_opens_the_notes_at_the_top_of_the_sidebar;
the unchanged v0.20.0 tag failed it too in a build-only run (40596485193). The test
now waits for Alpine boot before reading app data (CI timing race, not app code).
