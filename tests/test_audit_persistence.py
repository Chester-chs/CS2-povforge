"""Failed writes must not destroy the last valid user settings."""

import json
from pathlib import Path

import pytest

from povforge.gui import server


def test_preferences_survive_a_partial_write(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    server.save_prefs({"output": "keep this folder", "reel_fx": {"camera": {"victim": True}}})
    target = server.app_dir() / "app.json"
    before = target.read_bytes()
    original = Path.write_text

    def interrupted(path, text, **kwargs):
        if path.parent == target.parent:
            original(path, text[:8], **kwargs)
            raise OSError("disk write interrupted")
        return original(path, text, **kwargs)

    monkeypatch.setattr(Path, "write_text", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        server.save_prefs({"output": "new folder"})
    assert target.read_bytes() == before
    assert json.loads(target.read_text(encoding="utf-8"))["output"] == "keep this folder"
