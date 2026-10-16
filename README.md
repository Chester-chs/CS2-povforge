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
demo ──► plan ──► overlays ──► record (CS2 via CSVG) ──► compose ──► final.mp4
         which ticks    minimap +     one clip per round     overlay + join
         to record      keyboard      frame-exact            + chapters
```

1. **Plan**: reads rounds, deaths and positions with [demoparser2](https://github.com/LaihoE/demoparser) and picks one tick range per round (freeze-time end → death or round end).
2. **Overlays**: renders the minimap and key display for exactly the frames each clip will have.
3. **Record**: hands the clip list to [CS2 Video Generator (CSVG)](https://github.com/CS2OpenDev/CS2VideoGenerator), which renders each range in CS2 offline and frame-exact, locked to the player.
4. **Compose**: puts the overlays on each clip with FFmpeg and joins everything.

Key input comes from the player's real input commands when the demo has them (FACEIT demos do), including sub-tick taps; otherwise from the server's button state.

## Requirements

- Windows 10/11 with Counter-Strike 2 installed (for recording)
- Python 3.11+
- [FFmpeg](https://ffmpeg.org) on PATH, e.g. `winget install Gyan.FFmpeg`
- [CS2 Video Generator](https://github.com/CS2OpenDev/CS2VideoGenerator/releases): download the `win-x64` zip, extract it and add the folder to PATH (`csvg doctor` should pass)

## Install

```
pip install git+https://github.com/Chester-chs/cs2-povforge
```

## Usage

```
povforge inspect match.dem.zst                 # map, rounds, player names
povforge run match.dem.zst donk --rounds 1-2 --placeholder   # quick test, no CS2 needed
povforge run match.dem.zst donk                # the real thing
```

- Demos can be `.dem`, or FACEIT's `.dem.zst` / `.dem.gz` as downloaded. HLTV demos come as `.rar`: extract the `.dem` first.
- The player can be part of a name or a steamid.
- `--placeholder` uses grey test clips instead of recording, to check overlays and timing.
- Each job lives in `povforge-output/<demo>__<player>/` and can be resumed; steps can also be run one by one: `plan`, `overlays`, `record`, `compose`.

Settings (clip padding, resolution, overlay size and position, enemies on minimap, ...) go in `povforge.toml`; see [config.example.toml](config.example.toml).

> **VAC:** CSVG starts CS2 with `-insecure` for the recording session and restores your settings afterwards. Don't join online servers while it runs.

## Roadmap

- [x] Round planning, dead-time skipping, minimap, keyboard overlay, chapters
- [x] CSVG recording backend
- [ ] Watch a folder and process new demos automatically
- [ ] Download pro demos from HLTV
- [ ] FACEIT: find and download a followed player's matches
- [ ] Subscription mode

## FACEIT integration

The FACEIT Data API is used to look up a followed player's recent matches. The FACEIT Downloads API is used only to download demo files of those matches for local processing into POV videos. No FACEIT data is redistributed or sold.

## Credits

Built on [demoparser2](https://github.com/LaihoE/demoparser) (MIT), [CS2 Video Generator](https://github.com/CS2OpenDev/CS2VideoGenerator) (GPL-3.0, used as an external program), radar data via [cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons) (downloaded at runtime, not stored here) and FFmpeg. Details: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Not affiliated with Valve, FACEIT or HLTV. Counter-Strike 2 and its maps are property of Valve Corporation.

## License

[MIT](LICENSE)
