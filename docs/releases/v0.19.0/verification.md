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

- Full suite: 411 passed, 14 failed, 7 skipped. The 14 failures are the same
  FFmpeg/Windows-process cases that fail identically on the unchanged v0.18.1
  source in this environment.
- Theme text audit now includes the Auto matchmaking tab.

## Published package

- First attempt (run 40578694216, source 8c591f7) stopped in Tests: the
  Windows-only native-host probe replaces App without a watcher and main()
  called `app.auto.start()` unconditionally (1 failed, 406 passed). Nothing
  was built or published. Fixed in 54be1f5 (watcher optional in main) with a
  regression test.
- Source: `54be1f54143063f09e7f302b0aacc6a9a4a29752` (main), released through
  the workflow's manual dispatch (`release: v0.19.0`).
- [Release](https://github.com/Chester-chs/CS2-povforge/releases/tag/v0.19.0)
  published 2026-10-27T20:46:59Z; public, latest, both assets uploaded.
- [Windows workflow](https://github.com/Chester-chs/CS2-povforge/actions/runs/40579653426):
  **408 passed, 24 skipped in 136.16s**. Build, bundled FFmpeg, smoke, installer,
  incremental update, native WebView2 window and uninstall checks passed.
- Installer: 139397141 bytes; SHA-256
  `8805f160dc0442c60a52916965bddcfbd8a9d0d367b69664e80906ace7f153d7`.
- Portable ZIP: 218464595 bytes; SHA-256
  `6e7bad6d6ac9c8a87109445b1df76ee11359cfab01e542b1c05334c2d54a6eb9`.
