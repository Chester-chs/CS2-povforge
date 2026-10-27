English | [简体中文](README.zh-CN.md)

# CS2 POVForge

Turn a Counter-Strike 2 demo into a chosen player's first-person video, a highlight reel, or a sequence of kills and deaths. POVForge runs on Windows, plays the demo through CS2, records the selected moments and exports an MP4. You do not need to record your screen manually.

## Download

**[Download the Windows installer — PovForge-Setup.exe](https://github.com/Chester-chs/CS2-povforge/releases/latest/download/PovForge-Setup.exe)**

Run the installer, then open **PovForge** from the desktop or Start menu. It installs for the current Windows user. You do not need to install Python separately.

For a portable copy, download **[PovForge-windows.zip](https://github.com/Chester-chs/CS2-povforge/releases/latest/download/PovForge-windows.zip)**, extract the entire archive and open `PovForge.exe` inside the extracted folder. Do not run it from inside the ZIP.

[Releases](https://github.com/Chester-chs/CS2-povforge/releases/latest) contains release notes and all downloads. This README describes the current source; the published installer may not yet contain unreleased changes.

## Before your first recording

- Use Windows 10/11 with Steam and Counter-Strike 2 installed.
- Have a CS2 demo ready: `.dem`, `.dem.zst`, `.dem.gz` or `.dem.bz2`. Extract `.rar` archives first. A demo is match replay data, not an existing video.
- Keep enough disk space for both the finished video and temporary recordings.
- Keep Steam running; close CS2 and anti-cheat clients such as FACEIT before recording.

FFmpeg, the video encoder, is included in the Windows app. On first launch, click **Download the recording add-on** to download HLAE from its official GitHub release. HLAE controls CS2's demo playback and is downloaded separately so it can be updated when CS2 changes.

Recording starts CS2 through HLAE with `-insecure`. Use this session only for demos; do not join online servers. The app closes its recording session when finished. Afterwards, you can start CS2 normally from Steam.

## Make your first video

1. **Set up once, then open a demo.** Confirm your demo and output folders on first launch. We recommend one dedicated folder for all demos. Once configured and ready, the app opens the **Whole match** page directly. Search its match list or click **Upload Demo** to select a local file. You can revisit preparation through **Settings → General & storage → Environment check**.
2. **Choose a player.** Click their name in the scoreboard. Keep all rounds selected for a whole-match POV, or select one or two rounds for a short first try.
3. **Choose the output.** Use **Record** for a POV video, or **Make a reel** for the modes below. Output is fixed at 1080P; choose the frame rate and optional overlays as needed.
4. **Start and wait.** POVForge launches CS2, seeks to the required rounds, records and composes the video. Avoid playing another game during recording.
5. **Open the result.** Use the play or folder button. New installs save to `Videos/职业选手POV`, with every mode organized by player ID; change this under **Settings › Saving & folders**.

The top of the sidebar holds **Read before you start** (please read it before the first use), followed by **Whole match**, **Demo kill POV**, **Demo kills and deaths POV**, **Head-to-head data**, **Highlight reel** and **Auto matchmaking**, in that order. Open **Highlight reel**, select matches in the main area, and click **Continue** to choose players and rounds. Use **Choose matches** to change the selection later. While a job runs, you can browse and add more jobs to the queue; recordings run one at a time.

Frame rate is under **Recording & saving** in the main area; after you pick a player it also shows exactly where this video will be saved (duels go to player A's folder, reels with several players go to “Multi-player reels”). Settings has appearance, general/storage, saving & folders, and about/update pages. **Saving & folders** holds the output folder, the **Create a folder per player ID** switch, every known player folder, and preflight checks. The sidebar grows with large windows. Choose a theme, accent, font and popup corner radius, adjust language and storage, or check for updates.

Demo analysis is saved locally and reused after restarting the app. **Analysis saved** marks a reusable result. The first read, a changed file, or an update to parsing rules requires analysis again; ordinary app updates keep compatible results. This cache speeds up choosing a match, not the real-time recording itself.

## Automatic matchmaking recording

Official matchmaking (Premier / Competitive) replays can be handled end to end: download the match in CS2, quit CS2, and PovForge cuts and records your own POV automatically. **You never open CS2 yourself for this.**

1. In PovForge click **Auto matchmaking** in the sidebar (next to Whole match, Demo kill POV and the other modes) and turn on **Record matchmaking downloads automatically**. Keep PovForge open (minimized is fine).
2. In CS2 go to Watch → Your Matches, click download on the match and let it finish.
3. **Quit CS2.**
4. Once the game has closed, PovForge reads the match, picks your rounds, queues the recording, launches CS2 itself, then closes it and restores your game settings. The video appears in your player folder in the Video library.

The same page lets you choose **Whose POV** (by default the Steam account most recently signed in on this PC), **What to make** (Highlights, Kill POV, Kills & deaths POV or Whole match) and the CS2 replays folder (normally found automatically).

Before the first use, read **Read before you start** at the top of the sidebar; it opens automatically on first launch. Click **Got it, let’s start** when done.

Good to know:

- Do not open CS2 yourself, and leave the game window alone while it records.
- Always quit CS2 after downloading. While the game is open PovForge only waits; it never closes your game.
- Close anti-cheat clients such as FACEIT before recording, or PovForge keeps waiting.
- Only matches downloaded after you turn this on are handled; older ones can be picked manually in the match list.
- Official replays are kept only for a limited time, so download the matches you want soon.
- Nothing is recorded while PovForge is closed; matches downloaded meanwhile are picked up next time it opens.
- Highlights use rounds with 3+ kills or a won clutch, otherwise rounds with kills. Matches without the chosen account are skipped.
- Automatic tasks appear in the queue like any other and can be cancelled or removed.

## Each player's own look

On by default (Recording & saving → **Match each player’s look**). Each player is recorded as close to their own screen as possible:

- **Crosshair:** the player's own crosshair from the demo.
- **Resolution and aspect:** read from [prosettings.net](https://prosettings.net/). FalleN plays 1280×960 4:3 stretched, so the game is recorded in 4:3 (at 1440×1080 for sharpness) and stretched to the 1920×1080 video; black-bar setups keep their bars.
- **Viewmodel, bob and HUD:** also from prosettings.net, e.g. `viewmodel_fov 60; viewmodel_offset_x 1; viewmodel_offset_y 1; viewmodel_offset_z -1`.

They apply only while recording; your own CS2 settings are restored afterwards. After choosing a player, Recording & saving shows what was found and its source. If the wrong player or nobody was found, enter their page link, or use your own settings for that player. Lookups are kept on this PC for a week and the last copy is used offline.

Not reproducible: graphics quality, brightness, monitor colour and refresh rate exist only on the player's PC; yours are used. Because of how CS2 demos work, the viewmodel can differ slightly from what the player saw.

## Before recording and your video library

- **Preflight checks:** use **Check** under Settings › Saving & folders to verify output/work/player folders, write access, free space and Steam/CS2/component readiness. Submission checks these again. Unwritable folders or less than 512 MB free block starting; less than 8 GB shows a space advisory. This is not a capacity guarantee for the whole job.
- **Recording presets:** expand **Save current options**, name the preset, and keep its mode, FPS, weapons and recording options. Choose it next time, then review the matches, player and rounds. Same-name saves replace the preset; up to 20 are kept. Destinations and player identities are excluded, and applying a preset never starts recording.
- **Saved tasks:** once queued, player/round selections, mode, weapon filters, effects and recording options are saved automatically. After restarting, unfinished tasks wait paused until you click **Resume**. Valid recorded footage is reused; interrupted/missing parts need recording again. Restored jobs retain their original options without replacing current app preferences.
- **Weapon filters:** select AWP, AK-47, M4A4 or other weapons in Kill POV, Kills/deaths POV, Head-to-head and Highlights. Keep sequences containing a matching kill, including the entire mixed-weapon streak. **All weapons** clears the filter; duration estimates and victim replay choices follow the retained footage.
- **Estimated result:** after choosing players and rounds, check the main-footage duration and merged segment count. These exclude extra replays, intros/outros, slow motion and transitions. After three local recordings with matching mode and FPS, previous jobs provide ranges for processing time and output size. Temporary footage needs extra disk space.
- **Weapons per round:** all five modes show summaries such as `AK-47 ×2 · M4A4 ×1`. Expand a round for event times, players, weapons and headshots. Head-to-head shows only the selected pair's encounters. Previously cached demos need one additional read for the new timing/weapon index, which is then reused.
- **Video library:** open it from the sidebar to search by player, map or title, filter by mode, play videos and show their folders. Expand the arrow beside **Video library** to see player folders and video counts; select a folder to browse its contents, or click **Video library** for all videos. New results persist across restarts and queue clearing. Existing videos are discovered in configured output/player folders; their mode, map or duration may be unknown. Moved/deleted files are marked, without rerecording or changing the originals.

Click **Play video** in the library, then jump to rounds, kills, deaths or replays using the event list and Previous/Next controls. Times follow the finished video, including cards, slow motion, transitions and victim replays. Keep the `.mp4.povforge.json` index beside the video when moving it. Older videos remain playable without an index; older source recordings may have incomplete event data. Use the system player if the format is unsupported.

**Check finished videos** is on by default. It checks video metadata/audio and samples 15 seconds each at the start, middle and end; videos up to 45 seconds are checked throughout. Open the library player and click reported timestamps to review possible black or frozen frames. Intentional still shots may be flagged; sampling cannot guarantee the entire movie is fault-free. Disable automatic checks or use **Check video** manually in the library. Checks run before the next recording, never delete movies or reparse Demos, and stay local. Changing the file invalidates its old report.

## Choose what to record

| Output | What the video contains |
| --- | --- |
| Whole-match POV | The selected player's rounds with waiting time removed. By default each round starts shortly before freeze time ends and stops shortly after the player dies or the round ends. Individual rounds can also be selected. |
| Highlights · selected rounds | Suggested multi-kill and won-clutch rounds, with manual additions, removals and ordering. Each round stays continuous from before its first kill to after its last, preserving the action between kills. |
| Kills only · event order | Short windows around the selected player's kills, arranged by round and event time. Adjacent or overlapping windows in the same round are merged. |
| Kills + deaths · round order | The same chronological format, including the selected player's deaths as well as kills. |
| Duels · each A → B | Encounters where two confirmed opponents kill each other. Each encounter shows A's first-person view, then B's. Swap the pair to reverse the order. |

By default, reels keep **5 seconds before** each kill and **3 seconds after**. Overlapping solo event windows merge into a continuous clip; highlight rounds preserve everything between the first and last kill. The Highlight pace options can explicitly choose a different window. Round/demo boundaries may shorten the padding.

Solo event reels always use the selected player's own first-person view. Posthumous grenade or fire kills are excluded because the attacker's living POV is no longer available; their death can still appear in **Kills + deaths**. A round with no supported events is rejected before recording. Across multiple demos, source-list order is preserved, with events ordered within each demo.

**Victim perspective** is available in Kill POV, Kills/deaths POV and Highlights, off by default. Select individual kills to insert the victim's first-person view before death immediately after that kill, then resume the main footage. You can also collect these replays at the end. Extra recording is required; full-match recording and head-to-head mode have no victim replay option. Visual style controls are available only in Highlights.

## Video options

- **Fixed 1080P output, with 24, 30, 60, 120, 144 or 240 FPS selectable from a menu.** Higher frame rates require more processing time and disk space. The game's HUD is kept and demo playback controls are hidden. Choose where finished videos are saved; by default a folder named after the player's in-game ID is created on first use and reused later.
- **Whole-match overlays:** optional synchronized minimap, keyboard/mouse display, intro and round chapters. Keyboard information depends on the demo's data. FACEIT demos with a recognizable match ID can use a match-room intro; other demos can use a scoreboard.
- **Highlight editing:** transitions, grading, slow motion, kill effects, titles and background music. Reels use the game picture and HUD without the whole-match minimap or keyboard overlay.
- **Reference effects:** import a local video or supported Bilibili/YouTube link, preview it, select up to 60 seconds and describe one effect. Review the proposal before applying it. Supported effects are template approximations; object-tracked effects such as a ring around a moving knife are not supported. Use a local file if a site blocks downloading.
- **Music sync:** provide a song and optionally align a continuous excerpt with the final kill timeline. Beat/energy analysis does not guarantee every kill lands on a beat. Reference-video audio is not copied.
- **Upload materials:** whole-match output can include a cover image, description and `chapters.txt` alongside the video.

## How long does it take?

**Demo length, finished-video length and processing time are different.**

A whole-match POV is usually shorter than the demo because it skips pauses, halftime, most buy time and time spent watching teammates after the selected player dies. Event reels contain only selected moments and can be much shorter. There is no fixed conversion from demo minutes to video minutes.

POVForge still has to render and record the selected footage through CS2. A 16-minute output means 16 minutes of video to watch; it does **not** promise the job will finish in 16 minutes. Startup, seeking, recording, overlays and encoding all contribute to the wait. Hardware, output settings and reusable recordings affect that time. Start with one or two rounds to estimate performance on your PC.

## Settings and troubleshooting

After a failure, choose **Export diagnostics** on the failed-task page or in **Settings → General**, then pick a local folder. Reports include the version, component readiness and recent errors with paths, player identities and sensitive log lines hidden. Nothing is uploaded automatically; inspect the JSON before deciding to share it.

POVForge temporarily applies recording settings. Before starting CS2, it backs up the covered Steam and game configuration files, then restores them after the recording session closes. If restoration cannot finish, it keeps the backup and reports the problem. Avoid editing game settings during recording.

- **Interrupted recording:** close CS2 and wait for recording cleanup. If the app reports pending recovery, use **Restore now**. Restoration is blocked while CS2 or a recording job is active. Then retry the same job: completed compatible clips are reused and incomplete raw recordings are recorded again.
- **CS2/HLAE cannot start:** check that Steam is open, CS2 and anti-cheat clients are closed, and the recording add-on is up to date. A CS2 update can require a newer HLAE.
- **Reference link fails:** save the video yourself if permitted, then select the local file.
- **Low disk space:** use work-file cleanup after finishing jobs. Saved match-list analysis survives, but recording plans, detailed position/key data and raw takes are deleted. Recording again requires rebuilding that data and recording the footage; preparation time varies by demo and PC. Normally saved finished videos are kept. Do not place original demos or files you want to keep inside the work-files directory.
- **Updates:** use **Check for updates**, or install a newer `PovForge-Setup.exe` over the existing installation. Uninstall through Windows Settings → Apps.

## Optional: source installation and command line

The Windows download is the easiest starting point. For source installation, install Python 3.11+ and Git, then run:

```powershell
python -m pip install git+https://github.com/Chester-chs/CS2-povforge
povforge setup
povforge doctor
povforge gui
```

Useful commands:

```powershell
povforge inspect match.dem.zst
povforge run match.dem.zst donk --rounds 1-2
povforge run match.dem.zst donk --rounds 1-2 --placeholder
povforge reel reel.json
povforge restore-settings
```

The player can be a Steam ID or part of a name. `--placeholder` uses test pictures without starting CS2; it does not create gameplay footage. Only use `restore-settings` after CS2 and the recording process have exited. See [config.example.toml](config.example.toml) for advanced configuration.

Example `reel.json`:

```json
{
  "title": "My kills",
  "items": [
    {"demo": "match.dem", "steamid": "YOUR_STEAM_ID", "round": 1, "mode": "kill_events"}
  ]
}
```

Modes are `kills` (traditional highlights, also the default), `kill_events`, `kills_deaths` and `duel`. Duel items also need an `opponent` Steam ID. Use one content mode per reel.

## Credits and license

Built with [demoparser2](https://github.com/LaihoE/demoparser), [HLAE](https://github.com/advancedfx/advancedfx), FFmpeg and radar data from [cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons). HLAE launch settings reference [CS Demo Manager](https://github.com/akiver/cs-demo-manager). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

An independent project, not affiliated with Valve, FACEIT or HLTV. Counter-Strike 2 and its maps belong to Valve Corporation. Distributed under the [MIT license](LICENSE).
