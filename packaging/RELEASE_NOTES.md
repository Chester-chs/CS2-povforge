**What's new in v0.14.0 / 本次更新**

- Highlight reels now always use the selected player's first-person view. Camera imitation, follow/orbit/wide views and map-geometry downloads have been removed; old camera preferences cannot re-enable them.
  高光集锦固定为所选玩家第一人称，移除镜头复刻、跟随/环绕/远景与地图几何下载；旧设置不会重新启用这些功能。
- Optional victim views are off by default. All main highlights play first, followed by victims' first-person replays in the same kill order. Importing, changing or mixing styles preserves this independent choice.
  受害者视角默认关闭；全部主集锦播放完毕后，再按击杀顺序追加受害者第一人称片段。导入、切换和混搭风格不会改变这个独立开关。
- Victim recordings are batched per demo and cached with their settings. Replay sound follows the recorded demo time; small frame-boundary gaps trim to real footage. Short HLAE audio no longer truncates recorded video.
  受害者片段按 Demo 合并补录并缓存，声音对齐对应 Demo 时间，录制边界只保留真实视频帧；修复短音轨截断画面的问题。
- Settings protection covers setup failures, cancellation and temporary recording files. Failed takes cannot be reused as successful recordings.
  设置保护覆盖初始化失败、取消及临时录制文件，失败片段不会被当作成功录制复用。

- Recording jobs now recover from startup failure, reserve queued work once, and wait for cancellation/settings cleanup before starting the next job. Old process output cannot contaminate a later recording.
  修复启动失败后卡住、并发启动队列和旧进程输出串入新任务；取消时等待录制退出及设置清理后再继续队列。
- Recording and decompression caches verify demo source identity, player and planning settings. Replacing a compressed demo or using a same-name match no longer silently reuses unrelated footage.
  录像与解压缓存校验 Demo 来源、选手和计划设置，避免同名比赛或替换压缩 Demo 后误用旧片段。
- Preference saves preserve the previous file on failure. Reel exports publish only after successful rendering and clean failed temporary pieces; output folders on another drive remain supported.
  设置保存失败时保留原文件；集锦成功合成后才发布成片，失败时清理临时片段，并继续支持跨盘输出。
- Incremental updates reject unsafe archive/manifest paths, protect linked-directory boundaries and avoid deleting a replacement file when only its letter case changes.
  增量更新校验压缩包及清单路径、保护目录链接边界，并修复仅文件名大小写变化时误删替换文件的问题。

Validation: 216 automated tests and the director simulation passed before release. The release workflow also tests the packaged command line, GUI server, installer, incremental updates and uninstall on a clean Windows runner. A fresh real CS2/HLAE recording with this audited build has not been performed; no persistent CS2 settings were changed during the audit.
验证：发布前本地 216 项自动测试及导演脚本模拟通过；发布流水线还会在独立 Windows 环境验证打包命令行、界面服务、安装、增量更新及卸载。审查后的版本尚未重新进行真实 CS2/HLAE 录制；本轮审查未改动持久 CS2 设置。

**v0.13.0**

