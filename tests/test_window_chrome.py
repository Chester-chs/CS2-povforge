"""Window styling must never spill into another process's windows."""

import importlib
import ctypes
from ctypes import wintypes
import subprocess
import sys
from types import SimpleNamespace

import pytest


def module():
    return importlib.import_module("povforge.gui.window_chrome")


class Windows:
    def __init__(self, windows=((100, 42), (200, 99)), failed_attribute=None):
        self.windows = dict(windows)
        self.attributes = {}
        self.failed_attribute = failed_attribute

    def top_level_windows(self):
        return list(self.windows)

    def process_id(self, hwnd):
        return self.windows.get(hwnd, 0)

    def set_attribute(self, hwnd, attribute, value):
        if attribute == self.failed_attribute:
            return False
        self.attributes[hwnd, attribute] = value
        return True


def setup(monkeypatch, windows=None):
    chrome = module()
    windows = windows or Windows()
    monkeypatch.setattr(chrome.sys, "platform", "win32")
    monkeypatch.setattr(chrome, "_windows_api", lambda: windows)
    return chrome, windows


@pytest.mark.parametrize("dark,background,text", [(False, 0xF7F5F5, 0x1E1C1C), (True, 0x1E1C1C, 0xF7F5F5)])
def test_only_live_process_window_gets_matching_colourref(monkeypatch, dark, background, text):
    chrome, windows = setup(monkeypatch)
    assert chrome.apply(SimpleNamespace(pid=42, poll=lambda: None), dark)
    assert windows.attributes == {(100, 20): int(dark), (100, 34): background,
                                  (100, 35): background, (100, 36): text}


@pytest.mark.parametrize("process", [None, SimpleNamespace(pid=42, poll=lambda: 0),
                                    SimpleNamespace(pid=0, poll=lambda: None)])
def test_missing_or_exited_process_does_not_modify_any_window(monkeypatch, process):
    chrome, windows = setup(monkeypatch)
    assert chrome.apply(process, False) is False
    assert windows.attributes == {}


@pytest.mark.parametrize("owned", [[], [(100, 42), (101, 42)]])
def test_absent_or_ambiguous_owned_window_is_skipped(monkeypatch, owned):
    chrome, windows = setup(monkeypatch, Windows(owned + [(200, 99)]))
    assert chrome.apply(SimpleNamespace(pid=42, poll=lambda: None), False) is False
    assert windows.attributes == {}


def test_process_exit_between_enumeration_and_styling_is_safe(monkeypatch):
    chrome, windows = setup(monkeypatch)
    polls = iter([None, 0])
    assert chrome.apply(SimpleNamespace(pid=42, poll=lambda: next(polls)), False) is False
    assert windows.attributes == {}


def test_window_reassigned_between_enumeration_and_styling_is_safe(monkeypatch):
    chrome, windows = setup(monkeypatch)
    def poll():
        windows.windows[100] = 99
        return None
    calls = iter([lambda: None, poll])
    assert chrome.apply(SimpleNamespace(pid=42, poll=lambda: next(calls)()), False) is False
    assert windows.attributes == {}


def test_unsupported_dwm_attribute_reports_failure_without_raising(monkeypatch):
    chrome, windows = setup(monkeypatch, Windows(failed_attribute=35))
    assert chrome.apply(SimpleNamespace(pid=42, poll=lambda: None), False) is False
    assert all(hwnd == 100 for hwnd, _ in windows.attributes)


def test_non_windows_never_loads_native_api(monkeypatch):
    chrome, windows = setup(monkeypatch)
    monkeypatch.setattr(chrome.sys, "platform", "linux")
    monkeypatch.setattr(chrome, "_windows_api", lambda: pytest.fail("Native API loaded"))
    assert chrome.apply(SimpleNamespace(pid=42, poll=lambda: None), False) is False


def test_unavailable_native_api_is_optional(monkeypatch):
    chrome, _ = setup(monkeypatch)
    def missing():
        raise OSError("DWM unavailable")
    monkeypatch.setattr(chrome, "_windows_api", missing)
    assert chrome.apply(SimpleNamespace(pid=42, poll=lambda: None), False) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Native DWM integration requires Windows")
def test_real_dwm_accepts_colours_and_round_trips_dark_mode_on_own_native_window():
    if sys.getwindowsversion().build < 22000:
        pytest.skip("DWM caption colours require Windows 11")
    # The helper owns only this test window; never inspect or change user windows.
    script = r'''
import ctypes
from ctypes import wintypes
import sys
u = ctypes.WinDLL("user32", use_last_error=True)
u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
    wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
u.CreateWindowExW.restype = wintypes.HWND
u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
u.DestroyWindow.argtypes = [wintypes.HWND]
h = u.CreateWindowExW(0, "STATIC", "POVForge temporary DWM test", 0x00CF0000,
    0, 0, 240, 100, None, None, None, None)
if not h:
    raise ctypes.WinError(ctypes.get_last_error())
try:
    u.ShowWindow(h, 4)  # SW_SHOWNOACTIVATE: preserve the user's active window.
    print(h, flush=True)
    sys.stdin.readline()
finally:
    u.DestroyWindow(h)
'''
    # Windows venv python.exe is a redirector; use the real interpreter so the
    # explicit Popen PID owns the window instead of an untracked grandchild.
    executable = getattr(sys, "_base_executable", sys.executable)
    process = subprocess.Popen([executable, "-c", script], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        hwnd = int(process.stdout.readline())
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                            ctypes.c_void_p, wintypes.DWORD]
        dwm.DwmGetWindowAttribute.restype = ctypes.c_long
        for dark in (False, True):
            applied = module().apply(process, dark)
            if not applied:
                api = module()._windows_api()
                owned = [h for h in api.top_level_windows() if api.process_id(h) == process.pid]
                pytest.fail(f"DWM rejected test window {hwnd}; owned={owned}; pid={api.process_id(hwnd)}/{process.pid}; "
                            f"visible={api.user32.IsWindowVisible(hwnd)}; owner={api.user32.GetWindow(hwnd, 4)}")
            # Colours 34-36 are Set-only in the DWM contract; their Get calls
            # return E_INVALIDARG. Dark mode permits a real native round trip.
            value = wintypes.DWORD()
            assert dwm.DwmGetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)) >= 0
            assert value.value == int(dark)
    finally:
        try:
            process.communicate("\n", timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
