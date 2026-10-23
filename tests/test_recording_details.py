from types import SimpleNamespace

from povforge.model import Death, Player, Round


def test_details_keep_weapon_order_posthumous_flags_and_round_lengths():
    from povforge.recording_details import build
    demo = SimpleNamespace(tickrate=10, last_tick=420,
        players=[Player('a', 'A'), Player('b', 'B'), Player('c', 'C')],
        rounds=[Round(1, 30, 200), Round(2, 250, 400)],
        deaths=[Death(100, 'b', 'a', 'm4a1', True), Death(80, 'c', 'a', 'ak47'),
                Death(150, 'a', 'b', 'awp'), Death(180, 'c', 'a', 'inferno')])
    info = build(demo)
    assert [e['weapon'] for e in info['events']] == ['ak47', 'm4a1', 'awp', 'inferno']
    assert [e['pov'] for e in info['events']] == [True, True, True, False]
    assert info['events'][1]['headshot'] is True
    assert info['events'][0]['time'] == 5
    assert info['seconds']['a'] == [17, 20]


def test_details_cache_upgrade_is_opt_in_and_reused(tmp_path, monkeypatch):
    import json
    from povforge.gui import server
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path))
    monkeypatch.setattr(server, '_inspect_cache', {})
    src = tmp_path / 'x.dem'; src.write_bytes(b'demo')
    saved = server._inspection_file(server._inspection_key(src))
    saved.parent.mkdir(parents=True)
    saved.write_text(json.dumps({'rounds': 2}))
    calls = []
    fresh = {'rounds': 2, 'recording_details': {'version': 1, 'events': []}}
    def parse(*a, **kw):
        calls.append(a)
        return SimpleNamespace(returncode=0, stdout=json.dumps(fresh), stderr='')
    monkeypatch.setattr(server.subprocess, 'run', parse)
    assert server.inspect_isolated(str(src), tmp_path) == {'rounds': 2}
    assert not calls
    assert server.inspect_isolated(str(src), tmp_path, details=True) == fresh
    server._inspect_cache.clear()
    assert server.inspect_isolated(str(src), tmp_path, details=True) == fresh
    assert len(calls) == 1
