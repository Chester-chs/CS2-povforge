"""Entry point of the packaged app: no arguments opens the window, otherwise
it behaves like the `povforge` command (the app runs itself that way to record)."""

import sys


def main() -> int:
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        return cli_main()
    from .gui.server import main as gui_main
    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
