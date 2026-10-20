// PovForge app page (Alpine.js component).

const TEXT = {
  zh: {
    byPlayer: "按选手分文件夹", byPlayerHelp: "成片放进 保存位置/选手名/，几个选手的集锦放进「多人集锦」。文件夹名可以在下面改。",
    folderOf: "{name} 的文件夹", folderTaken: "已经有这个名字的文件夹了。", folderBusy: "正在录制，录完再改名。",
    modesLabel: "做什么", modeMatch: "整场录制", demosForReel: "点选要用的 demo", reelPickLeft: "在左边的 demo 列表里点选要用的场次，可以选好几场。",
    styleTitle: "成片风格", styleHelp: "不导入成片时，集锦原样拼接、不加任何效果。导入一个做好的集锦，软件读出它的开头、转场、击杀特效和结尾，存成你命名的风格，做集锦时照着加。",
    stylePlain: "不加效果", styleUnsaved: "{name}（未命名）", styleMix: "混搭", mixHelp: "也可以按项挑：每一项都来自你导入过的成片。",
    fromList: "来自 {list}",
    presetNameLabel: "给这组效果起个名字，存成你的预设", presetSaveRef: "存成预设", presetSaved: "已存为预设「{name}」，以后在上面的预设里直接选。",
    presetReplace: "已有同名预设，保存会替换它。", fromFile: "来自 {name}", vNone: "无", vYes: "有", vNo: "没有", vAbout: "约 {s} 秒", vTimes: "{n} 处",
    vAlso: "也有 {list}", vMatch: "{kind}，会照着它调", vPace: "每段约 {s} 秒，{kind}", vMusic: "有，约 {bpm} BPM", nowLabel: "当前效果：{text}", nowPlain: "当前：原样拼接，不加效果",
    fxTitle: "效果", fxHelp: "录制前选好，合成集锦时加上。不选就是原样拼接。", fxCopy: "导入成片…",
    preset_plain: "原样", preset_hype: "燃", preset_cinematic: "电影感", preset_clean: "简洁", presetRef: "照参考视频", presetCustom: "自定义",
    fxSave: "存为我的预设", fxSaveName: "给这组效果起个名字", save: "保存",
    fxIntro: "开头", intro_none: "无", intro_fade: "黑场渐入", intro_title: "标题卡", introText: "标题", introSub: "副标题",
    fxTransition: "转场", fxTransitionHelp: "段与段之间怎么切", fxLength: "时长", sec: "{s} 秒", gradeLike: "照着成片调色",
    tr_cut: "硬切", tr_flash: "闪白", tr_black: "黑场", tr_dissolve: "叠化", tr_slide: "推移", tr_wipe: "擦除", tr_zoom: "缩放", tr_blur: "模糊", tr_pixel: "像素化",
    fxKills: "击杀特效", fxKillsHelp: "击杀那一刻加上", k_slowmo: "慢动作", k_zoom: "放大", k_flash: "闪白", k_shake: "震动",
    fxScope: "加在哪些击杀上", scope_all: "每个击杀", scope_last: "每段最后一杀", scope_final: "只在全片最后一杀", slowAt: "{x} 倍速",
    fxGrade: "调色", g_none: "原色", g_vivid: "鲜艳", g_cinematic: "电影感", g_cool: "冷色", g_warm: "暖色", g_bw: "黑白", g_match: "照参考视频",
    fxBars: "电影黑边", fxBarsHelp: "上下加黑边（2.35:1）",
    fxOutro: "结尾", o_none: "无", o_fade: "渐黑", o_freeze: "定格", o_card: "结尾卡", outroText: "结尾文字", outroTextDefault: "感谢观看",
    fxPace: "节奏", fxPaceHelp: "每段在击杀前后留多久", pace_tight: "紧凑", pace_normal: "标准", pace_long: "舒缓",
    fxMusic: "背景音乐", musicNone: "不加", musicPick: "选择音乐…", musicVol: "音乐音量 {v}%", gameAudio: "游戏声音",
    game_keep: "保留", game_low: "调低", game_mute: "静音",
    analyzing: "正在分析 {name}…", analyzingHelp: "视频越长越久，通常一分钟内。", analyzeFailed: "没能分析这个视频",
    repTitle: "从 {name} 读到的效果，已填进下面的设置", repNothing: "没找到明显的特效：硬切、原色。",
    repNote: "做出来是同样的风格和节奏，不是逐帧复制。下面还可以再改。",
    rep_intro: "开头：{kind}（约 {s} 秒）", rep_transition: "转场：{kind}，约 {s} 秒（{n} 处）", rep_cuts: "转场：硬切（{n} 处）", rep_mixed: "；也有 {list}",
    rep_pace: "每段约 {s} 秒（{kind}）", rep_kill: "击杀特效：{kind}（{n} 处）", rep_colour: "调色：{kind}，会照着它调", rep_letterbox: "有电影黑边",
    rep_outro: "结尾：{kind}（约 {s} 秒）", rep_music: "有背景音乐（约 {bpm} BPM）", useMusic: "用这段视频的声音做背景音乐", musicUsed: "已用作背景音乐",
    look_natural: "自然", look_vivid: "鲜艳", look_muted: "偏淡", look_warm: "偏暖", look_cool: "偏冷", look_bw: "黑白",
    reelNav: "高光集锦", makeReel: "做集锦", reelTitle: "高光集锦", reelBody: "挑出最精彩的回合拼在一起。每个回合从第一个击杀前几秒连续到最后一个击杀后，中间不剪。只用游戏画面，不加小地图；导入做好的成片，可以照着它的风格加效果。",
    reelName: "名称", reelSources: "素材", reelSourcesHelp: "在左边点选，可以多选", reelPlayer: "选手",
    reelSame: "同一个人", reelEach: "每场分别选", reelEachHelp: "在上面每场 demo 的右边选这场用哪位选手。", reelPlayerIn: "{name}（{n} 场）", reelNotIn: "这场没有这名选手", reelPick: "选择选手",
    reelItems: "集锦内容", reelItemsHelp: "已自动挑出 3 杀以上和残局获胜的回合，按精彩程度排好，最强的放最后。拖动或用箭头调整顺序。",
    reelEmpty: "还没有回合。先勾选 demo 和选手，或从下面“其他回合”里加。", reelMore: "其他回合（{n}）",
    reelCount: "{n} 段", roundN: "第 {r} 回合", tagClutch: "1v{n} 残局", tagHs: "{n} 爆头", kills1: "{n} 杀",
    reelMake: "开始制作", reelQueue: "加入队列", reelNeedItems: "至少加一个回合。", up: "上移", down: "下移", add: "加入",
    stage_cut: "剪辑集锦", making: "正在制作 {name}", reelDone: "集锦做好了", anotherReel: "再做一个集锦", reelDefault: "{name} 高光集锦", reelDefaultMany: "高光集锦",
    reelSummary: "集锦，{n} 段", reelEmptySources: "demo 文件夹里还没有 demo。", reelStageRead: "读取 demo（第 {a} / {b} 场）",
    foldersTitle: "文件夹", demoFolderLabel: "从这里读取 demo", outputFolderLabel: "成片保存到", useFolders: "就用这两个",
    foldersHelp: "PovForge 会列出 demo 文件夹里的 demo，做好的视频放进保存文件夹。之后可以随时在这里或设置里更改。",
    hintFolders: "先选择 demo 和成片的文件夹",
    workFiles: "工作文件", workUsed: "占用 {size}", workNone: "没有", open: "打开", clean: "清理", cleanSure: "确定删除？", cleaning: "正在清理…",
    workHelp: "录制时留下的原始画面和中间文件，用来重试、改选项重新出片和再做集锦时直接复用。删掉不影响已经做好的视频，只是以后重做要重新录。",
    cleaned: "已清理 {size}", workBusy: "队列里还有录制任务，录完再清理。",
    settings: "设置", appearance: "外观", appAuto: "自动", appLight: "浅色", appDark: "深色", accent: "强调色", language: "语言",
    acc_blue: "蓝色", acc_purple: "紫色", acc_pink: "粉色", acc_red: "红色", acc_orange: "橙色", acc_yellow: "黄色", acc_green: "绿色", acc_graphite: "石墨色",
    checkUpdate: "检查更新", upChecking: "正在检查更新…", upCurrent: "已是最新版本", upCurrentBody: "PovForge {v} 是目前最新的版本。",
    upAvailable: "PovForge {v} 可以更新了", upYouHave: "你现在用的是 {v}。", upInstall: "更新并重新打开", upOpenPage: "去下载页面",
    upDownloading: "正在下载 PovForge {v}（只下载有变化的文件）", upMb: "{a} / {b} MB", upInstalling: "正在安装…",
    upInstallingBody: "PovForge 会关闭，装好后自动重新打开，设置都会保留。", upError: "更新没有完成", upBusy: "正在录制，录完再更新。",
    later: "以后再说", ok: "好", close: "关闭", cancel: "取消", upStarting: "正在准备更新…",
    upTimeout: "连接 GitHub 超时。检查一下网络后重试。", upNotStarted: "更新没能开始，请重试。",
    povOf: "{name} 的第一人称视角",
    finishSetup: "完成准备工作", hintCs2: "没找到 CS2", hintTools: "需要下载录制组件", hintAc: "请先退出反作弊客户端",
    someRounds: "选择回合", won: "胜", change: "更改…", failedTitle: "录制没有完成", notDemo: "这不是 CS2 的 demo 文件（.dem、.dem.zst、.dem.gz）。",
    playerCol: "选手", readyAll: "就绪", notReady: "未就绪", pickTitle: "选择选手", roundsHelp: "点一下选中或取消。小点是击杀数，红线表示这回合阵亡。",
    legendPicked: "要录", optsTitle: "成片内容", recordShort: "开始录制",
    optIntroHelp: "FACEIT 计分板截图和比赛时间", optMinimapHelp: "左上角雷达和队友位置",
    optKeyboardHelp: "画面下方显示按键和鼠标", optEnemiesHelp: "雷达上也画出敌人",
    optHighlightsHelp: "另存一个只有击杀片段的短视频", optUploadHelp: "生成封面图、投稿标题和章节",
    queueTitle: "录制队列", clearDone: "清除已完成", resume: "继续队列", remove: "移除",
    queueIt: "把 {name} 加入队列", addQueue: "加入队列，接着选", queuedNote: "{name} 已加入队列。", nRounds: "{n} 个回合", wholeMatch: "整场",
    st_queued: "排队中", st_running: "录制中", st_done: "完成", st_error: "失败", st_cancelled: "已停止",
    optHighlights: "精华版", optUpload: "封面和简介", stage_extras: "生成精华版、封面和简介",
    playHighlights: "播放精华版", titleLabel: "投稿标题", copy: "复制", copied: "已复制", openDesc: "打开简介和章节",
    updateAvail: "更新到 {v}", download: "下载",
    setupTitle: "开始之前", setupBody: "录制前需要准备好下面几项，只需要做一次。",
    ckCs2: "安装 Steam 和 CS2", ckCs2Help: "在 Steam 里安装 Counter-Strike 2，装好后这里会自动变绿。",
    ckTools: "下载录制组件", ckToolsHelp: "点下面的按钮，自动从官方 GitHub 下载 {list}（{size}），不用自己找。", ckToolsDone: "已就绪。",
    ckAc: "退出反作弊客户端", ckAcDone: "FACEIT、5E、完美世界都没有在运行。",
    ckDemo: "准备一个 demo", ckDemoHelp: "从 FACEIT 比赛房间或 HLTV 下载 demo，放进 demo 文件夹即可。", ckDemoDone: "demo 文件夹里有 {n} 个 demo，在左边选一个。",
    offlineTitle: "PovForge 已经关闭", offlineBody: "后台程序已退出。重新打开 PovForge 即可继续。",
    demos: "Demo", refresh: "刷新", lookingIn: "正在看：", noDemos: "这个文件夹里还没有 demo。下载一个 FACEIT 或 HLTV demo，或者手动选择文件。",
    openFile: "选择 demo 文件…", demoFolder: "更换 demo 文件夹…",
    setup: "准备工作", found: "已就绪", cs2Missing: "没找到，请先在 Steam 安装", notInstalled: "未安装",
    antiCheat: "反作弊", running: "正在运行", closed: "已关闭", installTools: "一键下载录制组件",
    preparing: "准备中…", settingsPending: "上次录制被打断，你的 CS2 设置还没还原。", restoreNow: "立即还原",
    safeNote: "录制不会改动你的 CS2 设置。",
    blankTitle: "选一个 demo", blankBody: "左边是 demo 文件夹里的 demo。选好比赛和选手，就能得到这名选手整场的第一人称视频。",
    reading: "正在读取 demo", readingBody: "解压并分析比赛，通常需要十几秒。", cantRead: "读不了这个 demo",
    rounds: "回合", minDemo: "分钟", others: "其他",
    pickPlayer: "点一位选手，录他的第一人称视角。", playerPicked: "默认录整场，也可以只选其中几个回合。",
    roundsTitle: "要录的回合", all: "全选", none: "清空",
    legendKill: "这回合的击杀", legendDied: "这回合阵亡",
    optIntro: "片头", optMinimap: "小地图", optKeyboard: "键鼠显示", optEnemies: "小地图显示敌人",
    saveTo: "保存到", record: "录制 {name} 的 POV",
    needRounds: "至少选一个回合。", needTools: "先下载录制组件（左下角一键下载）。", needCs2: "没找到 CS2。",
    needAntiCheat: "请先彻底退出 {list}（托盘图标 → 退出），它会阻止录制。", needWindows: "录制需要在 Windows 上运行。",
    recording: "正在录制 {name}", recorded: "录好了", failed: "没能完成", stopped: "已停止",
    stage_read: "读取 demo", stage_record: "在 CS2 里录制回合", stage_overlays: "生成小地图和键鼠画面",
    stage_intro: "制作片头", stage_compose: "合成视频",
    openMissing: "找不到这个文件，可能已被移动或删除。", openFailed: "没能打开：{e}",
    play: "播放视频", showFolder: "打开所在文件夹", another: "再录一个", retry: "重试", back: "返回",
    stop: "停止录制", details: "详细信息", cancelled: "录制已停止。你的 CS2 设置已还原。",
    retryHint: "重试时已录好的回合会直接复用。",
    roundTip: "第 {r} 回合：{k} 杀{d}", roundTipDied: "，阵亡",
    keep: "CS2 会在录完后自己关闭，期间别用电脑玩游戏。",
  },
  en: {
    byPlayer: "A folder per player", byPlayerHelp: "Videos go into save folder/player name/; reels of several players into \u201cMulti-player reels\u201d. Rename the folders below.",
    folderOf: "{name}'s folder", folderTaken: "There is already a folder with this name.", folderBusy: "A recording is running; rename it when it's done.",
    modesLabel: "What to make", modeMatch: "Whole match", demosForReel: "Pick demos for the reel", reelPickLeft: "Pick the demos to use in the list on the left; several are fine.",
    styleTitle: "Style", styleHelp: "Without a finished video the rounds are simply joined, no effects. Import a finished highlight video and PovForge reads its opening, transitions, kill effects and ending, keeps them as a style you name, and adds them to your reel.",
    stylePlain: "No effects", styleUnsaved: "{name} (unnamed)", styleMix: "Mixed", mixHelp: "Or pick item by item; every choice comes from a video you imported.",
    fromList: "from {list}",
    presetNameLabel: "Name these effects to keep them as your preset", presetSaveRef: "Save preset", presetSaved: "Saved as \u201c{name}\u201d; pick it from the presets above any time.",
    presetReplace: "A preset with this name exists; saving replaces it.", fromFile: "from {name}", vNone: "None", vYes: "Yes", vNo: "No", vAbout: "about {s} s", vTimes: "{n}×",
    vAlso: "also {list}", vMatch: "{kind}; yours will be matched to it", vPace: "about {s} s per moment, {kind}", vMusic: "yes, about {bpm} BPM", nowLabel: "Now: {text}", nowPlain: "Now: plain join, no effects",
    fxTitle: "Effects", fxHelp: "Chosen before recording, added when the reel is put together. None: the rounds are simply joined.", fxCopy: "Import a finished video…",
    preset_plain: "Plain", preset_hype: "Hype", preset_cinematic: "Cinematic", preset_clean: "Clean", presetRef: "Like the reference", presetCustom: "Custom",
    fxSave: "Save as my preset", fxSaveName: "Name these effects", save: "Save",
    fxIntro: "Opening", intro_none: "None", intro_fade: "Fade in", intro_title: "Title card", introText: "Title", introSub: "Subtitle",
    fxTransition: "Transition", fxTransitionHelp: "Between the moments", fxLength: "Length", sec: "{s} s", gradeLike: "matched to the video",
    tr_cut: "Cut", tr_flash: "Flash", tr_black: "Dip to black", tr_dissolve: "Dissolve", tr_slide: "Push", tr_wipe: "Wipe", tr_zoom: "Zoom", tr_blur: "Blur", tr_pixel: "Pixelate",
    fxKills: "Kill effects", fxKillsHelp: "On the moment of the kill", k_slowmo: "Slow motion", k_zoom: "Zoom", k_flash: "Flash", k_shake: "Shake",
    fxScope: "On which kills", scope_all: "Every kill", scope_last: "Last kill of each moment", scope_final: "Only the final kill", slowAt: "{x}× speed",
    fxGrade: "Colour", g_none: "Original", g_vivid: "Vivid", g_cinematic: "Cinematic", g_cool: "Cool", g_warm: "Warm", g_bw: "Black and white", g_match: "Like the reference",
    fxBars: "Cinema bars", fxBarsHelp: "Black bars top and bottom (2.35:1)",
    fxOutro: "Ending", o_none: "None", o_fade: "Fade out", o_freeze: "Freeze frame", o_card: "End card", outroText: "End card text", outroTextDefault: "Thanks for watching",
    fxPace: "Pace", fxPaceHelp: "Time kept around the kills", pace_tight: "Tight", pace_normal: "Normal", pace_long: "Relaxed",
    fxMusic: "Music", musicNone: "None", musicPick: "Choose music…", musicVol: "Music volume {v}%", gameAudio: "Game sound",
    game_keep: "Keep", game_low: "Lower", game_mute: "Mute",
    analyzing: "Reading {name}…", analyzingHelp: "Longer videos take longer; usually under a minute.", analyzeFailed: "Couldn't read this video",
    repTitle: "Found in {name}, filled in below", repNothing: "No clear effects found: straight cuts, original colour.",
    repNote: "You get the same style and pace, not a frame-by-frame copy. You can still change everything below.",
    rep_intro: "Opening: {kind} (about {s} s)", rep_transition: "Transition: {kind}, about {s} s ({n}×)", rep_cuts: "Transition: cut ({n}×)", rep_mixed: "; also {list}",
    rep_pace: "About {s} s per moment ({kind})", rep_kill: "Kill effect: {kind} ({n}×)", rep_colour: "Colour: {kind}; yours will be matched to it", rep_letterbox: "Cinema bars",
    rep_outro: "Ending: {kind} (about {s} s)", rep_music: "Background music (about {bpm} BPM)", useMusic: "Use this video's sound as the music", musicUsed: "Used as the music",
    look_natural: "natural", look_vivid: "vivid", look_muted: "muted", look_warm: "warm", look_cool: "cool", look_bw: "black and white",
    reelNav: "Highlight reel", makeReel: "Make a reel", reelTitle: "Highlight reel", reelBody: "The best rounds joined together. Each round runs unbroken from a few seconds before its first kill to just after its last. Game picture only, no minimap; import a finished video to give it that video's style.",
    reelName: "Name", reelSources: "Demos", reelSourcesHelp: "Pick them on the left; several are fine", reelPlayer: "Player",
    reelSame: "Same player", reelEach: "Per demo", reelEachHelp: "Choose the player for each demo on its row above.", reelPlayerIn: "{name} ({n} demos)", reelNotIn: "This player isn't in this demo", reelPick: "Choose a player",
    reelItems: "In the reel", reelItemsHelp: "Rounds with 3+ kills and won clutches are picked for you, best last. Drag or use the arrows to change the order.",
    reelEmpty: "No rounds yet. Tick demos and a player, or add some from Other rounds below.", reelMore: "Other rounds ({n})",
    reelCount: "{n} rounds", roundN: "Round {r}", tagClutch: "1v{n} clutch", tagHs: "{n} HS", kills1: "{n} kill",
    reelMake: "Make the reel", reelQueue: "Add to queue", reelNeedItems: "Add at least one round.", up: "Move up", down: "Move down", add: "Add",
    stage_cut: "Cut the reel", making: "Making {name}", reelDone: "Your reel is ready", anotherReel: "Make another reel", reelDefault: "{name} highlights", reelDefaultMany: "Highlights",
    reelSummary: "Reel, {n} rounds", reelEmptySources: "No demos in your demo folder yet.", reelStageRead: "Read the demo ({a} of {b})",
    foldersTitle: "Folders", demoFolderLabel: "Read demos from", outputFolderLabel: "Save videos to", useFolders: "Use these",
    foldersHelp: "PovForge lists the demos in the demo folder and puts finished videos in the save folder. You can change them here or in Settings any time.",
    hintFolders: "Choose your demo and video folders",
    workFiles: "Work files", workUsed: "{size} used", workNone: "None", open: "Open", clean: "Clean up", cleanSure: "Delete them?", cleaning: "Cleaning…",
    workHelp: "Recordings and in-between files, reused when you retry, re-render with other options or make a reel. Deleting them keeps your finished videos; redoing one just means recording again.",
    cleaned: "{size} freed", workBusy: "Recordings are still queued; clean up when they're done.",
    settings: "Settings", appearance: "Appearance", appAuto: "Auto", appLight: "Light", appDark: "Dark", accent: "Accent colour", language: "Language",
    acc_blue: "Blue", acc_purple: "Purple", acc_pink: "Pink", acc_red: "Red", acc_orange: "Orange", acc_yellow: "Yellow", acc_green: "Green", acc_graphite: "Graphite",
    checkUpdate: "Check for updates", upChecking: "Checking for updates…", upCurrent: "You're up to date", upCurrentBody: "PovForge {v} is the latest version.",
    upAvailable: "PovForge {v} is available", upYouHave: "You have {v}.", upInstall: "Update and reopen", upOpenPage: "Open download page",
    upDownloading: "Downloading PovForge {v} (only the files that changed)", upMb: "{a} of {b} MB", upInstalling: "Installing…",
    upInstallingBody: "PovForge will close and open again when the update is installed. Your settings are kept.", upError: "The update didn't finish", upBusy: "A recording is running; update when it's done.",
    later: "Later", ok: "OK", close: "Close", cancel: "Cancel", upStarting: "Getting the update ready…",
    upTimeout: "GitHub didn't answer in time. Check the connection and try again.", upNotStarted: "The update didn't start. Try again.",
    povOf: "{name}'s first-person view",
    finishSetup: "Finish setting up", hintCs2: "CS2 not found", hintTools: "Recording add-on needed", hintAc: "Quit the anti-cheat client",
    someRounds: "Pick rounds", won: "Won", change: "Change…", failedTitle: "The recording didn't finish", notDemo: "Not a CS2 demo file (.dem, .dem.zst, .dem.gz).",
    playerCol: "Player", readyAll: "Ready", notReady: "Not ready", pickTitle: "Choose a player", roundsHelp: "Click to select or clear. Dots are kills; a red line means they died.",
    legendPicked: "to record", optsTitle: "What goes in the video", recordShort: "Start recording",
    optIntroHelp: "FACEIT scoreboard and match time", optMinimapHelp: "Radar with teammates, top left",
    optKeyboardHelp: "Keys and mouse along the bottom", optEnemiesHelp: "Draw enemies on the radar too",
    optHighlightsHelp: "A short extra video of just the kills", optUploadHelp: "Cover image, upload title and chapters",
    queueTitle: "Queue", clearDone: "Clear finished", resume: "Resume queue", remove: "Remove",
    queueIt: "Add {name} to the queue", addQueue: "Queue and pick another", queuedNote: "{name} added to the queue.", nRounds: "{n} rounds", wholeMatch: "Whole match",
    st_queued: "Waiting", st_running: "Recording", st_done: "Done", st_error: "Failed", st_cancelled: "Stopped",
    optHighlights: "Highlights cut", optUpload: "Cover and description", stage_extras: "Make highlights, cover and description",
    playHighlights: "Play highlights", titleLabel: "Upload title", copy: "Copy", copied: "Copied", openDesc: "Open description and chapters",
    updateAvail: "Update to {v}", download: "Download",
    setupTitle: "Before you start", setupBody: "Recording needs the things below. You only do this once.",
    ckCs2: "Install Steam and CS2", ckCs2Help: "Install Counter-Strike 2 in Steam; this turns green once it's found.",
    ckTools: "Download the recording add-on", ckToolsHelp: "Click the button and {list} is downloaded from its official GitHub page ({size}).", ckToolsDone: "Ready.",
    ckAc: "Quit anti-cheat clients", ckAcDone: "FACEIT, 5E and Perfect World aren't running.",
    ckDemo: "Get a demo", ckDemoHelp: "Download a demo from a FACEIT match room or HLTV into your demo folder.", ckDemoDone: "{n} demos in your demo folder; pick one on the left.",
    offlineTitle: "PovForge has closed", offlineBody: "The background program stopped. Open PovForge again to carry on.",
    demos: "Demos", refresh: "Refresh", lookingIn: "Looking in", noDemos: "No demos in this folder yet. Download a FACEIT or HLTV demo, or choose a file.",
    openFile: "Choose a demo file…", demoFolder: "Change demo folder…",
    setup: "Setup", found: "Ready", cs2Missing: "Not found, install it in Steam", notInstalled: "Not installed",
    antiCheat: "Anti-cheat", running: "running", closed: "Closed", installTools: "Download the recording add-on",
    preparing: "Preparing…", settingsPending: "A recording was interrupted and your CS2 settings aren't restored yet.", restoreNow: "Restore now",
    safeNote: "Recording never changes your CS2 settings.",
    blankTitle: "Pick a demo to start", blankBody: "Demos from your demo folder are listed on the left. Choose a match and a player to get their full first-person video.",
    reading: "Reading the demo", readingBody: "Unpacking and analysing the match usually takes a few seconds.", cantRead: "Can't read this demo",
    rounds: "rounds", minDemo: "min", others: "Others",
    pickPlayer: "Click a player to record their first-person view.", playerPicked: "The whole match is recorded unless you pick rounds.",
    roundsTitle: "Rounds to record", all: "All", none: "None",
    legendKill: "kill this round", legendDied: "died this round",
    optIntro: "Intro", optMinimap: "Minimap", optKeyboard: "Keys and mouse", optEnemies: "Enemies on minimap",
    saveTo: "Save to", record: "Record {name}'s POV",
    needRounds: "Choose at least one round.", needTools: "Download the recording add-on first (bottom left).", needCs2: "CS2 wasn't found.",
    needAntiCheat: "Quit {list} completely first (tray icon → Exit); it blocks recording.", needWindows: "Recording needs Windows.",
    recording: "Recording {name}", recorded: "Done", failed: "Didn't finish", stopped: "Stopped",
    stage_read: "Read the demo", stage_record: "Record rounds in CS2", stage_overlays: "Draw minimap and keys",
    stage_intro: "Make the intro", stage_compose: "Put the video together",
    openMissing: "This file wasn't found; it may have been moved or deleted.", openFailed: "Couldn't open it: {e}",
    play: "Play video", showFolder: "Show in folder", another: "Record another", retry: "Try again", back: "Back",
    stop: "Stop recording", details: "Details", cancelled: "Recording stopped. Your CS2 settings are restored.",
    retryHint: "Rounds already recorded are reused when you try again.",
    roundTip: "Round {r}: {k} kills{d}", roundTipDied: ", died",
    keep: "CS2 closes by itself when it's done; don't play games on the PC meanwhile.",
  },
};

