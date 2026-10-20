# PyInstaller build file:  pyinstaller T2D-CAD.spec
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("ezdxf") + [("t2dcad/resources", "t2dcad/resources")]
hiddenimports = collect_submodules("ezdxf.addons.drawing") + [
    "ezdxf.addons.odafc", "ezdxf.addons.importer", "ezdxf.addons.xqt",
    "PySide6.QtPrintSupport", "pymupdf",
]

a = Analysis(
    ["run_t2dcad.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "PyQt5", "PyQt6", "IPython", "pytest",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="T2D-CAD",
    icon="assets/t2dcad.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="T2D-CAD")
