## PovForge v0.15.6

Download **PovForge-Setup.exe** to install or update; **PovForge-windows.zip** is the portable edition.

### English

- Choose 1080P, 2K (1440P), 4K, or Fit screen, and enter an integer frame rate from 1 to 240 FPS. Preferences, recording commands and video exports now honor these values instead of forcing 1080p/60.
- Smaller game footage is scaled to the chosen output size; upscaling does not add native detail. Higher quality uses more processing time and storage.
- Keep one app name in the native titlebar; remove the duplicate sidebar logo and name.
- Return to the top when opening a match, continuing to player/round selection or switching recording modes.
- Keep Demo analysis when changing quality; move incompatible old takes aside so they are not silently reused.

### 简体中文

下载安装或更新请使用 **PovForge-Setup.exe**；免安装版使用 **PovForge-windows.zip**。

- 可选 1080P、2K（1440P）、4K 或适应屏幕；帧率可填写 1–240 的整数。偏好保存、录制命令与视频输出均采用所选参数，不再强制回到 1080p/60。
- 若游戏实际画面较小，成片会放大到所选尺寸，但不会增加原生细节。更高画质需要更多处理时间和空间。
- 保留原生标题栏中的名称，删除侧边栏重复的图标和名称。
- 打开比赛、点击继续进入选手或回合选择、切换录制模式时自动回到页面顶部。
- 改画质后仍保留 Demo 解析记录；不兼容的旧录制片段另存到工作目录，避免误用。

Validation includes synthetic FFmpeg encoding and isolated UI tests. CS2 was not launched and the owner's game settings were not changed; native game capture at higher settings has not been tested here.
验证包括 FFmpeg 测试视频编码和隔离界面测试。未启动 CS2，未修改用户游戏设置；本次未实测游戏原生高分辨率录制。