document.addEventListener("alpine:init", () => {
  Alpine.data("povforge", () => ({
    version: "", lang: "zh", prefs: {}, setup: {}, job: { state: "idle", lines: [], recorded: [], planned: [], step: [0, 0] },
    demos: [], demosLoaded: false, offline: false, failures: 0, demo: null, inspecting: false, inspectError: "",
    updateOpen: false, updatingAway: false, upd: { state: "idle" },
    player: null, chosenRounds: [], lastRun: null, setupOpen: false, customRounds: false, lastPath: "",
    settingsOpen: false, reelOpen: false, dragFrom: null, work: { bytes: null, path: "", confirm: false, cleaning: false },
    reel: { title: "", titleEdited: false, mode: "same", steamid: "", sources: [], items: [], reordered: false },
    fx: null, fxMeta: { defaults: {}, presets: {}, transitions: [], grades: [] }, fxPreset: "plain", fxSaveOpen: false, fxSaveName: "",
    styleRef: { state: "idle", name: "", path: "", report: [], music: null, effects: null, musicUsed: false, error: "", presetName: "", savedAs: "" },
    accents: ["blue", "purple", "pink", "red", "orange", "yellow", "green", "graphite"],
    options: [
      { key: "intro", label: "optIntro" }, { key: "minimap", label: "optMinimap" }, { key: "keyboard", label: "optKeyboard" },
      { key: "show_enemies", label: "optEnemies" }, { key: "upload", label: "optUpload" },
    ],
    queue: { items: [], paused: false }, update: null, showRun: false, viewId: null, toasts: [], toastSeq: 0,

    async boot() {
      // closing the window: tell the app at once (a reload checks in again straight away)
      window.addEventListener("pagehide", () => { try { navigator.sendBeacon("/api/bye", "{}"); } catch (_) {} });
      fetch("/static/vendor/icons.svg").then(r => r.text()).then(s => { document.getElementById("icons").innerHTML = s; });
      await this.refresh();
      this.applyTheme();
      this.showRun = this.job.state === "running";
      this.lang = this.prefs.lang || (navigator.language.startsWith("zh") ? "zh" : "en");
      document.documentElement.lang = this.lang === "zh" ? "zh-CN" : "en";
      this.setupOpen = !this.ready;
      this.loadDemos();
      const tick = async () => {
        try {
          if (this.job.state === "running") { const j = await this.get("/api/job"); this.queue = j.queue; this.job = j; }
          else await this.refresh();
          if (this.updateOpen && ["downloading", "installing"].includes(this.upd.state)) this.upd = await this.get("/api/update");
          this.failures = 0; this.offline = false;
        } catch (e) {
          if (++this.failures >= 3) this.offline = true;
          if (this.upd.state === "installing") { this.updatingAway = true; try { window.close(); } catch (_) {} }
        }
        setTimeout(tick, this.job.state === "running" || this.updateOpen ? 1000 : 2500);
      };
      setTimeout(tick, 1000);
      this.$watch("job.lines", () => this.$nextTick(() => { const el = this.$refs.log; if (el) el.scrollTop = el.scrollHeight; }));
    },

    t(key, vars = {}) {
      let s = (TEXT[this.lang] || TEXT.zh)[key] ?? key;
      for (const [k, v] of Object.entries(vars)) s = s.replace("{" + k + "}", v);
      return s;
    },
    setLang(l) { if (l === this.lang) return; this.lang = l; this.prefs.lang = l; this.savePrefs(); document.documentElement.lang = l === "zh" ? "zh-CN" : "en"; },
    async openUpdate(check) {
      this.updateOpen = true;
      if (check || !this.update) {
        this.upd = { state: "checking" };
        try { this.upd = await this.post("/api/update/check", {}, 25000); }
        catch (e) { this.upd = { state: "error", error: e.name === "AbortError" ? this.t("upTimeout") : e.message }; }
        if (this.upd.state === "available") this.update = this.upd.info;
      } else {
        this.upd = { state: "available", info: this.update, can_install: true };
        this.get("/api/update").then(s => { if (this.upd.state === "available") this.upd.can_install = s.can_install; }).catch(() => {});
      }
    },
    async installUpdate() {
      this.upd = { ...this.upd, state: "starting" };
      try {
        const s = await this.post("/api/update/install", {}, 45000);
        // anything but progress or a clear answer is a failure to start, never an endless spinner
        this.upd = ["downloading", "installing", "current", "error"].includes(s.state) ? s
          : { ...s, state: "error", error: s.error === "busy" ? this.t("upBusy") : this.t("upNotStarted") };
      } catch (e) {
        this.upd = { ...this.upd, state: "error", error: e.name === "AbortError" ? this.t("upTimeout") : e.message };
      }
    },
    closeUpdate() { if (!["downloading", "installing"].includes(this.upd.state)) this.updateOpen = false; },
    // the release notes are written in both languages, a line each; show the reader's
    get notesText() {
      const cjk = /[\u3400-\u9fff]/, zh = this.lang === "zh";
      const lines = (this.upd.info?.notes || "").split("\n").filter(l => !l.trim() || cjk.test(l) === zh)
        .map(l => (/^\s{2,}\S/.test(l) ? "• " : "") + l.trim().replace(/^- /, "• "));
      return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
    },
    openSetup() { this.setupOpen = true; this.showRun = false; this.reelOpen = false; },

    // --- appearance ---
    applyTheme() {
      const r = document.documentElement;
      r.dataset.theme = this.prefs.appearance || "auto";
      r.dataset.accent = this.prefs.accent || "blue";
    },
    async openSettings() {
      this.settingsOpen = true;
      this.work = { bytes: null, path: "", confirm: false, cleaning: false };
      try { const w = await this.get("/api/workfiles"); this.work = { ...this.work, ...w }; } catch (e) { this.work.bytes = 0; }
    },
    async cleanWork() {
      if (!this.work.confirm) { this.work.confirm = true; return; }
      this.work.cleaning = true;
      try {
        const r = await this.post("/api/workfiles/clean");
        this.toast(this.t("cleaned", { size: this.gb(r.freed) }));
        this.work = { ...this.work, bytes: 0, confirm: false };
      } catch (e) {
        this.toast(e.message === "busy" ? this.t("workBusy") : e.message);
        this.work.confirm = false;
      }
      this.work.cleaning = false;
    },
    gb(n) { return n >= 1 << 30 ? (n / (1 << 30)).toFixed(1) + " GB" : Math.max(1, Math.round(n / (1 << 20))) + " MB"; },
    setAppearance(v) { this.prefs.appearance = v; this.applyTheme(); this.savePrefs(); },
    setAccent(v) { this.prefs.accent = v; this.applyTheme(); this.savePrefs(); },

    // --- a folder per player ---
    get playerFolderList() {
      if (this.prefs.by_player === false) return [];
      return Object.entries(this.prefs.player_folders || {}).sort((a, b) => a[1].folder.localeCompare(b[1].folder));
    },
    async renamePlayerFolder(sid, name, input) {
      try { this.prefs = await this.post("/api/player-folder", { steamid: sid, folder: name }); }
      catch (e) {
        this.toast(e.message === "taken" ? this.t("folderTaken") : e.message === "busy" ? this.t("folderBusy") : e.message);
        if (input) input.value = this.prefs.player_folders?.[sid]?.folder || "";
      }
    },
    get saveFolder() {
      const base = this.prefs.output || "";
      if (this.prefs.by_player === false || !this.player) return base;
      const f = this.prefs.player_folders?.[this.player.steamid]?.folder || this.player.name.replace(/[<>:"\/\\|?*]/g, "_");
      return base + (base.includes("\\") ? "\\" : "/") + f;
    },
    // --- the two modes ---
    openMatchMode() { this.reelOpen = false; this.showRun = false; this.viewId = null; },
    sourceLabel(x) { return x.info?.map_pretty || this.niceDemoName(this.demos.find(d => d.path === x.path) || { path: x.path }) || x.path.split(/[\\/]/).pop(); },
    sourceSub(x) {
      if (x.loading) return this.t("reading");
      const d = this.demos.find(d => d.path === x.path);
      return d ? [d.score, this.ago(d.mtime)].filter(Boolean).join("  ") : x.path.split(/[\\/]/).pop();
    },
    // --- highlight reel ---
    openReel(fromMatch) {
      this.reelOpen = true; this.showRun = false; this.setupOpen = false;
      if (fromMatch && this.demo && this.player) {
        this.reel = { title: "", titleEdited: false, mode: "same", steamid: this.player.steamid, items: [], reordered: false,
                      sources: [{ path: this.demo.path, info: this.demo, loading: false, error: "", steamid: this.player.steamid }] };
        this.recompute();
      }
    },
    reelSrc(path) { return this.reel.sources.find(x => x.path === path); },
    get reelRows() {
      const rows = this.demos.map(d => ({ path: d.path, label: d.map || this.niceDemoName(d), sub: [d.score, this.ago(d.mtime)].filter(Boolean).join("  ") }));
      for (const x of this.reel.sources)
        if (!rows.some(r => r.path === x.path)) rows.unshift({ path: x.path, label: x.info?.map_pretty || x.path.split(/[\\/]/).pop(), sub: "" });
      return rows;
    },
    async toggleSource(path) {
      const have = this.reelSrc(path);
      if (have) { this.reel.sources = this.reel.sources.filter(x => x.path !== path); this.recompute(); return; }
      const src = { path, info: null, loading: true, error: "", steamid: this.reel.steamid };
      this.reel.sources.push(src);
      try {
        const info = await this.post("/api/inspect", { path });
        const x = this.reelSrc(path); if (!x) return;
        x.info = info; x.loading = false;
        if (!this.reel.steamid) this.reel.steamid = this.reelPlayers[0]?.steamid || "";
        if (!this.playerIn(x.info, x.steamid)) x.steamid = this.playerIn(info, this.reel.steamid) ? this.reel.steamid : "";
        this.loadDemos();
      } catch (e) {
        const x = this.reelSrc(path); if (x) { x.loading = false; x.error = e.message === "not_a_demo" ? this.t("notDemo") : e.message; }
      }
      this.recompute();
    },
    playersOf(info) { return (info?.teams || []).flatMap(t => t.players); },
    playerIn(info, sid) { return this.playersOf(info).find(p => p.steamid === sid); },
    get reelPlayers() {
      const m = new Map();
      for (const x of this.reel.sources) for (const p of this.playersOf(x.info)) {
        const e = m.get(p.steamid) || { steamid: p.steamid, name: p.name, n: 0, k: 0 };
        e.n += 1; e.k += p.k || 0; m.set(p.steamid, e);
      }
      return [...m.values()].sort((a, b) => b.n - a.n || b.k - a.k);
    },
    srcPlayerId(x) { return this.reel.mode === "same" ? this.reel.steamid : x.steamid; },
    setMode(m) { this.reel.mode = m; for (const x of this.reel.sources) if (!x.steamid) x.steamid = this.playerIn(x.info, this.reel.steamid) ? this.reel.steamid : ""; this.recompute(); },
    // every round of the chosen player(s) in the chosen demos
    get reelCandidates() {
      const out = [];
      for (const x of this.reel.sources) {
        const p = this.playerIn(x.info, this.srcPlayerId(x));
        if (!p) continue;
        (p.rounds_k || []).forEach((k, i) => {
          const hs = p.rounds_hs?.[i] || 0, c = p.rounds_clutch?.[i] || 0;
          out.push({ key: x.path + "|" + p.steamid + "|" + (i + 1), path: x.path, map: x.info.map_pretty, steamid: p.steamid,
                     name: p.name, round: i + 1, k, hs, clutch: c, score: k * 10 + hs + (c ? 25 * c : 0) });
        });
      }
      return out;
    },
    recompute() {
      this.reel.items = this.reelCandidates.filter(c => c.k >= 3 || c.clutch >= 1).sort((a, b) => a.score - b.score);
      this.reel.reordered = false;
      if (!this.reel.titleEdited) {
        const names = [...new Set(this.reel.items.map(i => i.name))];
        const one = names.length === 1 ? names[0] : (this.reel.mode === "same" ? this.reelPlayers.find(p => p.steamid === this.reel.steamid)?.name : "");
        this.reel.title = one ? this.t("reelDefault", { name: one }) : this.t("reelDefaultMany");
      }
    },
    get reelOthers() {
      const inReel = new Set(this.reel.items.map(i => i.key));
      return this.reelCandidates.filter(c => !inReel.has(c.key) && (c.k > 0 || c.clutch > 0));
    },
    addReelItem(c) {
      const items = this.reel.items;
      const at = this.reel.reordered ? items.length : items.findIndex(i => i.score > c.score);
      items.splice(at < 0 ? items.length : at, 0, c);
    },
    removeReelItem(i) { this.reel.items.splice(i, 1); },
    moveReelItem(i, d) {
      const j = i + d, items = this.reel.items;
      if (j < 0 || j >= items.length) return;
      [items[i], items[j]] = [items[j], items[i]]; this.reel.reordered = true;
    },
    dropAt(i) {
      const from = this.dragFrom; this.dragFrom = null;
      if (from === null || from === i) return;
      const [it] = this.reel.items.splice(from, 1); this.reel.items.splice(i, 0, it); this.reel.reordered = true;
    },
    tagOf(c) {
      const zh = this.lang === "zh", names = zh ? { 2: "双杀", 3: "三杀", 4: "四杀", 5: "ACE" } : { 2: "2K", 3: "3K", 4: "4K", 5: "ACE" };
      const parts = [];
      if (c.k >= 2) parts.push(names[Math.min(c.k, 5)]); else if (c.k === 1) parts.push(this.t("kills1", { n: 1 }));
      if (c.clutch) parts.push(this.t("tagClutch", { n: c.clutch }));
      return parts.join("  ");
    },
    reelSeconds(items) { return Math.round(items.reduce((t, c) => t + (c.k ? 5.5 + (c.k - 1) * 2.5 : 8), 0)); },
    get reelWhyNot() {
      const w = this.whyNotSetup;
      return w || (this.reel.items.length ? "" : this.t("reelNeedItems"));
    },
    async startReel(watch) {
      const wasRunning = this.job.state === "running";
      const effects = { ...this.fx };
      if (effects.intro === "title" && !effects.intro_sub) effects.intro_sub = this.reelPlayersLine;
      if (effects.outro === "card" && !effects.outro_text) effects.outro_text = this.t("outroTextDefault");
      const body = { title: this.reel.title.trim() || this.t("reelDefaultMany"), summary: this.t("reelSummary", { n: this.reel.items.length }),
                     items: this.reel.items.map(c => ({ demo: c.path, steamid: c.steamid, round: c.round, name: c.name })), effects };
      const j = await this.post("/api/queue/add-reel", body);
      this.queue = j.queue; this.job = j;
      if (watch && !wasRunning) { this.viewId = null; this.reelOpen = false; this.showRun = true; }
      else this.toast(this.t("queuedNote", { name: body.title }));
    },
    // --- reel effects ---
    fxDefaults() { return JSON.parse(JSON.stringify(this.fxMeta.defaults || {})); },
    // the parts of the effects that make a look (not the music file or the texts)
    fxLook(fx) {
      const skip = new Set(["music", "music_volume", "music_start", "game_audio", "intro_text", "intro_sub", "outro_text", "grade_match"]);
      const full = { ...this.fxDefaults(), ...fx };
      return JSON.stringify(Object.keys(full).filter(k => !skip.has(k)).sort().map(k => [k, full[k]]));
    },
    presetOf(fx) {
      const me = this.fxLook(fx);
      if (this.fxLook({}) === me) return "plain";
      for (const p of this.prefs.fx_presets || []) if (this.fxLook(p.fx) === me) return "my:" + p.name;
      if (this.styleRef.effects && this.fxLook(this.styleRef.effects) === me) return "ref";
      return "custom";
    },
    keepOwn() {
      const f = this.fx || {};
      return { music: f.music || "", music_volume: f.music_volume ?? 0.8, music_start: f.music_start || 0, game_audio: f.game_audio || "keep",
               intro_text: f.intro_text || "", intro_sub: f.intro_sub || "", outro_text: f.outro_text || "" };
    },
    applyPreset(key) {
      const mine = (this.prefs.fx_presets || []).find(p => "my:" + p.name === key);
      const own = this.keepOwn();
      const texts = { intro_text: own.intro_text, intro_sub: own.intro_sub, outro_text: own.outro_text };
      this.fx = mine ? { ...this.fxDefaults(), ...mine.fx, ...texts } : { ...this.fxDefaults(), ...texts };
      this.fxPreset = mine ? key : "plain"; this.saveFx();
    },
    fxParts: [
      { key: "intro", label: "fxIntro", fields: ["intro", "intro_seconds"] },
      { key: "transition", label: "fxTransition", fields: ["transition", "transition_seconds", "transitions"] },
      { key: "kills", label: "fxKills", fields: ["kill_slowmo", "slowmo_speed", "kill_zoom", "kill_flash", "kill_shake", "kill_scope"] },
      { key: "grade", label: "fxGrade", fields: ["grade", "grade_match", "letterbox"] },
      { key: "outro", label: "fxOutro", fields: ["outro", "outro_seconds"] },
      { key: "pace", label: "fxPace", fields: ["pace"] },
      { key: "music", label: "fxMusic", fields: ["music", "music_volume", "music_start", "game_audio"] },
    ],
    partOf(key, fx) {
      const c = this.fxParts.find(c => c.key === key), full = { ...this.fxDefaults(), ...fx };
      return JSON.stringify(c.fields.map(f => full[f]));
    },
    // the styles the choices come from: your saved ones, and a video just read but not named yet
    partSources() {
      const list = (this.prefs.fx_presets || []).map(p => ({ value: "my:" + p.name, name: p.name, fx: p.fx }));
      if (this.styleRef.effects && !this.styleRef.savedAs) list.push({ value: "ref", name: this.styleRef.name, fx: this.styleRef.effects });
      return list;
    },
    partText(key, fx) {
      fx = { ...this.fxDefaults(), ...fx };
      const zh = this.lang === "zh";
      switch (key) {
        case "intro": return this.t("intro_" + fx.intro) + (fx.intro === "title" ? " " + this.t("sec", { s: fx.intro_seconds }) : "");
        case "transition": return this.t("tr_" + fx.transition) + (fx.transition !== "cut" ? " " + this.t("sec", { s: fx.transition_seconds }) : "");
        case "kills": return this.killText(fx) || this.t("vNone");
        case "grade": return (fx.grade === "match" ? this.t("gradeLike") : this.t("g_" + fx.grade)) + (fx.letterbox ? (zh ? " + " : " + ") + this.t("fxBars") : "");
        case "outro": return this.t("o_" + fx.outro) + (["freeze", "card"].includes(fx.outro) ? " " + this.t("sec", { s: fx.outro_seconds }) : "");
        case "pace": return this.t("pace_" + fx.pace);
        case "music": return fx.music ? fx.music.split(/[\\/]/).pop() : this.t("vNone");
      }
      return "";
    },
    partOptions(key) {
      const none = this.partOf(key, {});
      const noneLabel = { pace: this.t("pace_normal"), grade: this.t("g_none"), transition: this.t("tr_cut") }[key] || this.t("vNone");
      const opts = [{ value: "", label: noneLabel, sig: none }];
      for (const src of this.partSources()) {
        const sig = this.partOf(key, src.fx);
        const same = opts.find(o => o.sig === sig);
        if (same) { if (same.value) same.names.push(src.name); continue; }
        opts.push({ value: src.value, sig, text: this.partText(key, src.fx), names: [src.name] });
      }
      const sep = this.lang === "zh" ? "、" : ", ";
      return opts.map(o => ({ value: o.value, label: o.value ? o.text + (this.lang === "zh" ? "（" : " (") + this.t("fromList", { list: o.names.join(sep) }) + (this.lang === "zh" ? "）" : ")") : o.label }));
    },
    partNow(key) {
      const sig = this.partOf(key, this.fx || {});
      if (sig === this.partOf(key, {})) return "";
      const src = this.partSources().find(x => this.partOf(key, x.fx) === sig);
      return src ? src.value : "";
    },
    pickPart(key, value) {
      const c = this.fxParts.find(c => c.key === key);
      const from = value ? this.partSources().find(x => x.value === value)?.fx : {};
      const full = { ...this.fxDefaults(), ...(from || {}) };
      for (const f of c.fields) this.fx[f] = JSON.parse(JSON.stringify(full[f]));
      this.fxChanged();
    },
    applyRef() {
      this.fx = { ...this.fxDefaults(), ...this.keepOwn(), ...this.styleRef.effects };
      this.fxPreset = "ref"; this.saveFx();
    },
    fxChanged() { this.fxPreset = this.presetOf(this.fx); this.saveFx(); },
    saveFx() {
      clearTimeout(this.fxTimer);
      this.fxTimer = setTimeout(() => this.post("/api/prefs", { reel_fx: this.fx }).then(p => { this.prefs = p; }).catch(() => {}), 500);
    },
    async savePreset() {
      const name = this.fxSaveName.trim();
      if (!name) return;
      const list = (this.prefs.fx_presets || []).filter(p => p.name !== name).concat([{ name, fx: { ...this.fx } }]);
      this.prefs = await this.post("/api/prefs", { fx_presets: list });
      this.fxPreset = "my:" + name; this.fxSaveOpen = false; this.fxSaveName = "";
    },
    async deletePreset(name) {
      this.prefs = await this.post("/api/prefs", { fx_presets: (this.prefs.fx_presets || []).filter(p => p.name !== name) });
      this.fxPreset = this.presetOf(this.fx);
    },
    secondsChoices(cur, list) { return list.includes(cur) ? list : list.concat([cur]).sort((a, b) => a - b); },
    get musicName() { return (this.fx?.music || "").split(/[\\/]/).pop(); },
    get reelPlayersLine() { return [...new Set(this.reel.items.map(c => c.name))].join(" · "); },
    async pickMusic() {
      const r = await this.post("/api/pick", { kind: "audio" });
      if (r.path) { this.fx.music = r.path; this.fxChanged(); }
    },
    clearMusic() { this.fx.music = ""; this.fxChanged(); },
    async copyStyle() {
      const r = await this.post("/api/pick", { kind: "video" });
      if (!r.path) return;
      const name = r.path.split(/[\\/]/).pop();
      this.styleRef = { state: "working", name, path: r.path, report: [], music: null, effects: null, musicUsed: false, error: "",
                        presetName: name.replace(/\.[^.]+$/, "").slice(0, 40), savedAs: "" };
      try {
        const a = await this.post("/api/style/analyze", { path: r.path });
        this.styleRef = { ...this.styleRef, state: "done", report: a.report || [], music: a.music, effects: a.effects || {} };
        this.applyRef();
      } catch (e) {
        this.styleRef = { ...this.styleRef, state: "error", error: e.message };
      }
    },
    async useRefMusic() {
      try {
        const r = await this.post("/api/style/music", { path: this.styleRef.path });
        this.fx.music = r.path; this.styleRef.musicUsed = true; this.fxChanged();
      } catch (e) { this.toast(e.message); }
    },
    // --- what was found in a reference video, and keeping it as a preset ---
    repOf(what) { return (this.styleRef.report || []).find(r => r.what === what); },
    killText(fx, counts) {
      const on = ["slowmo", "zoom", "flash", "shake"].filter(k => fx["kill_" + k]);
      if (!on.length) return "";
      const sep = this.lang === "zh" ? "、" : ", ";
      const names = on.map(k => this.t("k_" + k) + (k === "slowmo" ? " " + this.t("slowAt", { x: fx.slowmo_speed }) : "")
        + (counts && counts[k] ? (this.lang === "zh" ? "（" : " (") + this.t("vTimes", { n: counts[k] }) + (this.lang === "zh" ? "）" : ")") : ""));
      return names.join(sep) + (this.lang === "zh" ? "；" : "; ") + this.t("scope_" + fx.kill_scope);
    },
    get refRows() {
      const fx = { ...this.fxDefaults(), ...(this.styleRef.effects || {}) };
      const zh = this.lang === "zh", sep = zh ? "、" : ", ", paren = v => zh ? "（" + v + "）" : " (" + v + ")";
      const rows = [];
      const intro = this.repOf("intro");
      rows.push({ label: this.t("fxIntro"), none: fx.intro === "none",
                  value: fx.intro === "none" ? this.t("vNone") : this.t("intro_" + fx.intro) + (intro ? paren(this.t("vAbout", { s: intro.seconds })) : "") });
      const tr = this.repOf("transition");
      let trv = this.t("tr_" + fx.transition);
      if (fx.transition !== "cut") trv += " " + this.t("vAbout", { s: fx.transition_seconds });
      if (tr) {
        trv += paren(this.t("vTimes", { n: tr.count }));
        const others = Object.entries(tr.all || {}).filter(([k]) => k !== tr.kind).map(([k, c]) => this.t("tr_" + k) + " " + this.t("vTimes", { n: c }));
        if (others.length) trv += zh ? "，" + this.t("vAlso", { list: others.join(sep) }) : "; " + this.t("vAlso", { list: others.join(sep) });
      }
      rows.push({ label: this.t("fxTransition"), value: trv, none: fx.transition === "cut" });
      const counts = {};
      for (const r of this.styleRef.report || []) if (r.what === "kill") counts[r.kind] = r.count;
      const kills = this.killText(fx, counts);
      rows.push({ label: this.t("fxKills"), value: kills || this.t("vNone"), none: !kills });
      const col = this.repOf("colour");
      rows.push({ label: this.t("fxGrade"), value: col ? this.t("vMatch", { kind: this.t("look_" + col.kind) }) : this.t("g_" + fx.grade), none: !col && fx.grade === "none" });
      rows.push({ label: this.t("fxBars"), value: fx.letterbox ? this.t("vYes") : this.t("vNo"), none: !fx.letterbox });
      const out = this.repOf("outro");
      rows.push({ label: this.t("fxOutro"), none: fx.outro === "none",
                  value: fx.outro === "none" ? this.t("vNone") : this.t("o_" + fx.outro) + (out ? paren(this.t("vAbout", { s: out.seconds })) : "") });
      const pace = this.repOf("pace");
      if (pace) rows.push({ label: this.t("fxPace"), value: this.t("vPace", { s: pace.seconds, kind: this.t("pace_" + pace.kind) }) });
      const mus = this.repOf("music");
      rows.push({ label: this.t("fxMusic"), value: mus ? this.t("vMusic", { bpm: mus.bpm }) : this.t("vNo"), none: !mus });
      return rows;
    },
    presetTaken(name) { const n = (name || "").trim(); return !!n && (this.prefs.fx_presets || []).some(p => p.name === n); },
    async saveRefPreset() {
      const name = (this.styleRef.presetName || "").trim().slice(0, 40);
      if (!name) return;
      const fx = { ...this.fxDefaults(), ...this.styleRef.effects };
      if (this.styleRef.musicUsed) { fx.music = this.fx.music; fx.game_audio = this.fx.game_audio; }
      const list = (this.prefs.fx_presets || []).filter(p => p.name !== name).concat([{ name, fx, source: this.styleRef.name }]);
      this.prefs = await this.post("/api/prefs", { fx_presets: list });
      this.fx = { ...this.keepOwn(), ...fx };
      this.fxPreset = "my:" + name; this.styleRef.savedAs = name; this.saveFx();
    },
    // one line saying what a set of effects does
    fxSummary(fx) {
      fx = { ...this.fxDefaults(), ...fx };
      const zh = this.lang === "zh", item = (label, v) => label + (zh ? "：" : ": ") + v, parts = [];
      if (fx.intro !== "none") parts.push(item(this.t("fxIntro"), this.t("intro_" + fx.intro)));
      if (fx.transition !== "cut") parts.push(item(this.t("fxTransition"), this.t("tr_" + fx.transition) + " " + this.t("sec", { s: fx.transition_seconds })));
      const on = ["slowmo", "zoom", "flash", "shake"].filter(k => fx["kill_" + k]).map(k => this.t("k_" + k));
      if (on.length) parts.push(item(this.t("fxKills"), on.join(zh ? "、" : ", ")));
      if (fx.grade !== "none") parts.push(item(this.t("fxGrade"), fx.grade === "match" ? this.t("gradeLike") : this.t("g_" + fx.grade)));
      if (fx.letterbox) parts.push(this.t("fxBars"));
      if (fx.outro !== "none") parts.push(item(this.t("fxOutro"), this.t("o_" + fx.outro)));
      if (fx.music) parts.push(this.t("fxMusic"));
      return parts.join(" · ");
    },
    presetTip(p) { return this.fxSummary(p.fx) + (p.source ? "\n" + this.t("fromFile", { name: p.source }) : ""); },
    get fxNowLine() {
      if (!this.fx) return "";
      const text = this.fxSummary(this.fx);
      if (!text) return this.t("nowPlain");
      const mine = this.fxPreset.startsWith("my:") && (this.prefs.fx_presets || []).find(p => "my:" + p.name === this.fxPreset);
      const src = mine?.source ? (this.lang === "zh" ? "（" : " (") + this.t("fromFile", { name: mine.source }) + (this.lang === "zh" ? "）" : ")") : "";
      return this.t("nowLabel", { text }) + src;
    },
    reportLine(r) {
      switch (r.what) {
        case "intro": return this.t("rep_intro", { kind: this.t("intro_" + r.kind), s: r.seconds });
        case "transition": {
          if (r.kind === "cut") return this.t("rep_cuts", { n: r.count });
          const others = Object.entries(r.all || {}).filter(([k]) => k !== r.kind).map(([k, c]) => this.t("tr_" + k) + " ×" + c);
          return this.t("rep_transition", { kind: this.t("tr_" + r.kind), s: r.seconds, n: r.count }) + (others.length ? this.t("rep_mixed", { list: others.join(this.lang === "zh" ? "、" : ", ") }) : "");
        }
        case "pace": return this.t("rep_pace", { s: r.seconds, kind: this.t("pace_" + r.kind) });
        case "kill": return this.t("rep_kill", { kind: this.t("k_" + r.kind), n: r.count });
        case "colour": return this.t("rep_colour", { kind: this.t("look_" + r.kind) });
        case "letterbox": return this.t("rep_letterbox");
        case "outro": return this.t("rep_outro", { kind: this.t("o_" + r.kind), s: r.seconds });
        case "music": return this.t("rep_music", { bpm: r.bpm });
      }
      return "";
    },
    get setupHint() {
      if (!this.prefs.folders_set) return this.t("hintFolders");
      if (!this.setup.cs2 && !this.setup.placeholder) return this.t("hintCs2");
      if (!this.setup.hlae || !this.setup.ffmpeg) return this.t("hintTools");
      if (this.setup.anticheat?.length) return this.t("hintAc");
      return "";
    },
    setCustom(on) { this.customRounds = on; if (!on) this.allRounds(); },

    async get(url) { const r = await fetch(url); return r.json(); },
    async post(url, body = {}, timeoutMs = 0) {
      const ctl = timeoutMs ? new AbortController() : null;
      const timer = ctl ? setTimeout(() => ctl.abort(), timeoutMs) : null;
      let r;
      try {
        r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: ctl?.signal });
      } finally { if (timer) clearTimeout(timer); }
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || r.statusText);
      return data;
    },
    async refresh() {
      const s = await this.get("/api/state");
      if (s.error) throw new Error(s.error);
      this.version = s.version; this.prefs = s.prefs; this.setup = s.setup; this.job = s.job;
      this.queue = s.queue; this.update = s.update;
      if (s.effects) this.fxMeta = s.effects;
      if (!this.fx && s.effects) {             // once: the effects used last time
        this.fx = { ...this.fxDefaults(), ...(this.prefs.reel_fx || {}) };
        // effects that don't come from an imported video can't be seen or changed any more
        const ok = this.fxParts.every(c => this.partOf(c.key, this.fx) === this.partOf(c.key, {}) || this.partNow(c.key));
        if (!ok) { this.fx = { ...this.fxDefaults() }; this.saveFx(); }
        this.fxPreset = this.presetOf(this.fx);
      }
    },
    async loadDemos() { this.demos = await this.get("/api/demos"); this.demosLoaded = true; },

    async pickDemo(path) {
      this.showRun = false; this.setupOpen = false; this.reelOpen = false; this.customRounds = false; this.lastPath = path;
      this.inspecting = true; this.inspectError = ""; this.demo = null; this.player = null;
      try {
        this.demo = await this.post("/api/inspect", { path });
        this.loadDemos();  // the list now knows this demo's map
        this.chosenRounds = this.roundList.slice();
      } catch (e) {
        this.inspectError = e.message === "not_a_demo" ? this.t("notDemo") : e.message;
      }
      this.inspecting = false;
    },
    async browse() {
      const r = await this.post("/api/browse");
      if (!r.path) return;
      if (this.reelOpen) { if (!this.reelSrc(r.path)) this.toggleSource(r.path); }
      else this.pickDemo(r.path);
    },
    async confirmFolders() { this.prefs = await this.post("/api/folders/confirm"); this.loadDemos(); },
    async chooseFolder(which) {
      this.prefs = await this.post("/api/folder", { which });
      if (which === "demos") this.loadDemos();
    },
    async savePrefs() { this.prefs = await this.post("/api/prefs", this.prefs); },

    pickPlayer(p) { this.player = p; },
    get roundList() { return Array.from({ length: this.demo?.rounds || 0 }, (_, i) => i + 1); },
    toggleRound(r) {
      const i = this.chosenRounds.indexOf(r);
      if (i >= 0) this.chosenRounds.splice(i, 1); else this.chosenRounds.push(r);
    },
    allRounds() { this.chosenRounds = this.roundList.slice(); },
    noRounds() { this.chosenRounds = []; },
    roundTitle(r) {
      const k = this.player?.rounds_k?.[r - 1] || 0;
      return this.t("roundTip", { r, k, d: this.player?.rounds_died?.[r - 1] ? this.t("roundTipDied") : "" });
    },

    get missingTools() { return [!this.setup.hlae && "HLAE", !this.setup.ffmpeg && "FFmpeg"].filter(Boolean); },
    get toolsHelp() {
      const m = this.missingTools;
      return this.t("ckToolsHelp", { list: m.join(this.lang === "zh" ? " 和 " : " and "), size: m.includes("FFmpeg") ? "~100 MB" : "~10 MB" });
    },
    get ready() { return !!(this.prefs.folders_set && (this.setup.cs2 || this.setup.placeholder) && this.setup.hlae && this.setup.ffmpeg && !this.setup.anticheat?.length); },
    get whyNotSetup() {
      if (!this.prefs.folders_set) return this.t("hintFolders");
      if (this.setup.placeholder) return "";
      if (!this.setup.windows) return this.t("needWindows");
      if (!this.setup.hlae || !this.setup.ffmpeg) return this.t("needTools");
      if (!this.setup.cs2) return this.t("needCs2");
      if (this.setup.anticheat?.length) return this.t("needAntiCheat", { list: this.setup.anticheat.join(", ") });
      return "";
    },
    get whyNot() { return this.whyNotSetup || (this.chosenRounds.length ? "" : this.t("needRounds")); },
    get canStart() { return !!this.player && !this.whyNot; },

    async start(watch) {
      const all = this.chosenRounds.length === this.demo.rounds;
      const wasRunning = this.job.state === "running";
      const body = { path: this.demo.path, steamid: this.player.steamid, name: this.player.name,
                     rounds: all ? [] : this.chosenRounds.slice().sort((a, b) => a - b), map: this.demo.map_pretty };
      const j = await this.post("/api/queue/add", body);
      this.queue = j.queue; this.job = j;
      if (watch && !wasRunning) { this.viewId = null; this.showRun = true; }
      else this.toast(this.t("queuedNote", { name: body.name }));
    },
    async retry() {
      const id = this.viewId || this.job.item;
      if (id) { this.queue = await this.post("/api/queue/retry", { id }); this.viewId = null; this.showRun = true; }
    },
    async retryItem(id) { this.queue = await this.post("/api/queue/retry", { id }); },
    async removeItem(id) { this.queue = await this.post("/api/queue/remove", { id }); if (this.viewId === id) { this.viewId = null; this.showRun = false; } },
    async clearQueue() { this.queue = await this.post("/api/queue/clear"); },
    async resumeQueue() { this.queue = await this.post("/api/queue/resume"); },
    openItem(it) {
      this.setupOpen = false; this.reelOpen = false;
      this.viewId = it.state === "running" ? null : it.id;
      this.showRun = true;
    },
    async cancel() { const j = await this.post("/api/cancel"); this.queue = j.queue || this.queue; this.job = j; },
    async again(toReel = false) {
      this.viewId = null; this.showRun = false;
      if (toReel) this.reelOpen = true;
      if (this.job.state !== "running") this.job = await this.post("/api/reset");
    },
    async openPath(path, select = false) {
      if (!path) { this.toast(this.t("openMissing")); return; }
      try { await this.post("/api/open", { path, select }); }
      catch (e) { this.toast(e.message === "missing" ? this.t("openMissing") : this.t("openFailed", { e: e.message })); }
    },
    openUrl(url) { this.post("/api/open-url", { url }); },
    async copy(text) {
      try { await navigator.clipboard.writeText(text); }
      catch (e) {
        const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand("copy"); ta.remove();
      }
      this.toast(this.t("copied"));
    },
    toast(text) {
      const id = ++this.toastSeq;
      this.toasts.push({ id, text });
      setTimeout(() => { this.toasts = this.toasts.filter(m => m.id !== id); }, 3500);
    },
    get winnerIndex() {
      const t = this.demo?.teams || [];
      if (t.length < 2 || t[0].score == null || t[0].score === t[1].score) return -1;
      return t[0].score > t[1].score ? 0 : 1;
    },
    // rough overall progress; recording rounds is most of the time
    get stages() { return this.job.kind === "reel" ? ["read", "record", "cut"] : ["read", "record", "overlays", "intro", "compose", "extras"]; },
    get progressPct() {
      const j = this.job;
      if (j.state === "done") return 100;
      const [a, b] = j.step || [0, 0], f = b ? Math.min(a / b, 1) : 0;
      if (j.kind === "reel") {     // each demo: read then record; then cutting at the end
        if (j.stage === "cut") return Math.round(85 + 15 * f);
        const [si, sn] = j.source?.[1] ? j.source : [1, 1];
        const within = j.stage === "record" ? 0.15 + 0.85 * f : 0.05;
        return Math.round(85 * ((si - 1 + within) / sn));
      }
      const span = { read: [2, 5], record: [5, 70], overlays: [70, 80], intro: [80, 83], compose: [83, 95], extras: [95, 100] }[j.stage] || [0, 0];
      return Math.round(span[0] + (span[1] - span[0]) * f);
    },
    get viewingItem() { return this.viewId !== null && this.viewId !== this.job.item; },
    get runVisible() { return this.showRun && (this.viewingItem || this.job.state !== "idle"); },
    get res() {
      if (this.viewingItem) {
        const it = this.queue.items.find(i => i.id === this.viewId);
        if (it) return { ...it, player: it.name };
      }
      return this.job;
    },
    thumbOf(r) {
      if (r.cover) return r.cover;
      const p = r.result || ""; const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/"));
      return p.slice(0, i + 1) + "parts" + p[i] + "intro.png";
    },
    async install() { this.setup = await this.post("/api/install", { what: "all" }); },
    async restoreSettings() { this.setup = await this.post("/api/restore-settings"); },

    roundDone(r) {
      return this.job.recorded.includes(r) || this.stages.indexOf(this.job.stage) > this.stages.indexOf("record");
    },
    get recordTotal() { return this.job.stage === "record" ? this.job.step[1] : 0; },
    get runRounds() { return this.job.planned.length ? this.job.planned : this.roundList; },
    get runTitle() {
      const r = this.res, n = r.player || "";
      if (r.kind === "reel") return { running: this.t("making", { name: n }), done: this.t("reelDone"), error: this.t("failed"), cancelled: this.t("stopped") }[r.state] || "";
      return { running: this.t("recording", { name: n }), done: this.t("recorded"), error: this.t("failed"), cancelled: this.t("stopped") }[r.state] || "";
    },
    get runSub() {
      const r = this.res;
      const item = this.queue.items.find(i => i.id === (this.viewingItem ? this.viewId : this.job.item));
      const map = item?.map || "";
      if (r.kind === "reel") return r.state === "done" ? (r.player || "") : map;
      if (r.state === "running") return [map, item ? (item.rounds.length ? this.t("nRounds", { n: item.rounds.length }) : this.t("wholeMatch")) : ""].filter(Boolean).join(" · ");
      return [r.player, map].filter(Boolean).join(" · ");
    },
    stageLabel(s) {
      const src = this.job.source || [0, 0];
      if (s === "read" && this.job.kind === "reel" && src[1] > 1) return this.t("reelStageRead", { a: src[0] || 1, b: src[1] });
      return this.t("stage_" + s);
    },
    stageClass(s) {
      const order = this.stages, cur = order.indexOf(this.job.stage);
      const i = order.indexOf(s);
      if (this.job.state === "done") return "done";
      if (i < cur) return "done";
      if (i === cur) return this.job.state === "running" ? "now" : (this.job.state === "error" ? "fail" : "todo");
      return "todo";
    },

    niceDemoName(d) { return d.name.replace(/\.dem(\.(zst|gz|bz2))?$/i, ""); },
    shortPath(p) { return (p || "").replace(/^.*[\\/](.+[\\/].+)$/, "…\\$1"); },
    clock(s) { s = Math.round(s); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); },
    mb(n) { return (n / 1048576).toFixed(0) + " MB"; },
    ago(ts) {
      const s = Date.now() / 1000 - ts, zh = this.lang === "zh";
      if (s < 3600) return zh ? Math.max(1, Math.round(s / 60)) + " 分钟前" : Math.max(1, Math.round(s / 60)) + " min ago";
      if (s < 86400) return zh ? Math.round(s / 3600) + " 小时前" : Math.round(s / 3600) + " h ago";
      return new Date(ts * 1000).toLocaleDateString(zh ? "zh-CN" : "en-GB", { month: "short", day: "numeric" });
    },
  }));
});
