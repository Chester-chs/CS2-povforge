## PovForge v0.15.3

Download **PovForge-Setup.exe** to install or update; **PovForge-windows.zip** is the portable edition.

### English

- Fix the gray titlebar remaining in v0.15.2: Windows now uses a native window containing WebView2, rather than Edge's app window with its independently painted caption.
- Match titlebar and page backgrounds when switching between light and dark themes. Actual native windows were visually checked in both themes and maximized.
- Preserve the current recording interface, Demo caches, preferences and busy-job lifetime. Updating the app closes the native window cleanly.
- Bundle the window-host dependencies. If the stable WebView2 runtime or required .NET runtime is unavailable, keep the previous browser fallback; that fallback does not guarantee matching titlebar colors.
- Add native-window integration coverage and verify the installed native host during the Windows release workflow.

No CS2 launch or changes to the owner's game settings were made while developing this fix.

### 简体中文

下载安装或更新请使用 **PovForge-Setup.exe**；免安装版使用 **PovForge-windows.zip**。

- 修复 v0.15.2 中顶部灰色标题栏仍然分层的问题：Windows 改用原生窗口承载 WebView2，不再依赖 Edge 自行绘制的标题栏。
- 浅色、深色主题下，标题栏与主界面背景保持一致；已检查真实原生窗口的两种主题和最大化画面。
- 保留现有录制界面、Demo 缓存、偏好设置和后台任务行为，更新退出时一并关闭原生窗口。
- 安装包内附窗口组件。若系统缺少正式版 WebView2 Runtime 或所需 .NET 运行环境，将回退到原来的浏览器窗口；回退模式不保证标题栏颜色一致。
- 新增原生窗口集成测试，并在 Windows 发布流程中验证安装后的程序能够加载原生窗口。

本次修复没有启动 CS2，也没有修改用户的游戏设置。
