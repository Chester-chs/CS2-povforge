"""Effects for highlight reels: an opening, transitions between the moments,
kill moments (slow motion, punch zoom, flash, shake), a colour look, cinema
bars, an ending and background music. All chosen before recording, applied
when the reel is put together.

The reel is put together in three steps, so every frame is encoded only once
and memory use stays small however long the reel is:

1. each moment is cut from its recording with its effects; its picture goes
   into up to three files (the head and the tail that take part in a
   transition, and the body in between), its sound into a WAV file;
2. each transition is made from the tail of one moment and the head of the next;
3. the picture files are joined without re-encoding, the sound is joined (with
   cross-fades where the pictures cross) and mixed with the music in one go,
   and both are put together.

Only FFmpeg filters are used (xfade, zoompan, eq, colorbalance, tpad, ...).
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .compose import AUDIO_RATE, ComposeSettings, concat_line
from .media import ffprobe_for, probe
from .camera import normalize_camera

# --- the choices ----------------------------------------------------------------

# name in the app -> FFmpeg xfade transition
TRANSITIONS = {
    "cut": None,            # straight cut
    "flash": "fadewhite",   # flash to white
    "black": "fadeblack",   # dip to black
    "dissolve": "fade",     # cross-dissolve
    "slide": "slideleft",   # push
    "wipe": "wipeleft",
    "zoom": "zoomin",
    "blur": "hblur",
    "pixel": "pixelize",
}

# Only fast filters here (LUT based): colorbalance would slow the reel down several times.
GRADES = {
    "none": "",
    "vivid": "eq=contrast=1.08:saturation=1.35",
    "cinematic": ("eq=contrast=1.1:saturation=0.85,"
                  "curves=r='0/0 0.5/0.52 1/1':g='0/0 0.5/0.5 1/0.98':b='0/0.06 0.5/0.48 1/0.92',vignette=PI/5"),
    "cool": "eq=saturation=1.08,lutyuv=u='clip(val+6,0,255)':v='clip(val-4,0,255)'",
    "warm": "eq=saturation=1.08,lutyuv=u='clip(val-5,0,255)':v='clip(val+5,0,255)'",
    "bw": "hue=s=0,eq=contrast=1.2",
    "match": None,          # matched to a reference video, see grade_filter()
}

INTROS = ("none", "fade", "title")
OUTROS = ("none", "fade", "freeze", "card")
KILL_SCOPES = ("all", "last", "final")
GAME_AUDIO = ("keep", "low", "mute")
PACES = {"tight": (2.0, 0.8), "normal": None, "long": (6.0, 2.5)}   # None = the app's settings

DEFAULTS: dict = {
    "intro": "none", "intro_text": "", "intro_sub": "", "intro_seconds": 2.5,
    "transition": "cut", "transition_seconds": 0.4, "transitions": {},
    "kill_slowmo": False, "slowmo_speed": 0.5, "kill_zoom": False, "kill_flash": False,
    "kill_shake": False, "kill_scope": "all",
    "grade": "none", "grade_match": None, "letterbox": False,
    "outro": "none", "outro_text": "", "outro_seconds": 2.0,
    "music": "", "music_volume": 0.8, "music_start": 0.0, "game_audio": "keep",
    "pace": "normal",
    "camera": normalize_camera(None),
}

# Looks are not made up here: the app only offers "no effects" and the styles the
# user copied from finished videos (style.py), kept in their settings.
PRESETS: dict[str, dict] = {"plain": {}}


def _num(v, lo: float, hi: float, default: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(x) else min(hi, max(lo, x))


def normalize(fx: dict | None) -> dict:
    """The effects with every setting present and in range (unknown keys dropped)."""
    fx = dict(fx or {})
    out = dict(DEFAULTS)
    for k in DEFAULTS:
        if k in fx and fx[k] is not None:
            out[k] = fx[k]
    pick = lambda k, ok: out[k] if out[k] in ok else DEFAULTS[k]  # noqa: E731
    out["intro"], out["outro"] = pick("intro", INTROS), pick("outro", OUTROS)
    out["transition"] = pick("transition", TRANSITIONS)
    out["grade"] = pick("grade", GRADES)
    out["kill_scope"], out["game_audio"] = pick("kill_scope", KILL_SCOPES), pick("game_audio", GAME_AUDIO)
    out["pace"] = pick("pace", PACES)
    out["camera"] = normalize_camera(out["camera"])
    out["transitions"] = {str(int(k)): v for k, v in dict(out["transitions"] or {}).items()
                          if str(k).lstrip("-").isdigit() and v in TRANSITIONS}
    for k in ("kill_slowmo", "kill_zoom", "kill_flash", "kill_shake", "letterbox"):
        out[k] = bool(out[k])
    out["intro_seconds"] = _num(out["intro_seconds"], 1.0, 6.0, 2.5)
    out["outro_seconds"] = _num(out["outro_seconds"], 1.0, 6.0, 2.0)
    out["transition_seconds"] = _num(out["transition_seconds"], 0.1, 1.5, 0.4)
    out["slowmo_speed"] = _num(out["slowmo_speed"], 0.2, 0.8, 0.5)
    out["music_volume"] = _num(out["music_volume"], 0.0, 1.5, 0.8)
    out["music_start"] = _num(out["music_start"], 0.0, 3600.0, 0.0)
    for k in ("intro_text", "intro_sub", "outro_text", "music"):
        out[k] = str(out[k] or "")
    gm = out["grade_match"]
    out["grade_match"] = ({k: float(gm[k]) for k in ("sat", "luma", "spread", "u", "v") if k in gm}
                          if isinstance(gm, dict) else None)
    if out["grade"] == "match" and not out["grade_match"]:
        out["grade"] = "none"
    return out


def is_plain(fx: dict | None) -> bool:
    """Nothing chosen (the pace aside): the reel is joined the quick way, as before."""
    fx = normalize(fx)
    fx["pace"] = DEFAULTS["pace"]
    camera = fx["camera"]
    if not camera["victim"]:
        fx["camera"] = normalize_camera(None)
    return fx == normalize({})


def pace_seconds(fx: dict, before: float, after: float) -> tuple[float, float]:
    """Seconds kept before the first kill and after the last of each moment."""
    return PACES.get(normalize(fx)["pace"]) or (before, after)


# --- a moment and its timing -------------------------------------------------------

@dataclass
class Moment:
    clip: Path
    start: float                      # seconds into the clip
    end: float
    kills: list[float] = field(default_factory=list)   # seconds from ``start``

    @property
    def length(self) -> float:
        return self.end - self.start


def chosen_kills(moments: list[Moment], scope: str) -> list[list[float]]:
    """The kills each moment's kill effects are applied to."""
    out = [sorted(k for k in m.kills if 0 <= k <= m.length) for m in moments]
    if scope == "final":
        final = next((i for i in range(len(out) - 1, -1, -1) if out[i]), -1)
        return [ks[-1:] if i == final else [] for i, ks in enumerate(out)]
    if scope == "last":
        return [ks[-1:] for ks in out]
    return out


