## PovForge v0.15.1

Download **PovForge-Setup.exe** to install or update. For a portable copy, extract **PovForge-windows.zip** and run `PovForge.exe`.

### English

- Event reels now offer **Kills only**, **Kills + deaths**, and **Duels**. Remove deaths-only. Keep traditional selected-round highlights and whole-match POV.
- Keep solo event reels in the selected player's first person, ordered by round and event time, merging adjacent moments. Duels remain A then B; traditional highlights retain optional ending victim replays.
- Exclude posthumous kills that cannot be shown from the attacker's living POV before recording. Refresh cached demo information so event counts and duel choices follow the same rule.
- Block manual settings restoration while CS2, recording or cancellation cleanup is active, and serialize restoration with recording startup.
- Validate interrupted raw recordings before reuse. Re-record incomplete or unreadable takes, while preserving valid footage when output packaging fails.
- Restrict thumbnail access to the resolved output directory. Validate the local server's Host and protect write requests with Origin checks and a session token.
- Rewrite English and Chinese READMEs with download links, first-use steps, mode comparisons and troubleshooting. Clarify that output playback duration is not the time required to record and encode it.

Validation: 284 local automated tests passed, along with 25 director simulation assertions. Independent review follow-ups were fixed and rechecked. No live CS2 recording was performed for this update, and the owner's game settings were not accessed or changed. Automated results do not replace live recording validation.

### 简体中文

下载安装或更新请使用 **PovForge-Setup.exe**；免安装版 **PovForge-windows.zip** 需完整解压后运行 `PovForge.exe`。

- 事件集锦保留 **仅击杀、击杀＋死亡、双人对位**，移除仅死亡；保留原有高光集锦和整场 POV。
- 单人事件保持所选选手本人的第一人称，按回合、事件时间排序并合并相邻片段。对位仍为每次 A → B；传统高光保留片尾追加被击杀者视角的选项。
- 录制前过滤无法由攻击者存活视角覆盖的死后击杀，并更新 demo 缓存，使界面统计和对位选择采用相同规则。
- CS2、录制或取消清理仍在运行时，禁止手动恢复设置；恢复与录制启动互斥，避免覆盖冲突。
- 复用录像前检查完整性；中断、损坏或过短的素材重新录制，输出封装失败时保留已经完整录好的原始素材。
- 修复缩略图路径越界，并为本地网页接口加入监听地址校验、Origin 检查及会话令牌。
- 中英文 README 面向第一次使用者重写，补齐下载、上手、模式说明和常见问题，明确成片播放时长不等于实际录制与编码耗时。

验证：本地 284 项自动化测试和 25 项导演脚本模拟断言通过，独立复审发现的补充问题已修复并复核。本次未进行 CS2 实机录制，也未访问或修改用户的实际游戏设置；自动化结果不代表已完成实机录制验收。
