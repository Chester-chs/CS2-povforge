English | [简体中文](README.zh-CN.md)

# CS2 POVForge

A personal, non-commercial tool that turns Counter-Strike 2 demos into full-match first-person (POV) videos of a chosen player.

## What it does

- Takes a CS2 demo (HLTV pro match, FACEIT match, or Valve matchmaking) and a player to follow
- Records every round from that player's point of view
- Skips dead time: freeze time, timeouts and halftime are never recorded, and each round stops shortly after the player dies
- Adds a synced 2D minimap and a keyboard/mouse input display (W A S D, Space, Ctrl, Shift, M1, M2, R, E)
- Writes chapter markers per round (embedded in the video and as a YouTube-ready `chapters.txt`)

A 28-minute FACEIT demo becomes a ~16-minute POV video.

## How it works

```
demo ──► plan ──► record (CS2 via HLAE) ──► overlays ──► compose ──► final.mp4
         which ticks    one clip per round       minimap +     overlay + join
         to record      fixed frame rate         keyboard      + chapters
```

1. **Plan**: reads rounds, deaths and positions with [demoparser2](https://github.com/LaihoE/demoparser) and picks one tick range per round (freeze-time end → death or round end).
2. **Record**: starts CS2 through [HLAE](https://github.com/advancedfx/advancedfx) and loads a small director script that, round by round, jumps to the clip, locks the camera on the player and renders it at a fixed frame rate, then closes the game. The exact start of every clip is read back from CS2's console log so the overlays line up.
3. **Overlays**: renders the minimap and key display for exactly the frames of each recorded clip.
4. **Compose**: puts the overlays on each clip with FFmpeg and joins everything.

Key input comes from the player's real input commands when the demo has them (FACEIT demos do), including sub-tick taps; otherwise from the server's button state.

## Requirements

- Windows 10/11 with Counter-Strike 2 installed (for recording)
- Python 3.11+
- [FFmpeg](https://ffmpeg.org) on PATH, e.g. `winget install Gyan.FFmpeg`
- [HLAE](https://github.com/advancedfx/advancedfx/releases): download the latest `hlae_*.zip` and extract it to `C:\Tools\hlae` (so that `C:\Tools\hlae\HLAE.exe` exists)
- Steam running; close CS2 and anti-cheat clients (FACEIT, 5E, Perfect World) before recording

Run `povforge doctor` to check everything.

## Install

```
pip install git+https://github.com/Chester-chs/cs2-povforge
```

## Usage

```
povforge doctor                                # check the setup
povforge inspect match.dem.zst                 # map, rounds, player names
povforge run match.dem.zst donk --rounds 1-2 --placeholder   # quick test, no CS2 needed
povforge run match.dem.zst donk                # the real thing
```

- Demos can be `.dem`, or FACEIT's `.dem.zst` / `.dem.gz` as downloaded. HLTV demos come as `.rar`: extract the `.dem` first.
- The player can be part of a name or a steamid.
- `--placeholder` uses grey test clips instead of recording, to check overlays and timing.
- Each job lives in `povforge-output/<demo>__<player>/` and can be resumed; steps can also be run one by one: `plan`, `overlays`, `record`, `compose`.

Settings (clip padding, resolution, overlay size and position, enemies on minimap, ...) go in `povforge.toml`; see [config.example.toml](config.example.toml).

> **VAC:** recording starts CS2 through HLAE with `-insecure` (VAC off for that session). Don't join online servers while it runs; a normal Steam start afterwards is back to normal. The only file added to the game folder is a temporary `cfg/povforge_job.cfg`, removed when recording ends.

## Roadmap

- [x] Round planning, dead-time skipping, minimap, keyboard overlay, chapters
- [x] HLAE recording backend (needs a first real test)
- [ ] Watch a folder and process new demos automatically
- [ ] Download pro demos from HLTV
- [ ] FACEIT: find and download a followed player's matches
- [ ] Subscription mode

## FACEIT integration

The FACEIT Data API is used to look up a followed player's recent matches. The FACEIT Downloads API is used only to download demo files of those matches for local processing into POV videos. No FACEIT data is redistributed or sold.

## Credits

Built on [demoparser2](https://github.com/LaihoE/demoparser) (MIT) and [HLAE](https://github.com/advancedfx/advancedfx) (MIT, used as an external program); HLAE launch settings follow [CS Demo Manager](https://github.com/akiver/cs-demo-manager) (MIT, reference only); radar data via [cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons) (downloaded at runtime, not stored here) and FFmpeg. Details: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Not affiliated with Valve, FACEIT or HLTV. Counter-Strike 2 and its maps are property of Valve Corporation.

## License

[MIT](LICENSE)
