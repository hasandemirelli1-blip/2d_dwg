"""Font library: bundled CAD stroke fonts (LibreCAD .lff, similar to AutoCAD
.shx fonts), user imported fonts and the system TrueType fonts."""
from __future__ import annotations

import glob
import hashlib
import os
import shutil
import sys
from pathlib import Path

import ezdxf
from ezdxf.fonts import fonts as ezfonts

from t2dcad import settings

# AutoCAD SHX font name -> bundled stroke font (shown in the font list)
SHX_LIBRARY = [
    ("txt.shx", "standard"), ("simplex.shx", "simplex"), ("romans.shx", "romans"),
    ("romanc.shx", "romanc"), ("romand.shx", "romand"), ("romant.shx", "romant"),
    ("romanp.shx", "romanp"), ("isocp.shx", "iso3098"), ("iso3098.shx", "iso3098"),
    ("iso.shx", "iso"), ("italic.shx", "italicc"), ("italicc.shx", "italicc"),
    ("italict.shx", "italict"), ("scriptc.shx", "scriptc"), ("scripts.shx", "scripts"),
    ("greekc.shx", "greekc"), ("greeks.shx", "greeks"), ("gothice.shx", "gothgbt"),
    ("gothicg.shx", "gothgrt"), ("gothici.shx", "gothitt"), ("cyrillic.shx", "cyrillic_ii"),
    ("cursive.shx", "cursive"), ("symbol.shx", "symbol_misc1"),
]
SHX_TO_LFF = {k.lower(): v for k, v in SHX_LIBRARY}


def resource_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    p = base / "t2dcad" / "resources"
    if not p.exists():
        p = Path(__file__).resolve().parent / "resources"
    return p


def bundled_font_dir() -> Path:
    return resource_dir() / "fonts"


def user_font_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    p = Path(base) / "T2D-CAD" / "Fonts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def autocad_font_dirs() -> list[str]:
    """Font folders of installed Autodesk products (real .shx fonts)."""
    out = []
    for pat in (r"C:\Program Files\Autodesk\*\Fonts", r"C:\Program Files (x86)\Autodesk\*\Fonts"):
        out.extend(glob.glob(pat))
    return out


def _lff_aliases(folder: Path) -> None:
    """ezdxf finds a stroke font for "simplex.shx" by the name "simplex.lff".
    Create copies with AutoCAD names (isocp.lff, italic.lff ...) once."""
    for shx, lff in SHX_LIBRARY:
        stem = shx[:-4]
        src = folder / f"{lff}.lff"
        dst = folder / f"{stem}.lff"
        if stem != lff and src.exists() and (not dst.exists() or dst.stat().st_size != src.stat().st_size):
            try:
                shutil.copyfile(src, dst)
            except OSError:
                pass


def _signature(dirs: list[str]) -> str:
    h = hashlib.md5()
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "**", "*.*"), recursive=True)):
            if f.lower().endswith((".ttf", ".otf", ".ttc", ".shx", ".lff", ".shp")):
                h.update(f.encode("utf8", "ignore"))
    return h.hexdigest()


def setup(force_rebuild=False) -> None:
    """Configure ezdxf to use the bundled, imported and AutoCAD fonts."""
    cache_fonts = user_font_dir().parent / "lff_aliases"
    cache_fonts.mkdir(parents=True, exist_ok=True)
    # aliases are written to a writable folder (the program folder may be read-only)
    for f in bundled_font_dir().glob("*.lff"):
        dst = cache_fonts / f.name
        if not dst.exists() or dst.stat().st_size != f.stat().st_size:
            try:
                shutil.copyfile(f, dst)
            except OSError:
                pass
    _lff_aliases(cache_fonts)
    dirs = [str(cache_fonts), str(user_font_dir())] + autocad_font_dirs()
    ezdxf.options.support_dirs = dirs
    # use real SHX fonts if available, then the stroke fonts, then TrueType
    ezdxf.options.set("drawing-addon", "shx_resolve_order", "slt")
    sig = _signature(dirs)
    if force_rebuild or settings.get("font_signature", "") != sig:
        try:
            ezfonts.font_manager.clear()
            ezfonts.font_manager.build()
            path = ezfonts._get_font_manager_path()
            ezfonts.make_cache_directory(path.parent)
            path.write_text(ezfonts.font_manager.dumps())
            settings.set("font_signature", sig)
        except Exception as ex:  # fonts are not critical
            print("font cache build failed:", ex)


def import_font(path: str) -> str:
    """Copy a font file into the user font folder. Returns the font name."""
    dst = user_font_dir() / Path(path).name
    shutil.copyfile(path, dst)
    setup(force_rebuild=True)
    return dst.name


def font_list() -> tuple[list[str], list[str]]:
    """(cad fonts like 'simplex.shx', truetype font file names)"""
    cad = [shx for shx, _ in SHX_LIBRARY]
    for f in user_font_dir().glob("*"):
        n = f.name.lower()
        if n.endswith((".shx", ".lff")):
            name = f.stem + ".shx"
            if name not in cad:
                cad.append(name)
    for d in autocad_font_dirs():
        for f in Path(d).glob("*.shx"):
            if f.name.lower() not in cad:
                cad.append(f.name.lower())
    ttf = set()
    try:
        for entry in ezfonts.font_manager._font_cache._cache.values():  # noqa
            fn = getattr(entry, "file_path", None) or getattr(entry, "filename", None)
            name = Path(str(fn)).name if fn else ""
            if name.lower().endswith((".ttf", ".otf", ".ttc")):
                ttf.add(name)
    except Exception:
        pass
    if not ttf:
        ttf = {"arial.ttf", "times.ttf", "cour.ttf", "calibri.ttf", "verdana.ttf", "tahoma.ttf"}
    return sorted(cad), sorted(ttf, key=str.lower)
