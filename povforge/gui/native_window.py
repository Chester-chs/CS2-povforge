"""Windows-owned caption with WebView2 content, instead of Edge's painted frame."""
import os
import sys
import threading
from urllib.parse import urlsplit


def runtime_available() -> bool:
    """Check WebView2/.NET before importing WinForms (never fall back to IE)."""
    if sys.platform != 'win32':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full') as key:
            if winreg.QueryValueEx(key, 'Release')[0] < 394802:
                return False
    except OSError:
        return False
    client = r'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    for hive, prefix in ((winreg.HKEY_CURRENT_USER, 'SOFTWARE\\'),
                         (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\')):
        try:
            with winreg.OpenKey(hive, prefix + client) as key:
                if int(winreg.QueryValueEx(key, 'pv')[0].split('.')[0]) >= 86:
                    return True
        except (OSError, ValueError, TypeError):
            pass
    return False


class NativeWindow:
    def __init__(self, window, webview, storage):
        self.window, self.webview, self.storage = window, webview, storage
        self.pid = os.getpid()
        self.closed = threading.Event()
        window.events.closed += self.closed.set

    def poll(self):
        return 0 if self.closed.is_set() else None

    def close(self):
        if not self.closed.is_set():
            self.window.destroy()

    def run(self):
        failed = threading.Event()
        def ready():
            if self.window.events.loaded.wait(30):
                print('Native WebView2 ready (Windows-owned titlebar)', flush=True)
            elif not self.closed.is_set():
                failed.set()
                self.close()
        try:
            self.webview.start(ready, gui='edgechromium', private_mode=False,
                               storage_path=str(self.storage))
        finally:
            self.closed.set()
        if failed.is_set():
            raise RuntimeError('WebView2 initialization timed out')


def create(url: str):
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or
            not parsed.port or parsed.path != '/' or parsed.query or parsed.fragment or parsed.username):
        raise ValueError('The native window only accepts the local PovForge root URL')
    if not runtime_available():
        return None
    try:
        import webview
        from webview.guilib import initialize
        backend = initialize('edgechromium')
        if backend.renderer != 'edgechromium':
            return None
        from .server import app_dir
        storage = app_dir() / 'webview'
        storage.mkdir(parents=True, exist_ok=True)
        window = webview.create_window('PovForge', url, width=1280, height=820,
                                      min_size=(760, 520), background_color='#f5f5f7',
                                      text_select=True)
        return NativeWindow(window, webview, storage)
    except Exception as exc:
        print(f'Native window unavailable; using browser window: {exc}', flush=True)
        return None
