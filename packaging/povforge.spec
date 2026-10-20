# PyInstaller build: one folder with PovForge.exe (app window) and povforge.exe
# (command line, povforge-cli.exe), sharing the same libraries. The names must
# differ by more than case: Windows file names ignore case. Run inside packaging:
#   pyinstaller --noconfirm povforge.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

datas = collect_data_files("povforge", includes=["director.js", "gui/static/**/*"])
binaries = collect_dynamic_libs("demoparser2")
hidden = ["povforge.gui.server", "povforge.cli", "povforge.app"]

# demoparser2 is a compiled extension that imports polars and pyarrow at run time
# (to build its tables), so PyInstaller can't see them: collect them explicitly.
# polars 1.3x+ keeps its compiled core in a separate _polars_runtime_* package.
for pkg in ("polars", "_polars_runtime_32", "_polars_runtime_64", "_polars_runtime_compat", "pyarrow"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += [x for x in d if not any(k in x[1].replace("\\", "/") for k in ("pyarrow/include", "pyarrow/src", "pyarrow/tests"))]
    binaries += b
    hidden += [m for m in h if ".tests" not in m]

# Read the checkout even when development dependencies were installed editable.
common = dict(pathex=[str(Path(SPECPATH).parent)], binaries=binaries, datas=datas, hiddenimports=hidden,
              excludes=["matplotlib", "IPython", "pytest", "scipy", "pyarrow.tests"],
              # code as separate .pyc files instead of one archive inside each .exe: a code
              # change then alters only the files it touches, so updates stay tiny
              noarchive=True)

a_app = Analysis(["app_main.py"], **common)
a_cli = Analysis(["cli_main.py"], **common)

exe_app = EXE(PYZ(a_app.pure), a_app.scripts, [], exclude_binaries=True, name="PovForge",
              console=False, icon="povforge.ico")
exe_cli = EXE(PYZ(a_cli.pure), a_cli.scripts, [], exclude_binaries=True, name="povforge-cli",
              console=True, icon="povforge.ico")

COLLECT(exe_app, a_app.binaries, a_app.datas, exe_cli, a_cli.binaries, a_cli.datas, name="PovForge")
