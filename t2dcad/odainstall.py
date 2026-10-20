"""Locate or automatically install the free ODA File Converter (DWG support).

Search order: next to T2D-CAD.exe ("oda" folder, bundled by the Windows build),
the per-user install folder, the standard ODA install folders."""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Optional

ODA_PAGE = "https://www.opendesign.com/guestfiles/oda_file_converter"
EXE = "ODAFileConverter.exe"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_oda_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(base) / "T2D-CAD" / "ODAFileConverter"


def _search(folder: Path) -> str:
    if not folder.exists():
        return ""
    hits = glob.glob(str(folder / "**" / EXE), recursive=True)
    return sorted(hits)[-1] if hits else ""


def find_bundled() -> str:
    for d in (app_dir() / "oda", app_dir() / "_internal" / "oda", user_oda_dir()):
        p = _search(d)
        if p:
            return p
    return ""


def find_download_url() -> str:
    req = urllib.request.Request(ODA_PAGE, headers={"User-Agent": "Mozilla/5.0 T2D-CAD"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf8", "ignore")
    links = re.findall(r'href="([^"]*?ODAFileConverter[^"]*?\.msi)"', html, re.I)
    if not links:
        links = re.findall(r'(/guestfiles/get\?filename=ODAFileConverter[^"\'&<> ]*?\.msi)', html, re.I)
    if not links:
        raise RuntimeError("İndirme bağlantısı bulunamadı.")
    links = sorted(links, key=lambda u: (("amd64" in u.lower() or "x64" in u.lower()), "qt6" in u.lower()),
                   reverse=True)
    url = links[0].replace("&amp;", "&")
    if url.startswith("/"):
        url = "https://www.opendesign.com" + url
    return url


def install(progress: Optional[Callable[[str, int], None]] = None) -> str:
    """Download the Windows MSI from the official site and extract it into the
    user folder (administrative install, no admin rights needed).
    Returns the path of ODAFileConverter.exe."""
    def say(msg, pct):
        if progress:
            progress(msg, pct)

    say("İndirme adresi alınıyor...", 2)
    url = find_download_url()
    tmp = Path(tempfile.gettempdir()) / "t2dcad_oda.msi"
    say("ODA File Converter indiriliyor...", 5)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 T2D-CAD"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                say("ODA File Converter indiriliyor...", 5 + int(80 * done / total))
    target = user_oda_dir()
    target.mkdir(parents=True, exist_ok=True)
    say("Kuruluyor...", 88)
    cmd = ["msiexec", "/a", str(tmp), "/qn", f"TARGETDIR={target}"]
    res = subprocess.run(cmd, capture_output=True, timeout=600)
    exe = _search(target)
    if not exe:
        # fall back to a normal installation (asks for administrator rights)
        subprocess.run(["msiexec", "/i", str(tmp), "/passive"], timeout=900)
        from t2dcad.docmodel import find_oda_converter
        exe = find_oda_converter()
    try:
        tmp.unlink()
    except OSError:
        pass
    if not exe:
        raise RuntimeError(f"Kurulum tamamlanamadı (msiexec kodu {res.returncode}).")
    say("Hazır", 100)
    return exe
