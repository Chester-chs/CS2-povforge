## PovForge v0.15.2

Download **PovForge-Setup.exe** to install or update. For a portable copy, extract **PovForge-windows.zip** and run `PovForge.exe`.

### English

- Move the searchable Demo library into the main area; show setup only on first use or when preparation needs attention. Recommend one dedicated Demo folder and add Upload Demo for local files.
- Give modes separate sidebar entries, ordered as Whole match, Demo kill POV, Demo kills and deaths POV, Highlight reel, and Head-to-head data. Preserve existing recording functionality.
- Reuse saved Demo analysis across restarts, share concurrent inspection requests, write caches atomically, and show analysis status in the library.
- Move resolution, frame rate and player-folder controls to Recording & saving in the main area.
- Add appearance, general/storage, and about/update settings. Save theme, accent, font and popup corner radius; preserve active radius edits during background refresh.
- Unify sidebar/main backgrounds and add best-effort native titlebar colors. **Native Edge/Chrome titlebar appearance awaits screenshots after installation**; accepted Windows API calls do not guarantee the browser renders the colors.
- Clarify cleanup: saved match-list analysis and normally saved finished videos survive; detailed recording data and raw takes must be rebuilt when needed again.

Validation: 306 local automated tests and 25 director simulation assertions passed, including an isolated frontend fixture. No live CS2 recording was performed for this release, and the owner's game settings were not changed.

### 简体中文

下载安装或更新请使用 **PovForge-Setup.exe**；免安装版 **PovForge-windows.zip** 需完整解压后运行 `PovForge.exe`。

- Demo 比赛列表移入主界面，支持搜索和「上传 Demo」选择本地文件。完成配置且环境就绪后不再反复显示首次设置，并建议统一使用一个 Demo 文件夹。
- 侧边栏按顺序显示 **Demo整场录制、Demo击杀视角、Demo击杀和死亡视角、高光集锦、双人对位数据**，保留现有录制功能和选手视角规则。
- 保存并复用 Demo 解析记录，重启后仍可使用；并发打开共享一次解析，缓存采用原子写入，比赛列表显示解析状态。
- 分辨率、帧率、按选手分文件夹及文件夹名称移到主界面的「录制与保存」。
- 设置分为「外观、通用与存储、关于与更新」。支持保存主题、强调色、字体和弹窗圆角；修复后台刷新打断圆角调整的问题。
- 统一侧边栏和主界面背景，加入原生标题栏颜色适配。**Edge/Chrome 标题栏实际显示效果待安装后截图确认**，Windows 接口接受颜色不等于浏览器一定会显示该颜色。
- 明确清理工作文件的影响：比赛列表解析记录和正常保存的成片保留；再次录制时需重新生成详细录制数据和原始片段。

验证：本地 306 项自动化测试及 25 项导演脚本模拟检查通过，界面使用隔离环境测试。本次没有启动 CS2 进行实机录制，也没有修改用户的游戏设置。
