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


def main() -> int:
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        return cli_main()
    hide_console_windows()
    from .gui.server import main as gui_main
    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