- Recording quality: choose the recording size (screen size, 1080p, 1440p, 4K; up to your screen's) and frame rate (60 or 120 fps, smooth slow motion) in Settings. Recordings and finished videos are encoded for quality first (bigger files).
  录制画质：在设置里选录制分辨率（跟屏幕一样、1080p、1440p、4K，不超过屏幕）和帧率（60 或 120 帧，慢动作更顺滑）。录制和成片改为画质优先编码（文件更大）。
- A 4K upload copy is saved next to each finished video and reel ("name [4K].mp4"): Bilibili and YouTube give 4K uploads more bitrate, so they look sharper there. Can be turned off in Settings.
  每个成片和集锦旁边另存一份放大到 4K 的上传版（"名字 [4K].mp4"），传 B 站、YouTube 时网站给的码率更高、更清楚。可在设置里关掉。
- Import a finished video from a link: paste a Bilibili, YouTube or other video link (or a direct .mp4); a small copy is fetched with yt-dlp, read and deleted.
  用链接导入成片：粘贴 B 站、YouTube 等视频链接（或直接的 .mp4 地址），软件用 yt-dlp 取一份低清晰度的，读完即删。
- Background music: add your own music files; they stay in a list to pick from next time. Game sound can be kept, lowered or muted.
  背景音乐：上传你自己的音乐文件，上传过的留在列表里下次直接选；游戏声音可以保留、调低或静音。

**v0.12.0**

- Finished videos are sorted into a folder per player (save folder/player/; reels of several players go into "Multi-player reels"). The folder is named after the player's in-game name and can be renamed in Settings; a new nickname keeps the same folder. Videos you already made are sorted once; a folder that already held one player's videos (like ".../Pro POV/donk") simply becomes that player's folder.
  成片按选手分文件夹（保存位置/选手名/；几个选手的集锦放进「多人集锦」）。文件夹默认用游戏名，可在设置里改名；选手改了游戏名也还放在同一个文件夹。已有的成片会整理一次；原来就只放一个选手视频的文件夹（比如"…/职业选手POV/donk"）直接成为他的文件夹。
- Whole match and Highlight reel are now two equal choices at the top of the sidebar; for a reel you pick the demos right in the list.
  侧边栏顶部改成并排的「整场录制」和「高光集锦」两个入口；做集锦时直接在 demo 列表里点选场次。
- Reel effects now only come from finished videos you import: without one the reel is simply joined; each imported video becomes a named style, you can switch between them or mix item by item. The hand-picked effects and the ready-made looks are gone.
  集锦效果只来自你导入的成片：不导入就原样拼接；每个导入的成片存成一个有名字的风格，可以来回切换，也能按项混搭。去掉了手动选的特效和"燃""电影感"等现成风格。
- Fixed: whole-match recordings could stop while drawing the minimap ("box offset can't be negative") with the image library the app now ships.
  修复：整场录制可能在画小地图时出错停止（"box offset can't be negative"）。

**v0.11.1**

- Fixed: "Play video" and "Show in folder" did nothing when the video's folder or name had Chinese in it (the path reached the app garbled). If a file can't be opened, the app now says why.
  修复：视频所在文件夹或文件名带中文时，"播放视频"和"打开所在文件夹"没有反应（路径传给软件时乱码了）。打不开时现在会提示原因。
- Copy a video's style now lists what it found in the video, item by item (opening, transition, kill effects, colour, cinema bars, ending, pace, music), and asks you to name it as a preset, so you can see which look each video uses and pick it again later. Your presets show where they came from.
  照着成片做：读完会逐项列出视频用了什么（开头、转场、击杀特效、调色、黑边、结尾、节奏、音乐），然后让你给这组效果起名存成预设，之后随时能选，也知道哪个预设来自哪个视频。

**v0.11.0**

- Highlight reels can now have effects, all chosen in the reel page before recording and added when the reel is put together: an opening (fade in or a title card), transitions between the moments (flash, dip to black, dissolve, push, wipe, zoom, blur, pixelate, with their length), effects on the kills (slow motion, zoom, flash, shake; on every kill, the last kill of each moment or only the final kill), colour looks, cinema bars, an ending (fade out, freeze frame or an end card), the pace around the kills, and background music with its volume and how loud the game stays. Ready-made looks (Plain, Hype, Cinematic, Clean) are one click, and you can save your own. With nothing chosen the reel is joined exactly as before.
  高光集锦可以加效果了，全部在集锦页里录制前选好，合成时加上：开头（黑场渐入或标题卡）、段与段之间的转场（闪白、黑场、叠化、推移、擦除、缩放、模糊、像素化，可选时长）、击杀特效（慢动作、放大、闪白、震动；可加在每个击杀、每段最后一杀或只在全片最后一杀）、调色、电影黑边、结尾（渐黑、定格或结尾卡）、击杀前后的节奏，以及背景音乐（音量、游戏声音保留/调低/静音）。现成的"原样""燃""电影感""简洁"一键套用，也能把自己调好的存成预设。什么都不选时，集锦和以前一样原样拼接。
- Copy a video's style: choose a finished highlight video and PovForge reads its effects (opening, transitions and their length, kill effects, colour, cinema bars, ending, pace, whether it has music) and fills them in for your reel, with a short report. Its sound can be used as your reel's music. You get the same style and pace, not a frame-by-frame copy.
  照着成片做：选一个做好的集锦视频，PovForge 会读出它用了哪些效果（开头、转场和时长、击杀特效、调色、黑边、结尾、节奏、有没有背景音乐），填进你的集锦设置，并列出读到了什么；还可以直接用它的声音做背景音乐。做出来是同样的风格和节奏，不是逐帧复制。

**v0.10.3**

- Fixed: "Update and reopen" did nothing and the window kept spinning on "Checking for updates…". The update check made at startup now readies the updater, the update window has a Cancel button and time limits, and it shows what went wrong instead of spinning.
  修复："更新并重新打开"没有反应、一直显示"正在检查更新…"。现在启动时的检查会直接让更新可用；更新窗口有"取消"按钮和超时，出错会说明原因，不会一直转圈。

**v0.10.2**

- The update window says it downloads only the files that changed. (A small update, mainly to check that updates now stay small.)
  更新窗口会注明只下载有变化的文件。（这是一个小更新，主要用来确认之后的更新确实很小。）

**v0.10.1**

- Updates after this one are usually well under 1 MB: the program code now ships as separate small files, so an update fetches only the files that changed. (Updating to this version itself replaces the code files once.)
  从这一版之后，更新通常不到 1 MB：程序代码改为一个个小文件，更新时只下载改动过的那几个。（升级到这一版本身会把代码文件整体换一次。）

**v0.10.0**

- Much faster updates from now on: "Check for updates" downloads only the files that changed (usually a few MB instead of the whole 170 MB installer), checks each one, swaps them in after PovForge closes and opens it again. If anything goes wrong the old files are put back; if an incremental update isn't possible, the full installer is used as before. (This version itself still installs the usual way.)
  以后更新快得多："检查更新"只下载有变化的文件（通常几 MB，而不是整个 170 MB 安装包），逐个校验，PovForge 关闭后替换并自动重新打开；出错会还原旧文件，无法增量更新时照旧用完整安装包。（这一版本身仍按原来的方式安装。）
- Smaller download: the FACEIT intro screenshot now drives the Edge/Chrome already on your PC directly, without the Playwright package.
  安装包更小：FACEIT 片头截图改为直接控制电脑自带的 Edge/Chrome，不再需要 Playwright。

**v0.9.4**

- Less waiting. A demo is read once: opening it again (even after restarting PovForge) is instant. Recording the same demo and player again skips reading it. A highlight reel of rounds you already recorded for the whole match is cut straight from that recording, without starting CS2; only missing rounds are recorded.
  少等待：同一个 demo 只解析一次，再打开（重启软件后也一样）立刻出结果；同一场同一个人再录会跳过重新解析；做集锦时，整场录制里已有的回合直接从整场录像里剪，不再开 CS2，缺的回合才补录。

**v0.9.3**

- Fixed: PovForge could close by itself ("PovForge 已经关闭") while you were using it, when its window was hidden behind others or minimised for a while. It now stays open as long as its window is open, and closes a few seconds after you close the window.
  修复：窗口被挡住或最小化一段时间后，PovForge 可能自己关闭（"PovForge 已经关闭"）。现在只要窗口开着就一直运行，关掉窗口几秒后才退出。
- Demos are read in a separate process, so a large or broken demo can't stall or crash the app.
  读 demo 改在单独的进程里进行，大文件或损坏的 demo 不会卡住或弄崩软件。
- The app keeps a log at %LOCALAPPDATA%\povforge\app.log for troubleshooting.
  软件会把运行记录写到 %LOCALAPPDATA%\povforge\app.log，方便排查问题。

**v0.9.2**

- First run asks where your demos are and where finished videos should go (both can be changed later on the setup page or in Settings).
  第一次打开时先选择 demo 所在的文件夹和成片保存的位置（之后可在准备页或设置里更改）。

**v0.9.1**

- Highlight reels keep each round unbroken, from 4 s before its first kill to 1.5 s after its last; nothing in between is cut.
  高光集锦每个回合完整保留：从第一个击杀前 4 秒连续到最后一个击杀后 1.5 秒，中间不剪。
- Tidier output folder: finished videos (and their cover .jpg and description .txt) sit at the top; recordings and other in-between files go into a "工作文件" subfolder. Settings show how much space it takes and can clean it up.
  保存文件夹更整洁：外面只放成片（以及同名的封面 .jpg 和简介 .txt），录制留下的中间文件放进"工作文件"子文件夹；设置里能看到占用多大，可一键清理。
- About half the disk space per match: raw recordings are removed once their clips are made. Recorded rounds are still reused when you pick other rounds.
  每场少占约一半空间：原始录像整理成片段后自动删除；改选回合时已录好的回合仍会复用。

**v0.9.0**

- Highlight reel, a new entry: pick one or more demos and players; rounds with 3+ kills or a won clutch are chosen for you (add or remove any), ordered best last (drag to change), kept unbroken from just before the first kill to just after the last, and joined. Game picture and HUD only. The old "highlights cut" switch is gone.
  高光集锦（新入口）：选一场或多场 demo、一位或多位选手，自动挑出 3 杀以上和残局获胜的回合（可增可减），默认最强的放最后（可拖动调整），每个回合从第一个击杀前到最后一个击杀后连续保留，再拼在一起，只用游戏画面和 HUD。原来的"精华版"开关去掉了。
- Settings (gear, bottom left): appearance auto / light / dark, eight accent colours, language.
  设置（左下角齿轮）：外观自动 / 浅色 / 深色、8 种强调色、语言。
- Earlier: update from inside the app (v0.8.5); demo reading fixed in the installed app, Apple-style look, FFmpeg built in (v0.8.4).
  之前：软件内一键更新（v0.8.5）；修复安装版读不了 demo、苹果风格界面、内置 FFmpeg（v0.8.4）。

**Windows / Windows 程序**

Download **PovForge-Setup.exe**, double-click it and click through. PovForge gets a desktop icon and a Start menu entry; open it from there. Installing a newer version over it keeps your settings. Uninstall from Windows Settings → Apps.
下载 **PovForge-Setup.exe**，双击，一路"下一步"。装好后桌面和开始菜单都有 PovForge 图标，以后从那里打开。新版本直接覆盖安装即可，设置会保留。卸载：Windows 设置 → 应用。

First time: click **Download the recording add-on** in the app (HLAE, about 10 MB; FFmpeg is already included). You need Steam and CS2 installed. Quit FACEIT / 5E / Perfect World before recording.
第一次使用：在软件里点 **一键下载录制组件**（HLAE，约 10 MB；FFmpeg 已内置）。需要已安装 Steam 和 CS2。录制前先退出 FACEIT / 5E / 完美世界。

`PovForge-windows.zip` is the same program without an installer (unzip and run `PovForge.exe`).
`PovForge-windows.zip` 是免安装版（解压后运行 `PovForge.exe`）。

Recording starts CS2 with `-insecure` (VAC off for that session); your CS2 settings are backed up and restored.
录制时 CS2 以 `-insecure` 启动（该次不连 VAC 服务器）；你的 CS2 设置会备份并在结束后还原。