SLOW_BEFORE, SLOW_AFTER = 0.30, 0.25


def time_map(length: float, kills: list[float], speed: float | None) -> list[tuple[float, float, float]]:
    """(from, to, speed) pieces covering the moment: slowed around each kill."""
    if not speed or not kills:
        return [(0.0, length, 1.0)]
    slow: list[list[float]] = []
    for k in sorted(kills):
        a, b = max(0.0, k - SLOW_BEFORE), min(length, k + SLOW_AFTER)
        if b <= a:
            continue
        if slow and a <= slow[-1][1]:
            slow[-1][1] = max(slow[-1][1], b)
        else:
            slow.append([a, b])
    out, t = [], 0.0
    for a, b in slow:
        if a > t + 1e-3:
            out.append((t, a, 1.0))
        out.append((a, b, speed))
        t = b
    if length > t + 1e-3:
        out.append((t, length, 1.0))
    return out


def mapped(t: float, parts: list[tuple[float, float, float]]) -> float:
    """Where a moment's time ``t`` ends up after the slow motion."""
    off = 0.0
    for a, b, s in parts:
        if t <= b:
            return off + (max(t, a) - a) / s
        off += (b - a) / s
    return off


def mapped_length(parts) -> float:
    return sum((b - a) / s for a, b, s in parts)


