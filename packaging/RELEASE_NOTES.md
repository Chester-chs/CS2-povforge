**What's new in v0.15.0 / 本次更新**

English

- Cap recording and output at 1080p / 60 fps. Remove the extra 4K upload copy and migrate old output preferences.
- Add deaths-only and kills + deaths reels, always from the selected player's first-person view in round/event order. Merge overlapping moments.
- Add opposing-player duels: mutual-kill encounters only, each A then B, with a swap control. Both views are already included, so no extra victim replay is appended in duel mode.
- Add a targeted reference-effect window: preview, select a time range, describe the effect, review a proposal, then explicitly apply that effect. Preserve unrelated settings and distinguish download failures from unsupported effects.
- Add optional music sync using actual Demo kill times. Select a continuous passage from a full song, prioritizing strong beats and energetic multi-kills, with explicit fallbacks.
- Fix exit-event round attribution, clip-end event coverage, fallback recording time bases, and reference-process cleanup during shutdown.

Known limits: knife-bound rings and other object-tracked particle effects are not supported. The supplied Bilibili example remained blocked during download; local reference files can be used. Music sync is an onset/energy heuristic and does not guarantee every kill lands exactly on a beat. New event modes were checked with real Demo parsing, browser tests and FFmpeg output tests; live CS2 recording of these new modes has not yet been verified. Existing settings backup/restoration remains in place.

简体中文

- 录制和输出最高 1080p、60 帧，移除额外 4K 上传版本，兼容迁移旧设置。
- 新增「仅死亡」「击杀＋死亡」集锦：始终使用所选选手本人的第一人称，按回合和事件时间拼接，合并重叠片段。
- 新增「双人对位」：只录敌方两人互相击杀的交手，每次先 A 后 B，可交换顺序。对位模式已包含双方视角，不再额外追加受害者重放。
- 新增指定特效窗口：预览成片、选择时间段、描述效果、查看方案，明确点击应用后才修改该效果。保留其他设置，区分下载失败与不支持的特效。
- 新增音乐自动卡点：根据 Demo 击杀时间，从整首歌曲选择连续片段，优先强拍及连杀附近的高能量段落，并明确处理回退情况。
- 修复回合结束后的事件归属、裁切终点漏掉事件、补录时间基准混用，以及关闭时参考视频子进程残留问题。

已知限制：刀身环绕光环等需要物体跟踪的复杂粒子效果暂不支持；给定 B 站示例的下载仍受限制，可改用本地参考文件。音乐卡点采用起音和能量分析，不保证每次击杀精确落拍。新模式已通过真实 Demo 解析、界面和 FFmpeg 输出验证，但尚未进行 CS2 实机录制验证。保留原有 CS2 设置备份与恢复流程。

Download **PovForge-Setup.exe** to install or update; **PovForge-windows.zip** is the portable version.
下载安装或更新请使用 **PovForge-Setup.exe**；**PovForge-windows.zip** 为免安装版。
