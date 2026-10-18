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
| [cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons) by MurkyYT | Assets are Valve's / 素材版权归 Valve | Radar images and overview files are downloaded at runtime into a local cache. They are **not** stored in this repository. 雷达图与地图坐标数据在运行时下载到本地缓存，**不**存放于本仓库。 |
| [CS2-insight-agent](https://github.com/DrEAmSs59/CS2-insight-agent) by DrEAmSs59 | PolyForm Noncommercial 1.0.0 | Reference only: its notes on demo HUD settings (`cl_spec_stats`) and on backing up CS2's settings while recording. No code or files copied. 仅作参考：参考了它关于回放 HUD 设置（`cl_spec_stats`）和录制时备份 CS2 设置的说明。未复制任何代码或文件。 |
| [FFmpeg](https://ffmpeg.org) | LGPL/GPL | External program for encoding. 外部程序，用于编码合成。 |
| [Playwright for Python](https://github.com/microsoft/playwright-python) by Microsoft | Apache-2.0 | Python dependency that drives the Edge/Chrome already on the PC to screenshot the public FACEIT match room for the intro. 作为 Python 依赖库，调用电脑自带的 Edge/Chrome 截取公开的 FACEIT 比赛房间页面做片头。 |
| [pandas](https://pandas.pydata.org), [NumPy](https://numpy.org), [Pillow](https://python-pillow.org), [zstandard](https://github.com/indygreg/python-zstandard) | BSD-3-Clause / MIT-CMU (Pillow) | Python dependencies. Python 依赖库。 |

Counter-Strike 2, its maps and radar images are trademarks and property of
Valve Corporation. This project is not affiliated with Valve, FACEIT or HLTV.

Counter-Strike 2 及其地图、雷达图为 Valve Corporation 的商标与财产。本项目与 Valve、FACEIT、HLTV 无关联。
