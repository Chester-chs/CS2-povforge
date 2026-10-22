import pytest
import shutil
import subprocess


def test_knife_effect_is_not_replaced_by_global_red_filter():
    from povforge.reference import propose
    r = propose({"effects": {"grade": "warm", "kill_flash": True}}, "auto", "红色光环环绕刀身")
    assert r["status"] == "unsupported" and not r["patch"]
    assert r["reason"] == "object_tracking"


def test_unknown_effect_is_not_silently_mapped_to_whole_style():
    from povforge.reference import propose
    assert propose({"effects": {"kill_flash": True}}, "auto", "未知的新效果")["status"] == "unsupported"


def test_specific_effect_proposal_does_not_apply_unrelated_settings():
    from povforge.reference import propose
    r = propose({"effects": {"kill_flash": True, "grade": "match", "intro": "fade"}}, "flash", "闪白")
    assert r["status"] == "detected"
    assert r["patch"] == {"kill_flash": True}
    r = propose({"effects": {"kill_flash": False}}, "flash", "闪白")
    assert r["status"] == "not_detected" and not r["patch"]


@pytest.mark.parametrize("start,end", [(4, 3), (-1, 3), (0, 100), (float("nan"), 2), (0, 1e20)])
def test_invalid_reference_ranges_are_rejected(start, end):
    from povforge.reference import selected_range
    with pytest.raises(ValueError):
        selected_range(start, end, 90)


def test_reference_range_and_http_range_validation():
    from povforge.reference import selected_range, byte_range
    assert selected_range(101, 105, 120) == (101, 105)
    assert byte_range("bytes=2-5", 10) == (2, 5)
    assert byte_range("bytes=-4", 10) == (6, 9)
    assert byte_range("bytes=6-", 10) == (6, 9)
    with pytest.raises(ValueError):
        byte_range("bytes=100-200", 10)


def test_preview_http_serves_seekable_ranges_from_registered_ids(tmp_path):
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    from types import SimpleNamespace
    from povforge.gui.server import ReferenceLibrary, make_handler
    library = ReferenceLibrary()
    preview = tmp_path / "preview.mp4"
    preview.write_bytes(b"0123456789")
    library.items["known"] = {"preview": str(preview)}
    app = SimpleNamespace(references=library, last_seen=0)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/style/video?id=known"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=2-5"})) as response:
            assert response.status == 206
            assert response.headers["Content-Range"] == "bytes 2-5/10"
            assert response.read() == b"2345"
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(url.replace("known", "../preview.mp4"))
        assert error.value.code >= 400
    finally:
        server.shutdown(); server.server_close(); worker.join(); library.close()


def test_failed_reference_prepare_cleans_its_folder(monkeypatch):
    from pathlib import Path
    from povforge.gui import server
    library = server.ReferenceLibrary()
    def fail(*args, **kwargs):
        folder = Path(args[-1]); folder.mkdir(); (folder / "partial.mp4").write_bytes(b"partial")
        raise RuntimeError("download failed")
    monkeypatch.setattr(server, "reference_isolated", fail)
    try:
        with pytest.raises(RuntimeError):
            library.prepare("https://example.com/video")
        assert list(Path(library.temp.name).iterdir()) == []
        assert library.items == {}
    finally:
        library.close()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_reference_preparation_and_selected_effect_are_bounded(tmp_path):
    from povforge import reference
    from povforge.media import probe
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=320x180:r=30:d=3", "-c:v", "libx264", "-preset", "ultrafast", str(source)], check=True)
    result = reference.prepare(str(source), tmp_path / "preview")
    assert 0 < probe(result["preview"]).duration < 3.2
    selection = reference.analyze_selection(str(source), 1, 2, "auto", "刀身红色环绕")
    assert selection["request"]["start"] == 1
    assert selection["proposal"]["reason"] == "object_tracking"
    selection = reference.analyze_selection(str(source), 1, 2, "flash", "white flash")
    assert selection["proposal"]["status"] == "not_detected"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_a_single_selected_flash_does_not_require_two_occurrences(tmp_path):
    from povforge import effects, reference
    from povforge.compose import ComposeSettings
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=480x270:r=30:d=4", "-c:v", "libx264", "-preset", "ultrafast", str(source)], check=True)
    rendered = effects.build([effects.Moment(source, 0, 4, [2])], {"kill_flash": True},
                              tmp_path / "flash.mp4", tmp_path / "work", (480, 270), 30,
                              ComposeSettings(preset="ultrafast"))
    result = reference.analyze_selection(str(rendered), 0.5, 3.5, "flash", "one white flash")
    assert result["proposal"]["status"] == "detected"
    assert result["proposal"]["patch"] == {"kill_flash": True}


def test_library_shutdown_stops_owned_child_and_prevents_late_registration(monkeypatch):
    import sys
    import time
    import threading
    from pathlib import Path
    from povforge.gui import server
    library = server.ReferenceLibrary()
    monkeypatch.setattr(server, "cli_command", lambda *args: [sys.executable, "-c", "import time; time.sleep(60)"])
    failures = []
    def prepare():
        try:
            library.prepare("fixture")
        except Exception as exc:
            failures.append(exc)
    thread = threading.Thread(target=prepare, daemon=True)
    thread.start()
    # Wait for registration, not for the child's work to finish.
    deadline = time.monotonic() + 3
    while not getattr(library, "processes", set()) and time.monotonic() < deadline:
        time.sleep(0.01)
    owned = list(getattr(library, "processes", set()))
    library.close()
    thread.join(timeout=3)
    assert owned and all(p.poll() is not None for p in owned)
    assert not thread.is_alive() and failures
    assert not Path(library.temp.name).exists()
    assert library.items == {}


def test_shutdown_waits_for_an_inflight_spawn_to_be_registered(monkeypatch):
    import sys
    import threading
    from povforge.gui import server
    library = server.ReferenceLibrary()
    spawned, release, closed = threading.Event(), threading.Event(), threading.Event()
    children = []
    original = subprocess.Popen
    def delayed_popen(cmd, **kwargs):
        proc = original(cmd, **kwargs)
        if cmd[0] == sys.executable:
            children.append(proc); spawned.set(); release.wait(3)
        return proc
    monkeypatch.setattr(server.subprocess, "Popen", delayed_popen)
    monkeypatch.setattr(server, "cli_command", lambda *args: [sys.executable, "-c", "import time; time.sleep(60)"])
    def prepare():
        try:
            library.prepare("fixture")
        except RuntimeError:
            pass
    worker = threading.Thread(target=prepare, daemon=True)
    worker.start()
    closer = threading.Thread(target=lambda: (library.close(), closed.set()), daemon=True)
    try:
        assert spawned.wait(3)
        closer.start()
        assert not closed.wait(0.1), "close must wait for an in-flight spawn"
    finally:
        release.set(); worker.join(3); closer.join(3)
        for proc in children:
            if proc.poll() is None:
                proc.kill(); proc.wait()
    assert closed.is_set() and all(proc.poll() is not None for proc in children)
