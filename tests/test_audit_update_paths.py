"""Update manifests cannot address files outside the staging/install roots."""

import hashlib
import json
import zipfile
import os
import subprocess

import pytest

from povforge import selfupdate


@pytest.mark.parametrize("rel", ["../outside.txt", "folder/../../outside.txt", "folder/../outside.txt"])
def test_update_rejects_parent_traversal_before_staging(tmp_path, rel):
    app, work = tmp_path / "app", tmp_path / "work"
    app.mkdir()
    payload = b"unexpected replacement"
    manifest = {"version": "2", "files": {rel: {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}}}
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("PovForge/manifest.json", json.dumps(manifest))
        z.writestr("PovForge/" + rel, payload)
    with pytest.raises(ValueError, match="[Uu]nsafe"):
        selfupdate.prepare(app, archive, "1", work)
    assert not (work / "outside.txt").exists()


@pytest.mark.parametrize("rel", ["../outside.txt", "C:/outside.txt", "C:outside.txt", "/outside.txt", "folder\\..\\outside.txt"])
def test_update_rejects_unsafe_removal_paths(rel):
    with pytest.raises(ValueError, match="[Uu]nsafe"):
        selfupdate.changes({"version": "2", "files": {}},
                           {"version": "1", "files": {rel: {"sha256": "old"}}})


def test_case_only_update_rename_never_removes_its_replacement():
    changed, removed = selfupdate.changes({"files": {"LIB.dll": {"sha256": "new"}}},
                                          {"files": {"lib.dll": {"sha256": "old"}}})
    assert changed == ["LIB.dll"]
    assert removed == []


@pytest.mark.skipif(os.name != "nt", reason="Windows case-insensitive filesystem")
def test_case_only_rename_keeps_the_installed_dll(tmp_path):
    app, work = tmp_path / "app", tmp_path / "work"
    app.mkdir()
    (app / "lib.dll").write_bytes(b"old")
    stage = work / "stage"
    stage.mkdir(parents=True)
    (stage / "LIB.dll").write_bytes(b"new")
    (stage / "manifest.json").write_text('{}', encoding="utf-8")
    changed, removed = selfupdate.changes({"files": {"LIB.dll": {"sha256": "new"}}},
                                          {"files": {"lib.dll": {"sha256": "old"}}})
    result = selfupdate.apply(app, work, {"version": "2", "changed": changed, "removed": removed},
                              tmp_path / "log.txt", relaunch=False, wait=True)
    assert result == 0
    assert (app / "LIB.dll").read_bytes() == b"new"


@pytest.mark.parametrize("files", [{"LIB.dll": {}, "lib.dll": {}}, {"lib./file.dll": {}}, {"lib /file.dll": {}}])
def test_update_rejects_ambiguous_windows_names(files):
    files = {name: {"sha256": "new"} for name in files}
    with pytest.raises(ValueError, match="Unsafe"):
        selfupdate.changes({"files": files}, {"files": {}})


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
def test_update_does_not_follow_junction_outside_installation(tmp_path):
    app, work, external = tmp_path / "app", tmp_path / "work", tmp_path / "external"
    app.mkdir()
    external.mkdir()
    keep = external / "keep.dll"
    keep.write_bytes(b"original external file")
    stage = work / "stage"
    (stage / "lib").mkdir(parents=True)
    (stage / "lib" / "keep.dll").write_bytes(b"replacement")
    (stage / "manifest.json").write_text('{}', encoding="utf-8")
    link = app / "lib"
    subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(link), str(external)], check=True, capture_output=True)
    try:
        with pytest.raises(ValueError, match="Unsafe"):
            selfupdate.apply(app, work, {"version": "2", "changed": ["lib/keep.dll"], "removed": []},
                             tmp_path / "log.txt", relaunch=False, wait=True)
        assert keep.read_bytes() == b"original external file"
    finally:
        link.rmdir()
