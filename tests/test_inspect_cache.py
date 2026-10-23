import json
import threading
import hashlib
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from povforge.gui import server


def test_concurrent_reads_parse_once_and_restart_reuses_result(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    monkeypatch.setattr(server, '_inspect_cache', {})
    src = tmp_path / 'match.dem'
    src.write_bytes(b'demo')
    entered, release, duplicate = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def parse(*args, **kwargs):
        calls.append(args)
        if len(calls) > 1:
            duplicate.set()
        entered.set()
        assert release.wait(3)
        return SimpleNamespace(returncode=0, stdout=json.dumps({'map': 'de_dust2', 'rounds': 23}), stderr='')

    monkeypatch.setattr(server.subprocess, 'run', parse)
    with ThreadPoolExecutor(2) as pool:
        one = pool.submit(server.inspect_isolated, str(src), tmp_path)
        assert entered.wait(3)
        two = pool.submit(server.inspect_isolated, str(src), tmp_path)
        # A second reader must wait for the first result, not start another parser.
        try:
            assert not duplicate.wait(0.2), 'a concurrent reader started a second parser'
        finally:
            release.set()
        assert one.result() == two.result()
    assert len(calls) == 1
    server._inspect_cache.clear()
    assert server.inspect_isolated(str(src), tmp_path)['rounds'] == 23
    assert len(calls) == 1
    assert server.find_demos([str(tmp_path)])[0]['cached'] is True
    src.write_bytes(b'changed demo')
    assert server.find_demos([str(tmp_path)])[0]['cached'] is False
    server.inspect_isolated(str(src), tmp_path)
    assert len(calls) == 2


def test_corrupt_cache_recovers_without_leaving_partial_file(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    monkeypatch.setattr(server, '_inspect_cache', {})
    src = tmp_path / 'match.dem'
    src.write_bytes(b'demo')
    result = {'map': 'de_nuke', 'rounds': 20}
    monkeypatch.setattr(server.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=0, stdout=json.dumps(result), stderr=''))
    server.inspect_isolated(str(src), tmp_path)
    saved = next((server.app_dir() / 'demo-info').glob('*.json'))
    saved.write_text('{broken')
    server._inspect_cache.clear()
    assert server.inspect_isolated(str(src), tmp_path) == result
    assert json.loads(saved.read_text()) == result
    assert not list(saved.parent.glob('*.tmp'))


def test_existing_v4_cache_is_used_without_reparse(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    monkeypatch.setattr(server, '_inspect_cache', {})
    src = tmp_path / 'legacy.dem'
    src.write_bytes(b'demo')
    st = src.stat()
    key = f'{src.resolve()}|{st.st_mtime}|{st.st_size}|v4'
    saved = server.app_dir() / 'demo-info' / (hashlib.sha1(key.encode()).hexdigest() + '.json')
    saved.parent.mkdir(parents=True)
    saved.write_text(json.dumps({'map': 'de_dust2', 'rounds': 24}))
    monkeypatch.setattr(server.subprocess, 'run', lambda *a, **kw: pytest.fail('valid v4 cache must not parse again'))
    assert server.inspect_isolated(str(src), tmp_path)['rounds'] == 24


def test_changed_during_parse_is_not_saved(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    monkeypatch.setattr(server, '_inspect_cache', {})
    src = tmp_path / 'match.dem'
    src.write_bytes(b'demo')

    def parse(*args, **kwargs):
        src.write_bytes(b'replacement demo')
        return SimpleNamespace(returncode=0, stdout='{"map":"de_nuke"}', stderr='')

    monkeypatch.setattr(server.subprocess, 'run', parse)
    with pytest.raises(RuntimeError, match='changed'):
        server.inspect_isolated(str(src), tmp_path)
    assert not list((server.app_dir() / 'demo-info').glob('*.json'))
