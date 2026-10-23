"""Map scenery is cached independently of recording radar assets."""
import io

import pytest

from povforge import maps


def test_scene_download_is_cached_across_calls(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_CACHE', str(tmp_path))
    calls = []
    png = b'\x89PNG\r\n\x1a\n' + b'scene'

    def download(req, timeout):
        calls.append(req.full_url)
        return io.BytesIO(png)

    monkeypatch.setattr(maps.urllib.request, 'urlopen', download)
    first = maps.get_map_thumbnail('de_dust2')
    assert first.read_bytes() == png
    assert maps.get_map_thumbnail('de_dust2') == first
    assert calls == [maps.SOURCE_BASE + '/images/thumbs/de_dust2_png.png']
    assert not list(tmp_path.rglob('*.part'))


@pytest.mark.parametrize('name', ['', '../secret', 'de_dust2/../../x', 'https://evil.test', 'a'*81])
def test_invalid_map_never_accesses_network(tmp_path, monkeypatch, name):
    monkeypatch.setenv('POVFORGE_CACHE', str(tmp_path))
    monkeypatch.setattr(maps.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network access'))
    with pytest.raises(ValueError):
        maps.get_map_thumbnail(name)


@pytest.mark.parametrize('data', [b'not an image', b'\x89PNG\r\n\x1a\n' + b'x' * (8*1024*1024)], ids=['invalid', 'oversized'])
def test_bad_or_oversized_response_not_cached(tmp_path, monkeypatch, data):
    monkeypatch.setenv('POVFORGE_CACHE', str(tmp_path))
    monkeypatch.setattr(maps.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(data))
    with pytest.raises(ValueError):
        maps.get_map_thumbnail('de_dust2')
    assert not list(tmp_path.rglob('*.png'))
