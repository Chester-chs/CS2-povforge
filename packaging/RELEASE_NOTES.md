**What's new in v0.9.0 / 本次更新**

- Highlight reel, a new entry: pick one or more demos and players; rounds with 3+ kills or a won clutch are chosen for you (add or remove any), ordered best last (drag to change), cut down to the kills and joined. Game picture and HUD only. The old "highlights cut" switch is gone.
  高光集锦（新入口）：选一场或多场 demo、一位或多位选手，自动挑出 3 杀以上和残局获胜的回合（可增可减），默认最强的放最后（可拖动调整），只剪击杀片段拼在一起，只用游戏画面和 HUD。原来的"精华版"开关去掉了。
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
