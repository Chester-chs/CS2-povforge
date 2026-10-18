"""Player-style bottom bar, drawn over the game's spectator panel.

When CS2 plays a demo it shows a spectator panel at the bottom (name, avatar,
weapon skin). A player sees a slimmer bar instead: health on the left, the
team badge in the middle, ammo on the right. This layer covers the spectator
panel and draws that bar from demo data, plus a skull for every kill the
player has made this round. The rest of the game HUD (money, scoreboard,
kill feed, weapon list) stays as the game draws it.

Drawn for 1080p and multiplied by ``scale``. The layer is placed at the
bottom centre of the frame.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from ..timeline import HudState
from . import font

TEAM_COLORS = {
    2: (232, 186, 82),    # T
    3: (96, 150, 255),    # CT
}
NEUTRAL = (220, 224, 232)
LOW = (255, 72, 60)
SS = 2  # supersampling


def _rgba(c, a=255):
    return (c[0], c[1], c[2], a)


class PlayerBarRenderer:
    # Layout in 1080p pixels, relative to the layer (820 x 104, bottom centre:
    # x 550..1370 on a 1920 frame). The spectator panel sits at about x 600..1320,
    # y 988..1075, so the opaque middle of the cover spans that.
    W, H = 820, 104

    def __init__(self, scale: float = 1.0):
        self.k = scale
        self.size = (int(self.W * scale), int(self.H * scale))
        self._cache: dict[tuple, bytes] = {}
        self._cover = self._make_cover()

    def _make_cover(self) -> Image.Image:
        """Dark band, solid where the spectator panel is, soft at the edges."""
        w, h = self.size
        k = self.k
        feather_x, feather_top = 46 * k, 14 * k
        a = Image.new("L", (w, h), 0)
        px = a.load()
        for x in range(w):
            fx = min(1.0, x / feather_x, (w - 1 - x) / feather_x)
            for y in range(h):
                fy = min(1.0, y / feather_top)
                px[x, y] = int(248 * max(0.0, fx) * fy)
        cover = Image.new("RGBA", (w, h), (8, 10, 14, 255))
        cover.putalpha(a)
        return cover

    # --- small icons (drawn supersampled) ---------------------------------------

    @staticmethod
    def _shield(d, x, y, s, col, width):
        pts = [(x - s * 0.5, y - s * 0.55), (x + s * 0.5, y - s * 0.55), (x + s * 0.5, y + s * 0.05),
               (x, y + s * 0.6), (x - s * 0.5, y + s * 0.05), (x - s * 0.5, y - s * 0.55)]
        d.line(pts, fill=col, width=width, joint="curve")

    @staticmethod
    def _skull(d, x, y, s, col, hs: bool):
        d.ellipse((x - s * 0.5, y - s * 0.55, x + s * 0.5, y + s * 0.35), fill=col)
        d.rounded_rectangle((x - s * 0.3, y + s * 0.15, x + s * 0.3, y + s * 0.55), radius=s * 0.08, fill=col)
        eye = (12, 14, 18, 255)
        for ex in (-0.2, 0.2):
            d.ellipse((x + s * (ex - 0.13), y - s * 0.2, x + s * (ex + 0.13), y + s * 0.06), fill=eye)
        if hs:  # headshot: small red mark on the forehead
            d.ellipse((x - s * 0.09, y - s * 0.46, x + s * 0.09, y - s * 0.28), fill=_rgba(LOW))

    @staticmethod
    def _bullet(d, x, y, s, col):
        d.rounded_rectangle((x - s * 0.16, y - s * 0.2, x + s * 0.16, y + s * 0.5), radius=s * 0.04, fill=col)
        d.pieslice((x - s * 0.16, y - s * 0.52, x + s * 0.16, y - s * 0.08), 180, 360, fill=col)

    # --- the bar ---------------------------------------------------------------

    def render(self, st: HudState, team: int = 0, kills: tuple[bool, ...] = ()) -> bytes:
        """``kills``: one entry per kill this round, True for a headshot."""
        key = (st.alive, st.health, st.armor, st.helmet, st.ammo, st.reserve, team, kills)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        im = self._cover.copy()
        if st.alive:
            im.alpha_composite(self._content(st, team, kills))
        data = im.tobytes()
        self._cache[key] = data
        return data

    def image(self, st: HudState, team: int = 0, kills: tuple[bool, ...] = ()) -> Image.Image:
        return Image.frombytes("RGBA", self.size, self.render(st, team, kills))

    def _content(self, st: HudState, team: int, kills) -> Image.Image:
        k = self.k * SS
        w, h = self.size[0] * SS, self.size[1] * SS
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        col = TEAM_COLORS.get(team, NEUTRAL)
        main, line = _rgba(col), _rgba(col, 150)
        cy = 50 * k                     # baseline row of the bar
        big, small, tiny = font(46 * k), font(30 * k), font(15 * k)
        lw = max(2, int(2 * k))

        # left: armor shield (value inside), health number underlined
        sx = 86 * k
        self._shield(d, sx, cy, 34 * k, _rgba(col, 220 if st.armor else 110), lw)
        d.text((sx, cy - 3 * k), str(st.armor), font=tiny, fill=main if st.armor else line, anchor="mm")
        hcol = _rgba(LOW) if st.health <= 20 else main
        hx = 122 * k
        d.text((hx, cy), str(st.health), font=big, fill=hcol, anchor="lm")
        hw = d.textlength(str(st.health), font=big)
        d.rectangle((hx, cy + 27 * k, hx + hw, cy + 27 * k + lw), fill=hcol)

        # centre: team badge with lines running to both sides
        bx, br = w / 2, 25 * k
        d.ellipse((bx - br, cy - br, bx + br, cy + br), outline=main, width=lw)
        d.text((bx, cy), "CT" if team == 3 else ("T" if team == 2 else ""), font=font(20 * k),
               fill=main, anchor="mm")
        left_end = hx + hw + 22 * k
        d.line((left_end, cy, bx - br - 14 * k, cy), fill=line, width=lw)

        # right: magazine (underlined) with a bullet icon (reserve too, if known)
        right_start = bx + br + 14 * k
        ax = w - 170 * k
        if st.ammo >= 0:
            acol = _rgba(LOW) if st.ammo == 0 else main
            d.text((ax, cy), str(st.ammo), font=big, fill=acol, anchor="rm")
            aw = d.textlength(str(st.ammo), font=big)
            d.rectangle((ax - aw, cy + 27 * k, ax, cy + 27 * k + lw), fill=acol)
            bx2 = ax + 20 * k
            if st.reserve >= 0:
                d.text((bx2, cy + 6 * k), str(st.reserve), font=small, fill=main, anchor="lm")
                bx2 += d.textlength(str(st.reserve), font=small) + 14 * k
            self._bullet(d, bx2, cy + 4 * k, 26 * k, main)
            line_end = ax - aw - 22 * k
        else:
            line_end = ax

        # kills this round: skulls just right of the badge, the line continues after them
        s = 24 * k
        x = right_start + s * 0.6
        for hs in list(kills)[:8]:
            self._skull(d, x, cy, s, _rgba((245, 246, 248)), hs)
            x += s * 1.2
        if kills:
            right_start = x - s * 0.1
        if line_end > right_start:
            d.line((right_start, cy, line_end, cy), fill=line, width=lw)

        return layer.reduce(SS)
