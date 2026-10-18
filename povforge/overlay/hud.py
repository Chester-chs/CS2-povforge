"""A player-style HUD drawn from demo data.

CS2 shows demos with a spectator HUD. With the game set to draw only the
kill feed, we draw what the player saw instead: health, armor, money, ammo,
plus a crosshair and a sniper scope.

All sizes are designed for 1080p and multiplied by ``scale``.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from ..timeline import HudState
from . import font, shadow_text

TEXT = (240, 242, 245, 255)
ACCENT = (110, 180, 255, 255)
LOW = (255, 80, 70, 255)
DIM = (240, 242, 245, 150)


def _weapon_label(name: str) -> str:
    return name.replace("Weapon_", "").replace("weapon_", "").strip()


class HudRenderer:
    """Bottom strip: money (left), health + armor (left-centre), ammo + weapon (right)."""

    def __init__(self, width: int, scale: float = 1.0):
        self.k = scale
        self.size = (width, int(130 * scale))
        self._cache: dict[tuple, bytes] = {}
        w, h = self.size
        base = Image.new("RGBA", self.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        for y in range(h):  # soft gradient so white text stays readable on bright maps
            d.line((0, y, w, y), fill=(0, 0, 0, int(120 * (y / h) ** 1.6)))
        self._base = base

    def _icon_health(self, d, x, y, s, color):
        t = s * 0.34
        d.rectangle((x - t / 2, y - s / 2, x + t / 2, y + s / 2), fill=color)
        d.rectangle((x - s / 2, y - t / 2, x + s / 2, y + t / 2), fill=color)

    def _icon_armor(self, d, x, y, s, color, helmet):
        pts = [(x - s / 2, y - s / 2), (x + s / 2, y - s / 2), (x + s / 2, y + s * 0.05),
               (x, y + s / 2), (x - s / 2, y + s * 0.05)]
        d.polygon(pts, fill=color)
        if helmet:
            d.text((x, y - s * 0.05), "H", font=font(s * 0.62), fill=(20, 22, 28, 255), anchor="mm")

    def render(self, st: HudState) -> bytes:
        key = (st.alive, st.health, st.armor, st.helmet, st.money, st.weapon, st.ammo, st.reserve)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        im = self._base.copy()
        if st.alive:
            k, (w, h) = self.k, self.size
            d = ImageDraw.Draw(im)
            cy = h - 52 * k
            big, small = font(54 * k), font(26 * k)

            shadow_text(d, (44 * k, cy), f"${st.money}", font(46 * k), ACCENT, anchor="lm")

            hx = w * 0.29
            color = LOW if st.health <= 25 else TEXT
            self._icon_health(d, hx, cy, 30 * k, color)
            shadow_text(d, (hx + 28 * k, cy), str(st.health), big, color, anchor="lm")
            ax = hx + 200 * k
            self._icon_armor(d, ax, cy, 30 * k, TEXT if st.armor else DIM, st.helmet)
            shadow_text(d, (ax + 28 * k, cy), str(st.armor), big, TEXT if st.armor else DIM, anchor="lm")

            rx = w - 48 * k
            if st.ammo >= 0:
                reserve = f" / {st.reserve}" if st.reserve >= 0 else ""
                shadow_text(d, (rx, cy), reserve, small, DIM, anchor="rm")
                rw = d.textlength(reserve, font=small)
                shadow_text(d, (rx - rw, cy), str(st.ammo),
                            big, LOW if st.ammo == 0 else TEXT, anchor="rm")
            if st.weapon:
                shadow_text(d, (rx, cy - 52 * k), _weapon_label(st.weapon), font(24 * k), DIM, anchor="rm")
        data = im.tobytes()
        self._cache[key] = data
        return data

    def image(self, st: HudState) -> Image.Image:
        return Image.frombytes("RGBA", self.size, self.render(st))


def crosshair_png(path: Path, scale: float = 1.0, color=(80, 255, 200)) -> Path:
    """Small classic crosshair, drawn on top of the video centre."""
    k = scale
    size = int(40 * k) | 1
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, gap, ln, th = size // 2, 4 * k, 9 * k, max(2, round(2 * k))
    bars = [(c - th / 2, c - gap - ln, c + th / 2, c - gap), (c - th / 2, c + gap, c + th / 2, c + gap + ln),
            (c - gap - ln, c - th / 2, c - gap, c + th / 2), (c + gap, c - th / 2, c + gap + ln, c + th / 2)]
    for x0, y0, x1, y1 in bars:
        d.rectangle((x0 - 1, y0 - 1, x1, y1), fill=(0, 0, 0, 200))
    for x0, y0, x1, y1 in bars:
        d.rectangle((x0, y0, x1 - 1, y1 - 1), fill=color + (255,))
    im.save(path)
    return path


def scope_png(path: Path, width: int, height: int) -> Path:
    """Sniper scope: black around a circular lens with thin cross lines."""
    ss = 2
    W, H = width * ss, height * ss
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    r = H * 0.49
    cx, cy = W / 2, H / 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 0))
    # darker rim inside the lens
    for i in range(int(r * 0.06)):
        a = int(150 * (1 - i / (r * 0.06)) ** 2)
        d.ellipse((cx - r + i, cy - r + i, cx + r - i, cy + r - i), outline=(0, 0, 0, a), width=1)
    lw = max(2, round(H / 1080 * 2 * ss / 2))
    d.line((0, cy, W, cy), fill=(0, 0, 0, 255), width=lw)
    d.line((cx, 0, cx, H), fill=(0, 0, 0, 255), width=lw)
    im = im.resize((width, height), Image.LANCZOS)
    im.save(path)
    return path


def intervals(flags: list[bool], fps: float) -> list[tuple[float, float]]:
    """[True, True, False, True] -> [(0, 2/fps), (3/fps, 4/fps)] in seconds."""
    out, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((round(start / fps, 4), round(i / fps, 4)))
            start = None
    return out


def enable_expr(spans: list[tuple[float, float]]) -> str:
    return "+".join(f"between(t,{a},{b - 1e-4:.4f})" for a, b in spans) or "0"


_ = math  # keep import for future shapes
