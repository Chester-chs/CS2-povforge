"""2D radar minimap synced to the demo.

Shows the followed player (with a view cone) and their teammates. Enemies are
hidden by default so the video stays a fair first-person view; enable them
with ``show_enemies``.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

import re

from ..maps import RADAR_SIZE, MapInfo
from ..timeline import PlayerState
from . import font, shadow_text

PLACE_COLOR = (120, 180, 255, 255)


def pretty_place(name: str) -> str:
    """'BombsiteB' -> 'Bombsite B', 'TSpawn' -> 'T Spawn', 'TopofMid' -> 'Top of Mid'."""
    s = re.sub(r"(?<=[a-z])of(?=[A-Z])", " of ", name)
    s = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[0-9])(?=[A-Za-z])", " ", s)
    return re.sub(r"\s+", " ", s).strip()

TEAM_COLORS = {
    2: (234, 179, 64),    # T
    3: (93, 160, 230),    # CT
}
SS = 2  # supersampling factor for smooth markers


class MinimapRenderer:
    def __init__(
        self,
        info: MapInfo,
        radar: Path,
        radar_lower: Path | None = None,
        size: int = 360,
        show_enemies: bool = False,
        opacity: float = 0.92,
        place_label: bool = True,
        show_utility: bool = True,
    ):
        self.show_utility = show_utility
        self.info = info
        self.size = size
        # Radar images have wide empty borders: crop to the map itself so it fills the box.
        # (faint, nearly transparent edge pixels are ignored, so the map fills the box)
        boxes = [Image.open(p).getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox()
                 for p in (radar, radar_lower) if p is not None]
        boxes = [b for b in boxes if b] or [(0, 0, RADAR_SIZE, RADAR_SIZE)]
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        side = max(x1 - x0, y1 - y0) * 1.06
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.crop = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
        self.label_h = int(size * 0.13) if place_label else 0
        self.layer_size = (size, size + self.label_h)
        self._label_cache: dict[str, Image.Image] = {}
        self.show_enemies = show_enemies
        self.k = size / side
        self._bases = {False: self._base(radar, opacity)}
        if radar_lower is not None:
            self._bases[True] = self._base(radar_lower, opacity)

    def _base(self, path: Path, opacity: float) -> Image.Image:
        s = self.size
        bg = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(bg).rounded_rectangle(
            (0, 0, s - 1, s - 1), radius=max(6, s // 24), fill=(12, 14, 18, 170)
        )
        img = Image.open(path).convert("RGBA")
        x0, y0, x1, y1 = self.crop
        # the square around the map can reach past the image edge; newer Pillow refuses
        # such a box, so give the image a transparent border first
        pad = int(max(0.0, -x0, -y0, x1 - img.width, y1 - img.height)) + 1
        if pad > 1:
            framed = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
            framed.paste(img, (pad, pad))
            img, box = framed, (x0 + pad, y0 + pad, x1 + pad, y1 + pad)
        else:
            box = self.crop
        radar = img.resize((s, s), Image.LANCZOS, box=box)
        if opacity < 1:
            a = radar.getchannel("A").point(lambda v: int(v * opacity))
            radar.putalpha(a)
        bg.alpha_composite(radar)
        return bg

    def _px(self, st: PlayerState) -> tuple[float, float]:
        return self._xy(st.x, st.y)

    def _xy(self, x: float, y: float) -> tuple[float, float]:
        rx, ry = self.info.to_radar(x, y)
        return (rx - self.crop[0]) * self.k * SS, (ry - self.crop[1]) * self.k * SS

    def _units(self, u: float) -> float:
        """World units -> supersampled minimap pixels."""
        return u / self.info.scale * self.k * SS

    def _draw_utility(self, d: ImageDraw.ImageDraw, util, teams: dict[str, int]) -> None:
        trails, areas, bursts = util
        for area, left in areas:
            x, y = self._xy(area.x, area.y)
            if area.kind == "smoke":
                R, fill, ring = self._units(144), (205, 210, 218, 150), (255, 255, 255, 230)
            else:
                R, fill, ring = self._units(150), (255, 110, 30, 120), (255, 190, 80, 240)
            d.ellipse((x - R, y - R, x + R, y + R), fill=fill)
            w = max(2, int(R * 0.14))
            d.arc((x - R, y - R, x + R, y + R), -90, -90 + 360 * max(0.0, left), fill=ring, width=w)
            secs = math.ceil(left * (area.end - area.start) / 64)
            d.text((x, y), str(secs), font=font(max(R * 0.8, 11 * SS)), fill=(20, 22, 28, 230) if area.kind == "smoke"
                   else (255, 255, 255, 240), anchor="mm")
        for tr, xs, ys, alpha in trails:
            col = TEAM_COLORS.get(teams.get(tr.steamid, 0), (230, 230, 230))
            pts = [self._xy(x, y) for x, y in zip(xs[::2], ys[::2])] + [self._xy(xs[-1], ys[-1])]
            if len(pts) >= 2:
                d.line(pts, fill=col + (int(220 * alpha),), width=max(2, int(SS * 1.5)), joint="curve")
                hx, hy = pts[-1]
                q = SS * 2.2
                d.ellipse((hx - q, hy - q, hx + q, hy + q), fill=(255, 255, 255, int(255 * alpha)))
        for x, y, kind, left in bursts:
            px, py = self._xy(x, y)
            R = self._units(180 if kind == "he" else 220) * (1.2 - left)
            col = (255, 255, 255) if kind == "flash" else (255, 90, 40)
            d.ellipse((px - R, py - R, px + R, py + R), outline=col + (int(255 * left),), width=max(2, SS * 2))

    def render_image(self, me: PlayerState | None, others: list[PlayerState], util=None) -> Image.Image:
        lower = bool(me and self.info.is_lower(me.z) and True in self._bases)
        frame = self._bases[lower].copy()
        layer = Image.new("RGBA", (self.size * SS, self.size * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        r = max(3.0, self.size * 0.017) * SS
        lim = self.size * SS
        if util is not None:
            self._draw_utility(d, util, {p.steamid: p.team for p in others})

        def visible(x, y):
            return -r <= x <= lim + r and -r <= y <= lim + r

        def level_alpha(st):
            same = self.info.is_lower(st.z) == lower
            return 255 if same else 110

        my_team = me.team if me else None
        for st in others:
            if me is not None and st.steamid == me.steamid:
                continue
            if my_team is not None and st.team != my_team and not self.show_enemies:
                continue
            x, y = self._px(st)
            if not visible(x, y):
                continue
            col = TEAM_COLORS.get(st.team, (200, 200, 200))
            a = level_alpha(st)
            if st.alive:
                d.ellipse((x - r, y - r, x + r, y + r), fill=col + (a,),
                          outline=(0, 0, 0, a), width=SS)
                yaw = math.radians(st.yaw)
                d.line((x, y, x + math.cos(yaw) * r * 1.9, y - math.sin(yaw) * r * 1.9),
                       fill=col + (a,), width=max(1, int(r * 0.45)))
            else:
                c = r * 0.75
                d.line((x - c, y - c, x + c, y + c), fill=(220, 60, 60, a), width=int(r * 0.5))
                d.line((x - c, y + c, x + c, y - c), fill=(220, 60, 60, a), width=int(r * 0.5))

        if me is not None:
            x, y = self._px(me)
            if visible(x, y):
                col = TEAM_COLORS.get(me.team, (255, 255, 255))
                if me.alive:
                    yaw = math.radians(me.yaw)
                    reach = self.size * 0.11 * SS
                    half = math.radians(45)
                    pts = [(x, y)] + [
                        (x + math.cos(yaw + t) * reach, y - math.sin(yaw + t) * reach)
                        for t in (half * i / 6 for i in range(-6, 7))
                    ]
                    d.polygon(pts, fill=(255, 255, 255, 60))
                    R = r * 1.4
                    d.ellipse((x - R, y - R, x + R, y + R), fill=col + (255,),
                              outline=(255, 255, 255, 255), width=int(SS * 1.5))
                else:
                    c = r
                    d.line((x - c, y - c, x + c, y + c), fill=(255, 255, 255, 255), width=int(r * 0.6))
                    d.line((x - c, y + c, x + c, y - c), fill=(255, 255, 255, 255), width=int(r * 0.6))

        frame.alpha_composite(layer.reduce(SS))  # box-filter downsample = anti-aliasing
        return frame

    def _label(self, place: str) -> Image.Image:
        im = self._label_cache.get(place)
        if im is None:
            im = Image.new("RGBA", (self.size, self.label_h), (0, 0, 0, 0))
            if place:
                shadow_text(ImageDraw.Draw(im), (self.size / 2, self.label_h / 2), pretty_place(place),
                            font(self.label_h * 0.62), PLACE_COLOR, anchor="mm")
            self._label_cache[place] = im
        return im

    def render(self, me: PlayerState | None, others: list[PlayerState], place: str = "", util=None) -> bytes:
        radar = self.render_image(me, others, util)
        if not self.label_h:
            return radar.tobytes()
        out = Image.new("RGBA", self.layer_size, (0, 0, 0, 0))
        out.paste(radar, (0, 0))
        out.paste(self._label(place), (0, self.size))
        return out.tobytes()
