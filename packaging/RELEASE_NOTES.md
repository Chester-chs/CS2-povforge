**What's new in v0.8.5 / 本次更新**

- Check for updates inside the app (bottom left): it downloads the new installer, checks it against the release's SHA-256, installs quietly and reopens PovForge. Settings are kept.
  软件内检查更新（左下角）：自动下载新版安装包、核对 SHA-256、静默安装并重新打开，设置保留。
- Fixed: the installed app couldn't read demos ("No module named 'polars'"). The build now includes the libraries demoparser2 needs, and the build check reads them.
  修复：安装版读不了 demo（"No module named 'polars'"）。打包时漏了 demoparser2 需要的库，现已补上，并加入构建检查。
- New look following Apple's design guidelines: follows Windows light/dark mode, sidebar plus grouped lists, segmented control for whole match or picked rounds, switches, a bottom toolbar. The setup panel only shows up when something needs doing.
  界面按苹果设计规范重做：跟随系统浅色/深色模式，侧边栏加分组列表，"整场/选择回合"分段控件，开关和底部工具栏；准备工作只在有事要做时才出现。
- FFmpeg is built in; first-time setup only downloads HLAE (about 10 MB).
  FFmpeg 已内置，第一次只需下载 HLAE（约 10 MB）。

**Windows / Windows 程序**

Download **PovForge-Setup.exe**, double-click it and click through. PovForge gets a desktop icon and a Start menu entry; open it from there. Installing a newer version over it keeps your settings. Uninstall from Windows Settings → Apps.
下载 **PovForge-Setup.exe**，双击，一路"下一步"。装好后桌面和开始菜单都有 PovForge 图标，以后从那里打开。新版本直接覆盖安装即可，设置会保留。卸载：Windows 设置 → 应用。

First time: click **Download the recording add-on** in the app (HLAE, about 10 MB; FFmpeg is already included). You need Steam and CS2 installed. Quit FACEIT / 5E / Perfect World before recording.
第一次使用：在软件里点 **一键下载录制组件**（HLAE，约 10 MB；FFmpeg 已内置）。需要已安装 Steam 和 CS2。录制前先退出 FACEIT / 5E / 完美世界。

`PovForge-windows.zip` is the same program without an installer (unzip and run `PovForge.exe`).
`PovForge-windows.zip` 是免安装版（解压后运行 `PovForge.exe`）。

Recording starts CS2 with `-insecure` (VAC off for that session); your CS2 settings are backed up and restored.
录制时 CS2 以 `-insecure` 启动（该次不连 VAC 服务器）；你的 CS2 设置会备份并在结束后还原。
