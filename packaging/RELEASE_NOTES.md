**What's new in v0.10.3 / 本次更新**

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
