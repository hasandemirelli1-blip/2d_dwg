"""AutoCAD style ribbon (Şerit) built from the main window actions."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QWidget, QTabWidget, QHBoxLayout, QVBoxLayout, QToolButton,
                               QLabel, QFrame, QMenu, QSizePolicy, QScrollArea)

from t2dcad.ui import branding
from t2dcad.ui.propbar import PropertyBar

# (tab, [(panel, [(size, action key) | ("W", widget name)])])
LAYOUT = [
    ("Giriş", [
        ("Çizim", [("L", "line"), ("L", "pline"), ("L", "circle"), ("L", "arc"),
                   ("S", "rect"), ("S", "polygon"), ("S", "ellipse"), ("S", "hatch"), ("S", "xline"),
                   ("S", "point")]),
        ("Değiştir", [("S", "move"), ("S", "rotate"), ("S", "trim"), ("S", "copy"), ("S", "mirror"),
                      ("S", "fillet"), ("S", "stretch"), ("S", "scale"), ("S", "array"), ("S", "erase"),
                      ("S", "explode"), ("S", "offset"), ("S", "extend"), ("S", "break"), ("S", "join"),
                      ("S", "chamfer")]),
        ("Açıklama", [("L", "mtext"), ("S", "text"), ("S", "dli"), ("S", "le"), ("S", "dra"), ("S", "tstyle")]),
        ("Katmanlar", [("L", "layer"), ("W", "layerbar"), ("S", "laymcur"), ("S", "layoff"), ("S", "layiso"),
                       ("S", "layon")]),
        ("Blok", [("L", "insert"), ("S", "block")]),
        ("Özellikler", [("L", "ma"), ("W", "propbar")]),
        ("Yardımcılar", [("L", "dist"), ("S", "area"), ("S", "list"), ("S", "selall")]),
        ("Pano", [("L", "paste"), ("S", "copyclip"), ("S", "cut")]),
    ]),
    ("Ekle", [
        ("Blok", [("L", "insert"), ("L", "block")]),
        ("Yazı tipi", [("L", "fontimport"), ("S", "tstyle")]),
    ]),
    ("Açıklama", [
        ("Yazı", [("L", "mtext"), ("S", "text"), ("S", "ed"), ("S", "tstyle")]),
        ("Ölçüler", [("L", "dli"), ("S", "dal"), ("S", "dan"), ("S", "dra"), ("S", "ddi"), ("S", "dco"),
                     ("S", "dba"), ("S", "dst")]),
        ("Kılavuz", [("L", "le")]),
        ("Tarama", [("L", "hatch")]),
    ]),
    ("Görünüm", [
        ("Gezinme", [("L", "ze"), ("S", "zw"), ("S", "zp"), ("S", "pan"), ("S", "regen")]),
        ("Paneller", [("L", "props"), ("S", "cmdtoggle"), ("S", "startpage")]),
        ("Arayüz", [("L", "classic")]),
    ]),
    ("Çıktı", [
        ("Çizdir", [("L", "plot"), ("L", "pdf")]),
    ]),
    ("Yönet", [
        ("Ayarlar", [("L", "options"), ("S", "osnapset"), ("S", "purge")]),
        ("Yardım", [("L", "help"), ("S", "about")]),
    ]),
]


class _Panel(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("ribbonPanel")
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 3, 4, 1)
        v.setSpacing(1)
        self.body = QHBoxLayout()
        self.body.setSpacing(2)
        v.addLayout(self.body, 1)
        lab = QLabel(title)
        lab.setAlignment(Qt.AlignCenter)
        lab.setObjectName("ribbonPanelTitle")
        v.addWidget(lab)
        self._small_col = None
        self._small_count = 0

    def add_large(self, action):
        b = QToolButton()
        b.setDefaultAction(action)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(32, 32))
        b.setAutoRaise(True)
        b.setMinimumWidth(max(56, b.fontMetrics().horizontalAdvance(action.text().replace("&", "")) + 12))
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.body.addWidget(b)
        self._small_col = None

    def add_small(self, action):
        if self._small_col is None or self._small_count >= 3:
            col = QVBoxLayout()
            col.setSpacing(0)
            col.setAlignment(Qt.AlignTop)
            self.body.addLayout(col)
            self._small_col = col
            self._small_count = 0
        b = QToolButton()
        b.setDefaultAction(action)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setIconSize(QSize(16, 16))
        b.setAutoRaise(True)
        b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._small_col.addWidget(b)
        self._small_count += 1

    def add_widget(self, w):
        self._small_col = None
        self.body.addWidget(w)


class Ribbon(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.prop_bars = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.app_btn = QToolButton()
        self.app_btn.setObjectName("appButton")
        self.app_btn.setIcon(branding.logo_icon())
        self.app_btn.setIconSize(QSize(38, 38))
        self.app_btn.setToolTip("Uygulama menüsü")
        self.app_btn.setPopupMode(QToolButton.InstantPopup)
        self.app_btn.setMenu(self._app_menu())
        self.app_btn.setFixedWidth(58)
        lay.addWidget(self.app_btn, 0, Qt.AlignTop)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("ribbonTabs")
        self.tabs.setDocumentMode(True)
        lay.addWidget(self.tabs, 1)
        acts = main._actions
        for tab_title, panels in LAYOUT:
            page = QWidget()
            h = QHBoxLayout(page)
            h.setContentsMargins(2, 2, 2, 2)
            h.setSpacing(3)
            for ptitle, items in panels:
                panel = _Panel(ptitle)
                for size, key in items:
                    if size == "W":
                        bar = PropertyBar(main, layer=(key == "layerbar"), props=(key == "propbar"),
                                          vertical=(key == "propbar"))
                        self.prop_bars.append(bar)
                        panel.add_widget(bar)
                    elif key in acts:
                        (panel.add_large if size == "L" else panel.add_small)(acts[key])
                h.addWidget(panel)
            h.addStretch(1)
            # pages scroll horizontally on small screens instead of widening the window
            sa = QScrollArea()
            sa.setWidget(page)
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.NoFrame)
            sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.tabs.addTab(sa, tab_title)
        self.setFixedHeight(144)
        self.setMinimumWidth(200)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def _app_menu(self) -> QMenu:
        m = QMenu(self)
        a = self.main._actions
        for k in ("new", "open"):
            m.addAction(a[k])
        self.recent_menu = m.addMenu("Son kullanılanlar")
        for k in ("save", "saveas", None, "plot", "pdf", None, "startpage", "options", None, "close", "quit"):
            if k is None:
                m.addSeparator()
            else:
                m.addAction(a[k])
        return m
