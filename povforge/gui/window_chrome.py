"""Best-effort DWM colours for the one window of our living browser process.

Chromium can draw its own caption, so a successful DWM call does not guarantee
that the browser displays these colours. Reused browser processes and ambiguous
window ownership are deliberately skipped. No system preferences are changed.
"""

import ctypes
from ctypes import wintypes
import sys


class _WindowsAPI:
    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user32.EnumWindows.argtypes = [self.callback_type, wintypes.LPARAM]
        self.user32.EnumWindows.restype = wintypes.BOOL
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        self.user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                                    ctypes.c_void_p, wintypes.DWORD]
        self.dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

    def top_level_windows(self):
        windows = []

        @self.callback_type
        def collect(hwnd, _):
            # Ignore hidden helper windows and owned dialogs (GW_OWNER = 4).
            if self.user32.IsWindowVisible(hwnd) and not self.user32.GetWindow(hwnd, 4):
                windows.append(hwnd)
            return True

        return windows if self.user32.EnumWindows(collect, 0) else []

    def process_id(self, hwnd):
        pid = wintypes.DWORD()
        if not self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)):
            return 0
        return pid.value

    def set_attribute(self, hwnd, attribute, value):
        # All four attributes use a 32-bit BOOL or COLORREF.
        data = wintypes.DWORD(value)
        result = self.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))
        return result >= 0


def _windows_api():
    return _WindowsAPI()


def apply(window_process, dark: bool) -> bool:
    """Set per-window colours if exactly one window belongs to this live Popen.

    Returns whether all DWM attributes were accepted, not visual confirmation.
    Unsupported Windows versions/platforms fail quietly. Never finds a window
    by its caption or follows a browser process that has handed off and exited.
    """
    if sys.platform != "win32" or window_process is None:
        return False
    try:
        pid = window_process.pid
        if not isinstance(pid, int) or pid <= 0 or window_process.poll() is not None:
            return False
        api = _windows_api()
        matches = [hwnd for hwnd in api.top_level_windows() if api.process_id(hwnd) == pid]
        if len(matches) != 1:
            return False
        hwnd = matches[0]
        # COLORREF is 0x00BBGGRR, unlike CSS's #RRGGBB.
        background, text = (0x1E1C1C, 0xF7F5F5) if dark else (0xF7F5F5, 0x1E1C1C)
        accepted = True
        for attribute, value in ((20, int(dark)), (34, background), (35, background), (36, text)):
            if window_process.poll() is not None or api.process_id(hwnd) != pid:
                return False
            accepted = api.set_attribute(hwnd, attribute, value) and accepted
        return accepted
    except (OSError, AttributeError, TypeError, ValueError):
        return False
