"""Keyboard / mouse input display (W A S D, Space, Ctrl, Shift, M1, M2, R, E)."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import font

# label, demo field, column, row, width in key units
_LAYOUT = [
    ("W", "FORWARD", 1.0, 0, 1.0),
    ("A", "LEFT", 0.0, 1, 1.0),
    ("S", "BACK", 1.0, 1, 1.0),
    ("D", "RIGHT", 2.0, 1, 1.0),
    ("M1", "FIRE", 3.4, 0, 1.0),
    ("M2", "RIGHTCLICK", 4.4, 0, 1.0),
    ("R", "RELOAD", 3.4, 1, 1.0),
    ("E", "USE", 4.4, 1, 1.0),
    ("SHIFT", "WALK", 0.0, 2, 1.5),
    ("CTRL", "DUCK", 1.5, 2, 1.5),
    ("SPACE", "JUMP", 3.0, 2, 2.4),
]


@dataclass
class KeyboardStyle:
    unit: int = 44
    gap: int = 6
    radius: int = 8
    off_fill: tuple = (18, 20, 26, 150)
    off_border: tuple = (255, 255, 255, 70)
    off_text: tuple = (255, 255, 255, 170)
    on_fill: tuple = (255, 255, 255, 240)
    on_border: tuple = (255, 255, 255, 255)
    on_text: tuple = (18, 20, 26, 255)


class KeyboardRenderer:
    def __init__(self, scale: float = 1.0, style: KeyboardStyle | None = None):
        st = style or KeyboardStyle()
        self.u = max(16, int(st.unit * scale))
        self.g = max(2, int(st.gap * scale))
        self.st = st
        cols = max(c + w for _, _, c, _, w in _LAYOUT)
        rows = max(r for _, _, _, r, _ in _LAYOUT) + 1
        self.size = (int(cols * (self.u + self.g)), int(rows * (self.u + self.g)))
        self._tiles = {}
        for label, field, col, row, w in _LAYOUT:
            box_w = int(w * self.u + (w - 1) * self.g)
            self._tiles[field] = (
                (int(col * (self.u + self.g)), int(row * (self.u + self.g))),
                self._tile(label, box_w, False),
                self._tile(label, box_w, True),
            )
        self._cache: dict[tuple, bytes] = {}

    def _tile(self, label: str, w: int, on: bool) -> Image.Image:
        st = self.st
        im = Image.new("RGBA", (w, self.u), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        r = max(3, int(st.radius * self.u / st.unit))
        d.rounded_rectangle(
            (0, 0, w - 1, self.u - 1), radius=r,
            fill=st.on_fill if on else st.off_fill,
            outline=st.on_border if on else st.off_border, width=2,
        )
        f = font(int(self.u * (0.42 if len(label) <= 2 else 0.30)))
        d.text((w / 2, self.u / 2), label, font=f, anchor="mm",
               fill=st.on_text if on else st.off_text)
        return im

    def render(self, keys: dict[str, bool]) -> bytes:
        """RGBA bytes for one frame; identical key states are cached."""
        state = tuple(bool(keys.get(f)) for f in self._tiles)
        hit = self._cache.get(state)
        if hit is not None:
            return hit
        im = Image.new("RGBA", self.size, (0, 0, 0, 0))
        for (field, (xy, off, on)), pressed in zip(self._tiles.items(), state):
            im.alpha_composite(on if pressed else off, xy)
        data = im.tobytes()
        self._cache[state] = data
        return data

    def image(self, keys: dict[str, bool]) -> Image.Image:
        return Image.frombytes("RGBA", self.size, self.render(keys))
