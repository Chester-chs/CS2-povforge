import gzip
from pathlib import Path

from povforge.demo import prepare_demo


def test_replaced_compressed_demo_is_unpacked_again(tmp_path):
    archive = tmp_path / "match.dem.gz"
    archive.write_bytes(gzip.compress(b"first demo"))
    out = prepare_demo(archive)
    archive.write_bytes(gzip.compress(b"replacement match with different data"))
    assert prepare_demo(archive).read_bytes() == b"replacement match with different data"
    before = out.stat().st_mtime_ns
    assert prepare_demo(archive) == out
    assert out.stat().st_mtime_ns == before


def test_same_named_archives_do_not_share_unpacked_fallback(tmp_path, monkeypatch):
    archives = []
    for name in ("one", "two"):
        directory = tmp_path / name
        directory.mkdir()
        archive = directory / "match.dem.gz"
        archive.write_bytes(gzip.compress(name.encode()))
        archives.append(archive)
    mkdir = Path.mkdir

    def read_only(directory, *args, **kwargs):
        if directory in [a.parent for a in archives]:
            raise PermissionError("read-only source folder")
        return mkdir(directory, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", read_only)
    work = tmp_path / "work"
    assert prepare_demo(archives[0], work).read_bytes() == b"one"
    assert prepare_demo(archives[1], work).read_bytes() == b"two"
