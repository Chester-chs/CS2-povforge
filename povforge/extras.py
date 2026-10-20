"""Things made from the finished video: a kills-only highlight cut, and a cover
image plus description for uploading (Bilibili / YouTube)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import highlights
from .compose import AUDIO_RATE, ComposeSettings, concat_line, encode_args, safe_filename
from .config import Config
from .hlae import actual_starts, clip_id
from .intro import pretty_map
from .media import probe
from .model import Plan
from .overlay import font

FADE = 0.12


def kill_windows(plan: Plan, starts: dict[str, float], kills: list[tuple[int, bool]],
                 durations: list[float], before: float, after: float, gap: float) -> list[tuple[int, float, float]]:
    """(part index, start s, end s) around every kill, close kills merged."""
    out = []
    for i, (seg, dur) in enumerate(zip(plan.segments, durations)):
        start_tick = starts.get(clip_id(seg), float(seg.start_tick))
        times = sorted((t - start_tick) / plan.tickrate for t, _ in kills if seg.start_tick <= t <= seg.end_tick)
        spans: list[list[float]] = []
        for t in times:
            a, b = max(0.0, t - before), min(dur, t + after)
            if b <= a:
                continue
            if spans and a - spans[-1][1] < gap:
                spans[-1][1] = max(spans[-1][1], b)
            else:
                spans.append([a, b])
        out += [(i, a, b) for a, b in spans]
    return out


def _cut(src: Path, a: float, b: float, out: Path, s: ComposeSettings) -> None:
    d = b - a
    fade = min(FADE, d / 4)
    subprocess.run([
        s.ffmpeg, "-y", "-loglevel", "error", "-ss", f"{a:.3f}", "-i", str(src), "-t", f"{d:.3f}",
        "-vf", f"fade=t=in:st=0:d={fade},fade=t=out:st={d - fade:.3f}:d={fade}",
        "-af", f"afade=t=in:st=0:d={fade},afade=t=out:st={d - fade:.3f}:d={fade},aresample={AUDIO_RATE}",
        *encode_args(s), str(out)], check=True)


def make_highlight_video(cfg: Config, job: Path, plan: Plan, parts: list[Path],
                         intro: Path | None) -> Path | None:
    kf = job / "kills.json"
    kills = [(int(t), bool(h)) for t, h in json.loads(kf.read_text())] if kf.exists() else []
    s, h = cfg.compose, cfg.highlights
    durations = [probe(p, s.ffmpeg).duration for p in parts]
    windows = kill_windows(plan, actual_starts(job), kills, durations, h.before, h.after, h.merge_gap)
    if not windows:
        return None
    pieces_dir = job / "highlights"
    pieces_dir.mkdir(exist_ok=True)
    for f in pieces_dir.glob("*.mp4"):
        f.unlink()
    pieces = []
    for n, (i, a, b) in enumerate(windows):
        out = pieces_dir / f"h{n:03d}.mp4"
        _cut(parts[i], a, b, out, s)
        pieces.append(out)
    listing = pieces_dir / "list.txt"
    listing.write_text("".join(concat_line(p) for p in ([intro] if intro else []) + pieces),
                       encoding="utf-8")
    final = job / f"{safe_filename(plan.player.name)}_{plan.map_name}_highlights.mp4"
    subprocess.run([s.ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    return final


# --- upload kit ---------------------------------------------------------------

def _player_stats(meta: dict, steamid: str) -> tuple[dict | None, list[dict]]:
    teams = meta.get("teams", [])
    for t in teams:
        for p in t.get("players", []):
            if p.get("steamid") == steamid:
                return p, teams
    return None, teams


def _score_line(teams: list[dict], steamid: str) -> str:
    if len(teams) != 2:
        return ""
    mine = next((t for t in teams if any(p.get("steamid") == steamid for p in t.get("players", []))), teams[0])
    other = teams[1] if mine is teams[0] else teams[0]
    return f"{mine['score']}:{other['score']}"


def make_cover(cfg: Config, job: Path, plan: Plan, clips: list[Path], out: Path,
               hl: dict[int, highlights.RoundHighlight], date: str, lang: str) -> Path:
    W, H = cfg.record.width, cfg.record.height
    k = H / 1080
    s = cfg.compose
    # background: a clean game frame from the player's best round, just before its last kill
    best = max(plan.segments, key=lambda sg: hl[sg.round_number].score if sg.round_number in hl else 0,
               default=None)
    frame = job / "cover_bg.png"
    if best is not None and clips:
        i = plan.segments.index(best)
        kf = job / "kills.json"
        kills = [int(t) for t, _ in json.loads(kf.read_text())] if kf.exists() else []
        in_round = [t for t in kills if best.start_tick <= t <= best.end_tick]
        start = actual_starts(job).get(clip_id(best), float(best.start_tick))
        at = max(0.5, ((in_round[-1] if in_round else best.start_tick + 5 * plan.tickrate) - start)
                 / plan.tickrate - 0.4)
        subprocess.run([s.ffmpeg, "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", str(clips[i]),
                        "-frames:v", "1", str(frame)], check=False)
    if frame.exists():
        # cut away the game's scoreboard bar (top ~190 px at 1080p) and bottom HUD, keep 16:9
        f = Image.open(frame).convert("RGB")
        sk = f.height / 1080
        top, bottom = 200 * sk, f.height - 115 * sk
        ch = bottom - top
        cw = ch * f.width / f.height
        bg = f.crop(((f.width - cw) / 2, top, (f.width + cw) / 2, bottom)).resize((W, H), Image.LANCZOS)
    else:
        bg = Image.new("RGB", (W, H), (23, 32, 42))
    # darken the left side for the text
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line((x, 0, x, H), fill=int(225 * max(0.0, 1 - x / (W * 0.62)) ** 1.2))
    im = Image.composite(Image.new("RGB", (W, H), (10, 13, 18)), bg, shade).convert("RGBA")
    d = ImageDraw.Draw(im)

    meta = json.loads((job / "meta.json").read_text(encoding="utf-8")) if (job / "meta.json").exists() else {}
    me, teams = _player_stats(meta, plan.player.steamid)
    gold, white, dim = (220, 174, 79, 255), (244, 246, 248, 255), (200, 208, 216, 255)
    x = int(90 * k)
    name = plan.player.name
    size = 200 if len(name) <= 8 else max(110, int(1600 / len(name)))
    d.text((x, int(250 * k)), name, font=font(size * k, cjk=True), fill=white, anchor="ls",
           stroke_width=int(3 * k), stroke_fill=(0, 0, 0, 255))
    d.text((x, int(345 * k)), "POV", font=font(96 * k), fill=gold, anchor="ls")
    line = [pretty_map(plan.map_name)]
    score = _score_line(teams, plan.player.steamid)
    if score:
        line.append(score)
    if date:
        line.append(date)
    d.text((x, int(440 * k)), "   ".join(line), font=font(52 * k, cjk=True), fill=dim, anchor="ls")
    whole = len({sg.round_number for sg in plan.segments}) >= len(hl)
    if me and whole:
        kd = f"{me['kills']} / {me['deaths']} / {me['assists']}"
        d.text((x, int(560 * k)), kd, font=font(110 * k), fill=white, anchor="ls")
        d.text((x, int(615 * k)), "K / D / A" if lang != "zh" else "击杀 / 死亡 / 助攻", font=font(36 * k, cjk=True),
               fill=dim, anchor="ls")
    tags = [highlights.describe(hl[sg.round_number], lang) for sg in plan.segments if sg.round_number in hl]
    tags = [t for t in tags if t]
    top = sorted({t for t in tags}, key=lambda t: ("ACE" not in t, "四杀" not in t and "4K" not in t, t))[:3]
    y = int(760 * k)
    for t in top:
        tw = d.textlength(t, font=font(48 * k, cjk=True))
        d.rounded_rectangle((x - 18 * k, y - 50 * k, x + tw + 18 * k, y + 16 * k), radius=int(8 * k), fill=gold)
        d.text((x, y), t, font=font(48 * k, cjk=True), fill=(42, 31, 6, 255), anchor="ls")
        x += int(tw + 60 * k)
    im.convert("RGB").save(out, quality=92)
    return out


def make_upload_kit(cfg: Config, job: Path, plan: Plan, clips: list[Path], final: Path,
                    date: str) -> tuple[Path, Path]:
    lang = cfg.compose.chapter_lang
    hl = highlights.load(job / "highlights.json")
    cover = make_cover(cfg, job, plan, clips, job / "cover.jpg", hl, date, lang)
    meta = json.loads((job / "meta.json").read_text(encoding="utf-8")) if (job / "meta.json").exists() else {}
    me, teams = _player_stats(meta, plan.player.steamid)
    score = _score_line(teams, plan.player.steamid)
    recorded = {sg.round_number for sg in plan.segments}   # only what's in this video
    whole = len(recorded) >= len(hl)                         # the whole match, or a few rounds
    top = sorted((h for n, h in hl.items() if n in recorded), key=lambda h: -h.score)
    star = ""
    if top and (top[0].kills >= 3 or top[0].clutch):          # worth a mention in the title
        star = highlights.describe(top[0], lang)
    mp = pretty_map(plan.map_name)
    src = "FACEIT" if meta.get("faceit_match") else ""
    chapters = (job / "chapters.txt").read_text(encoding="utf-8").strip() if (job / "chapters.txt").exists() else ""
    if lang == "zh":
        bits = [f"【CS2 POV】{plan.player.name} 第一人称", f"{mp} {score}".strip()]
        if me and whole:
            bits.append(f"{me['kills']}杀" + (f" {star}" if star else ""))
        elif star:
            bits.append(star)
        if src or date:
            bits.append(" ".join(b for b in (src, date) if b))
        title = " | ".join(bits)
        body = [title, "", f"选手：{plan.player.name}", f"地图：{mp}" + (f"   比分：{score}" if score else "")]
        if me:
            body.append(f"数据：{me['kills']} 杀 / {me['deaths']} 死 / {me['assists']} 助攻，ADR {me['adr']:.0f}，"
                        f"爆头率 {me['hs_pct']:.0f}%")
        if date:
            body.append(f"比赛时间：{date}")
        body += ["", "章节：", chapters]
    else:
        bits = [f"{plan.player.name} POV", f"{mp} {score}".strip()]
        if me and whole:
            bits.append(f"{me['kills']} kills" + (f" {star}" if star else ""))
        elif star:
            bits.append(star)
        if src or date:
            bits.append(" ".join(b for b in (src, date) if b))
        title = " | ".join(bits)
        body = [title, "", f"Player: {plan.player.name}", f"Map: {mp}" + (f"   Score: {score}" if score else "")]
        if me:
            body.append(f"Stats: {me['kills']}/{me['deaths']}/{me['assists']}, ADR {me['adr']:.0f}, HS {me['hs_pct']:.0f}%")
        if date:
            body.append(f"Played: {date}")
        body += ["", "Chapters:", chapters]
    desc = job / "description.txt"
    desc.write_text("\n".join(body).strip() + "\n", encoding="utf-8")
    return cover, desc
