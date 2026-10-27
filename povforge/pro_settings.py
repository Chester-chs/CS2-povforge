"""A pro player's in-game look, from their public prosettings.net page.

Only settings that change what the recording looks like are used: resolution,
aspect ratio and scaling, viewmodel, bob, crosshair and HUD. They are turned
into plain console commands from a fixed allow-list, applied only inside the
recording session (the user's own CS2 settings are backed up and restored).

Settings that live only on the player's PC (graphics quality, brightness,
monitor colour) are reported but not applied.
"""
from __future__ import annotations

import html
import re
import time
import urllib.request

BASE = "https://prosettings.net/players/"
TIMEOUT = 10
MAX_BYTES = 4 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PovForge"
URL = re.compile(r"https://prosettings\.net/players/[a-z0-9_-]{1,64}/?")

# cvar -> value kind. Only these become commands.
NUMERIC = {
    "viewmodel_fov", "viewmodel_offset_x", "viewmodel_offset_y", "viewmodel_offset_z",
    "cl_bob_lower_amt", "cl_bobamt_lat", "cl_bobamt_vert", "cl_bobcycle",
    "hud_scaling",
    "cl_crosshair_length", "cl_crosshair_thickness", "cl_crosshair_gap",
    "cl_crosshairoutline_r", "cl_crosshairoutline_g", "cl_crosshairoutline_b", "cl_crosshairoutline_a",
    "cl_crosshaircolor_r", "cl_crosshaircolor_g", "cl_crosshaircolor_b", "cl_crosshaircolor_a",
    "cl_crosshair_dynamic_splitdist", "cl_crosshair_dynamic_splitalpha_innermod",
    "cl_crosshair_dynamic_splitalpha_outermod", "cl_crosshair_dynamic_maxdist_splitratio",
    "cl_crosshair_outlinethickness", "cl_crosshairgap_useweaponvalue", "cl_crosshaircolor",
    "cl_crosshairalpha", "cl_crosshairusealpha",
}
BOOLEAN = {"cl_crosshair_recoil", "cl_crosshairdot", "cl_crosshair_drawoutline", "cl_crosshair_t",
           "cl_crosshairusealpha", "cl_crosshairgap_useweaponvalue"}
CROSSHAIR_STYLES = {"default": 0, "default static": 1, "classic": 2, "classic dynamic": 3,
                    "classic static": 4, "static cross": 4, "static": 4}
HUD_COLORS = {"default": 0, "white": 1, "light blue": 2, "blue": 3, "purple": 4, "red": 5,
              "orange": 6, "yellow": 7, "green": 8, "aqua": 9, "pink": 10, "team color": 11}
NOT_APPLIED = ("brightness", "display_mode", "max_fps", "model_texture_detail", "shader_detail",
               "particle_detail", "global_shadow_quality", "multisampling_anti-aliasing_mode",
               "texture_filtering_mode", "ambient_occlusion", "high_dynamic_range", "boost_player_contrast")
CODE = re.compile(r"CSGO(-[A-Za-z0-9]{5}){5}")


def slug(name: str) -> str:
    """prosettings.net page name for an in-game name: 'm0NESY' -> 'm0nesy'."""
    s = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return s[:64]


def page_url(name: str) -> str:
    return BASE + slug(name) + "/" if slug(name) else ""


def valid_url(url: str) -> bool:
    return bool(URL.fullmatch(str(url or "").strip()))


def fetch(url: str) -> str:
    if not valid_url(url):
        raise ValueError("Not a prosettings.net player page.")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 - fixed https host
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("The page is unexpectedly large.")
    return data.decode("utf-8", errors="replace")


def _number(text: str) -> float | None:
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*%?\s*", text)
    return float(m.group(1)) if m else None


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.4f}".rstrip("0").rstrip(".")


def parse(page: str) -> dict:
    """The structured settings tables of a player page."""
    fields: dict[str, str] = {}
    for key, value in re.findall(r'data-field="([a-z0-9_\-]+)"><th>[^<]*</th><td>(.*?)</td>', page, re.S):
        text = html.unescape(re.sub(r"<[^>]+>", "", value)).strip()
        fields.setdefault(key, text)        # the first table wins (game video before the monitor)
    title = re.search(r"<title>(.*?) CS2 Settings", page, re.S)
    name = html.unescape(title.group(1)).strip() if title else ""
    # Only the player's own section; visitors' comments also contain codes.
    own = re.search(r'id="cs2_crosshair".*?</section>', page, re.S)
    code = CODE.search(own.group(0)) if own else None
    return {"name": name[:64], "fields": fields, "crosshair_code": code.group(0) if code else ""}


def look(parsed: dict, url: str = "") -> dict:
    """Recording look for a parsed page: window size/fit and console commands."""
    f = parsed.get("fields", {})
    out: dict = {"source": url, "name": parsed.get("name", ""), "fetched": time.time(), "commands": [],
                 "resolution": "", "aspect": f.get("aspect_ratio", ""), "scaling": f.get("scaling_mode", ""),
                 "fit": "native", "game": None, "summary": {}, "not_applied": {}}
    m = re.fullmatch(r"\s*(\d{3,4})\s*[x×]\s*(\d{3,4})\s*", f.get("resolution", ""))
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        out["resolution"] = f"{w}x{h}"
        if 1.0 <= w / h < 1.7:            # 4:3, 5:4, 16:10: not the 16:9 of the video
            scaling = out["scaling"].lower()
            out["fit"] = "stretch" if "stretch" in scaling else "pad"
            # Same picture as the player's screen, recorded at 1080 lines for sharpness.
            out["game"] = [max(2, round(1080 * w / h / 2) * 2), 1080]
    commands = []
    for key, raw in f.items():
        value = raw.strip().lower()
        if key == "cl_crosshairstyle":
            n = CROSSHAIR_STYLES.get(value, _number(value))
        elif key == "cl_hud_color":
            n = HUD_COLORS.get(value, _number(value))
        elif key in BOOLEAN and value in ("yes", "no", "true", "false", "on", "off"):
            n = 1 if value in ("yes", "true", "on") else 0
        elif key in NUMERIC or key in BOOLEAN:
            n = _number(value)
        else:
            if key in NOT_APPLIED:
                out["not_applied"][key] = raw[:40]
            continue
        if n is None or not -1000 <= n <= 1000:
            continue
        commands.append(f"{key} {_fmt(n)}")
        if key.startswith(("viewmodel", "hud_", "cl_hud")):
            out["summary"][key] = _fmt(n)
    out["commands"] = commands
    if parsed.get("crosshair_code"):
        out["crosshair_code"] = parsed["crosshair_code"]
    return out


def lookup(name: str = "", url: str = "") -> dict:
    """Fetch and convert; raises on network or format problems."""
    url = url.strip() if url else page_url(name)
    if not url:
        raise ValueError("No player name.")
    data = look(parse(fetch(url)), url)
    if not data["resolution"] and not data["commands"]:
        raise ValueError("No settings found on that page.")
    return data
