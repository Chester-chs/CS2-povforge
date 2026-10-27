## PovForge v0.20.1

Download **PovForge-Setup.exe** to install or update; **PovForge-windows.zip** is the portable edition.

### 简体中文

下载安装或更新请使用 **PovForge-Setup.exe**；免安装版使用 **PovForge-windows.zip**。

**受害者视角改成一个开关。** 打开后，集锦里的每个击杀都会补上对方阵亡前的第一人称画面（插在击杀之后，或统一放在片尾）；不再需要逐个勾选击杀。

**修复：比赛里有人掉线时，受害者视角录不出来。** 有玩家中途掉线的比赛（官匹常见）会导致整场的阵营识别失败：受害者视角为空，爆头、残局数显示为 0。现在掉线玩家会被跳过，其他人照常识别。旧的解析缓存会自动重新读取一次。

**修复：背景音乐文件找不到时被悄悄跳过。** 如果选择的音乐被移动、改名或删除，现在会在录制前直接报错提醒你重新选择，而不是生成一个没有音乐的集锦。自动录制官匹时则不加音乐继续录制。

### English

**Victim perspective is now one switch.** When on, every kill in the reel also gets the victim's view before death (after the kill, or at the end); there is no per-kill picker any more.

**Fixed: no victim replays when a player disconnected.** A disconnected player's missing team made the whole match lose its sides, which emptied victim replays and zeroed headshot/clutch counts. That player is now skipped. Old demo caches are read again once.

**Fixed: missing background music was skipped silently.** If the chosen track was moved, renamed or deleted, the reel now stops before recording and asks you to choose it again. Automatic matchmaking recording continues without music.

Development and testing did not launch CS2 or change the owner's game settings.
开发和验证未启动 CS2，未修改用户游戏设置。
