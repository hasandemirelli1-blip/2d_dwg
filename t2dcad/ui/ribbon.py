"""AutoCAD / progeCAD style ribbon (Şerit) built from the main window actions.

Panels are compact: a few large buttons, small buttons stacked three high
(with or without text) and drop-down buttons that group variants (Circle,
Trim/Extend, Fillet/Chamfer...). The arrow next to a panel title opens the
panel's extra commands. When the window is too narrow, panels collapse from
the right into a single button that opens their commands as a menu."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QWidget, QTabWidget, QHBoxLayout, QVBoxLayout, QToolButton,
                               QLabel, QFrame, QMenu, QSizePolicy, QScrollArea)

from t2dcad.i18n import tr
from t2dcad.ui import branding
from t2dcad.ui.propbar import PropertyBar

# Panel items:
#   ("L", key)                large button          ("L", [keys], "Label")  large drop-down
#   ("S", key) / ("S", [keys]) small button with text (stacked three high)
#   ("I", key) / ("I", [keys]) small icon-only button (stacked three high)
#   ("W", name)               widget (layerbar / propbar)
#   ("G", [[item, ...], ...])  rows of items (combo on top, icon rows below)
# A panel is (title, items, extra keys shown by the arrow next to the title).
LAYOUT = [
    ("Giriş", [
        ("Çizim", [("L", "line"), ("L", "pline"),
                   ("L", ["circle_cr", "circle_cd", "circle_2p", "circle_3p", "circle_ttr"], "Çember"),
                   ("L", ["arc_3p", "arc_cse"], "Yay"),
                   ("I", ["rect", "polygon"]), ("I", "ellipse"), ("I", "hatch"),
                   ("I", "xline"), ("I", "ray"), ("I", "point")],
         ["donut", "text", "mtext", "block"]),
        ("Değiştir", [("S", "move"), ("S", "copy"), ("S", "stretch"),
                      ("S", "rotate"), ("S", "mirror"), ("S", "scale"),
                      ("S", ["trim", "extend"]), ("S", ["fillet", "chamfer"]), ("S", "array"),
                      ("I", "erase"), ("I", "explode"), ("I", "offset"),
                      ("I", ["break", "brp"]), ("I", "join"), ("I", "align")],
         ["lengthen", "ed", "ma"]),
        ("Açıklama", [("L", ["mtext", "text"], "Yazı"),
                      ("S", ["dli", "dal", "dan", "dra", "ddi", "dco", "dba"]), ("S", "le"),
                      ("S", ["tstyle", "dst"])],
         ["ed", "fontimport"]),
        ("Katmanlar", [("L", "layer"),
                       ("G", [[("W", "layerbar")],
                              [("I", "laymcur"), ("I", "layoff"), ("I", "layon"), ("I", "layiso"),
                               ("I", "layuniso")],
                              [("I", "layfrz"), ("I", "laythw"), ("I", "laylck"), ("I", "layulk"),
                               ("I", "laymch")]])],
         []),
        ("Blok", [("L", "insert"), ("S", "block"), ("S", "refedit")], ["imageattach", "pdfimport"]),
        ("Özellikler", [("L", "ma"), ("W", "propbar")], ["props", "lts"]),
        ("Yardımcılar", [("L", ["dist", "area", "list", "id"], "Ölç"), ("I", "selall"), ("I", "osnapset"),
                         ("I", "purge")],
         []),
        ("Pano", [("L", "paste"), ("I", "copyclip"), ("I", "cut"), ("I", "copybase")], []),
    ]),
    ("Ekle", [
        ("Blok", [("L", "insert"), ("L", "block"), ("L", "refedit")], []),
        ("İçe aktar", [("L", "pdfimport"), ("L", "imageattach")], []),
        ("Yazı tipi", [("L", "fontimport"), ("S", "tstyle")], []),
    ]),
    ("Açıklama", [
        ("Yazı", [("L", "mtext"), ("L", "text"), ("S", "ed"), ("S", "tstyle")], []),
        ("Ölçüler", [("L", ["dli", "dal"], "Ölçü"), ("S", "dan"), ("S", "dra"), ("S", "ddi"),
                     ("S", "dco"), ("S", "dba"), ("S", "dst")], []),
        ("Kılavuz", [("L", "le")], []),
        ("Tarama", [("L", "hatch")], []),
    ]),
    ("Görünüm", [
        ("Gezinme", [("L", "ze"), ("S", "zw"), ("S", "zp"), ("S", "pan"), ("L", "regen")], []),
        ("Paneller", [("L", "props"), ("S", "cmdtoggle"), ("S", "startpage")], []),
        ("Arayüz", [("L", "classic"), ("L", "language")], []),
    ]),
    ("Çıktı", [
        ("Çizdir", [("L", "plot"), ("L", "pdf")], []),
    ]),
    ("Yönet", [
        ("Ayarlar", [("L", "options"), ("S", "osnapset"), ("S", "purge")], []),
        ("Yardım", [("L", "help"), ("S", "about")], []),
    ]),
]

LARGE_ICON = 32
SMALL_ICON = 16


def _plain(text: str) -> str:
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&").replace("...", "")


def _wrap(text: str) -> str:
    """Two lines for long labels of large buttons (like 'Layer\\nmanager')."""
    t = _plain(text).strip()
    if len(t) <= 9 or " " not in t:
        return t
    mid = len(t) / 2
    i = min((k for k, ch in enumerate(t) if ch == " "), key=lambda k: abs(k - mid))
    return t[:i] + "\n" + t[i + 1:]


class _ActButton(QToolButton):
    """Tool button showing one action of a group; with several actions it is a
    split button whose arrow chooses the variant (the last one is remembered)."""

    def __init__(self, actions, style: str, label: str = None):
        super().__init__()
        self.acts = list(actions)
        self.style_kind = style
        self.label = label
        self.setAutoRaise(True)
        self.current = self.acts[0]
        if style == "L":
            self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            self.setIconSize(QSize(LARGE_ICON, LARGE_ICON))
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        else:
            self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if style == "S" else Qt.ToolButtonIconOnly)
            self.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if len(self.acts) > 1:
            m = QMenu(self)
            for a in self.acts:
                m.addAction(a)
            m.triggered.connect(self._chosen)
            self.setMenu(m)
            self.setPopupMode(QToolButton.MenuButtonPopup)
        self.clicked.connect(lambda: self.current.trigger())
        self._show()

    def _chosen(self, a):
        self.current = a
        self._show()

    def _show(self):
        a = self.current
        self.setIcon(a.icon())
        self.setToolTip(a.toolTip())
        if self.style_kind == "L":
            self.setText(_wrap(tr(self.label) if self.label else a.text()))
            lines = self.text().split("\n")
            w = max(self.fontMetrics().horizontalAdvance(s) for s in lines) + 10
            self.setMinimumWidth(max(44, w + (14 if len(self.acts) > 1 else 0)))
        elif self.style_kind == "S":
            self.setText(_plain(a.text()))


class _Panel(QFrame):
    def __init__(self, title: str, extra_actions):
        super().__init__()
        self.setObjectName("ribbonPanel")
        self.title = tr(title)
        self.all_actions = []
        self.extra = list(extra_actions)
        v = QVBoxLayout(self)
        v.setContentsMargins(3, 2, 3, 0)
        v.setSpacing(0)
        self.content = QWidget()
        self.body = QHBoxLayout(self.content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(1)
        v.addWidget(self.content, 1)
        # collapsed form: one large button opening the panel as a menu
        self.collapsed_btn = QToolButton()
        self.collapsed_btn.setObjectName("ribbonCollapsed")
        self.collapsed_btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.collapsed_btn.setIconSize(QSize(LARGE_ICON, LARGE_ICON))
        self.collapsed_btn.setAutoRaise(True)
        self.collapsed_btn.setPopupMode(QToolButton.InstantPopup)
        self.collapsed_btn.setText(_wrap(self.title) + " ▾")
        self.collapsed_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.collapsed_btn.hide()
        v.addWidget(self.collapsed_btn, 1)
        # title bar; the arrow opens the extra commands (slide-out)
        self.title_btn = QToolButton()
        self.title_btn.setObjectName("ribbonPanelTitle")
        self.title_btn.setAutoRaise(True)
        self.title_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.title_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if self.extra:
            self.title_btn.setText(self.title + " ▾")
            m = QMenu(self)
            for a in self.extra:
                m.addAction(a)
            self.title_btn.setMenu(m)
            self.title_btn.setPopupMode(QToolButton.InstantPopup)
        else:
            self.title_btn.setText(self.title)
        v.addWidget(self.title_btn)
        self._stack = None
        self._stack_n = 0
        self._stack_style = None
        self.collapsed = False

    # ---------------------------------------------------------- building
    def _button(self, style, acts, label=None):
        b = _ActButton(acts, style, label)
        for a in acts:
            if a not in self.all_actions:
                self.all_actions.append(a)
        return b

    def add_large(self, acts, label=None):
        self._stack = None
        self.body.addWidget(self._button("L", acts, label))

    def add_small(self, style, acts):
        if self._stack is None or self._stack_n >= 3 or self._stack_style != style:
            col = QVBoxLayout()
            col.setSpacing(0)
            col.setContentsMargins(0, 0, 0, 0)
            col.setAlignment(Qt.AlignTop)
            self.body.addLayout(col)
            self._stack, self._stack_n, self._stack_style = col, 0, style
        self._stack.addWidget(self._button(style, acts))
        self._stack_n += 1

    def add_widget(self, w):
        self._stack = None
        self.body.addWidget(w)

    def add_rows(self, rows):
        self._stack = None
        col = QVBoxLayout()
        col.setSpacing(1)
        col.setContentsMargins(0, 0, 0, 0)
        col.setAlignment(Qt.AlignTop)
        for row in rows:
            h = QHBoxLayout()
            h.setSpacing(0)
            h.setContentsMargins(0, 0, 0, 0)
            for item in row:
                if isinstance(item, QWidget):
                    h.addWidget(item)
                else:
                    style, acts = item
                    h.addWidget(self._button(style, acts))
            h.addStretch(1)
            col.addLayout(h)
        self.body.addLayout(col)

    def finish(self):
        m = QMenu(self)
        for a in self.all_actions:
            m.addAction(a)
        if self.extra:
            m.addSeparator()
            for a in self.extra:
                m.addAction(a)
        self.collapsed_btn.setMenu(m)
        if self.all_actions:
            self.collapsed_btn.setIcon(self.all_actions[0].icon())

    def set_collapsed(self, on: bool):
        if on == self.collapsed:
            return
        self.collapsed = on
        self.content.setVisible(not on)
        self.title_btn.setVisible(not on)
        self.collapsed_btn.setVisible(on)


class _Page(QScrollArea):
    """Ribbon tab page: collapses panels from the right when it does not fit."""

    def __init__(self, panels):
        super().__init__()
        self.panels = panels
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(2, 1, 2, 1)
        h.setSpacing(2)
        for p in panels:
            h.addWidget(p)
        h.addStretch(1)
        self.setWidget(page)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def _needed(self) -> int:
        lay = self.widget().layout()
        m = lay.contentsMargins()
        w = m.left() + m.right()
        for p in self.panels:
            p.layout().invalidate()
            w += p.sizeHint().width() + lay.spacing()
        return w

    def fit(self):
        avail = self.viewport().width()
        if avail <= 0:
            return
        for p in self.panels:
            p.set_collapsed(False)
        # keep the first two panels (Draw, Modify) open as long as possible
        order = list(reversed(self.panels[2:])) + list(reversed(self.panels[:2]))
        need = self._needed()
        for p in order:
            if need <= avail:
                break
            p.set_collapsed(True)
            n = self._needed()
            if n >= need:  # the collapsed form is not narrower
                p.set_collapsed(False)
            else:
                need = n

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.fit()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.fit()


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
        self.app_btn.setIconSize(QSize(20, 20))
        self.app_btn.setText(" Dosya")
        self.app_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.app_btn.setToolTip("Uygulama menüsü")
        self.app_btn.setPopupMode(QToolButton.InstantPopup)
        self.app_btn.setMenu(self._app_menu())
        self.tabs = QTabWidget()
        self.tabs.setObjectName("ribbonTabs")
        self.tabs.setDocumentMode(True)
        # the application button sits in the tab row like AutoCAD (no empty column)
        self.tabs.setCornerWidget(self.app_btn, Qt.TopLeftCorner)
        lay.addWidget(self.tabs, 1)
        self.pages = []
        for tab_title, panels in LAYOUT:
            built = [self._panel(*p) for p in panels]
            page = _Page(built)
            self.pages.append(page)
            self.tabs.addTab(page, tab_title)
        self.setFixedHeight(132)
        self.setMinimumWidth(200)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def _acts(self, keys):
        acts = self.main._actions
        keys = [keys] if isinstance(keys, str) else keys
        return [acts[k] for k in keys if k in acts]

    def _bar(self, name):
        bar = PropertyBar(self.main, layer=(name == "layerbar"), props=(name == "propbar"),
                          vertical=(name == "propbar"))
        if bar.layer_combo is not None:
            bar.layer_combo.setMinimumWidth(150)
        for cb, w in ((bar.color_combo, 120), (bar.lt_combo, 120), (bar.lw_combo, 120)):
            if cb is not None:
                cb.setMinimumWidth(w)
        self.prop_bars.append(bar)
        return bar

    def _panel(self, title, items, extra):
        panel = _Panel(title, self._acts(extra))
        for item in items:
            kind = item[0]
            if kind == "W":
                panel.add_widget(self._bar(item[1]))
            elif kind == "G":
                rows = []
                for row in item[1]:
                    r = []
                    for sub in row:
                        if sub[0] == "W":
                            r.append(self._bar(sub[1]))
                        else:
                            a = self._acts(sub[1])
                            if a:
                                r.append((sub[0], a))
                    rows.append(r)
                panel.add_rows(rows)
            else:
                a = self._acts(item[1])
                if not a:
                    continue
                if kind == "L":
                    panel.add_large(a, item[2] if len(item) > 2 else None)
                else:
                    panel.add_small(kind, a)
        panel.finish()
        return panel

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
