"""Work out the style of a finished highlight video ("照着成片做").

The video is read as tiny frames (64x36) and its sound at a low sample rate,
and the effects PovForge can make are looked for:

* the opening: a fade in from black, or a still title card;
* the joins between moments: straight cuts, flashes to white, dips to black,
  cross-dissolves, slides/wipes, and how long they last;
* effects inside a moment (on the kills): short flashes, punch zooms, shakes,
  slow motion (repeated frames);
* the colour (saturation, brightness, contrast, tint), cinema bars;
* the ending: a freeze, a still end card, a fade to black;
* background music (a steady beat), and how long each moment lasts.

The result is a set of reel effects (see effects.py) plus what was found, so
the app can fill in its settings and show a short report. It gives the same
kind of effects and rhythm, not a frame-exact copy.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .media import ffprobe_for

TW, TH = 64, 36                 # analysis frame size
MAX_SECONDS = 15 * 60
SHIFTS = [(dx, dy) for dy in range(-2, 3) for dx in range(-4, 5)]
ZOOMS = (1.015, 1.03, 1.06, 1.10)
NEW_SCENE = 35                  # _scene_diff above this: a different picture, not the same one moved


# --- reading -------------------------------------------------------------------------

def video_info(path: Path, ffmpeg: str) -> dict:
    out = subprocess.run([ffprobe_for(ffmpeg), "-v", "error", "-show_entries",
                          "stream=codec_type,avg_frame_rate,r_frame_rate,width,height:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    if out.returncode != 0:
        raise ValueError(f"Not a video PovForge can read: {Path(path).name}")
    d = json.loads(out.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    if v is None:
        raise ValueError(f"{Path(path).name} has no picture.")

    def rate(r: str) -> float:
        n, _, m = (r or "0/1").partition("/")
        return float(n) / float(m or 1) if float(m or 1) else 0.0
    fps = rate(v.get("avg_frame_rate")) or rate(v.get("r_frame_rate")) or 30.0
    return {"fps": fps, "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
            "duration": float(d.get("format", {}).get("duration") or 0),
            "audio": any(s.get("codec_type") == "audio" for s in d.get("streams", []))}


def _frames(cmd: list[str], chunk: int = 512):
    """Yield (n, TH, TW, 3) float32 arrays of the frames FFmpeg writes."""
    size = TW * TH * 3
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=flags)
    try:
        while True:
            data = p.stdout.read(size * chunk)
            n = len(data) // size
            if n == 0:
                break
            yield np.frombuffer(data[:n * size], np.uint8).reshape(n, TH, TW, 3).astype(np.float32)
    finally:
        p.stdout.close()
        p.wait()


def _yuv(a: np.ndarray):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    u = -0.168736 * r - 0.331264 * g + 0.5 * b + 128
    v = 0.5 * r - 0.418688 * g - 0.081312 * b + 128
    return y, u, v


def _colour(y, u, v) -> dict[str, np.ndarray]:
    flat = y.reshape(len(y), -1)
    return {"luma": flat.mean(1), "sat": np.sqrt((u - 128) ** 2 + (v - 128) ** 2).reshape(len(y), -1).mean(1),
            "spread": np.percentile(flat, 95, axis=1) - np.percentile(flat, 5, axis=1),
            "u": u.reshape(len(y), -1).mean(1), "v": v.reshape(len(y), -1).mean(1)}


def colour_stats(clips: list[tuple[Path, float, float]], ffmpeg: str) -> dict | None:
    """Average colour of some video parts ((file, start, seconds)), a few frames a second."""
    rows = []
    for path, start, secs in clips:
        cmd = [ffmpeg, "-v", "error", "-ss", f"{max(0.0, start):.3f}", "-t", f"{secs:.3f}", "-i", str(path),
               "-an", "-vf", f"fps=4,scale={TW}:{TH}:flags=area,format=rgb24", "-f", "rawvideo", "-"]
        for a in _frames(cmd):
            c = _colour(*_yuv(a))
            rows.append(np.stack([c[k] for k in ("sat", "luma", "spread", "u", "v")], 1))
    if not rows:
        return None
    m = np.concatenate(rows).mean(0)
    return {k: round(float(x), 2) for k, x in zip(("sat", "luma", "spread", "u", "v"), m)}


# zoom about the centre: where each pixel of the zoomed frame comes from (bilinear)
def _zoom_map(z: float):
    ys, xs = np.mgrid[0:TH, 0:TW].astype(np.float32)
    sy = (TH - 1) / 2 + (ys - (TH - 1) / 2) / z
    sx = (TW - 1) / 2 + (xs - (TW - 1) / 2) / z
    y0, x0 = np.floor(sy).astype(int), np.floor(sx).astype(int)
    wy, wx = sy - y0, sx - x0
    y1, x1 = np.clip(y0 + 1, 0, TH - 1), np.clip(x0 + 1, 0, TW - 1)
    return np.clip(y0, 0, TH - 1), np.clip(x0, 0, TW - 1), y1, x1, wy, wx


_ZMAPS = {z: _zoom_map(z) for z in ZOOMS + tuple(1 / z for z in ZOOMS)}


def _zoomed(a: np.ndarray, z: float) -> np.ndarray:
    y0, x0, y1, x1, wy, wx = _ZMAPS[z]
    return (a[:, y0, x0] * (1 - wy) * (1 - wx) + a[:, y0, x1] * (1 - wy) * wx
            + a[:, y1, x0] * wy * (1 - wx) + a[:, y1, x1] * wy * wx)


_NX = len({dx for dx, _ in SHIFTS})
_NY = len({dy for _, dy in SHIFTS})


def _subpixel(errs: np.ndarray, best: np.ndarray, axis: int) -> np.ndarray:
    """Best shift along x (axis 0) or y (1), refined between whole pixels."""
    bx, by = best % _NX, best // _NX
    pos, size, step = (bx, _NX, 1) if axis == 0 else (by, _NY, _NX)
    whole = np.array([SHIFTS[i][axis] for i in best], np.float32)
    ok = (pos > 0) & (pos < size - 1)
    rows = np.arange(len(best))
    i = np.where(ok, best, 0)
    lo = errs[rows, np.where(ok, i - step, 0)]
    mid = errs[rows, i]
    hi = errs[rows, np.where(ok, i + step, 0)]
    den = lo - 2 * mid + hi
    frac = np.where(ok & (den > 1e-6), 0.5 * (lo - hi) / np.where(den > 1e-6, den, 1), 0)
    return whole + np.clip(frac, -0.5, 0.5).astype(np.float32)


@dataclass
class Features:
    fps: float
    duration: float
    luma: np.ndarray = None
    sat: np.ndarray = None
    spread: np.ndarray = None
    u: np.ndarray = None
    v: np.ndarray = None
    top: np.ndarray = None          # brightest pixel in the top rows (cinema bars)
    bottom: np.ndarray = None
    diff: np.ndarray = None         # change from the frame before
    still: np.ndarray = None        # change from the frame before, ignoring brightness (fades)
    moved: np.ndarray = None        # change from the frame before, allowing for a small camera move
    dx: np.ndarray = None
    dy: np.ndarray = None
    zoom: np.ndarray = None         # best zoom from a few frames before (1 = none)
    zoom_gain: np.ndarray = None    # how much better that zoom explains the change than a move
    small: np.ndarray = None        # 32x18 YUV frames


def _shift_errs(cur: np.ndarray, before: np.ndarray, shifts) -> np.ndarray:
    return np.stack([np.abs(cur - before[:, 2 + dy:TH - 2 + dy, 4 + dx:TW - 4 + dx]).mean((1, 2))
                     for dx, dy in shifts], 1)


def read_features(path: Path, ffmpeg: str, info: dict | None = None, max_seconds: float = MAX_SECONDS,
                  progress=None) -> Features:
    info = info or video_info(path, ffmpeg)
    fps = info["fps"]
    lag = max(2, int(round(fps / 15)))          # zooms are measured over ~1/15 s
    cmd = [ffmpeg, "-v", "error", "-t", str(max_seconds), "-i", str(path), "-an", "-sn",
           "-vf", f"scale={TW}:{TH}:flags=area,format=rgb24", "-f", "rawvideo", "-"]
    names = ("luma", "sat", "spread", "u", "v", "top", "bottom", "diff", "still", "moved", "dx", "dy",
             "zoom", "zoom_gain", "small")
    cols: dict[str, list] = {k: [] for k in names}
    tail = None                                  # the last frames of the chunk before
    cy, cx = slice(2, TH - 2), slice(4, TW - 4)
    coarse = [(dx, dy) for dy in (-2, 0, 2) for dx in (-4, -2, 0, 2, 4)]
    zs = list(_ZMAPS)
    total = max(1, int(min(info["duration"] or max_seconds, max_seconds) * fps))
    done = 0
    for a in _frames(cmd):
        y, u, v = _yuv(a)
        for k, val in _colour(y, u, v).items():
            cols[k].append(val)
        cols["top"].append(y[:, :4].reshape(len(y), -1).max(1))
        cols["bottom"].append(y[:, -4:].reshape(len(y), -1).max(1))
        yuv = np.stack([y, u, v], -1).reshape(len(y), TH // 2, 2, TW // 2, 2, 3).mean((2, 4))
        cols["small"].append(np.clip(yuv, 0, 255).astype(np.uint8))
        allf = y if tail is None else np.concatenate([tail, y])
        off = len(allf) - len(y)
        prev1 = allf[np.maximum(np.arange(len(y)) + off - 1, 0)]
        prevL = allf[np.maximum(np.arange(len(y)) + off - lag, 0)]
        cur = y[:, cy, cx]
        cols["diff"].append(np.abs(cur - prev1[:, cy, cx]).mean((1, 2)))
        # brightness and contrast taken out, so fades count as still
        pc = prev1[:, cy, cx]
        c0 = (cur - cur.mean((1, 2), keepdims=True)) / np.maximum(cur.std((1, 2), keepdims=True), 4)
        p0 = (pc - pc.mean((1, 2), keepdims=True)) / np.maximum(pc.std((1, 2), keepdims=True), 4)
        cols["still"].append(np.abs(c0 - p0).mean((1, 2)) * 40)
        errs = _shift_errs(cur, prev1, SHIFTS)
        best = errs.argmin(1)
        cols["moved"].append(errs.min(1))
        cols["dx"].append(_subpixel(errs, best, 0))
        cols["dy"].append(_subpixel(errs, best, 1))
        # zooms are measured on the middle rows (4..31), clear of any cinema bars
        inner = cur[:, 2:-2]
        moveL = np.stack([np.abs(inner - prevL[:, 4 + dy:TH - 4 + dy, 4 + dx:TW - 4 + dx]).mean((1, 2))
                          for dx, dy in coarse], 1).min(1)
        zerr = np.stack([np.abs(inner - _zoomed(prevL, z)[:, 4:TH - 4, cx]).mean((1, 2)) for z in zs], 1)
        cols["zoom"].append(np.array([zs[i] for i in zerr.argmin(1)], np.float32))
        cols["zoom_gain"].append(moveL - zerr.min(1))
        tail = allf[-lag:]
        done += len(y)
        if progress:
            progress(min(1.0, done / total))
    if not cols["luma"]:
        raise ValueError("No frames could be read from this video.")
    f = Features(fps, info["duration"], **{k: np.concatenate(v) for k, v in cols.items()})
    f.diff[0] = f.still[0] = f.moved[0] = 0
    f.zoom_gain[:lag] = 0
    f.zoom[:lag] = 1
    return f


def read_audio(path: Path, ffmpeg: str, rate: int = 11025, max_seconds: float = MAX_SECONDS) -> np.ndarray | None:
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    r = subprocess.run([ffmpeg, "-v", "error", "-t", str(max_seconds), "-i", str(path), "-vn", "-ac", "1",
                        "-ar", str(rate), "-f", "s16le", "-"], capture_output=True, creationflags=flags)
    if r.returncode != 0 or len(r.stdout) < rate * 2:
        return None
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768


# --- finding things ---------------------------------------------------------------------

def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) of each run of True."""
    m = np.concatenate([[False], mask.astype(bool), [False]])
    d = np.flatnonzero(m[1:] != m[:-1])
    return [(int(a), int(b)) for a, b in zip(d[::2], d[1::2])]


