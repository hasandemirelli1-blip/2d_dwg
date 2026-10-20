"""Start (home) page: new/open buttons and recent drawings with thumbnails."""
from __future__ import annotations

import datetime
import hashlib
import os
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QImage, QFont, QCursor
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QScrollArea, QGridLayout,
                               QFrame, QMenu, QSizePolicy)

from t2dcad import settings, APP_NAME, __version__
from t2dcad.ui import branding
from t2dcad.i18n import tr


def thumb_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    p = Path(base) / "T2D-CAD" / "thumbs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def thumb_path(path: str) -> Path:
    key = hashlib.md5(os.path.abspath(path).lower().encode("utf8")).hexdigest()
    return thumb_dir() / f"{key}.png"


def save_thumbnail(tab) -> None:
    """Render the drawing extents of a document tab into a small preview."""
    if not tab.doc.path:
        return
    try:
        r = tab.renderer.extents()
        img = QImage(440, 300, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor(33, 40, 48))
        if r is not None and r.width() > 0 and r.height() >= 0:
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing, True)
            w, h = max(r.width(), 1e-9), max(r.height(), 1e-9)
            s = min(420 / w, 280 / h)
            tw, th = w * s, h * s
            p.translate((440 - tw) / 2, (300 - th) / 2 + th)
            p.scale(1, -1)
            tab.renderer.scene.render(p, QRectF(0, 0, tw, th), r, Qt.IgnoreAspectRatio)
            p.end()
        img.save(str(thumb_path(tab.doc.path)))
    except Exception as ex:
        print("thumbnail failed:", ex)


class _Card(QFrame):
    def __init__(self, page, path: str):
        super().__init__()
        self.page = page
        self.path = path
        self.setObjectName("recentCard")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedSize(236, 222)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(3)
        img = QLabel()
        img.setFixedSize(220, 150)
        img.setAlignment(Qt.AlignCenter)
        tp = thumb_path(path)
        exists = os.path.exists(path)
        if tp.exists():
            img.setPixmap(QPixmap(str(tp)).scaled(220, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            img.setPixmap(branding.logo_pixmap(90))
            img.setStyleSheet("background:#212830;")
        v.addWidget(img)
        name = QLabel(Path(path).name)
        name.setStyleSheet("font-weight:bold;color:%s;" % ("#f0f0f0" if exists else "#888"))
        v.addWidget(name)
        folder = QLabel(str(Path(path).parent))
        folder.setStyleSheet("color:#9aa6b4;font-size:8pt;")
        folder.setToolTip(path)
        v.addWidget(folder)
        try:
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d.%m.%Y %H:%M")
        except OSError:
            dt = "dosya bulunamadı"
        d = QLabel(dt)
        d.setStyleSheet("color:#9aa6b4;font-size:8pt;")
        v.addWidget(d)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.page.main.file_open(self.path)
        elif ev.button() == Qt.RightButton:
            m = QMenu(self)
            m.addAction("Aç", lambda: self.page.main.file_open(self.path))
            m.addAction("Listeden kaldır", lambda: self.page.remove_recent(self.path))
            m.exec(ev.globalPosition().toPoint())


class StartPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setObjectName("startPage")
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        # left column
        left = QFrame()
        left.setObjectName("startLeft")
        left.setFixedWidth(300)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(28, 30, 28, 24)
        lv.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(branding.logo_pixmap(110))
        lv.addWidget(logo, 0, Qt.AlignLeft)
        title = QLabel('<span style="color:#ffffff;font-size:30px;font-weight:700;">T2D</span>'
                       '<span style="color:#DC6E2D;font-size:30px;font-weight:300;"> CAD</span>')
        lv.addWidget(title)
        sub = QLabel("2B Teknik Çizim · DWG / DXF")
        sub.setStyleSheet("color:#b9c7d8;")
        lv.addWidget(sub)
        lv.addSpacing(18)
        for text, slot, primary in (("Yeni çizim", main.file_new, True), ("Aç...", main.file_open, False)):
            b = QPushButton(text)
            b.setObjectName("startPrimary" if primary else "startButton")
            b.setMinimumHeight(38)
            b.clicked.connect(lambda checked=False, s=slot: s())
            lv.addWidget(b)
        lv.addSpacing(12)
        self.dwg_label = QLabel()
        self.dwg_label.setWordWrap(True)
        lv.addWidget(self.dwg_label)
        self.dwg_btn = QPushButton("DWG desteğini kur")
        self.dwg_btn.setObjectName("startButton")
        self.dwg_btn.clicked.connect(main.install_dwg_support)
        lv.addWidget(self.dwg_btn)
        lv.addStretch(1)
        tips = QLabel("İpucu: Komutları doğrudan yazın (L, C, TR, O...).\n"
                      "Yazarken öneri listesi açılır.\nF1: komut listesi")
        tips.setStyleSheet("color:#8fa0b3;font-size:8pt;")
        lv.addWidget(tips)
        ver = QLabel(f"Sürüm {__version__}")
        ver.setStyleSheet("color:#6f8196;font-size:8pt;")
        lv.addWidget(ver)
        h.addWidget(left)
        # right: recent files
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(30, 26, 20, 10)
        head = QLabel("Son kullanılan çizimler")
        head.setStyleSheet("color:#ffffff;font-size:18px;font-weight:bold;")
        rv.addWidget(head)
        line = QFrame()
        line.setFixedHeight(3)
        line.setFixedWidth(90)
        line.setStyleSheet("background:#DC6E2D;")
        rv.addWidget(line)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        rv.addWidget(self.scroll, 1)
        h.addWidget(right, 1)
        self.refresh()

    def refresh(self):
        from t2dcad.docmodel import find_oda_converter
        oda = find_oda_converter()
        if oda:
            self.dwg_label.setText(tr('<span style="color:#7fd17f;">● DWG desteği hazır</span>'))
            self.dwg_btn.hide()
        else:
            self.dwg_label.setText(tr('<span style="color:#e8a060;">● DWG desteği kurulu değil</span><br>'
                                      '<span style="color:#9aa6b4;font-size:8pt;">DXF dosyaları yine açılır.</span>'))
            self.dwg_btn.show()
        body = QWidget()
        grid = QGridLayout(body)
        grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        grid.setSpacing(14)
        recent = settings.get_list("recent")
        if not recent:
            lab = QLabel("Henüz açılmış bir çizim yok.\nYeni bir çizim oluşturun veya bir DWG/DXF dosyası açın.")
            lab.setStyleSheet("color:#9aa6b4;")
            grid.addWidget(lab, 0, 0)
        cols = max(1, (self.scroll.viewport().width() - 10) // 250) if self.scroll.viewport().width() > 300 else 4
        for i, p in enumerate(recent):
            grid.addWidget(_Card(self, p), i // cols, i % cols)
        self.scroll.setWidget(body)
        self._cols = cols

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        cols = max(1, (self.scroll.viewport().width() - 10) // 250)
        if cols != getattr(self, "_cols", cols):
            self.refresh()

    def remove_recent(self, path):
        lst = [p for p in settings.get_list("recent") if p != path]
        settings.set("recent", lst)
        self.main._fill_recent()
        self.refresh()
