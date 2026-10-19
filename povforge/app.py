"""Entry point of the packaged app: no arguments opens the window, otherwise
it behaves like the `povforge` command (the app runs itself that way to record)."""

import subprocess
import sys


def hide_console_windows() -> None:
    """A windowed program that starts a console program (ffmpeg, taskkill, ...)
    makes Windows pop up a black console window each time. Start them hidden."""
    if sys.platform != "win32":
        return
    flag = subprocess.CREATE_NO_WINDOW
    original = subprocess.Popen.__init__

    def init(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = flag
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = init


def log_to_file() -> None:
    """The windowed app has no console: keep what it prints (and any crash) in
    %LOCALAPPDATA%\\povforge\\app.log, so problems can be looked up afterwards."""
    import datetime
    import os
    from pathlib import Path
    base = Path(os.environ.get("POVFORGE_STATE") or os.environ.get("LOCALAPPDATA") or Path.home()) / "povforge"
    base.mkdir(parents=True, exist_ok=True)
    log = base / "app.log"
    if log.exists() and log.stat().st_size > 2_000_000:
        log.replace(base / "app.log.1")
    f = open(log, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = f
    from . import __version__
    print(f"--- PovForge {__version__} started {datetime.datetime.now():%Y-%m-%d %H:%M:%S}", flush=True)


def main() -> int:
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        return cli_main()
    if getattr(sys, "frozen", False):
        try:
            log_to_file()
        except Exception:
            pass
    hide_console_windows()
    from .gui.server import main as gui_main
    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
