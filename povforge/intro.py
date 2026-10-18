"""Intro card: "<player> POV" title over the final scoreboard of the match."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .compose import AUDIO_RATE, ComposeSettings, encode_args
from .demo import TeamStats
from .overlay import font, shadow_text

WHITE = (245, 246, 248, 255)
DIM = (200, 205, 215, 200)
ACCENT = (255, 170, 60, 255)
WIN = (110, 220, 140, 255)
LOSE = (255, 110, 100, 255)


@dataclass
class IntroInfo:
    title: str
    subtitle: str
    player_steamid: str
    teams: list[TeamStats]


def pretty_map(name: str) -> str:
    base = name.split("/")[-1]
    for prefix in ("de_", "cs_", "ar_", "dz_"):
        if base.startswith(prefix):
            base = base[len(prefix):]
    return base.replace("_", " ").title()


def render_card(info: IntroInfo, size: tuple[int, int], background: Image.Image | None = None) -> Image.Image:
    W, H = size
    k = H / 1080
    if background is not None:
        bg = background.convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(18 * k))
        im = Image.blend(bg, Image.new("RGB", (W, H), (8, 10, 14)), 0.62).convert("RGBA")
    else:
        im = Image.new("RGBA", (W, H), (14, 16, 22, 255))
    d = ImageDraw.Draw(im)

    shadow_text(d, (W / 2, 150 * k), info.title, font(108 * k, cjk=True), WHITE, anchor="mm", offset=int(4 * k))
    shadow_text(d, (W / 2, 245 * k), info.subtitle, font(40 * k, cjk=True), DIM, anchor="mm")

    teams = sorted(info.teams, key=lambda t: not any(p.steamid == info.player_steamid for p in t.players))
    if len(teams) == 2:
        a, b = teams
        cy = 345 * k
        shadow_text(d, (W / 2, cy), ":", font(84 * k), WHITE, anchor="mm")
        shadow_text(d, (W / 2 - 40 * k, cy), str(a.score), font(84 * k),
                    WIN if a.score > b.score else LOSE, anchor="rm")
        shadow_text(d, (W / 2 + 40 * k, cy), str(b.score), font(84 * k),
                    WIN if b.score > a.score else LOSE, anchor="lm")

    cols = [("K", 300), ("D", 370), ("A", 440), ("ADR", 530), ("HS%", 630)]
    table_w, row_h, top = 700 * k, 62 * k, 450 * k
    for ti, team in enumerate(teams[:2]):
        x0 = W / 2 - 40 * k - table_w if ti == 0 else W / 2 + 40 * k
        panel = Image.new("RGBA", (int(table_w), int(row_h * 6.4)), (0, 0, 0, 0))
        ImageDraw.Draw(panel).rounded_rectangle((0, 0, panel.width - 1, panel.height - 1),
                                                radius=int(14 * k), fill=(10, 12, 18, 170))
        im.alpha_composite(panel, (int(x0), int(top)))
        d = ImageDraw.Draw(im)
        y = top + row_h * 0.6
        d.text((x0 + 24 * k, y), team.name, font=font(30 * k, cjk=True), fill=WHITE, anchor="lm")
        for label, cx in cols:
            d.text((x0 + cx * k, y), label, font=font(24 * k), fill=DIM, anchor="mm")
        for i, p in enumerate(team.players[:5]):
            y = top + row_h * (1.6 + i)
            me = p.steamid == info.player_steamid
            if me:  # translucent highlight, blended (drawing directly would overwrite the pixels)
                hl = Image.new("RGBA", (int(table_w - 16 * k), int(row_h * 0.9)), (0, 0, 0, 0))
                ImageDraw.Draw(hl).rounded_rectangle((0, 0, hl.width - 1, hl.height - 1),
                                                     radius=int(10 * k), fill=(255, 170, 60, 70))
                im.alpha_composite(hl, (int(x0 + 8 * k), int(y - row_h * 0.45)))
                d = ImageDraw.Draw(im)
            color = ACCENT if me else WHITE
            d.text((x0 + 24 * k, y), p.name[:16], font=font(30 * k, cjk=True), fill=color, anchor="lm")
            for (label, cx), v in zip(cols, (p.kills, p.deaths, p.assists, f"{p.adr:.0f}", f"{p.hs_pct:.0f}%")):
                d.text((x0 + cx * k, y), str(v), font=font(30 * k), fill=color, anchor="mm")
    return im


def render_screenshot_card(info: IntroInfo, size: tuple[int, int], shot: Image.Image) -> Image.Image:
    """A screenshot (e.g. the FACEIT match room) with the title written over it."""
    W, H = size
    k = H / 1080
    shot = shot.convert("RGB")
    # blurred, cropped copy fills the frame; the full screenshot sits on top
    sc = max(W / shot.width, H / shot.height)
    cover = shot.resize((int(shot.width * sc) + 1, int(shot.height * sc) + 1))
    cover = cover.crop(((cover.width - W) // 2, (cover.height - H) // 2,
                        (cover.width - W) // 2 + W, (cover.height - H) // 2 + H))
    im = Image.blend(cover.filter(ImageFilter.GaussianBlur(24 * k)), Image.new("RGB", (W, H)), 0.55)
    fit = min(W / shot.width, H / shot.height)
    front = shot.resize((int(shot.width * fit), int(shot.height * fit)), Image.LANCZOS)
    im.paste(front, ((W - front.width) // 2, (H - front.height) // 2))
    im = Image.blend(im, Image.new("RGB", (W, H)), 0.30).convert("RGBA")

    d = ImageDraw.Draw(im)
    lines = [(info.title, 120)] + [(p.strip(), 62) for p in info.subtitle.split("·") if p.strip()]
    total = sum(sz for _, sz in lines) * k * 1.15
    y = H / 2 - total / 2
    for text, sz in lines:
        f = font(sz * k, cjk=True)
        y += sz * k * 0.575
        d.text((W / 2, y), text, font=f, fill=WHITE, anchor="mm",
               stroke_width=max(2, int(sz * k * 0.07)), stroke_fill=(0, 0, 0, 255))
        y += sz * k * 0.575
    return im


def make_intro(info: IntroInfo, out: Path, size: tuple[int, int], fps: float, seconds: float,
               s: ComposeSettings, background_clip: Path | None = None,
               screenshot: Path | None = None) -> Path:
    bg = None
    if screenshot is not None:
        card = out.with_name("intro.png")
        render_screenshot_card(info, size, Image.open(screenshot)).convert("RGB").save(card)
        return _encode_card(card, out, fps, seconds, s)
    if background_clip is not None and background_clip.exists():
        frame = out.with_name("intro_bg.png")
        subprocess.run([s.ffmpeg, "-y", "-loglevel", "error", "-ss", "3", "-i", str(background_clip),
                        "-frames:v", "1", str(frame)], check=False)
        if frame.exists():
            bg = Image.open(frame)
    card = out.with_name("intro.png")
    render_card(info, size, bg).convert("RGB").save(card)
    return _encode_card(card, out, fps, seconds, s)


def _encode_card(card: Path, out: Path, fps: float, seconds: float, s: ComposeSettings) -> Path:
    fade = min(0.5, seconds / 4)
    subprocess.run([
        s.ffmpeg, "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", str(fps), "-i", str(card),
        "-f", "lavfi", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo",
        "-t", str(seconds),
        "-vf", f"fade=t=in:st=0:d={fade},fade=t=out:st={seconds - fade}:d={fade},format=yuv420p",
        "-map", "0:v", "-map", "1:a", "-r", str(fps), "-shortest",
        *encode_args(s), str(out),
    ], check=True)
    return out
