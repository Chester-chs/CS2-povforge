English | [简体中文](README.zh-CN.md)

# CS2 POVForge

A personal, non-commercial tool that turns Counter-Strike 2 demos into full-match first-person (POV) videos of a chosen player.

## What it does

- Takes a CS2 demo (HLTV pro match, FACEIT match, or Valve matchmaking) and a player to follow
- Records every round from that player's point of view
- Skips dead time: each round starts 3 seconds before freeze time ends (no timeouts, no halftime) and stops shortly after the player dies
- Keeps CS2's own HUD; the demo playback bar and game radar are hidden
- Your CS2 settings are never changed: every settings file (Steam userdata cfg and game cfg) is backed up before CS2 starts and put back byte for byte after it closes. If a recording is interrupted, the next povforge command restores them first (`povforge restore-settings` does it on demand)
- Synced 2D minimap: teammates, grenade flight paths, smokes and molotovs with countdowns
- Keyboard/mouse display (Shift, Ctrl, W A S D, Space, mouse buttons) just above the HUD's kill icons
- Intro: "<player> POV" written over the FACEIT match room. The screenshot is taken automatically from the demo's match id (headless Edge/Chrome, no login, cookie banner hidden, nothing accepted). The intro also shows the match start time in your time zone. Other demos get the final scoreboard
- Writes chapter markers per round (embedded in the video and as a YouTube-ready `chapters.txt`), named after what happened: "Round 18 · ACE", "Round 7 · 3K · 1v2 clutch"
- Highlight reel (its own entry in the app): the best rounds of one or more demos and players (3+ kills or a won clutch, picked for you and editable), each round kept unbroken from 4 s before its first kill to 1.5 s after its last and joined in the order you choose, best last by default. Game picture and HUD only, no overlays or intro. Only the needed seconds are recorded
- Upload kit: `cover.jpg` (the best moment, name, map, score, K/D/A) and `description.txt` (a title, match info and the chapters)

A 28-minute FACEIT demo becomes a ~16-minute POV video.

## The app

Download **PovForge-Setup.exe** from [Releases](https://github.com/Chester-chs/CS2-povforge/releases/latest) and run it. It installs for your Windows user (no admin rights needed) and puts a **PovForge** icon on the desktop and in the Start menu. Open it from there; it shows a window where you:

1. pick a demo (demos in your Downloads folder are listed; any file can be chosen),
2. click a player on the scoreboard and, if you like, the rounds to record (each round shows that player's kills and whether they died),
3. press **Record** and follow the progress; when it's done, play the video, copy the upload title, or open the folder.

For a highlight reel, press **Make a reel** after picking a player, or open **Highlight reel** in the sidebar to combine several demos. Appearance (auto, light, dark), accent colour and language are under the gear at the bottom left.

While one recording runs you can keep browsing and press **Queue** to add more players or demos; they're recorded one after another. The app tells you when a new version is out.

FFmpeg (the video encoder) comes with the app. The first time, click **Download the recording add-on**: it fetches HLAE (about 10 MB) from its official GitHub release into `%LOCALAPPDATA%\povforge\tools`; HLAE isn't bundled because it has to keep up with CS2 updates. Steam and CS2 must be installed. Videos go to `Videos\PovForge` (changeable).

To update, click **Check for updates** at the bottom left: the app downloads the new installer, checks it, installs it and reopens. Newer versions install over the old one and keep your settings; uninstall from Windows Settings → Apps. There's also a no-install `PovForge-windows.zip`. From the command line, `povforge gui` opens the same window.

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
- For the command line: Python 3.11+ (the app needs nothing else)
- HLAE and FFmpeg: the app bundles FFmpeg and downloads HLAE with one click. From source, `povforge setup` downloads both; an FFmpeg on PATH or HLAE in `C:\Tools\hlae` is used if present
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
povforge run match.dem.zst donk --intro-image latest   # intro from your own screenshot instead
povforge faceit match.dem.zst --show       # test the FACEIT intro screenshot on its own
povforge reel reel.json                    # highlight reel; reel.json: {"title": ..., "items": [{"demo": ..., "steamid": ..., "round": 18}, ...]}
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
