**What's new in v0.8.2 / 本次更新**

New look: the app is rebuilt on [Basecoat UI](https://github.com/hunvreus/basecoat) (shadcn/ui style, MIT) with a dark theme and CS2-amber accent: scoreboard tables, round grid, option switches, a sticky record bar, an overall progress bar and pop-up notices.
界面重做：基于开源的 Basecoat UI（shadcn/ui 风格），深色主题加 CS2 琥珀色点缀；计分板式选手表、回合格子、开关式选项、底部固定的录制栏、总进度条和弹出提示。

**Windows / Windows 程序**

Download **PovForge-Setup.exe**, double-click it and click through. PovForge gets a desktop icon and a Start menu entry; open it from there. Installing a newer version over it keeps your settings. Uninstall from Windows Settings → Apps.
下载 **PovForge-Setup.exe**，双击，一路"下一步"。装好后桌面和开始菜单都有 PovForge 图标，以后从那里打开。新版本直接覆盖安装即可，设置会保留。卸载：Windows 设置 → 应用。

First time: click **Install HLAE and FFmpeg** in the app. You need Steam and CS2 installed. Quit FACEIT / 5E / Perfect World before recording.
第一次使用：在软件里点 **一键安装 HLAE 和 FFmpeg**。需要已安装 Steam 和 CS2。录制前先退出 FACEIT / 5E / 完美世界。

`PovForge-windows.zip` is the same program without an installer (unzip and run `PovForge.exe`).
`PovForge-windows.zip` 是免安装版（解压后运行 `PovForge.exe`）。

Recording starts CS2 with `-insecure` (VAC off for that session); your CS2 settings are backed up and restored.
录制时 CS2 以 `-insecure` 启动（该次不连 VAC 服务器）；你的 CS2 设置会备份并在结束后还原。