# --- filters -------------------------------------------------------------------------

def _f(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def setpts_expr(parts) -> str:
    """Piecewise time stretch for setpts (T = input seconds)."""
    if len(parts) == 1 and parts[0][2] == 1.0:
        return "PTS-STARTPTS"
    expr, off = "", 0.0
    pieces = []
    for a, b, s in parts:
        pieces.append((b, f"{_f(off)}+(T-{_f(a)})/{_f(s)}"))
        off += (b - a) / s
    expr = pieces[-1][1]
    for b, e in reversed(pieces[:-1]):
        expr = f"if(lt(T,{_f(b)}),{e},{expr})"
    return f"({expr})/TB"


def atempo_chain(speed: float) -> str:
    """atempo takes 0.5..2 per step; chain steps for slower speeds."""
    steps = []
    while speed < 0.5 - 1e-9:
        steps.append(0.5)
        speed /= 0.5
    steps.append(speed)
    return ",".join(f"atempo={_f(s)}" for s in steps if abs(s - 1.0) > 1e-9) or "anull"


def _pulse_sum(kills: list[float], var: str, rise: float, fall: float) -> str:
    """Sum of quick-rise, slow-fall pulses at the kills (peak 1 at each kill)."""
    terms = [f"if(lt({var},{_f(k)}),exp(-pow(({var}-{_f(k)})/{_f(rise)},2)),exp(-({var}-{_f(k)})/{_f(fall)}))"
             for k in kills]
    return "+".join(terms) or "0"


def _after_sum(kills: list[float], var: str, fall: float) -> str:
    terms = [f"gte({var},{_f(k)})*exp(-({var}-{_f(k)})/{_f(fall)})" for k in kills]
    return "+".join(terms) or "0"


ZOOM_AMOUNT, SHAKE_AMOUNT, FLASH_AMOUNT = 0.12, 0.016, 0.32


def zoom_shake_filter(kills: list[float], zoom: bool, shake: bool, size: tuple[int, int], fps: int) -> str:
    if not kills or not (zoom or shake):
        return ""
    z_terms = []
    if zoom:
        z_terms.append(f"{ZOOM_AMOUNT}*min(1,{_pulse_sum(kills, 'it', 0.06, 0.22)})")
    env = f"min(1,{_after_sum(kills, 'it', 0.14)})"
    dx = dy = "0"
    if shake:
        z_terms.append(f"{2.6 * SHAKE_AMOUNT:.4f}*{env}")
        dx = f"iw*{SHAKE_AMOUNT}*{env}*sin(2*PI*31*it)"
        dy = f"ih*{SHAKE_AMOUNT * 0.7:.4f}*{env}*sin(2*PI*23*it+1)"
    z = "1+" + "+".join(z_terms)
    x = f"clip(iw/2-iw/zoom/2+{dx},0,iw-iw/zoom)"
    y = f"clip(ih/2-ih/zoom/2+{dy},0,ih-ih/zoom)"
    w, h = size
    return f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={fps}"


def flash_filter(kills: list[float]) -> str:
    if not kills:
        return ""
    return f"eq=brightness='min(0.5,{FLASH_AMOUNT}*({_after_sum(kills, 't', 0.08)}))':eval=frame"


def grade_filter(fx: dict, source_stats: dict | None = None) -> str:
    """The colour look. ``match`` scales saturation and contrast, and shifts
    brightness and tint, so the moments' averages come out like the reference's."""
    g = fx["grade"]
    if g != "match":
        return GRADES.get(g, "")
    ref, src = fx.get("grade_match") or {}, source_stats or {}
    if not ref or not src:
        return ""
    sat = min(2.0, max(0.3, ref["sat"] / max(src["sat"], 1.0)))
    con = min(1.6, max(0.6, ref["spread"] / max(src["spread"], 1.0)))
    luma_after = (src["luma"] - 128) * con + 128
    bri = min(0.3, max(-0.3, (ref["luma"] - luma_after) / 255))
    du = ref["u"] - ((src["u"] - 128) * sat + 128)
    dv = ref["v"] - ((src["v"] - 128) * sat + 128)
    out = f"eq=contrast={_f(con)}:brightness={_f(bri)}:saturation={_f(sat)}"
    if abs(du) >= 1 or abs(dv) >= 1:
        out += f",lutyuv=u='clip(val+{_f(du)},0,255)':v='clip(val+{_f(dv)},0,255)'"
    return out


def letterbox_filter(size: tuple[int, int]) -> str:
    w, h = size
    bar = int(round(h * (1 - (w / h) / 2.35) / 2 / 2)) * 2      # 2.35:1, even number of rows
    if bar <= 0:
        return ""
    return (f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,"
            f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill")


# --- running FFmpeg ----------------------------------------------------------------

def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tail = "\n".join((r.stderr or "").strip().splitlines()[-6:])
        raise RuntimeError(f"FFmpeg failed: {tail}")


def has_audio(path: Path, ffmpeg: str) -> bool:
    r = subprocess.run([ffprobe_for(ffmpeg), "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=index", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(r.stdout.strip())


def video_args(s: ComposeSettings) -> list[str]:
    return ["-c:v", "libx264", "-crf", str(s.crf), "-preset", s.preset, "-pix_fmt", "yuv420p"]


@dataclass
class Rendered:
    head: Path | None
    body: Path
    tail: Path | None
    wav: Path
    head_s: float = 0.0
    body_s: float = 0.0
    tail_s: float = 0.0

    @property
    def seconds(self) -> float:
        return self.head_s + self.body_s + self.tail_s


def _write_video(cmd_in: list[str], fc: str, outs_audio: list[str], base: Path, head: float, tail: float,
                 total: float, fps: int, s: ComposeSettings) -> tuple[Path | None, Path, Path | None]:
    """Run FFmpeg once: picture into head/body/tail files (split on frames), sound per ``outs_audio``."""
    cuts = []
    if head > 0:
        cuts.append(head)
    if tail > 0:
        cuts.append(total - tail)
    # split half a frame early: the split lands exactly on the frame at that time
    times = ",".join(f"{max(0.0, c - 0.5 / fps):.6f}" for c in cuts)
    for f in base.parent.glob(base.name + "_*.mp4"):
        f.unlink()
    cmd = cmd_in + ["-filter_complex", fc, "-map", "[v]", *video_args(s)]
    if cuts:
        cmd += ["-force_key_frames", times, "-f", "segment", "-segment_times", times, "-reset_timestamps", "1",
                "-segment_format", "mp4", "-segment_format_options", "video_track_timescale=90000",
                str(base.parent / (base.name + "_%d.mp4"))]
    else:
        cmd += ["-video_track_timescale", "90000", str(base.parent / (base.name + "_0.mp4"))]
    cmd += outs_audio
    _run(cmd)
    files = sorted(base.parent.glob(base.name + "_*.mp4"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    if len(files) != len(cuts) + 1:
        raise RuntimeError(f"expected {len(cuts) + 1} parts of {base.name}, got {len(files)}")
    h = files.pop(0) if head > 0 else None
    t = files.pop() if tail > 0 else None
    return h, files[0], t


def _seconds(path: Path | None, fps: int, ffmpeg: str) -> float:
    return probe(path, ffmpeg).frames / fps if path else 0.0


def render_moment(m: Moment, kills: list[float], fx: dict, out: Path, size: tuple[int, int], fps: int,
                  s: ComposeSettings, head: float, tail: float, first: bool, last: bool,
                  grade: str) -> Rendered:
    """One moment with its effects; ``head``/``tail`` = seconds taking part in transitions."""
    parts = time_map(m.length, kills, fx["slowmo_speed"] if fx["kill_slowmo"] else None)
    length = mapped_length(parts)
    kt = [mapped(k, parts) for k in kills]
    freeze = fx["outro_seconds"] if (last and fx["outro"] == "freeze") else 0.0
    total = length + freeze
    w, h = size
    vf = ["setpts=PTS-STARTPTS",
          f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"]
    if len(parts) > 1:
        vf.append(f"setpts='{setpts_expr(parts)}'")
    vf.append(f"fps={fps}")
    for f in (zoom_shake_filter(kt, fx["kill_zoom"], fx["kill_shake"], size, fps),
              flash_filter(kt if fx["kill_flash"] else []), grade,
              letterbox_filter(size) if fx["letterbox"] else ""):
        if f:
            vf.append(f)
    if freeze:
        vf.append(f"tpad=stop_mode=clone:stop_duration={_f(freeze)}")
    if first and fx["intro"] == "fade":
        vf.append("fade=t=in:st=0:d=0.6")
    if last and fx["outro"] in ("fade", "freeze"):
        d = min(1.0, total / 3)
        vf.append(f"fade=t=out:st={_f(total - d)}:d={_f(d)}")
    vf.append("format=yuv420p")

    audio_in = "0:a" if has_audio(m.clip, s.ffmpeg) else "1:a"
    cmd = [s.ffmpeg, "-y", "-loglevel", "error", "-ss", f"{m.start:.3f}", "-t", f"{m.length:.3f}", "-i", str(m.clip),
           "-f", "lavfi", "-t", f"{m.length:.3f}", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo"]
    a_pre = f"aresample={AUDIO_RATE},aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS"
    if len(parts) > 1:
        names = [f"s{i}" for i in range(len(parts))]
        af = f"[{audio_in}]{a_pre},asplit={len(parts)}" + "".join(f"[{n}]" for n in names) + ";"
        for n, (a, b, sp) in zip(names, parts):
            af += f"[{n}]atrim=start={_f(a)}:end={_f(b)},asetpts=PTS-STARTPTS,{atempo_chain(sp)}[{n}o];"
        af += "".join(f"[{n}o]" for n in names) + f"concat=n={len(parts)}:v=0:a=1"
    else:
        af = f"[{audio_in}]{a_pre}"
    if freeze:
        af += f",apad=pad_dur={_f(freeze)}"
    if first and fx["intro"] == "fade":
        af += ",afade=t=in:st=0:d=0.4"
    if last and fx["outro"] in ("fade", "freeze"):
        d = min(1.2, total / 3)
        af += f",afade=t=out:st={_f(total - d)}:d={_f(d)}"
    fc = f"[0:v]{','.join(vf)}[v];{af}[a]"
    wav = out.parent / (out.name + ".wav")
    hd, body, tl = _write_video(cmd, fc, ["-map", "[a]", "-c:a", "pcm_s16le", "-ar", str(AUDIO_RATE), "-ac", "2",
                                          str(wav)], out, head, tail, total, fps, s)
    return Rendered(hd, body, tl, wav, _seconds(hd, fps, s.ffmpeg), _seconds(body, fps, s.ffmpeg),
                    _seconds(tl, fps, s.ffmpeg))


def render_card(image: Path, seconds: float, out: Path, size: tuple[int, int], fps: int, s: ComposeSettings,
                head: float, tail: float, fade_in: bool, fade_out: bool, letterbox: bool) -> Rendered:
    w, h = size
    vf = [f"scale={w}:{h},setsar=1,fps={fps}"]
    if letterbox:
        vf.append(letterbox_filter(size))
    if fade_in:
        vf.append("fade=t=in:st=0:d=0.5")
    if fade_out:
        vf.append(f"fade=t=out:st={_f(seconds - 0.7)}:d=0.7")
    vf.append("format=yuv420p")
    cmd = [s.ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-t", _f(seconds),
           "-i", str(image), "-f", "lavfi", "-t", _f(seconds), "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo"]
    fc = f"[0:v]{','.join(vf)}[v];[1:a]anull[a]"
    wav = out.parent / (out.name + ".wav")
    hd, body, tl = _write_video(cmd, fc, ["-map", "[a]", "-c:a", "pcm_s16le", "-ar", str(AUDIO_RATE), "-ac", "2",
                                          str(wav)], out, head, tail, seconds, fps, s)
    return Rendered(hd, body, tl, wav, _seconds(hd, fps, s.ffmpeg), _seconds(body, fps, s.ffmpeg),
                    _seconds(tl, fps, s.ffmpeg))


def render_transition(a: Path, b: Path, kind: str, seconds: float, offset: float, out: Path,
                      s: ComposeSettings) -> None:
    """``a`` crossing into ``b`` over ``seconds``, starting ``offset`` into ``a``: as long as both minus the crossing."""
    _run([s.ffmpeg, "-y", "-loglevel", "error", "-i", str(a), "-i", str(b), "-filter_complex",
          f"[0:v][1:v]xfade=transition={TRANSITIONS[kind]}:duration={seconds:.6f}:offset={offset:.6f},"
          "format=yuv420p[v]",
          "-map", "[v]", *video_args(s), "-video_track_timescale", "90000", str(out)])


# --- cards ----------------------------------------------------------------------------

def grab_frame(clip: Path, at: float, out: Path, size: tuple[int, int], ffmpeg: str) -> Path | None:
    w, h = size
    r = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{max(0.0, at):.3f}", "-i", str(clip),
                        "-frames:v", "1", "-vf", f"scale={w}:{h}", str(out)], capture_output=True)
    return out if r.returncode == 0 and out.exists() else None


def make_card(title: str, subtitle: str, background: Path | None, out: Path, size: tuple[int, int]) -> Path:
    """A title card: the blurred, darkened picture behind large centred text."""
    from PIL import Image, ImageDraw, ImageFilter

    from .overlay import font

    w, h = size
    if background and background.exists():
        bg = Image.open(background).convert("RGB").resize((w, h))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=max(8, w // 70)))
        bg = Image.blend(bg, Image.new("RGB", (w, h), (0, 0, 0)), 0.55)
    else:
        bg = Image.new("RGB", (w, h), (12, 12, 14))
    d = ImageDraw.Draw(bg)
    size_t = int(h * 0.10)
    ft = font(size_t, cjk=True)
    while size_t > 24 and d.textlength(title, font=ft) > w * 0.84:
        size_t = int(size_t * 0.9)
        ft = font(size_t, cjk=True)
    size_s = int(h * 0.042)
    fs = font(size_s, cjk=True)
    y = h * 0.5 - (size_t * 0.75 if subtitle else size_t * 0.55)
    tw = d.textlength(title, font=ft)
    d.text(((w - tw) / 2 + 2, y + 3), title, font=ft, fill=(0, 0, 0))
    d.text(((w - tw) / 2, y), title, font=ft, fill=(255, 255, 255))
    if subtitle:
        sw = d.textlength(subtitle, font=fs)
        d.text(((w - sw) / 2, y + size_t * 1.5), subtitle, font=fs, fill=(214, 214, 220))
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out)
    return out


# --- the whole reel -------------------------------------------------------------------

def _log(msg: str) -> None:
    print(msg, flush=True)


def boundary_kind(fx: dict, index: int) -> str:
    """Transition into moment ``index`` (1 = between the first and second)."""
    return fx["transitions"].get(str(index), fx["transition"])


def build(moments: list[Moment], fx: dict, out: Path, work: Path, size: tuple[int, int], fps: int,
          s: ComposeSettings, title: str = "", source_stats: dict | None = None) -> Path:
    """Put the reel together with its effects into ``out``."""
    fx = normalize(fx)
    if not moments:
        raise ValueError("no moments")
    work.mkdir(parents=True, exist_ok=True)
    grade = grade_filter(fx, source_stats)
    kills = chosen_kills(moments, fx["kill_scope"])

    # the sequence: optional cards around the moments
    seq: list[tuple[str, object]] = []
    if fx["intro"] == "title":
        bg = grab_frame(moments[0].clip, moments[0].start, work / "intro_bg.png", size, s.ffmpeg)
        seq.append(("card", make_card(fx["intro_text"] or title, fx["intro_sub"], bg, work / "intro.png", size)))
    seq += [("moment", i) for i in range(len(moments))]
    if fx["outro"] == "card":
        last = moments[-1]
        bg = grab_frame(last.clip, last.end - 0.1, work / "outro_bg.png", size, s.ffmpeg)
        seq.append(("card", make_card(fx["outro_text"] or title, "", bg, work / "outro.png", size)))

    # the transition at each join and its length
    joins: list[tuple[str, float]] = []
    def length_of(item) -> float:
        kind, v = item
        if kind == "card":
            return fx["intro_seconds"] if v.name == "intro.png" else fx["outro_seconds"]
        return mapped_length(time_map(moments[v].length, kills[v], fx["slowmo_speed"] if fx["kill_slowmo"] else None))
    for j in range(1, len(seq)):
        a, b = seq[j - 1], seq[j]
        if a[0] == "card" or b[0] == "card":
            kind = fx["transition"] if fx["transition"] != "cut" else "black"
            secs = max(0.4, fx["transition_seconds"])
        else:
            kind = boundary_kind(fx, b[1])
            secs = fx["transition_seconds"]
        if kind != "cut":
            secs = min(secs, 0.4 * length_of(a), 0.4 * length_of(b))
        joins.append((kind, secs if kind != "cut" else 0.0))

    rendered: list[Rendered] = []
    for j, (kind, v) in enumerate(seq):
        head = joins[j - 1][1] if j > 0 else 0.0
        tail = joins[j][1] if j < len(joins) else 0.0
        base = work / f"p{j:03d}"
        if kind == "card":
            _log(f"Effects: {'opening' if j == 0 else 'ending'} card")
            rendered.append(render_card(v, length_of(seq[j]), base, size, fps, s, head, tail,
                                        fade_in=j == 0, fade_out=j == len(seq) - 1, letterbox=fx["letterbox"]))
        else:
            _log(f"Effects: moment {v + 1}/{len(moments)}")
            rendered.append(render_moment(moments[v], kills[v], fx, base, size, fps, s, head, tail,
                                          first=v == 0 and j == 0, last=v == len(moments) - 1 and j == len(seq) - 1,
                                          grade=grade))

    # transitions
    files: list[Path] = []
    crossings: list[float] = []
    for j, r in enumerate(rendered):
        if j > 0 and joins[j - 1][1] > 0:
            prev = rendered[j - 1]
            d = min(prev.tail_s, r.head_s)
            t = work / f"t{j:03d}.mp4"
            render_transition(prev.tail, r.head, joins[j - 1][0], d, prev.tail_s - d, t, s)
            files.append(t)
            crossings.append(d)
        elif j > 0:
            crossings.append(0.0)
        files.append(r.body)

    _log("Effects: joining the picture ...")
    listing = work / "list.txt"
    listing.write_text("".join(concat_line(p) for p in files), encoding="utf-8")
    picture = work / "picture.mp4"
    _run([s.ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
          "-c", "copy", "-an", str(picture)])

    _log("Effects: sound and music ...")
    sound = work / "sound.m4a"
    total = sum(r.seconds for r in rendered) - sum(crossings)
    mix_sound(rendered, crossings, fx, total, sound, s)

    out.parent.mkdir(parents=True, exist_ok=True)
    _run([s.ffmpeg, "-y", "-loglevel", "error", "-i", str(picture), "-i", str(sound), "-map", "0:v", "-map", "1:a",
          "-c", "copy", "-movflags", "+faststart", str(out)])
    return out


def mix_sound(rendered: list[Rendered], crossings: list[float], fx: dict, total: float, out: Path,
              s: ComposeSettings) -> None:
    cmd = [s.ffmpeg, "-y", "-loglevel", "error"]
    for r in rendered:
        cmd += ["-i", str(r.wav)]
    fc = []
    for i, r in enumerate(rendered):
        fade = ""
        if i > 0 and crossings[i - 1] == 0:
            fade += ",afade=t=in:st=0:d=0.01"
        if i < len(rendered) - 1 and crossings[i] == 0:
            fade += f",afade=t=out:st={_f(r.seconds - 0.01)}:d=0.01"
        fc.append(f"[{i}:a]aformat=sample_fmts=fltp:sample_rates={AUDIO_RATE}:channel_layouts=stereo,"
                  f"apad,atrim=end={r.seconds:.6f},asetpts=PTS-STARTPTS{fade}[g{i}]")
    cur = "g0"
    for i in range(1, len(rendered)):
        nxt = f"j{i}"
        if crossings[i - 1] > 0:
            fc.append(f"[{cur}][g{i}]acrossfade=d={crossings[i - 1]:.6f}:c1=tri:c2=tri[{nxt}]")
        else:
            fc.append(f"[{cur}][g{i}]concat=n=2:v=0:a=1[{nxt}]")
        cur = nxt
    game = {"keep": 1.0, "low": 0.35, "mute": 0.0}[fx["game_audio"]]
    music = Path(fx["music"]) if fx["music"] else None
    if music is not None and music.is_file():
        cmd += ["-stream_loop", "-1", "-ss", _f(fx["music_start"]), "-i", str(music)]
        m = len(rendered)
        fade_out = min(2.5, total / 4)
        fc.append(f"[{m}:a]aformat=sample_fmts=fltp:sample_rates={AUDIO_RATE}:channel_layouts=stereo,"
                  f"atrim=duration={total:.6f},asetpts=PTS-STARTPTS,volume={_f(fx['music_volume'])},"
                  f"afade=t=in:st=0:d=0.8,afade=t=out:st={_f(total - fade_out)}:d={_f(fade_out)}[mus]")
        if game > 0:
            fc.append(f"[{cur}]volume={_f(game)}[gm]")
            fc.append("[gm][mus]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:latency=1[out]")
        else:
            fc.append(f"[{cur}]volume=0[gm]")
            fc.append("[gm][mus]amix=inputs=2:duration=first:normalize=0[out]")
    else:
        fc.append(f"[{cur}]anull[out]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[out]", "-c:a", "aac", "-b:a", "192k",
            "-ar", str(AUDIO_RATE), "-ac", "2", str(out)]
    _run(cmd)


def describe(fx: dict) -> list[str]:
    """Short English summary for the log."""
    fx = normalize(fx)
    out = []
    if fx["intro"] != "none":
        out.append(f"opening {fx['intro']}")
    if fx["transition"] != "cut" or fx["transitions"]:
        out.append(f"transition {fx['transition']} {fx['transition_seconds']:.1f}s")
    ks = [k for k in ("slowmo", "zoom", "flash", "shake") if fx[f"kill_{k}"]]
    if ks:
        out.append(f"kills: {'+'.join(ks)} ({fx['kill_scope']})")
    if fx["grade"] != "none":
        out.append(f"colour {fx['grade']}")
    if fx["letterbox"]:
        out.append("cinema bars")
    if fx["outro"] != "none":
        out.append(f"ending {fx['outro']}")
    if fx["music"]:
        out.append(f"music {Path(fx['music']).name}")
    camera = fx["camera"]
    if camera["victim"]:
        out.append("victim views after the main reel, in kill order")
    return out


def cleanup(work: Path) -> None:
    shutil.rmtree(work, ignore_errors=True)


def dump(fx: dict) -> str:
    return json.dumps(normalize(fx), ensure_ascii=False)
