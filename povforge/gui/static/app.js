// PovForge app page (Alpine.js component).

const TEXT = {
  zh: {
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
    updateAvail: "有新版本 v{v}", download: "下载",
    setupTitle: "开始之前", setupBody: "录制前需要准备好下面几项，只需要做一次。",
    ckCs2: "安装 Steam 和 CS2", ckCs2Help: "在 Steam 里安装 Counter-Strike 2，装好后这里会自动变绿。",
    ckTools: "下载录制组件", ckToolsHelp: "点下面的按钮，自动从官方 GitHub 下载 {list}（{size}），不用自己找。", ckToolsDone: "已就绪。",
    ckAc: "退出反作弊客户端", ckAcDone: "FACEIT、5E、完美世界都没有在运行。",
    ckDemo: "准备一个 demo", ckDemoHelp: "从 FACEIT 比赛房间或 HLTV 下载 demo，放进下载文件夹即可。", ckDemoDone: "下载文件夹里有 {n} 个 demo，在左边选一个。",
    offlineTitle: "PovForge 已经关闭", offlineBody: "后台程序已退出。重新打开 PovForge 即可继续。",
    demos: "Demo", refresh: "刷新", lookingIn: "正在看：", noDemos: "这个文件夹里还没有 demo。下载一个 FACEIT 或 HLTV demo，或者手动选择文件。",
    openFile: "选择 demo 文件…", demoFolder: "更换 demo 文件夹…",
    setup: "准备工作", found: "已就绪", cs2Missing: "没找到，请先在 Steam 安装", notInstalled: "未安装",
    antiCheat: "反作弊", running: "正在运行", closed: "已关闭", installTools: "一键下载录制组件",
    preparing: "准备中…", settingsPending: "上次录制被打断，你的 CS2 设置还没还原。", restoreNow: "立即还原",
    safeNote: "录制不会改动你的 CS2 设置。",
    blankTitle: "选一个 demo", blankBody: "左边是下载文件夹里的 demo。选好比赛和选手，就能得到这名选手整场的第一人称视频。",
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
    play: "播放视频", showFolder: "打开所在文件夹", another: "再录一个", retry: "重试", back: "返回",
    stop: "停止录制", details: "详细信息", cancelled: "录制已停止。你的 CS2 设置已还原。",
    retryHint: "重试时已录好的回合会直接复用。",
    roundTip: "第 {r} 回合：{k} 杀{d}", roundTipDied: "，阵亡",
    keep: "CS2 会在录完后自己关闭，期间别用电脑玩游戏。",
  },
  en: {
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
    updateAvail: "Version v{v} is out", download: "Download",
    setupTitle: "Before you start", setupBody: "Recording needs the things below. You only do this once.",
    ckCs2: "Install Steam and CS2", ckCs2Help: "Install Counter-Strike 2 in Steam; this turns green once it's found.",
    ckTools: "Download the recording add-on", ckToolsHelp: "Click the button and {list} is downloaded from its official GitHub page ({size}).", ckToolsDone: "Ready.",
    ckAc: "Quit anti-cheat clients", ckAcDone: "FACEIT, 5E and Perfect World aren't running.",
    ckDemo: "Get a demo", ckDemoHelp: "Download a demo from a FACEIT match room or HLTV into your Downloads folder.", ckDemoDone: "{n} demos in your Downloads folder; pick one on the left.",
    offlineTitle: "PovForge has closed", offlineBody: "The background program stopped. Open PovForge again to carry on.",
    demos: "Demos", refresh: "Refresh", lookingIn: "Looking in", noDemos: "No demos in this folder yet. Download a FACEIT or HLTV demo, or choose a file.",
    openFile: "Choose a demo file…", demoFolder: "Change demo folder…",
    setup: "Setup", found: "Ready", cs2Missing: "Not found, install it in Steam", notInstalled: "Not installed",
    antiCheat: "Anti-cheat", running: "running", closed: "Closed", installTools: "Download the recording add-on",
    preparing: "Preparing…", settingsPending: "A recording was interrupted and your CS2 settings aren't restored yet.", restoreNow: "Restore now",
    safeNote: "Recording never changes your CS2 settings.",
    blankTitle: "Pick a demo to start", blankBody: "Demos from your Downloads folder are listed on the left. Choose a match and a player to get their full first-person video.",
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
    player: null, chosenRounds: [], lastRun: null, setupOpen: false, customRounds: false, lastPath: "",
    options: [
      { key: "intro", label: "optIntro" }, { key: "minimap", label: "optMinimap" }, { key: "keyboard", label: "optKeyboard" },
      { key: "show_enemies", label: "optEnemies" }, { key: "highlights", label: "optHighlights" }, { key: "upload", label: "optUpload" },
    ],
    stages: ["read", "record", "overlays", "intro", "compose", "extras"],
    queue: { items: [], paused: false }, update: null, showRun: false, viewId: null, toasts: [], toastSeq: 0,

    async boot() {
      fetch("/static/vendor/icons.svg").then(r => r.text()).then(s => { document.getElementById("icons").innerHTML = s; });
      await this.refresh();
      this.showRun = this.job.state === "running";
      this.lang = this.prefs.lang || (navigator.language.startsWith("zh") ? "zh" : "en");
      document.documentElement.lang = this.lang === "zh" ? "zh-CN" : "en";
      this.setupOpen = !this.ready;
      this.loadDemos();
      const tick = async () => {
        try {
          if (this.job.state === "running") { const j = await this.get("/api/job"); this.queue = j.queue; this.job = j; }
          else await this.refresh();
          this.failures = 0; this.offline = false;
        } catch (e) {
          if (++this.failures >= 3) this.offline = true;
        }
        setTimeout(tick, this.job.state === "running" ? 1000 : 2500);
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
    openSetup() { this.setupOpen = true; this.showRun = false; },
    get setupHint() {
      if (!this.setup.cs2 && !this.setup.placeholder) return this.t("hintCs2");
      if (!this.setup.hlae || !this.setup.ffmpeg) return this.t("hintTools");
      if (this.setup.anticheat?.length) return this.t("hintAc");
      return "";
    },
    setCustom(on) { this.customRounds = on; if (!on) this.allRounds(); },

    async get(url) { const r = await fetch(url); return r.json(); },
    async post(url, body = {}) {
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || r.statusText);
      return data;
    },
    async refresh() {
      const s = await this.get("/api/state");
      if (s.error) throw new Error(s.error);
      this.version = s.version; this.prefs = s.prefs; this.setup = s.setup; this.job = s.job;
      this.queue = s.queue; this.update = s.update;
    },
    async loadDemos() { this.demos = await this.get("/api/demos"); this.demosLoaded = true; },

    async pickDemo(path) {
      this.showRun = false; this.setupOpen = false; this.customRounds = false; this.lastPath = path;
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
      if (r.path) this.pickDemo(r.path);
    },
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
    get ready() { return !!((this.setup.cs2 || this.setup.placeholder) && this.setup.hlae && this.setup.ffmpeg && !this.setup.anticheat?.length); },
    get whyNot() {
      if (this.setup.placeholder) return this.chosenRounds.length ? "" : this.t("needRounds");
      if (!this.setup.windows) return this.t("needWindows");
      if (!this.setup.hlae || !this.setup.ffmpeg) return this.t("needTools");
      if (!this.setup.cs2) return this.t("needCs2");
      if (this.setup.anticheat?.length) return this.t("needAntiCheat", { list: this.setup.anticheat.join(", ") });
      if (!this.chosenRounds.length) return this.t("needRounds");
      return "";
    },
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
      this.setupOpen = false;
      this.viewId = it.state === "running" ? null : it.id;
      this.showRun = true;
    },
    async cancel() { const j = await this.post("/api/cancel"); this.queue = j.queue || this.queue; this.job = j; },
    async again() {
      this.viewId = null; this.showRun = false;
      if (this.job.state !== "running") this.job = await this.post("/api/reset");
    },
    openPath(path, select = false) { if (path) this.post("/api/open", { path, select }); },
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
    get progressPct() {
      const j = this.job;
      if (j.state === "done") return 100;
      const [a, b] = j.step || [0, 0], f = b ? Math.min(a / b, 1) : 0;
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
      return { running: this.t("recording", { name: n }), done: this.t("recorded"), error: this.t("failed"), cancelled: this.t("stopped") }[r.state] || "";
    },
    get runSub() {
      const r = this.res;
      const item = this.queue.items.find(i => i.id === (this.viewingItem ? this.viewId : this.job.item));
      const map = item?.map || "";
      if (r.state === "running") return [map, item ? (item.rounds.length ? this.t("nRounds", { n: item.rounds.length }) : this.t("wholeMatch")) : ""].filter(Boolean).join(" · ");
      return [r.player, map].filter(Boolean).join(" · ");
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
