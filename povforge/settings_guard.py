"""Keep the player's CS2 settings exactly as they were.

Recording needs some console settings (no demo bar, player HUD, ...). CS2
saves console settings to the player's own config files when it closes, so
without care they would carry over into normal games. Before CS2 starts we
copy every settings file away; after CS2 has closed we put them back byte for
byte and check the result.

If recording is interrupted, the copy is kept with a "pending" mark, and the
next povforge command restores it first (``povforge restore-settings`` does
it on demand).

Files covered:
- Steam/userdata/<account>/730/local/cfg/*  (convars, key binds, video settings)
- Steam/userdata/<account>/730/remote/cfg/* (Steam Cloud copy, if any)
- <CS2>/game/csgo/cfg/*.vcfg
- <CS2>/game/csgo/cfg/povforge_job.cfg (including recovery after a forced stop)
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path


def guard_dir() -> Path:
    base = os.environ.get("POVFORGE_STATE") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "povforge" / "cs2_settings_backup"


def _manifest() -> Path:
    return guard_dir() / "manifest.json"


def settings_folders(steam: Path | None, csgo: Path | None) -> list[tuple[Path, str]]:
    """(folder, file pattern) pairs holding CS2 settings."""
    out = []
    if steam is not None:
        for part in ("local", "remote"):  # remote = Steam Cloud copy
            out += [(d, "*") for d in sorted((steam / "userdata").glob(f"*/730/{part}/cfg")) if d.is_dir()]
    if csgo is not None and (csgo / "cfg").is_dir():
        out.append((csgo / "cfg", "*.vcfg"))
        out.append((csgo / "cfg", "povforge_job.cfg"))
    return out


def _files(folders: list[tuple[Path, str]]) -> list[Path]:
    return sorted(f for d, pat in folders for f in d.glob(pat) if f.is_file())


def pending() -> bool:
    return _manifest().exists()


def owned_by(pid: int) -> bool:
    """Only a matching recording child may force-close CS2 for this backup."""
    if type(pid) is not int or pid <= 0:
        return False
    try:
        data = json.loads(_manifest().read_text(encoding="utf-8"))
        return type(data.get("owner_pid")) is int and data["owner_pid"] == pid
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def backup(steam: Path | None, csgo: Path | None) -> int:
    """Copy all settings files away. Restores an unfinished earlier backup first,
    so a backup is never taken of already-changed settings."""
    if pending():
        restore()
        if pending():
            raise RuntimeError("Your CS2 settings from an earlier recording could not be restored yet "
                               "(is CS2 running?). Close CS2 and run: povforge restore-settings")
    folders = settings_folders(steam, csgo)
    root = guard_dir()
    if root.exists():
        shutil.rmtree(root)
    (root / "files").mkdir(parents=True)
    entries = []
    for i, f in enumerate(_files(folders)):
        b = root / "files" / f"{i:04d}_{f.name}"
        shutil.copy2(f, b)
        entries.append({"path": str(f), "backup": b.name})
    data = {"time": time.time(), "owner_pid": os.getpid(),
            "folders": [[str(d), pat] for d, pat in folders], "files": entries}
    _manifest().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return len(entries)


def restore() -> int:
    """Put every backed-up file back as it was and remove files CS2 created
    meanwhile. Returns how many files were changed back. The backup is only
    dropped once everything checks out."""
    if not pending():
        return 0
    data = json.loads(_manifest().read_text(encoding="utf-8"))
    root = guard_dir() / "files"
    known = {e["path"] for e in data["files"]}
    changed = 0
    for e in data["files"]:
        orig, b = Path(e["path"]), root / e["backup"]
        if not orig.exists() or orig.read_bytes() != b.read_bytes():
            orig.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(b, orig)  # new timestamp, so no sync treats the changed copy as newer
            changed += 1
    folders = [(Path(d), pat) for d, pat in data["folders"]]
    for f in _files(folders):
        if str(f) not in known and f.stat().st_mtime >= data["time"] - 1:
            f.unlink()  # created by CS2 during the recording
            changed += 1
    ok = all(Path(e["path"]).exists() and Path(e["path"]).read_bytes() == (root / e["backup"]).read_bytes()
             for e in data["files"])
    if ok:
        shutil.rmtree(guard_dir())
    return changed
