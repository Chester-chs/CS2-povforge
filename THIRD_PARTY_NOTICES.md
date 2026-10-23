# Third-party notices / 第三方声明

CS2 POVForge's own code is MIT-licensed. It contains **no copied code** from
the projects below; it uses them as installed libraries, external programs, or
downloaded data, as described here.

本项目自身代码采用 MIT 协议，**未复制**下列项目的任何代码，仅以依赖库、外部程序或运行时下载数据的方式使用。

| Project / 项目 | License / 协议 | How it's used / 使用方式 |
|---|---|---|
| [demoparser2](https://github.com/LaihoE/demoparser) by LaihoE | MIT | Python dependency that reads `.dem` files. 作为 Python 依赖库解析 demo。 |
| [HLAE / advancedfx](https://github.com/advancedfx/advancedfx) | MIT | External program, installed separately by the user. We launch CS2 through it and use its documented console commands and `mirv_script` API (our own `director.js`). 用户自行安装的外部程序；本项目通过它启动 CS2，并使用其公开的控制台命令和脚本接口（导演脚本 `director.js` 为本项目原创）。 |
| [CS Demo Manager](https://github.com/akiver/cs-demo-manager) by AkiVer | MIT | Reference only: our HLAE launch options and CS2 console settings follow what it does. No code copied. 仅作参考：HLAE 启动参数和 CS2 控制台设置参考了它的做法，未复制代码。 |
| [cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons) by MurkyYT | Assets are Valve's / 素材版权归 Valve | Map scenery thumbnails, radar images and overview files are downloaded at runtime into a local cache. They are **not** stored in this repository. 地图场景缩略图、雷达图与地图坐标数据在运行时下载到本地缓存，**不**存放于本仓库。 |
| [CS2-insight-agent](https://github.com/DrEAmSs59/CS2-insight-agent) by DrEAmSs59 | PolyForm Noncommercial 1.0.0 | Reference only: its notes on demo HUD settings (`cl_spec_stats`) and on backing up CS2's settings while recording. No code or files copied. 仅作参考：参考了它关于回放 HUD 设置（`cl_spec_stats`）和录制时备份 CS2 设置的说明。未复制任何代码或文件。 |
| [FFmpeg](https://ffmpeg.org) | GPL v3 (this build) | Run as a separate program for encoding; not linked into PovForge. 作为独立程序调用来编码合成，没有链接进 PovForge 的代码。 |
| [HLAE / advancedfx](https://github.com/advancedfx/advancedfx/releases) download | MIT | `povforge setup` / the app download the official release zip to the user's PC at runtime. Not bundled. 运行时从官方发布页下载到用户电脑，不随本项目分发。 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) download | Unlicense (its exe bundles other open-source components, see its releases) | When the user imports a finished video from a link, the app downloads the official `yt-dlp.exe` release to the user's PC (and lets it update itself) and runs it to fetch a small copy of that video, which is read and deleted. Not bundled. 用户用链接导入成片时，软件在运行时把官方发布的 `yt-dlp.exe` 下载到用户电脑（并让它自行更新），用它取一份低清晰度的视频，读完即删。不随本项目分发。 |
| [FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) by BtbN | GPL v3 | **Bundled, unmodified**: the Windows installer and zip include the win64 GPL shared build (ffmpeg.exe, ffprobe.exe and its DLLs) in the `ffmpeg` folder, with its `LICENSE.txt` and a `SOURCE.txt` naming the exact FFmpeg commit and where its source and the build scripts are. Running from source, `povforge setup` downloads the same build instead. 安装包里**原样附带** BtbN 的 GPL 版 FFmpeg（在 `ffmpeg` 文件夹），附 GPL 许可证和写明对应源码位置的 `SOURCE.txt`；用源码运行时由 `povforge setup` 下载。 |
| [Alpine.js](https://github.com/alpinejs/alpine) by Caleb Porzio | MIT | Vendored unmodified in `povforge/gui/static/vendor/alpine.min.js` (v3.17.4) with its licence. 原样随附（含许可证），用于软件界面交互。 |
| [Lucide](https://github.com/lucide-icons/lucide) icons | ISC | 41 icons copied unmodified into `povforge/gui/static/vendor/icons.svg` (lucide-static 1.59.0), licence included. 原样复制 41 个图标（含许可证）。 |
| [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines) | Apple documentation | Design reference only: the app follows its layout and control conventions (sidebar, grouped lists, segmented controls, switches) and uses Apple's published system colour values. No Apple code, fonts, icons or images are included; the CSS is written for this project. 仅作设计参考：界面遵循苹果设计规范的布局和控件习惯，使用其公开的系统颜色值；没有包含苹果的代码、字体、图标或图片，CSS 是本项目自己写的。 |
| [Inno Setup](https://github.com/jrsoftware/issrc) by Jordan Russell and Martijn Laan | Inno Setup License | Builds the Windows installer `PovForge-Setup.exe`. Its official Simplified Chinese messages file (`packaging/ChineseSimplified.isl`, maintained by Zhenghan Yang) is included unmodified with its header. 用于制作 Windows 安装包；随附其官方简体中文界面文件，原样保留文件头。 |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | GPL 2.0 with bootloader exception | Builds the Windows app; the exception allows distributing the built program under our own licence. 用于打包 Windows 程序，其例外条款允许按本项目协议分发打包结果。 |
| [pywebview](https://github.com/r0x0r/pywebview), [pythonnet](https://github.com/pythonnet/pythonnet) | BSD-3-Clause / MIT | Bundled Windows native window host and .NET bridge. 使用系统 WebView2 Runtime 显示界面，以原生窗口控制标题栏。 |
| [pandas](https://pandas.pydata.org), [NumPy](https://numpy.org), [Pillow](https://python-pillow.org), [zstandard](https://github.com/indygreg/python-zstandard) | BSD-3-Clause / MIT-CMU (Pillow) | Python dependencies. Python 依赖库。 |

Counter-Strike 2, its maps and radar images are trademarks and property of
Valve Corporation. This project is not affiliated with Valve, FACEIT or HLTV.

Counter-Strike 2 及其地图、雷达图为 Valve Corporation 的商标与财产。本项目与 Valve、FACEIT、HLTV 无关联。
