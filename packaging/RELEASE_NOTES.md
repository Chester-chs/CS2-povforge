## PovForge v0.20.2

Download **PovForge-Setup.exe** to install or update; **PovForge-windows.zip** is the portable edition.

### 简体中文

下载安装或更新请使用 **PovForge-Setup.exe**；免安装版使用 **PovForge-windows.zip**。

**受害者视角加长：阵亡前 3 秒 + 倒地后约 1 秒。** 不再在对方死亡那一刻就切走画面，而是继续显示他倒下的过程（CS2 自己的死亡画面），约 1 秒后接回主画面；如果 CS2 提前把镜头切离阵亡的玩家，就在那一刻结束。片段会受当前击杀片段的长度限制。

**修复：背景音乐文件找不到时，录制显示“Failed to execute script 'cli_main'”。** v0.20.1 会在录制前检查音乐文件，但找不到时程序直接崩溃，没有给出原因。现在会明确提示“找不到背景音乐文件”及其路径；请重新选择音乐或去掉音乐后再录制。

### English

**Longer victim perspective: 3 s before death plus about 1 s after.** The replay no longer cuts at the moment of death; it keeps CS2's own death view as the victim goes down, then returns to the main footage (earlier if CS2 moves the camera off the dead player). Each replay stays within its kill moment.

**Fixed: a missing background-music file showed "Failed to execute script 'cli_main'".** v0.20.1 checks the track before recording but crashed instead of explaining. It now says the music file was not found, with its path; choose it again or remove it, then record again.

Development and testing did not launch CS2 or change the owner's game settings.
开发和验证未启动 CS2，未修改用户游戏设置。
