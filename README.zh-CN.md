[English](README.md) | 简体中文

# CS2 POVForge

一个个人、非商业用途的工具，把 Counter-Strike 2 的 demo 自动录制成指定选手的整场第一人称（POV）视频。

## 功能

- 输入一个 CS2 demo（HLTV 职业比赛或 FACEIT 比赛）和要跟随的选手
- 以该选手的第一人称视角录制整场比赛
- 自动跳过无效时间：冻结时间、暂停、半场换边，以及选手阵亡后的剩余回合时间
- 叠加同步的 2D 小地图和键盘按键显示（W/A/S/D、跳、蹲、开火）
- 订阅模式：关注的选手有新比赛时自动加入录制队列

## FACEIT 接入说明

使用 FACEIT Data API 查询关注选手的近期比赛；FACEIT Downloads API 仅用于下载这些比赛的 demo 文件，在本地处理成 POV 视频。不会转发或出售任何 FACEIT 数据。

## 状态

早期开发中。

## 免责声明

本项目与 Valve、FACEIT、HLTV 无任何关联。demo 播放仅在用户本地的 CS2 中进行，不会连接任何 VAC 保护的服务器。
