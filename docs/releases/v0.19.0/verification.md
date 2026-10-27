# v0.19.0 verification

Scope: automatic recording of official-matchmaking downloads
(`povforge/auto_mm.py`, Settings › Auto matchmaking, sidebar status entry,
`/api/auto-mm`, replays folder included in the match list while enabled).

Behaviour guaranteed by tests (`tests/test_auto_mm.py`):

- Replays folder derived from the detected cs2.exe; Steam accounts read from
  `config/loginusers.vdf`, most recent first, invalid IDs ignored.
- Only demos modified after the switch was turned on are handled; each match
  (by file stem) once, remembered across restarts in `auto-demos.json`.
- A file must be unchanged across two polls and settle for 3 s.
- While the user's own CS2 or an anti-cheat client runs, the watcher only
  waits (status `cs2`/`anticheat`); it never closes the game. A CS2 owned by a
  running PovForge job does not block queueing.
- `.dem` preferred over a `.dem.bz2` of the same match.
- Round choice matches the editor: highlights = 3k+ or won clutch (best last),
  falling back to rounds with kills; kill POV = rounds with event kills;
  kills/deaths = kills or deaths; whole match uses the normal match queue.
- Missing account, account absent from the match, no usable rounds and read
  failures are recorded once as skipped/error, without retry loops.
- Settings page explains the 4-step flow and notes; choices post to the API.

No CS2/HLAE launch, Steam access or game-settings change during development.
The real end-to-end flow (download in CS2 → quit → automatic recording) needs
confirmation on the owner's Windows PC.

## Local evidence (Linux, headless Chromium)

- Full suite: 410 passed, 14 failed, 7 skipped. The 14 failures are the same
  FFmpeg/Windows-process cases that fail identically on the unchanged v0.18.1
  source in this environment.
- Theme text audit now includes the Auto matchmaking tab.

## Published package

Filled in after the Windows workflow completes.
