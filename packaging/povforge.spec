# PyInstaller build: one folder with PovForge.exe (app window) and povforge.exe
# (command line, povforge-cli.exe), sharing the same libraries. The names must
# differ by more than case: Windows file names ignore case. Run from the repo root:
#   pyinstaller packaging/povforge.spec
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("povforge", includes=["director.js", "gui/static/**/*"])
datas += collect_data_files("playwright")          # the browser driver used for the FACEIT screenshot
binaries = collect_dynamic_libs("demoparser2")
hidden = ["povforge.gui.server", "povforge.cli", "povforge.app"]

common = dict(pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden,
              excludes=["matplotlib", "IPython", "pytest"])

a_app = Analysis(["app_main.py"], **common)
a_cli = Analysis(["cli_main.py"], **common)

exe_app = EXE(PYZ(a_app.pure), a_app.scripts, [], exclude_binaries=True, name="PovForge",
              console=False, icon="povforge.ico")
exe_cli = EXE(PYZ(a_cli.pure), a_cli.scripts, [], exclude_binaries=True, name="povforge-cli",
              console=True, icon="povforge.ico")

COLLECT(exe_app, a_app.binaries, a_app.datas, exe_cli, a_cli.binaries, a_cli.datas, name="PovForge")
