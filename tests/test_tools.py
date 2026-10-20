import zipfile

import pytest

from povforge import tools


def test_hlae_url_from_tag():
    assert tools._hlae_url_for("v2.192.8").endswith("/download/v2.192.8/hlae_2_192_8.zip")


def test_extract_strips_the_top_folder(tmp_path):
    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("ffmpeg-build/bin/ffmpeg.exe", "x")
    tools._extract(z, tmp_path / "ffmpeg", strip_top=True)
    assert (tmp_path / "ffmpeg" / "bin" / "ffmpeg.exe").read_text() == "x"


def test_extract_refuses_paths_outside_the_folder(tmp_path):
    z = tmp_path / "bad.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../evil.txt", "x")
    with pytest.raises(RuntimeError):
        tools._extract(z, tmp_path / "out", strip_top=False)
    assert not (tmp_path / "evil.txt").exists()


def test_downloaded_ffmpeg_is_used_when_none_on_path(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(tools, "_usual_ffmpeg_places", lambda: [])
    assert tools.find_ffmpeg() is None
    tools.ffmpeg_exe().parent.mkdir(parents=True)
    tools.ffmpeg_exe().write_text("")
    assert tools.find_ffmpeg() == str(tools.ffmpeg_exe())


def test_bundled_ffmpeg_comes_first_in_the_packaged_app(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    monkeypatch.setattr(tools.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    app = tmp_path / "PovForge"
    (app / "ffmpeg").mkdir(parents=True)
    (app / "ffmpeg" / "ffmpeg.exe").write_text("")
    monkeypatch.setattr(tools.sys, "executable", str(app / "PovForge.exe"))
    assert tools.find_ffmpeg() == "/usr/bin/ffmpeg"  # running from source: no bundle
    monkeypatch.setattr(tools.sys, "frozen", True, raising=False)
    assert tools.find_ffmpeg() == str((app / "ffmpeg" / "ffmpeg.exe").resolve())
    assert tools.find_ffmpeg("D:/my/ffmpeg.exe") == str((app / "ffmpeg" / "ffmpeg.exe").resolve())  # missing path ignored
