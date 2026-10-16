"""2D radar minimap synced to the demo.

Shows the followed player (with a view cone) and their teammates. Enemies are
hidden by default so the video stays a fair first-person view; enable them
with ``show_enemies``.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from ..maps import RADAR_SIZE, MapInfo
from ..timeline import PlayerState

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
    ):
        self.info = info
        self.size = size
        self.show_enemies = show_enemies
        self._bases = {False: self._base(radar, opacity)}
        if radar_lower is not None:
            self._bases[True] = self._base(radar_lower, opacity)
        self.k = size / RADAR_SIZE

    def _base(self, path: Path, opacity: float) -> Image.Image:
        s = self.size
        bg = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(bg).rounded_rectangle(
            (0, 0, s - 1, s - 1), radius=max(6, s // 24), fill=(12, 14, 18, 170)
        )
        radar = Image.open(path).convert("RGBA").resize((s, s), Image.LANCZOS)
        if opacity < 1:
            a = radar.getchannel("A").point(lambda v: int(v * opacity))
            radar.putalpha(a)
        bg.alpha_composite(radar)
        return bg

    def _px(self, st: PlayerState) -> tuple[float, float]:
        rx, ry = self.info.to_radar(st.x, st.y)
        return rx * self.k * SS, ry * self.k * SS

    def render_image(self, me: PlayerState | None, others: list[PlayerState]) -> Image.Image:
        lower = bool(me and self.info.is_lower(me.z) and True in self._bases)
        frame = self._bases[lower].copy()
        layer = Image.new("RGBA", (self.size * SS, self.size * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        r = max(3.0, self.size * 0.017) * SS
        lim = self.size * SS

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

        frame.alpha_composite(layer.resize((self.size, self.size), Image.LANCZOS))
        return frame

    def render(self, me: PlayerState | None, others: list[PlayerState]) -> bytes:
        return self.render_image(me, others).tobytes()
