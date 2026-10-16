# Third-party notices / 第三方声明

CS2 POVForge's own code is MIT-licensed. It contains **no copied code** from
the projects below; it uses them as installed libraries, external programs, or
downloaded data, as described here.

本项目自身代码采用 MIT 协议，**未复制**下列项目的任何代码，仅以依赖库、外部程序或运行时下载数据的方式使用。

| Project / 项目 | License / 协议 | How it's used / 使用方式 |
|---|---|---|
| [demoparser2](https://github.com/LaihoE/demoparser) by LaihoE | MIT | Python dependency that reads `.dem` files. 作为 Python 依赖库解析 demo。 |
| [CS2 Video Generator (CSVG)](https://github.com/CS2OpenDev/CS2VideoGenerator) by CS2OpenDev | GPL-3.0 | External program, installed separately by the user and run as a command (`csvg generate`). We only write its documented JSON input. 用户自行安装的外部程序，本项目仅生成其公开文档中的 JSON 输入并调用命令行，不包含、不分发其代码。 |
| [cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons) by MurkyYT | Assets are Valve's / 素材版权归 Valve | Radar images and overview files are downloaded at runtime into a local cache. They are **not** stored in this repository. 雷达图与地图坐标数据在运行时下载到本地缓存，**不**存放于本仓库。 |
| [FFmpeg](https://ffmpeg.org) | LGPL/GPL | External program for encoding. 外部程序，用于编码合成。 |
| [pandas](https://pandas.pydata.org), [NumPy](https://numpy.org), [Pillow](https://python-pillow.org), [zstandard](https://github.com/indygreg/python-zstandard) | BSD-3-Clause / MIT-CMU (Pillow) | Python dependencies. Python 依赖库。 |

Counter-Strike 2, its maps and radar images are trademarks and property of
Valve Corporation. This project is not affiliated with Valve, FACEIT or HLTV.

Counter-Strike 2 及其地图、雷达图为 Valve Corporation 的商标与财产。本项目与 Valve、FACEIT、HLTV 无关联。
