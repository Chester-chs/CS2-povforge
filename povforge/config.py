"""Settings, with optional overrides from a TOML file (see config.example.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path

from .compose import ComposeSettings
from .hlae import RecordSettings
from .planner import PlanOptions


@dataclass
class OverlaySettings:
    minimap: bool = True
    minimap_size: int = 360          # pixels at 1080p; scaled with output height
    show_enemies: bool = False
    keyboard: bool = True
    keyboard_scale: float = 1.0      # 1.0 = sized for 1080p
    sync_offset_frames: float = 0.0  # shift overlays if a recording shows drift
    place_label: bool = False        # location name under the minimap
    utility: bool = True             # grenade paths, smokes and fires (with timers) on the minimap
    player_bar: bool = True          # with the game HUD: replace the spectator panel at the bottom
                                     # with a player-style bar (health, team, ammo, kills this round)
    # Only used with [record] game_hud = "killfeed" (game HUD hidden):
    hud: bool = True                 # health / armor / money / ammo
    crosshair: bool = True
    scope: bool = True               # sniper scope while scoped in


@dataclass
class IntroSettings:
    enabled: bool = True
    seconds: float = 4.0
    title: str = "{player} POV"      # {player} {map} placeholders
    subtitle: str = "{map}  ·  {date}  ·  {width}x{height}"
    date: str = ""                   # empty = FACEIT match start time, else the demo file date
    date_format: str = "%Y年%m月%d日 %H:%M"
    timezone: str = ""               # e.g. "Asia/Shanghai"; empty = this PC's time zone
    image: str = "auto"              # "auto" = screenshot the FACEIT match room by itself
                                     # (FACEIT demos), otherwise the scoreboard card;
                                     # "" = scoreboard card; or an image file path
    show_browser: bool = False       # show the browser window while taking the screenshot


@dataclass
class Config:
    output_dir: Path = Path("povforge-output")
    plan: PlanOptions = field(default_factory=PlanOptions)
    record: RecordSettings = field(default_factory=RecordSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    compose: ComposeSettings = field(default_factory=ComposeSettings)
    intro: IntroSettings = field(default_factory=IntroSettings)


def _apply(obj, values: dict, where: str) -> None:
    known = {f.name for f in fields(obj)}
    for k, v in values.items():
        if k not in known:
            raise ValueError(f"Unknown setting '{k}' in [{where}]")
        cur = getattr(obj, k)
        if is_dataclass(cur):
            _apply(cur, v, f"{where}.{k}")
        else:
            setattr(obj, k, type(cur)(v) if cur is not None and not isinstance(cur, bool) else v)


def load_config(path: str | Path | None) -> Config:
    cfg = Config()
    if path is None:
        default = Path("povforge.toml")
        if not default.exists():
            return cfg
        path = default
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if "output" in data and "dir" in data["output"]:
        cfg.output_dir = Path(data["output"]["dir"])
    for section in ("plan", "record", "overlay", "compose", "intro"):
        if section in data:
            _apply(getattr(cfg, section), data[section], section)
    return cfg
