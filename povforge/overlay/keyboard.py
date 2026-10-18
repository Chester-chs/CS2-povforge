"""Keyboard / mouse input display: SHIFT, CTRL, W A S D, SPACE and a mouse.

Pressed keys light up green. Sized for 1080p; ``scale`` multiplies it.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import font

# label, demo field, x, y, w, h (in key units)
_KEYS = [
    ("SHIFT", "WALK", 0.0, 0.0, 1.55, 1.0),
    ("CTRL", "DUCK", 0.0, 1.1, 1.55, 1.0),
    ("W", "FORWARD", 2.75, 0.0, 1.0, 1.0),
    ("A", "LEFT", 1.65, 1.1, 1.0, 1.0),
    ("S", "BACK", 2.75, 1.1, 1.0, 1.0),
    ("D", "RIGHT", 3.85, 1.1, 1.0, 1.0),
    ("SPACE", "JUMP", 1.65, 2.2, 3.2, 0.72),
]
_MOUSE = (5.15, 0.0, 1.35, 2.92)  # x, y, w, h


@dataclass
class KeyboardStyle:
    unit: int = 46
    radius: int = 8
    off_fill: tuple = (16, 18, 24, 150)
    off_border: tuple = (255, 255, 255, 70)
    off_text: tuple = (255, 255, 255, 180)
    on_fill: tuple = (60, 190, 110, 235)
    on_border: tuple = (150, 255, 190, 255)
    on_text: tuple = (255, 255, 255, 255)


class KeyboardRenderer:
    FIELDS = [k[1] for k in _KEYS] + ["FIRE", "RIGHTCLICK"]

    def __init__(self, scale: float = 1.0, style: KeyboardStyle | None = None):
        self.st = style or KeyboardStyle()
        self.u = max(14.0, self.st.unit * scale)
        right = max(x + w for _, _, x, _, w, _ in _KEYS + [("", "", *_MOUSE)])
        bottom = max(y + h for _, _, _, y, _, h in _KEYS + [("", "", *_MOUSE)])
        self.size = (int(right * self.u) + 2, int(bottom * self.u) + 2)
        self._cache: dict[tuple, bytes] = {}

    def _box(self, d, x, y, w, h, on, label=None):
        st, u = self.st, self.u
        r = max(3, int(st.radius * u / st.unit))
        box = (x * u, y * u, (x + w) * u - 1, (y + h) * u - 1)
        d.rounded_rectangle(box, radius=r, fill=st.on_fill if on else st.off_fill,
                            outline=st.on_border if on else st.off_border, width=2)
        if label:
            size = u * (0.42 if len(label) == 1 else 0.27)
            d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), label, font=font(size),
                   fill=st.on_text if on else st.off_text, anchor="mm")

    def render(self, keys: dict[str, bool]) -> bytes:
        state = tuple(bool(keys.get(f)) for f in self.FIELDS)
        hit = self._cache.get(state)
        if hit is not None:
            return hit
        on = dict(zip(self.FIELDS, state))
        im = Image.new("RGBA", self.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for label, field, x, y, w, h in _KEYS:
            self._box(d, x, y, w, h, on[field], label)

        # mouse: body, then left/right buttons on the top part
        st, u = self.st, self.u
        mx, my, mw, mh = (v * u for v in _MOUSE)
        r = mw / 2
        d.rounded_rectangle((mx, my, mx + mw - 1, my + mh - 1), radius=int(r),
                            fill=st.off_fill, outline=st.off_border, width=2)
        split = my + mh * 0.42
        for side, field in ((0, "FIRE"), (1, "RIGHTCLICK")):
            if on[field]:
                x0 = mx + 3 if side == 0 else mx + mw / 2 + 1
                x1 = mx + mw / 2 - 1 if side == 0 else mx + mw - 4
                btn = Image.new("L", self.size, 0)
                ImageDraw.Draw(btn).rounded_rectangle((mx + 3, my + 3, mx + mw - 4, my + mh - 4),
                                                      radius=int(r) - 3, fill=255)
                ImageDraw.Draw(btn).rectangle((0, split, self.size[0], self.size[1]), fill=0)
                ImageDraw.Draw(btn).rectangle(
                    (0, 0, x0 - 1, self.size[1]) if side == 1 else (x1 + 1, 0, self.size[0], self.size[1]),
                    fill=0)
                color = Image.new("RGBA", self.size, st.on_fill)
                im.paste(color, (0, 0), btn)
        d = ImageDraw.Draw(im)
        d.line((mx + 4, split, mx + mw - 5, split), fill=st.off_border, width=2)
        d.line((mx + mw / 2, my + 4, mx + mw / 2, split), fill=st.off_border, width=2)

        data = im.tobytes()
        self._cache[state] = data
        return data

    def image(self, keys: dict[str, bool]) -> Image.Image:
        return Image.frombytes("RGBA", self.size, self.render(keys))
