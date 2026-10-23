"""Windows can briefly lock Chromium's port file while publishing its endpoint."""
from pathlib import Path

import pytest

from povforge import cdp


def fake_browser(tmp_path, monkeypatch, outcomes):
    profile = tmp_path/'browser-profile'
    profile.mkdir()
    (profile/'DevToolsActivePort').write_text('pending')
    class Process:
        terminated = False
        def poll(self):
            return 0 if self.terminated else None
        def terminate(self):
            self.terminated = True
        def wait(self, timeout):
            return 0
    proc = Process()
    monkeypatch.setattr(cdp, 'find_browser', lambda: Path('fake-browser.exe'))
    monkeypatch.setattr(cdp.tempfile, 'mkdtemp', lambda **kwargs: str(profile))
    monkeypatch.setattr(cdp.subprocess, 'Popen', lambda *args, **kwargs: proc)
    reads = []
    def read(path, *args, **kwargs):
        reads.append(path)
        result = outcomes[min(len(reads)-1, len(outcomes)-1)]
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(Path, 'read_text', read)
    # Advance both clocks: this also reproduces bounded startup on the old loop.
    counter = iter(n/10 for n in range(100))
    monkeypatch.setattr(cdp.time, 'time', lambda: next(counter))
    monkeypatch.setattr(cdp.time, 'monotonic', lambda: next(counter))
    monkeypatch.setattr(cdp.time, 'sleep', lambda _: None)
    return proc, profile, reads


def test_startup_retries_file_lock_partial_and_invalid_port_then_uses_one_snapshot(tmp_path, monkeypatch):
    outcomes = [PermissionError('sharing violation'), '9222\n', 'bad\n/devtools/browser/id\n',
                '9222\n/devtools/browser/id\n', PermissionError('must not reread')]
    proc, profile, reads = fake_browser(tmp_path, monkeypatch, outcomes)
    with cdp.Browser(timeout=2) as browser:
        assert browser.port == 9222
        assert len(reads) == 4
    assert proc.terminated and not profile.exists()


def test_persistent_port_file_lock_times_out_and_cleans_up(tmp_path, monkeypatch):
    proc, profile, _ = fake_browser(tmp_path, monkeypatch, [PermissionError('locked')])
    with pytest.raises(RuntimeError, match='did not start'):
        cdp.Browser(timeout=.3)
    assert proc.terminated and not profile.exists()
