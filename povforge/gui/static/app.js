// PovForge app page (Alpine.js component).

const TEXT = {
  zh: {
    demos: "Demo", refresh: "刷新", lookingIn: "正在看：", noDemos: "这个文件夹里还没有 demo。下载一个 FACEIT 或 HLTV demo，或者手动选择文件。",
    openFile: "选择 demo 文件…", demoFolder: "更换 demo 文件夹…",
    setup: "录制环境", found: "已就绪", cs2Missing: "没找到，请先在 Steam 安装", notInstalled: "未安装",
    antiCheat: "反作弊", running: "正在运行", closed: "已关闭", installTools: "一键安装 HLAE 和 FFmpeg",
    preparing: "准备中…", settingsPending: "上次录制被打断，你的 CS2 设置还没还原。", restoreNow: "立即还原",
    safeNote: "录制不会改动你的 CS2 设置。",
    blankTitle: "选一个 demo 开始", blankBody: "左边列出了下载文件夹里的 demo。选好比赛和选手，就能得到这个人的完整第一人称视频。",
    reading: "正在读取 demo", readingBody: "解压并分析比赛，通常需要十几秒。", cantRead: "读不了这个 demo",
    rounds: "回合", minDemo: "分钟", others: "其他",
    pickPlayer: "点一位选手，录他的第一人称视角。", playerPicked: "已选好选手。可以在下面挑回合，默认整场。",
    roundsTitle: "要录的回合", all: "全选", none: "清空",
    legendKill: "这回合的击杀", legendDied: "这回合阵亡",
    optIntro: "片头", optMinimap: "小地图", optKeyboard: "键鼠显示", optEnemies: "小地图显示敌人",
    saveTo: "保存到", record: "录制 {name} 的 POV",
    needRounds: "至少选一个回合。", needTools: "先安装 HLAE 和 FFmpeg（左下角）。", needCs2: "没找到 CS2。",
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
    demos: "Demos", refresh: "Refresh", lookingIn: "Looking in", noDemos: "No demos in this folder yet. Download a FACEIT or HLTV demo, or choose a file.",
    openFile: "Choose a demo file…", demoFolder: "Change demo folder…",
    setup: "Recording setup", found: "Ready", cs2Missing: "Not found, install it in Steam", notInstalled: "Not installed",
    antiCheat: "Anti-cheat", running: "running", closed: "Closed", installTools: "Install HLAE and FFmpeg",
    preparing: "Preparing…", settingsPending: "A recording was interrupted and your CS2 settings aren't restored yet.", restoreNow: "Restore now",
    safeNote: "Recording never changes your CS2 settings.",
    blankTitle: "Pick a demo to start", blankBody: "Demos from your Downloads folder are listed on the left. Choose a match and a player to get their full first-person video.",
    reading: "Reading the demo", readingBody: "Unpacking and analysing the match usually takes a few seconds.", cantRead: "Can't read this demo",
    rounds: "rounds", minDemo: "min", others: "Others",
    pickPlayer: "Click a player to record their first-person view.", playerPicked: "Player chosen. Pick rounds below, or keep the whole match.",
    roundsTitle: "Rounds to record", all: "All", none: "None",
    legendKill: "kill this round", legendDied: "died this round",
    optIntro: "Intro", optMinimap: "Minimap", optKeyboard: "Keys and mouse", optEnemies: "Enemies on minimap",
    saveTo: "Save to", record: "Record {name}'s POV",
    needRounds: "Choose at least one round.", needTools: "Install HLAE and FFmpeg first (bottom left).", needCs2: "CS2 wasn't found.",
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
    demos: [], demosLoaded: false, demo: null, inspecting: false, inspectError: "",
    player: null, chosenRounds: [], lastRun: null,
    stages: ["read", "record", "overlays", "intro", "compose"],

    async boot() {
      fetch("/static/vendor/icons.svg").then(r => r.text()).then(s => { document.getElementById("icons").innerHTML = s; });
      await this.refresh();
      this.lang = this.prefs.lang || (navigator.language.startsWith("zh") ? "zh" : "en");
      document.documentElement.lang = this.lang === "zh" ? "zh-CN" : "en";
      this.loadDemos();
      const tick = async () => {
        try {
          if (this.job.state === "running") this.job = await this.get("/api/job");
          else await this.refresh();
        } catch (e) { /* app closing */ }
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
    toggleLang() { this.lang = this.lang === "zh" ? "en" : "zh"; this.prefs.lang = this.lang; this.savePrefs(); document.documentElement.lang = this.lang === "zh" ? "zh-CN" : "en"; },

    async get(url) { const r = await fetch(url); return r.json(); },
    async post(url, body = {}) {
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || r.statusText);
      return data;
    },
    async refresh() {
      const s = await this.get("/api/state");
      this.version = s.version; this.prefs = s.prefs; this.setup = s.setup; this.job = s.job;
    },
    async loadDemos() { this.demos = await this.get("/api/demos"); this.demosLoaded = true; },

    async pickDemo(path) {
      this.inspecting = true; this.inspectError = ""; this.demo = null; this.player = null;
      try {
        this.demo = await this.post("/api/inspect", { path });
        this.chosenRounds = this.roundList.slice();
      } catch (e) {
        this.inspectError = e.message === "not_a_demo" ? "Not a CS2 demo file (.dem, .dem.zst, .dem.gz)." : e.message;
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

    get ready() { return !!(this.setup.cs2 && this.setup.hlae && this.setup.ffmpeg && !this.setup.anticheat?.length); },
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

    async start() {
      const all = this.chosenRounds.length === this.demo.rounds;
      this.lastRun = { path: this.demo.path, steamid: this.player.steamid, name: this.player.name,
                       rounds: all ? [] : this.chosenRounds.slice().sort((a, b) => a - b) };
      this.job = await this.post("/api/run", this.lastRun);
    },
    async retry() { if (this.lastRun) this.job = await this.post("/api/run", this.lastRun); },
    async cancel() { this.job = await this.post("/api/cancel"); },
    async again() { this.job = await this.post("/api/reset"); },
    async install() { this.setup = await this.post("/api/install", { what: "all" }); },
    async restoreSettings() { this.setup = await this.post("/api/restore-settings"); },
    openResult(select) { this.post("/api/open", { path: this.job.result, select }); },

    roundDone(r) {
      return this.job.recorded.includes(r) || this.stages.indexOf(this.job.stage) > this.stages.indexOf("record");
    },
    get recordTotal() { return this.job.stage === "record" ? this.job.step[1] : 0; },
    get runRounds() { return this.job.planned.length ? this.job.planned : this.roundList; },
    get thumbPath() { const p = this.job.result || ""; const i = Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")); return p.slice(0, i + 1) + "parts" + p[i] + "intro.png"; },
    get runTitle() {
      const n = this.job.player || this.player?.name || "";
      return { running: this.t("recording", { name: n }), done: this.t("recorded"), error: this.t("failed"), cancelled: this.t("stopped") }[this.job.state] || "";
    },
    get runSub() {
      if (this.job.state === "running") return (this.demo?.map_pretty ? this.demo.map_pretty + " · " : "") + this.t("keep");
      return this.job.player ? this.job.player + (this.demo?.map_pretty ? " · " + this.demo.map_pretty : "") : "";
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
    mb(n) { return (n / 1048576).toFixed(0) + " MB"; },
    ago(ts) {
      const s = Date.now() / 1000 - ts, zh = this.lang === "zh";
      if (s < 3600) return zh ? Math.max(1, Math.round(s / 60)) + " 分钟前" : Math.max(1, Math.round(s / 60)) + " min ago";
      if (s < 86400) return zh ? Math.round(s / 3600) + " 小时前" : Math.round(s / 3600) + " h ago";
      return new Date(ts * 1000).toLocaleDateString(zh ? "zh-CN" : "en-GB", { month: "short", day: "numeric" });
    },
  }));
});
