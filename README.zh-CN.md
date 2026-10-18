[English](README.md) | 简体中文

# CS2 POVForge

一个个人、非商业用途的工具，把 Counter-Strike 2 的 demo 自动录制成指定选手的整场第一人称（POV）视频。

## 功能

- 输入一个 CS2 demo（HLTV 职业比赛、FACEIT 比赛或官方匹配）和要跟随的选手
- 以该选手的第一人称视角录制每一个回合
- 自动跳过无效时间：每回合从冻结时间结束前 3 秒开始录，不录暂停和半场换边；选手阵亡后片刻即切到下一回合
- 保留 CS2 原本的 HUD，只隐藏 demo 播放控制栏和游戏雷达
- 同步的 2D 小地图：队友位置、所在区域名、道具飞行轨迹、烟雾和燃烧瓶（带倒计时）
- 键鼠显示（Shift、Ctrl、W A S D、空格、鼠标左右键），位于 HUD 正上方
- 片头：在比赛房间截图（`--intro-image`）上写 "选手名 POV"，没有截图时使用全场战绩卡
- 按回合生成章节标记（嵌入视频，并输出可直接粘贴到 YouTube/B 站的 `chapters.txt`）

一场 28 分钟的 FACEIT demo 会生成约 16 分钟的 POV 视频。

## 工作原理

```
demo ──► 规划 ──► 录制（HLAE 驱动 CS2）──► 叠加层 ──► 合成 ──► 成片.mp4
        录哪些 tick   每回合一段，固定帧率      小地图 +    叠加 + 拼接
                                              键盘        + 章节
```

1. **规划**：用 [demoparser2](https://github.com/LaihoE/demoparser) 读取回合、死亡和坐标，为每回合确定一个 tick 区间（冻结时间结束 → 阵亡或回合结束）。
2. **录制**：通过 [HLAE](https://github.com/advancedfx/advancedfx) 启动 CS2，加载一个"导演"脚本：逐回合跳到片段开头、锁定该选手视角、以固定帧率录制，全部录完自动关闭游戏。每段的实际起始 tick 会从 CS2 的控制台日志读回，保证叠加层对齐。
3. **叠加层**：按每段录像的实际帧数渲染小地图和按键显示。
4. **合成**：用 FFmpeg 把叠加层盖到每段录像上并拼接成片。

按键数据优先使用 demo 中记录的选手真实输入指令（FACEIT demo 有），包括一个 tick 内完成的快速点按；没有时退回服务器端的按键状态。

## 环境要求

- 装有 Counter-Strike 2 的 Windows 10/11（录制需要）
- Python 3.11+
- [FFmpeg](https://ffmpeg.org) 并加入 PATH，例如 `winget install Gyan.FFmpeg`
- [HLAE](https://github.com/advancedfx/advancedfx/releases)：下载最新的 `hlae_*.zip`，解压到 `C:\Tools\hlae`（解压后应有 `C:\Tools\hlae\HLAE.exe`）
- 录制时 Steam 要开着；关闭 CS2 和各平台反作弊客户端（FACEIT、5E、完美世界）

运行 `povforge doctor` 可以一次检查全部环境。

## 安装

```
pip install git+https://github.com/Chester-chs/cs2-povforge
```

## 使用

```
povforge doctor                                # 检查环境
povforge inspect match.dem.zst                 # 查看地图、回合数、选手名
povforge run match.dem.zst donk --rounds 1-2 --placeholder   # 快速测试，不需要 CS2
povforge run match.dem.zst donk                # 正式录制
povforge run match.dem.zst donk --intro-image latest   # 用你最新的一张截图做片头
```

- 支持 `.dem`，以及 FACEIT 直接下载的 `.dem.zst` / `.dem.gz`。HLTV 的 demo 是 `.rar`，需先解压出 `.dem`。
- 选手可以写名字的一部分，也可以写 steamid。
- `--placeholder` 用灰色测试画面代替真实录制，用来检查叠加层和时间对齐。
- 每个任务保存在 `povforge-output/<demo>__<选手>/`，中断后可继续；也可以分步运行：`plan`、`overlays`、`record`、`compose`。

各项设置（片段前后留白、分辨率、叠加层大小和位置、小地图是否显示敌人等）写在 `povforge.toml`，参考 [config.example.toml](config.example.toml)。

> **关于 VAC**：录制时通过 HLAE 以 `-insecure` 启动 CS2（本次运行关闭 VAC）。录制期间不要进入任何在线服务器；之后正常从 Steam 启动即可恢复。游戏目录里只会临时添加 `cfg/povforge_job.cfg`，录制结束自动删除。

## 开发计划

- [x] 回合规划、跳过无效时间、小地图、键盘叠加层、章节
- [x] HLAE 录制后端（待首次真机测试）
- [ ] 监控文件夹，自动处理新 demo
- [ ] 从 HLTV 下载职业比赛 demo
- [ ] FACEIT：查找并下载关注选手的比赛
- [ ] 订阅模式

## FACEIT 接入说明

使用 FACEIT Data API 查询关注选手的近期比赛；FACEIT Downloads API 仅用于下载这些比赛的 demo 文件，在本地处理成 POV 视频。不会转发或出售任何 FACEIT 数据。

## 致谢

基于 [demoparser2](https://github.com/LaihoE/demoparser)（MIT）和 [HLAE](https://github.com/advancedfx/advancedfx)（MIT，作为外部程序调用）；HLAE 启动设置参考了 [CS Demo Manager](https://github.com/akiver/cs-demo-manager)（MIT，仅参考）；通过 [cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons) 获取的雷达数据（运行时下载，不存放于本仓库）以及 FFmpeg。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本项目与 Valve、FACEIT、HLTV 无关联。Counter-Strike 2 及其地图归 Valve Corporation 所有。

## 协议

[MIT](LICENSE)