def _local_median(x: np.ndarray, half: int) -> np.ndarray:
    n = len(x)
    out = np.empty(n, np.float32)
    step = max(1, half // 2)
    for i in range(0, n, step):
        out[i:i + step] = np.median(x[max(0, i - half):min(n, i + half + 1)])
    return out


def _zoom_small(p: np.ndarray, z: float) -> np.ndarray:
    """A 32x18 frame zoomed about its centre (nearest pixel)."""
    if z == 1:
        return p
    h, w = p.shape[:2]
    ys = np.clip(np.round((h - 1) / 2 + (np.arange(h) - (h - 1) / 2) / z).astype(int), 0, h - 1)
    xs = np.clip(np.round((w - 1) / 2 + (np.arange(w) - (w - 1) / 2) / z).astype(int), 0, w - 1)
    return p[ys][:, xs]


def _scene_diff(f: Features, a: int, b: int, reach: int = 6) -> float:
    """How different two frames' pictures are, allowing for a camera move or a
    punch zoom (0-255 scale)."""
    a, b = max(0, a), min(len(f.small) - 1, b)
    pa0, pb = f.small[a].astype(np.float32), f.small[b].astype(np.float32)
    best = np.inf
    w = pb.shape[1]
    yb = pb[..., 0] - pb[..., 0].mean()
    for z in (1.0, 1.08, 1 / 1.08, 1.16, 1 / 1.16):
        pa = _zoom_small(pa0, z)
        ya = pa[..., 0] - pa[..., 0].mean()
        for dx in range(-reach, reach + 1):
            x1, x2 = max(0, dx), min(w, w + dx)
            s = np.abs(yb[:, x1:x2] - ya[:, x1 - dx:x2 - dx]).mean()
            c = np.abs(pb[:, x1:x2, 1:] - pa[:, x1 - dx:x2 - dx, 1:]).mean()
            best = min(best, float(s + 1.5 * c))
    return best


def _moved_from(A: np.ndarray, B: np.ndarray, M: np.ndarray, reach: int = 12) -> float:
    """How well ``M`` is just ``A`` or ``B`` moved sideways or zoomed (camera
    motion, a punch zoom), 0 = exactly."""
    span = max(float(np.abs(A - B).mean()), 1e-3)
    w = M.shape[1]
    best = np.inf
    for P0 in (A, B):
        for z in (1.0, 1.06, 1 / 1.06, 1.12, 1 / 1.12):
            P = _zoom_small(P0, z)
            for dx in range(-reach, reach + 1, 1 if z == 1.0 else 2):
                x1, x2 = max(0, dx), min(w, w + dx)
                # the columns a move would bring in count as not explained
                err = float(np.abs(M[:, x1:x2] - P[:, x1 - dx:x2 - dx]).mean()) * (x2 - x1) + span * (w - (x2 - x1))
                best = min(best, err / w / span)
    return best


def _scene_series(small: np.ndarray, k: int, reach: int = 6) -> np.ndarray:
    """For every frame t: how different frame t+k is from t-k, allowing for a
    sideways camera move (as _scene_diff, without zooms), 0 at the ends."""
    n = len(small)
    out = np.zeros(n, np.float32)
    if n <= 2 * k:
        return out
    A, B = small[:-2 * k], small[2 * k:]
    ya = A[..., 0] - A[..., 0].mean((1, 2), keepdims=True)
    yb = B[..., 0] - B[..., 0].mean((1, 2), keepdims=True)
    w = small.shape[2]
    best = np.full(len(A), np.inf, np.float32)
    for dx in range(-reach, reach + 1):
        x1, x2 = max(0, dx), min(w, w + dx)
        sd = np.abs(yb[:, :, x1:x2] - ya[:, :, x1 - dx:x2 - dx]).mean((1, 2))
        cd = np.abs(B[:, :, x1:x2, 1:] - A[:, :, x1 - dx:x2 - dx, 1:]).mean((1, 2, 3))
        best = np.minimum(best, sd + 1.5 * cd)
    out[k:n - k] = best
    return out


def _peaks(x: np.ndarray, above: float, half: int) -> list[int]:
    """Frames where ``x`` is above ``above`` and the highest within ``half`` frames."""
    out = []
    for a, b in _runs(x > above):
        seg = x[a:b]
        t = a + int(seg.argmax())
        out.append(t)
        # long runs can hold more than one join
        for c in range(a, b, max(1, 2 * half)):
            s2 = x[c:min(b, c + 2 * half)]
            t2 = c + int(s2.argmax())
            if abs(t2 - t) > half and all(abs(t2 - o) > half for o in out):
                out.append(t2)
    return sorted(out)


def _blend_error(A: np.ndarray, B: np.ndarray, M: np.ndarray) -> float:
    span = max(float(np.abs(A - B).mean()), 1e-3)
    return float(np.abs(M - 0.5 * (A + B)).mean()) / span


def _slide_fit(A: np.ndarray, B: np.ndarray, M: np.ndarray) -> tuple[float, float, str]:
    """How well the frame is part of one picture and part of the other: (error,
    0 = exactly; share of the new picture; "slide" if the pictures move, "wipe" if not)."""
    w = A.shape[1]
    span = max(float(np.abs(A - B).mean()), 1e-3)
    best, share, kind = np.inf, 0.0, "slide"
    for s in range(1, w):
        preds = (("slide", np.concatenate([A[:, s:], B[:, :s]], 1)), ("slide", np.concatenate([B[:, w - s:], A[:, :w - s]], 1)),
                 ("wipe", np.concatenate([A[:, :w - s], B[:, w - s:]], 1)), ("wipe", np.concatenate([B[:, :s], A[:, s:]], 1)))
        for name, p in preds:
            e = float(np.abs(M - p).mean()) / span
            if e < best:
                best, share, kind = e, s / w, name
    return best, share, kind


def _slide_error(A: np.ndarray, B: np.ndarray, M: np.ndarray) -> float:
    e, share, _ = _slide_fit(A, B, M)
    return e if 0.15 <= share <= 0.85 else np.inf


def _slide_extent(ys: np.ndarray, t: int, k: int, far: int, lo: int, hi: int) -> tuple[int, int]:
    """First and last frame of a slide: where the new picture covers 15..85% of the frame, widened."""
    K = max(k, min(far, t - lo, hi - 1 - t))
    A, B = ys[t - K], ys[t + K]
    shares = {}
    for j in range(t - K + 1, t + K):
        e, sh, _ = _slide_fit(A, B, ys[j])
        shares[j] = sh if e < 0.45 else (0.0 if j < t else 1.0)
    mid = [j for j, sh in shares.items() if 0.15 < sh < 0.85]
    if not mid:
        return t - k, t + k
    a, b = min(mid), max(mid)
    grow = (b - a + 1) / 0.7 * 0.15
    return max(lo, int(round(a - grow))), min(hi - 1, int(round(b + grow)))


@dataclass
class Found:
    cuts: list[int] = field(default_factory=list)
    transitions: list[tuple[str, int, int]] = field(default_factory=list)   # (kind, first frame, last frame)
    flashes: list[int] = field(default_factory=list)
    zooms: list[int] = field(default_factory=list)
    shakes: list[int] = field(default_factory=list)
    slowmo: list[tuple[int, int, float]] = field(default_factory=list)      # (start, end, speed)
    intro: tuple[str, float] = ("none", 0.0)
    outro: tuple[str, float] = ("none", 0.0)


def find(f: Features) -> Found:
    fps, n = f.fps, len(f.luma)
    out = Found()
    sec = lambda s: max(1, int(round(s * fps)))  # noqa: E731
    base_luma = _local_median(f.luma, sec(1.5))
    still = f.still < 1.0
    dark = f.luma < 16

    # the opening: a fade in from black, a still title card
    start = 0
    while start < n and dark[start]:
        start += 1
    if 0 < start < n:
        ref = float(np.median(f.luma[start:start + sec(2)]))
        while start < n and f.luma[start] < 0.6 * ref:
            start += 1
        if start <= sec(2.5):
            out.intro = ("fade", start / fps)
    first = 0
    while first < n and dark[first]:
        first += 1
    s_end = first
    while s_end < n - 1 and (still[s_end + 1] or (s_end < start and f.luma[s_end + 1] > f.luma[s_end])):
        s_end += 1
    lo = start
    if s_end - max(first, start) >= sec(0.9) and s_end < n - sec(2):
        out.intro = ("title", s_end / fps)
        lo = s_end

    # the ending: a fade to black, and before it maybe a still part (a freeze or an end card)
    last = n
    while last > 0 and dark[last - 1]:
        last -= 1
    fade0 = last
    if last < n:                       # it ends in black: walk back over the fade
        while fade0 > 1 and f.luma[fade0 - 1] > f.luma[fade0] + 0.3 and fade0 > last - sec(2.5):
            fade0 -= 1
    e0 = fade0
    while e0 > 1 and still[e0 - 1]:
        e0 -= 1
    if fade0 - e0 >= sec(0.6) or (fade0 == last == n and n - e0 >= sec(0.8)):
        hi = e0
    else:
        e0 = fade0
        hi = fade0

    # flashes to white and dips to black
    taken = np.zeros(n, bool)          # already explained
    joined = np.zeros(n, bool)         # joins between moments
    bright = f.luma > np.maximum(140, base_luma + 30)
    for a, b in _runs(bright[lo:hi]):
        a, b = a + lo, b + lo
        a2, b2 = a, b
        while a2 > lo and f.luma[a2 - 1] > base_luma[a2 - 1] + 12:
            a2 -= 1
        while b2 < hi and f.luma[b2] > base_luma[b2] + 12:
            b2 += 1
        if b2 - a2 > sec(1.2):           # a flashbang, not an effect
            continue
        if _scene_diff(f, a2 - 2, b2 + 1) > NEW_SCENE:
            out.transitions.append(("flash", a2, b2))
            joined[max(0, a2 - 2):b2 + 2] = True
        else:
            out.flashes.append(a)
        taken[max(0, a2 - 2):b2 + 2] = True
    dim = f.luma < np.minimum(30, base_luma - 35)
    for a, b in _runs(dim[lo:hi]):
        a, b = a + lo, b + lo
        a2, b2 = a, b
        while a2 > lo and f.luma[a2 - 1] < base_luma[a2 - 1] - 12:
            a2 -= 1
        while b2 < hi and f.luma[b2] < base_luma[b2] - 12:
            b2 += 1
        if b2 - a2 <= sec(1.6) and _scene_diff(f, a2 - 2, b2 + 1) > NEW_SCENE:
            out.transitions.append(("black", a2, b2))
            taken[max(0, a2 - 2):b2 + 2] = joined[max(0, a2 - 2):b2 + 2] = True

    # punch zooms: a quick zoom in, then back out
    zin = (f.zoom >= 1.06) & (f.zoom_gain > 2.0)
    zin[:lo] = zin[hi:] = False
    for a, b in _runs(zin):
        after = slice(b, min(n, b + sec(0.8)))
        if ((f.zoom[after] < 0.99) & (f.zoom_gain[after] > 0.3)).sum() >= 2:
            out.zooms.append(a)
            taken[max(0, a - 3):b + 3] = True

    # hard cuts: one frame changes a lot, the frames around it don't
    m = f.moved
    lm = _local_median(m, sec(0.5))
    for t in range(max(lo, 3), min(hi, n - 3)):
        if taken[t]:
            continue
        neigh = max(m[t - 3:t].max(), m[t + 1:t + 4].max())
        if f.luma[t] > f.luma[t - 1] + 20 and f.luma[min(n - 1, t + sec(0.5))] < f.luma[t] - 15:
            continue                     # a flash on a kill, not a new picture
        if m[t] > max(18, 3 * lm[t]) and m[t] > 2.2 * neigh and _scene_diff(f, t - 1, t) > NEW_SCENE:
            out.cuts.append(t)
            taken[t - 1:t + 2] = joined[t - 2:t + 3] = True

    # gradual joins: where the picture becomes a different one over a few frames.
    # The middle frame is a blend of the frames either side (dissolve), or part
    # of one and part of the other (slide / wipe).
    small = f.small.astype(np.float32)
    ys = small[..., 0]
    for k in (sec(0.45), sec(0.25), sec(0.12)):
        if n <= 2 * k + 1:
            continue
        change = _scene_series(small, k)                 # change[t]: frame t-k against t+k
        for t in _peaks(change, 50, k):
            if not (lo + k <= t < hi - k) or taken[t - k:t + k + 1].any():
                continue
            near = range(max(lo + k, t - k // 2), min(hi - k, t + k // 2 + 1))
            kind = None
            big = change[t] >= 100                       # clearly a different picture
            tb = min(near, key=lambda j: _blend_error(ys[j - k], ys[j + k], ys[j]))
            be = _blend_error(ys[tb - k], ys[tb + k], ys[tb])
            if (be < 0.25 if big else be < 0.12) and _moved_from(ys[tb - k], ys[tb + k], ys[tb]) > be + 0.15:
                kind, t = "dissolve", tb
            elif big:
                ts = min(near, key=lambda j: _slide_error(ys[j - k], ys[j + k], ys[j]))
                err = _slide_error(ys[ts - k], ys[ts + k], ys[ts])
                if err < 0.3 and _moved_from(ys[ts - k], ys[ts + k], ys[ts]) > err + 0.03:
                    kind, t = _slide_fit(ys[ts - k], ys[ts + k], ys[ts])[2], ts
            if kind is None:
                continue
            if kind == "dissolve":
                a, b = _extent(small, t, k, sec(0.8), lo, hi)
            else:                                        # slide or wipe
                a, b = _slide_extent(ys, t, k, sec(0.8), lo, hi)
            out.transitions.append((kind, a, b))
            taken[a:b + 1] = True
            joined[max(0, a - 2):b + 3] = True
    out.transitions.sort(key=lambda x: x[1])

    # the ending, now that the joins are known
    if e0 < fade0:
        new_picture = any(abs(b - e0) <= sec(0.25) for _, _, b in out.transitions) or \
            _scene_diff(f, e0 - 1, e0 + 1) > 12
        out.outro = ("card" if new_picture else "freeze", (n - e0) / fps)
    elif last < n:
        out.outro = ("fade", (n - fade0) / fps)

    # inside the moments: shakes and repeated frames (slow motion)
    inside = ~joined
    inside[:lo] = inside[hi:] = False
    sign = np.sign(f.dx) * (np.abs(f.dx) >= 0.4)
    flips = np.concatenate([[False], (sign[1:] * sign[:-1]) < 0]) & inside
    win = sec(0.35)
    t = 0
    while t < n:
        if flips[t] and flips[t:t + win].sum() >= 3:
            out.shakes.append(t)
            t += win * 2
        else:
            t += 1
    # slow motion made by repeating frames: repeated and new frames take turns
    # (a picture that just stands still repeats every frame instead)
    near = np.maximum.reduce([np.roll(f.still, k) for k in (-3, -2, -1, 1, 2, 3)])
    dup = (f.still < 0.12) & (f.still < 0.3 * near) & inside
    w = sec(0.3)
    if n > w and inside.any():
        box = np.ones(w) / w
        rate = np.convolve(dup.astype(np.float32), box, mode="same")
        turns = np.convolve(np.concatenate([[0], (dup[1:] != dup[:-1]).astype(np.float32)]), box, mode="same")
        base = float(np.median(rate[inside]))
        for a, b in _runs((rate > base + 0.3) & (rate < 0.9) & (turns > 0.3) & inside):
            if b - a >= w // 2 and _regular(dup[a:b]):
                share = float(dup[a:b].mean())
                out.slowmo.append((a, b, round(max(0.2, min(0.8, 1 - share)), 2)))
    return out


def _regular(dup: np.ndarray) -> bool:
    """Repeated frames from slowing down come in an even pattern (every other
    frame, or two of every three...)."""
    runs_d = [b - a for a, b in _runs(dup)]
    runs_n = [b - a for a, b in _runs(~dup)]
    inner = lambda r: r[1:-1] if len(r) > 2 else r  # noqa: E731  (the ends are cut off by the window)
    return len(runs_d) >= 3 and float(np.std(inner(runs_d))) <= 0.6 and float(np.std(inner(runs_n))) <= 0.6


def _extent(small: np.ndarray, t: int, k: int, far: int, lo: int, hi: int) -> tuple[int, int]:
    """First and last frame of a gradual join centred near ``t``. Comparing the
    frames ``j`` before and after: the difference grows steadily while both are
    inside the join, then levels off; the bend is at half its length."""
    K = min(far, t - lo, hi - 1 - t)
    if K < 4:
        return t - k, t + k
    S = np.array([np.abs(small[t - j].astype(np.float32) - small[t + j]).mean() for j in range(1, K + 1)])
    J = np.arange(1, K + 1, dtype=np.float64)
    best, knee = np.inf, k
    for j in range(2, K - 1):
        rise = S[j - 1] / j * J[:j]                      # straight up from 0 to the bend
        rest = S[j - 1:]
        x = J[j - 1:] - j
        slope = float((x * (rest - S[j - 1])).sum() / max((x * x).sum(), 1e-9))
        err = float(((S[:j] - rise) ** 2).sum() + ((rest - S[j - 1] - slope * x) ** 2).sum())
        if slope < S[j - 1] / j and err < best:          # it must level off after the bend
            best, knee = err, j
    return max(lo, t - knee), min(hi - 1, t + knee)


# --- music ------------------------------------------------------------------------------

def music_info(samples: np.ndarray | None, rate: int = 11025) -> dict:
    """A steady beat in the sound means background music."""
    if samples is None or len(samples) < rate * 4:
        return {"music": False}
    hop, size = 256, 1024
    frames = len(samples) // hop - size // hop
    if frames < 50:
        return {"music": False}
    idx = np.arange(size)[None, :] + hop * np.arange(frames)[:, None]
    win = np.hanning(size).astype(np.float32)
    mag = np.abs(np.fft.rfft(samples[idx] * win, axis=1))
    logm = np.log1p(mag * 10)
    flux = np.maximum(0, np.diff(logm, axis=0)).sum(1)
    flux = flux - flux.mean()
    rms = np.sqrt((samples[idx] ** 2).mean(1))
    silent = float((rms < max(rms.max(), 1e-6) * 0.01).mean())
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    if ac[0] <= 0:
        return {"music": False, "silent": silent}
    ac = ac / ac[0]
    hop_s = hop / rate
    lags = np.arange(len(ac))
    ok = (lags * hop_s >= 60 / 190) & (lags * hop_s <= 60 / 70)
    if not ok.any():
        return {"music": False, "silent": silent}
    best = int(lags[ok][ac[ok].argmax()])
    strength = float(ac[best])
    # the beat repeats: twice the lag is strong too
    again = float(ac[min(len(ac) - 1, best * 2)]) if best * 2 < len(ac) else 0.0
    bpm = 60 / (best * hop_s)
    music = strength > 0.2 and again > 0.12 and silent < 0.2
    return {"music": bool(music), "bpm": round(bpm), "beat": round(strength, 2), "silent": round(silent, 2)}


# --- putting it together -------------------------------------------------------------------

def kill_scope(groups, edges: list[int]) -> str:
    """Which kills the effects were put on: every kill, the last of each moment,
    or only the very last one, judged by where they are in their moments."""
    parts = list(zip(edges, edges[1:]))
    def part(t):
        return next((i for i, (a, b) in enumerate(parts) if a <= t < b), len(parts) - 1)
    late = total = 0
    for g in groups:
        where = [part(t) for t in g]
        if len(set(where)) < len(where):
            return "all"                                  # two in one moment
        if where and all(w == len(parts) - 1 for w in where) and len(parts) > 2:
            continue
        for t, w in zip(g, where):
            a, b = parts[w]
            total += 1
            late += t >= a + 0.5 * (b - a)
    if total == 0:
        return "final"
    return "last" if late >= 0.8 * total else "all"


def _median(xs: list[float], default: float) -> float:
    return float(np.median(xs)) if xs else default


def analyze(path: str | Path, ffmpeg: str = "ffmpeg") -> dict:
    """The effects that reproduce this video's style, and what was found."""
    path = Path(path)
    info = video_info(path, ffmpeg)
    f = read_features(path, ffmpeg, info)
    found = find(f)
    fps = f.fps
    music = music_info(read_audio(path, ffmpeg)) if info["audio"] else {"music": False}

    fx: dict = {}
    report: list[dict] = []
    scale = {"flash": 1.2, "black": 1.15}
    def join_len(kind, a, b):
        return (b - a + 1) / fps * scale.get(kind, 1.0)
    if found.intro[0] != "none":
        fx["intro"] = found.intro[0]
        secs = found.intro[1]
        if found.intro[0] == "title":
            # the card lasts until the end of its transition into the first moment
            end = int(secs * fps)
            secs += next((join_len(k, a, b) for k, a, b in found.transitions if abs(a - end) <= fps * 0.25), 0.0)
            fx["intro_seconds"] = round(min(6.0, max(1.0, secs)), 1)
        report.append({"what": "intro", "kind": found.intro[0], "seconds": round(secs, 1)})

    # the joins
    joins = [(k, join_len(k, a, b)) for k, a, b in found.transitions] + [("cut", 0.0)] * len(found.cuts)
    counts: dict[str, int] = {}
    for k, _ in joins:
        counts[k] = counts.get(k, 0) + 1
    if counts:
        joins_n = sum(counts.values())
        styled = {k: c for k, c in counts.items() if k != "cut"}
        # effects editors mix a few plain cuts in; a transition used often enough is the style
        if styled and max(styled.values()) >= 0.35 * joins_n:
            kind = max(styled, key=lambda k: styled[k])
        else:
            kind = max(counts, key=lambda k: counts[k])
        fx["transition"] = kind
        if kind != "cut":
            secs = _median([d for k, d in joins if k == kind], 0.4)
            # a dissolve looks done a little before it ends, the others measure their full length
            fx["transition_seconds"] = round(min(1.5, max(0.1, secs)), 2)
        report.append({"what": "transition", "kind": kind, "count": counts[kind],
                       "seconds": fx.get("transition_seconds", 0), "mixed": len(counts) > 1,
                       "all": counts})

    # the moments between joins
    edges = sorted([0] + found.cuts + [a for _, a, _ in found.transitions] + [len(f.luma)])
    shots = [(b - a) / fps for a, b in zip(edges, edges[1:]) if (b - a) / fps > 1.0]
    if found.intro[0] == "title" and shots:
        shots = shots[1:]
    if found.outro[0] == "card" and shots:
        shots = shots[:-1]
    shot = _median(shots, 0)
    if shot:
        fx["pace"] = "tight" if shot < 5 else "long" if shot > 10 else "normal"
        report.append({"what": "pace", "kind": fx["pace"], "seconds": round(shot, 1), "count": len(shots)})

    # kill effects: how many of them per moment
    moments = max(1, len(shots))
    events = {"flash": found.flashes, "zoom": found.zooms, "shake": found.shakes,
              "slowmo": [a for a, _, _ in found.slowmo]}
    used = {k: v for k, v in events.items() if len(v) >= (1 if k == "slowmo" else 2)}
    for k, v in used.items():
        fx[f"kill_{k}"] = True
        report.append({"what": "kill", "kind": k, "count": len(v)})
    if found.slowmo:
        fx["slowmo_speed"] = round(_median([s for _, _, s in found.slowmo], 0.5), 2)
    if used:
        fx["kill_scope"] = kill_scope(used.values(), edges)

    # colour, on the moments only (not black or white frames, or the cards)
    keep = (f.luma > 20) & (f.luma < 235)
    if found.intro[0] == "title":
        keep[:int(found.intro[1] * fps)] = False
    if found.outro[0] in ("card", "freeze"):
        keep[len(keep) - int(found.outro[1] * fps):] = False
    for _, a, b in found.transitions:
        keep[a:b + 1] = False
    if keep.sum() > 10:
        stats = {k: round(float(getattr(f, k)[keep].mean()), 2) for k in ("sat", "luma", "spread", "u", "v")}
        bars = float(((f.top[keep] < 22) & (f.bottom[keep] < 22)).mean())
        fx["grade"] = "match"
        fx["grade_match"] = stats
        look = ("bw" if stats["sat"] < 4 else "warm" if stats["v"] - stats["u"] > 8 else
                "cool" if stats["u"] - stats["v"] > 8 else "vivid" if stats["sat"] > 40 else
                "muted" if stats["sat"] < 14 else "natural")
        report.append({"what": "colour", "kind": look, **stats})
        if bars > 0.85:
            fx["letterbox"] = True
            report.append({"what": "letterbox"})

    if found.outro[0] != "none":
        fx["outro"] = found.outro[0]
        secs = found.outro[1]
        if found.outro[0] == "card":
            start = len(f.luma) - int(secs * fps)
            secs += next((join_len(k, a, b) for k, a, b in found.transitions if abs(b - start) <= fps * 0.25), 0.0)
        if found.outro[0] in ("card", "freeze"):
            fx["outro_seconds"] = round(min(6.0, max(1.0, secs)), 1)
        report.append({"what": "outro", "kind": found.outro[0], "seconds": round(secs, 1)})

    if music.get("music"):
        fx["game_audio"] = "low"
        report.append({"what": "music", "bpm": music.get("bpm")})

    return {"effects": fx, "report": report, "video": {"seconds": round(len(f.luma) / fps, 1), "fps": round(fps, 2),
                                                        "width": info["width"], "height": info["height"]},
            "music": music}


def extract_music(path: str | Path, out: Path, ffmpeg: str = "ffmpeg") -> Path:
    """The reference video's sound as an audio file, to use as the reel's music."""
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(path), "-vn", "-c:a", "aac", "-b:a", "192k",
                        str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Could not take the sound out of the video.")
    return out
