"""T2D-CAD main window."""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QAction, QKeySequence, QPalette, QColor, QIcon, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QDockWidget, QToolBar, QLabel,
                               QStatusBar, QToolButton, QFileDialog, QMessageBox, QComboBox, QInputDialog,
                               QWidget, QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QStyleFactory)

from ezdxf.math import Vec2

from t2dcad import APP_NAME, __version__, settings
from t2dcad import commands  # noqa: F401  (registers commands)
from t2dcad.docmodel import CadDocument, FileError, DWG_VERSIONS
from t2dcad.doctab import DocumentTab
from t2dcad.engine import fmt
from t2dcad.snap import DEFAULT_MODES
from t2dcad.ui.cmdline import CommandLine
from t2dcad.ui.icons import icon, app_icon, color_icon
from t2dcad.ui.properties import PropertiesPanel
from t2dcad.ui.widgets import ColorCombo, LinetypeCombo, LineweightCombo, aci_qcolor

FILE_FILTER = "Çizimler (*.dwg *.dxf);;AutoCAD Çizimi (*.dwg);;DXF (*.dxf);;Tüm dosyalar (*)"
SAVE_FILTERS = {
    "dwg": "AutoCAD {ver} Çizimi (*.dwg)",
    "dxf": "AutoCAD {ver} DXF (*.dxf)",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1400, 900)
        self.setAcceptDrops(True)
        self.clipboard = None
        self.lwt = settings.get_bool("lwt", False)
        if settings.get_bool("osnap_modes_set", False):
            self.osnap_modes = set(settings.get_list("osnap_modes"))
        else:
            self.osnap_modes = set(DEFAULT_MODES)
        self.osnap_on = settings.get_bool("osnap", True)
        self._untitled = 0

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(lambda i: self.close_tab(self.tabs.widget(i)))
        self.tabs.currentChanged.connect(self._tab_changed)
        self.setCentralWidget(self.tabs)

        self.cmdline = CommandLine(self)
        dock = QDockWidget("Komut Satırı", self)
        dock.setObjectName("cmdline")
        dock.setWidget(self.cmdline)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable |
                         QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.cmd_dock = dock

        self.props = PropertiesPanel(self)
        pdock = QDockWidget("Özellikler", self)
        pdock.setObjectName("props")
        pdock.setWidget(self.props)
        self.addDockWidget(Qt.LeftDockWidgetArea, pdock)
        pdock.setMinimumWidth(250)
        self.props_dock = pdock

        self._actions = {}
        self._build_menus_and_toolbars()
        self._build_statusbar()
        self._build_shortcuts()

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self._restart_autosave()

        state = settings.get("window_state", None)
        geo = settings.get("window_geometry", None)
        if geo is not None:
            try:
                self.restoreGeometry(geo)
            except Exception:
                pass
        if state is not None:
            try:
                self.restoreState(state)
            except Exception:
                pass
        self.cmdline.add_history(f"{APP_NAME} {__version__} - AutoCAD benzeri 2B çizim. Yardım için F1.")

    # ------------------------------------------------------------ helpers
    def current_tab(self) -> DocumentTab | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, DocumentTab) else None

    def manager(self):
        t = self.current_tab()
        return t.manager if t else None

    def bg_color_name(self) -> str:
        return settings.get("bg_color", "#212830")

    def run(self, cmd: str):
        t = self.current_tab()
        if t is None:
            if cmd in ("NEW", "OPEN"):
                self.file_new() if cmd == "NEW" else self.file_open()
            return
        t.canvas.setFocus()
        t.manager.start(cmd)

    # ------------------------------------------------------------ UI build
    def _act(self, key, text, cmd=None, ic=None, shortcut=None, slot=None, checkable=False):
        a = QAction(text, self)
        if ic:
            a.setIcon(icon(ic))
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if checkable:
            a.setCheckable(True)
        if slot is not None:
            a.triggered.connect(slot)
        elif cmd:
            a.triggered.connect(lambda checked=False, c=cmd: self.run(c))
        tip = text.replace("&", "")
        if cmd:
            tip += f"  [{cmd}]"
        a.setToolTip(tip)
        a.setStatusTip(tip)
        self._actions[key] = a
        return a

    def _build_menus_and_toolbars(self):
        A = self._act
        mb = self.menuBar()
        m = mb.addMenu("&Dosya")
        m.addAction(A("new", "&Yeni", None, "new", "Ctrl+N", self.file_new))
        m.addAction(A("open", "&Aç...", None, "open", "Ctrl+O", self.file_open))
        self.recent_menu = m.addMenu("Son kullanılanlar")
        self._fill_recent()
        m.addAction(A("save", "&Kaydet", None, "save", "Ctrl+S", self.file_save))
        m.addAction(A("saveas", "&Farklı kaydet...", None, None, "Ctrl+Shift+S", self.file_save_as))
        m.addSeparator()
        m.addAction(A("plot", "&Çizdir / Yazdır...", "PLOT", "print", "Ctrl+P"))
        m.addAction(A("pdf", "PDF olarak dışa aktar...", "EXPORTPDF"))
        m.addSeparator()
        m.addAction(A("close", "Çizimi kapat", None, None, "Ctrl+F4",
                      lambda: self.close_tab(self.current_tab())))
        m.addAction(A("quit", "Çı&kış", None, None, "Alt+F4", self.close))

        m = mb.addMenu("Dü&zen")
        m.addAction(A("undo", "Geri al", "U", "undo", "Ctrl+Z"))
        m.addAction(A("redo", "Yinele", "REDO", "redo", "Ctrl+Y"))
        m.addSeparator()
        m.addAction(A("cut", "Kes", "CUTCLIP", None, "Ctrl+X"))
        m.addAction(A("copyclip", "Kopyala", "COPYCLIP", None, "Ctrl+C"))
        m.addAction(A("copybase", "Temel noktayla kopyala", "COPYBASE", None, "Ctrl+Shift+C"))
        m.addAction(A("paste", "Yapıştır", "PASTECLIP", None, "Ctrl+V"))
        m.addSeparator()
        m.addAction(A("selall", "Tümünü seç", "SELECTALL", None, "Ctrl+A"))
        m.addAction(A("erase", "Sil", "ERASE", "erase"))

        m = mb.addMenu("&Görünüm")
        m.addAction(A("ze", "Zoom Kapsam", "ZE", "zoomext"))
        m.addAction(A("zw", "Zoom Pencere", "ZW", "zoomwin"))
        m.addAction(A("zp", "Zoom Önceki", "ZP", "zoomprev"))
        m.addAction(A("pan", "Kaydır (Pan)", "PAN", "pan"))
        m.addAction(A("regen", "Yeniden oluştur (Regen)", "REGEN"))
        m.addSeparator()
        m.addAction(self.props_dock.toggleViewAction())
        m.addAction(self.cmd_dock.toggleViewAction())
        self.view_menu = m

        m = mb.addMenu("Çi&z")
        for key, text, cmd, ic in [
            ("line", "Çizgi", "LINE", "line"), ("pline", "Çoklu çizgi", "PLINE", "pline"),
            ("xline", "Yapı çizgisi", "XLINE", "xline"), ("ray", "Işın", "RAY", None), (None,) * 4,
            ("circle", "Çember", "CIRCLE", "circle"), ("arc", "Yay", "ARC", "arc"),
            ("rect", "Dikdörtgen", "RECTANG", "rect"), ("polygon", "Çokgen", "POLYGON", "polygon"),
            ("ellipse", "Elips", "ELLIPSE", "ellipse"), ("donut", "Halka", "DONUT", None),
            ("point", "Nokta", "POINT", "point"), (None,) * 4,
            ("hatch", "Tarama...", "HATCH", "hatch"), ("block", "Blok tanımla...", "BLOCK", "block"),
            ("insert", "Blok ekle...", "INSERT", "insert"), (None,) * 4,
            ("text", "Tek satır yazı", "TEXT", "text"), ("mtext", "Çok satırlı yazı", "MTEXT", "mtext"),
        ]:
            if key is None:
                m.addSeparator()
            else:
                m.addAction(A(key, text, cmd, ic))

        m = mb.addMenu("Ö&lçü")
        for key, text, cmd, ic in [
            ("dli", "Doğrusal", "DIMLINEAR", "dimlinear"), ("dal", "Hizalı", "DIMALIGNED", "dimaligned"),
            ("dan", "Açısal", "DIMANGULAR", "dimangular"), ("dra", "Yarıçap", "DIMRADIUS", "dimradius"),
            ("ddi", "Çap", "DIMDIAMETER", "dimradius"), ("dco", "Devam ettir", "DIMCONTINUE", None),
            ("dba", "Taban çizgisi", "DIMBASELINE", None), ("le", "Kılavuz (Leader)", "QLEADER", "leader"),
            (None,) * 4, ("dst", "Ölçü stili...", "DIMSTYLE", None),
        ]:
            if key is None:
                m.addSeparator()
            else:
                m.addAction(A(key, text, cmd, ic))

        m = mb.addMenu("&Değiştir")
        for key, text, cmd, ic in [
            ("props", "Özellikler", None, "properties"), ("ma", "Özellik eşle", "MATCHPROP", "matchprop"),
            (None,) * 4,
            ("erase2", "Sil", "ERASE", "erase"), ("copy", "Kopyala", "COPY", "copy"),
            ("mirror", "Aynala", "MIRROR", "mirror"), ("offset", "Ofset", "OFFSET", "offset"),
            ("array", "Dizi", "ARRAY", "array"), ("move", "Taşı", "MOVE", "move"),
            ("rotate", "Döndür", "ROTATE", "rotate"), ("scale", "Ölçekle", "SCALE", "scale"),
            ("stretch", "Gerdir", "STRETCH", "stretch"), ("lengthen", "Uzunluk değiştir", "LENGTHEN", None),
            ("trim", "Buda", "TRIM", "trim"), ("extend", "Uzat", "EXTEND", "extend"),
            ("break", "Kır", "BREAK", "break"), ("brp", "Noktadan kır", "BREAKATPOINT", None),
            ("join", "Birleştir", "JOIN", "join"), ("chamfer", "Pah", "CHAMFER", "chamfer"),
            ("fillet", "Kavis (Fillet)", "FILLET", "fillet"), ("explode", "Patlat", "EXPLODE", "explode"),
            (None,) * 4, ("ed", "Yazı düzenle", "TEXTEDIT", None),
        ]:
            if key is None:
                m.addSeparator()
            elif key == "props":
                m.addAction(A(key, text, None, ic, "Ctrl+1", self.toggle_properties))
            else:
                m.addAction(A(key, text, cmd, ic))

        m = mb.addMenu("&Araçlar")
        m.addAction(A("layer", "Katman yöneticisi...", "LAYER", "layer"))
        m.addAction(A("osnapset", "Nesne yakalama ayarları...", "OSNAP"))
        m.addAction(A("dist", "Uzaklık ölç", "DIST", "dist"))
        m.addAction(A("area", "Alan ölç", "AREA"))
        m.addAction(A("list", "Liste", "LIST"))
        m.addAction(A("id", "Nokta koordinatı", "ID"))
        m.addSeparator()
        m.addAction(A("purge", "Temizle (Purge)", "PURGE"))
        m.addAction(A("options", "Seçenekler...", "OPTIONS"))

        m = mb.addMenu("&Yardım")
        m.addAction(A("help", "Komut yardımı", None, None, "F1", self.show_help))
        m.addAction(A("about", f"{APP_NAME} hakkında", None, None, None, self.about))

        # toolbars
        def tb(name, keys, area=Qt.TopToolBarArea, vertical=False):
            t = QToolBar(name, self)
            t.setObjectName(name)
            t.setIconSize(QSize(22, 22))
            for k in keys:
                if k == "|":
                    t.addSeparator()
                else:
                    t.addAction(self._actions[k])
            if vertical:
                t.setOrientation(Qt.Vertical)
            self.addToolBar(area, t)
            return t

        tb("Standart", ["new", "open", "save", "plot", "|", "undo", "redo", "|", "pan", "ze", "zw", "zp",
                        "|", "props", "ma", "layer", "dist"])
        self.addToolBarBreak()
        self._build_layer_toolbar()
        tb("Çizim", ["line", "pline", "xline", "polygon", "rect", "arc", "circle", "ellipse", "point",
                     "hatch", "block", "insert", "text", "mtext"], Qt.LeftToolBarArea, True)
        tb("Değiştir", ["erase", "copy", "mirror", "offset", "array", "move", "rotate", "scale", "stretch",
                        "trim", "extend", "break", "join", "chamfer", "fillet", "explode"],
           Qt.RightToolBarArea, True)
        tb("Ölçü", ["dli", "dal", "dan", "dra", "ddi", "le"], Qt.RightToolBarArea, True)

    def _build_layer_toolbar(self):
        t = QToolBar("Katmanlar", self)
        t.setObjectName("Katmanlar")
        t.setIconSize(QSize(22, 22))
        t.addAction(self._actions["layer"])
        self.layer_combo = QComboBox()
        self.layer_combo.setMinimumWidth(220)
        self.layer_combo.setToolTip("Geçerli katman")
        self.layer_combo.activated.connect(self._layer_combo_changed)
        t.addWidget(self.layer_combo)
        a = QAction(icon("layer"), "Nesnenin katmanını geçerli yap", self)
        a.triggered.connect(lambda: self.run("LAYMCUR"))
        t.addAction(a)
        self.addToolBar(Qt.TopToolBarArea, t)
        t2 = QToolBar("Özellikler", self)
        t2.setObjectName("OzelliklerTB")
        self.color_combo = ColorCombo()
        self.color_combo.setMinimumWidth(130)
        self.color_combo.setToolTip("Renk")
        self.color_combo.changed.connect(lambda v: self._prop_combo("color", v))
        self.lt_combo = QComboBox()
        self.lt_combo.setMinimumWidth(140)
        self.lt_combo.setToolTip("Çizgi tipi")
        self.lt_combo.activated.connect(lambda i: self._prop_combo("linetype", self.lt_combo.currentData()))
        self.lw_combo = LineweightCombo()
        self.lw_combo.setMinimumWidth(120)
        self.lw_combo.setToolTip("Çizgi kalınlığı")
        self.lw_combo.changed.connect(lambda v: self._prop_combo("lineweight", v))
        t2.addWidget(self.color_combo)
        t2.addWidget(self.lt_combo)
        t2.addWidget(self.lw_combo)
        self.addToolBar(Qt.TopToolBarArea, t2)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.coord_label = QLabel("0.0000, 0.0000")
        self.coord_label.setMinimumWidth(220)
        sb.addWidget(self.coord_label)
        self.toggle_buttons = {}
        for key, text, tip in [("grid", "IZGARA", "Izgara (F7)"), ("snapmode", "SNAP", "Adım yakalama (F9)"),
                               ("ortho", "ORTHO", "Dik mod (F8)"), ("polar", "KUTUPSAL", "Kutupsal izleme (F10)"),
                               ("osnap", "OSNAP", "Nesne yakalama (F3) - sağ tık: ayarlar"),
                               ("lwt", "KALINLIK", "Çizgi kalınlığını göster")]:
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.clicked.connect(lambda checked, k=key: self.toggle(k, checked))
            if key == "osnap":
                b.setContextMenuPolicy(Qt.CustomContextMenu)
                b.customContextMenuRequested.connect(lambda _: self.osnap_settings())
            sb.addPermanentWidget(b)
            self.toggle_buttons[key] = b
        self.model_label = QLabel(" MODEL ")
        sb.addPermanentWidget(self.model_label)
        self._sync_toggles()

    def _build_shortcuts(self):
        for key, name in (("F3", "osnap"), ("F7", "grid"), ("F8", "ortho"), ("F9", "snapmode"),
                          ("F10", "polar"), ("F12", None)):
            if name is None:
                continue
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda n=name: self.toggle(n))
        sc = QShortcut(QKeySequence("F2"), self)
        sc.activated.connect(self.cmdline.show_history_window)
        sc = QShortcut(QKeySequence("Ctrl+9"), self)
        sc.activated.connect(lambda: self.cmd_dock.setVisible(not self.cmd_dock.isVisible()))

    # ------------------------------------------------------------ toggles
    def toggle(self, key, value=None):
        tab = self.current_tab()
        if key == "osnap":
            self.osnap_on = (not self.osnap_on) if value is None else bool(value)
            settings.set("osnap", self.osnap_on)
            for t in self._tabs():
                t.snap.enabled = self.osnap_on
            self.cmdline.add_history(f"<Nesne yakalama {'açık' if self.osnap_on else 'kapalı'}>")
        elif key == "lwt":
            self.lwt = (not self.lwt) if value is None else bool(value)
            settings.set("lwt", self.lwt)
            for t in self._tabs():
                t.regen()
        else:
            if tab is None:
                self._sync_toggles()
                return
            c = tab.canvas
            cur = getattr(c, key if key != "snapmode" else "snap_grid")
            new = (not cur) if value is None else bool(value)
            for t in self._tabs():
                setattr(t.canvas, key if key != "snapmode" else "snap_grid", new)
                if key == "ortho" and new:
                    t.canvas.polar = False
                if key == "polar" and new:
                    t.canvas.ortho = False
                t.canvas.invalidate()
            settings.set(key, new)
            if key in ("ortho", "polar"):
                settings.set("polar" if key == "ortho" else "ortho", False)
            names = {"grid": "Izgara", "snapmode": "Snap", "ortho": "Ortho", "polar": "Kutupsal"}
            self.cmdline.add_history(f"<{names[key]} {'açık' if new else 'kapalı'}>")
        self._sync_toggles()

    def _sync_toggles(self):
        tab = self.current_tab()
        vals = {
            "osnap": self.osnap_on, "lwt": self.lwt,
            "grid": tab.canvas.grid if tab else settings.get_bool("grid"),
            "snapmode": tab.canvas.snap_grid if tab else settings.get_bool("snapmode"),
            "ortho": tab.canvas.ortho if tab else settings.get_bool("ortho"),
            "polar": tab.canvas.polar if tab else settings.get_bool("polar"),
        }
        for k, b in self.toggle_buttons.items():
            b.blockSignals(True)
            b.setChecked(bool(vals[k]))
            b.blockSignals(False)
            b.setStyleSheet("QToolButton{color:#7fb8ff;font-weight:bold;}" if vals[k] else
                            "QToolButton{color:#888;}")

    def _tabs(self):
        return [self.tabs.widget(i) for i in range(self.tabs.count())
                if isinstance(self.tabs.widget(i), DocumentTab)]

    # ------------------------------------------------------------ tabs/documents
    def add_document(self, cad_doc: CadDocument) -> DocumentTab:
        tab = DocumentTab(self, cad_doc)
        if not cad_doc.path:
            self._untitled += 1
            tab.untitled_name = f"Çizim{self._untitled}.dwg"
        else:
            tab.untitled_name = ""
        tab.canvas.cursor_moved.connect(self._cursor_moved)
        i = self.tabs.addTab(tab, "")
        self.tabs.setCurrentIndex(i)
        self.update_tab_title(tab)
        QTimer.singleShot(0, lambda: (tab.canvas.zoom_extents(push=False), tab.canvas.setFocus()))
        self.refresh_layer_combo()
        return tab

    def tab_name(self, tab) -> str:
        return Path(tab.doc.path).name if tab.doc.path else tab.untitled_name

    def update_tab_title(self, tab):
        i = self.tabs.indexOf(tab)
        if i < 0:
            return
        name = self.tab_name(tab)
        self.tabs.setTabText(i, name + (" *" if tab.doc.modified else ""))
        self.tabs.setTabToolTip(i, tab.doc.path or name)
        if tab is self.current_tab():
            self.setWindowTitle(f"{APP_NAME} - [{name}{' *' if tab.doc.modified else ''}]")

    def _tab_changed(self, i):
        tab = self.current_tab()
        if tab:
            self.update_tab_title(tab)
            self.cmdline.set_prompt(tab.manager.prompt_text())
            tab.canvas.setFocus()
        else:
            self.setWindowTitle(APP_NAME)
            self.cmdline.set_prompt("Komut:")
        self.refresh_layer_combo()
        self._sync_toggles()
        self.on_selection_changed()

    def file_new(self):
        doc = CadDocument.new()
        doc.save_version = settings.get("save_version", "R2018")
        tab = self.add_document(doc)
        return tab

    def file_open(self, path: str | None = None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Dosya seçin", settings.get("last_dir", ""), FILE_FILTER)
            if not path:
                return
        path = os.path.abspath(path)
        for t in self._tabs():
            if t.doc.path and os.path.abspath(t.doc.path) == path:
                self.tabs.setCurrentWidget(t)
                return
        settings.set("last_dir", os.path.dirname(path))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            doc = CadDocument.open(path)
        except FileError as ex:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Açma hatası", str(ex))
            return
        except Exception as ex:
            QApplication.restoreOverrideCursor()
            traceback.print_exc()
            QMessageBox.critical(self, "Açma hatası", f"Dosya açılamadı:\n{ex}")
            return
        try:
            cur = self.current_tab()
            # replace an untouched empty drawing like AutoCAD does
            if cur and not cur.doc.path and not cur.doc.modified and len(cur.doc.msp) == 0:
                self.tabs.removeTab(self.tabs.indexOf(cur))
                cur.deleteLater()
            self.add_document(doc)
        finally:
            QApplication.restoreOverrideCursor()
        self._add_recent(path)
        self.cmdline.add_history(f'"{path}" açıldı ({len(doc.msp)} nesne, {doc.doc.acad_release}).')

    def file_save(self, tab=None) -> bool:
        tab = tab or self.current_tab()
        if tab is None:
            return False
        if not tab.doc.path:
            return self.file_save_as(tab)
        return self._save(tab, tab.doc.path, tab.doc.save_version)

    def file_save_as(self, tab=None) -> bool:
        tab = tab or self.current_tab()
        if tab is None:
            return False
        filters = []
        keys = []
        for ext in ("dwg", "dxf"):
            for ver, txt in DWG_VERSIONS.items():
                filters.append(SAVE_FILTERS[ext].format(ver=txt.split("/")[0].replace("AutoCAD ", "")))
                keys.append((ext, ver))
        cur_ext = "dwg" if (not tab.doc.path or tab.doc.file_format == "dwg") else "dxf"
        cur_ver = tab.doc.save_version if tab.doc.save_version in DWG_VERSIONS else "R2018"
        sel = filters[keys.index((cur_ext, cur_ver))]
        start = tab.doc.path or os.path.join(settings.get("last_dir", os.path.expanduser("~")), tab.untitled_name)
        path, chosen = QFileDialog.getSaveFileName(self, "Çizimi farklı kaydet", start, ";;".join(filters), sel)
        if not path:
            return False
        ext, ver = keys[filters.index(chosen)] if chosen in filters else (cur_ext, cur_ver)
        if Path(path).suffix.lower() not in (".dwg", ".dxf"):
            path += "." + ext
        elif Path(path).suffix.lower() != "." + ext:
            ext = Path(path).suffix.lower()[1:]
        settings.set("last_dir", os.path.dirname(path))
        ok = self._save(tab, path, ver)
        if ok:
            self._add_recent(path)
        return ok

    def _save(self, tab, path, version) -> bool:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            tab.doc.save(path, version)
        except FileError as ex:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Kaydetme hatası", str(ex))
            return False
        except Exception as ex:
            QApplication.restoreOverrideCursor()
            traceback.print_exc()
            QMessageBox.critical(self, "Kaydetme hatası", f"Kaydedilemedi:\n{ex}")
            return False
        QApplication.restoreOverrideCursor()
        self.update_tab_title(tab)
        self.cmdline.add_history(f'Kaydedildi: "{path}" ({DWG_VERSIONS.get(version, version)})')
        return True

    def maybe_save(self, tab) -> bool:
        if not tab.doc.modified:
            return True
        r = QMessageBox.question(self, APP_NAME, f"{self.tab_name(tab)} çizimindeki değişiklikler kaydedilsin mi?",
                                 QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Yes:
            return self.file_save(tab)
        return True

    def close_tab(self, tab):
        if tab is None:
            return
        if tab.manager.active:
            tab.manager.cancel(quiet=True)
        if not self.maybe_save(tab):
            return
        self.tabs.removeTab(self.tabs.indexOf(tab))
        if self.clipboard and self.clipboard[0] is tab:
            pass
        tab.deleteLater()
        self._tab_changed(self.tabs.currentIndex())

    def closeEvent(self, ev):
        for t in self._tabs():
            self.tabs.setCurrentWidget(t)
            if not self.maybe_save(t):
                ev.ignore()
                return
        settings.set("window_state", self.saveState())
        settings.set("window_geometry", self.saveGeometry())
        ev.accept()

    # ------------------------------------------------------------ recent files
    def _add_recent(self, path):
        lst = [p for p in settings.get_list("recent") if p != path]
        lst.insert(0, path)
        settings.set("recent", lst[:10])
        self._fill_recent()

    def _fill_recent(self):
        self.recent_menu.clear()
        for p in settings.get_list("recent"):
            a = self.recent_menu.addAction(p)
            a.triggered.connect(lambda checked=False, p=p: self.file_open(p))
        if not settings.get_list("recent"):
            self.recent_menu.addAction("(boş)").setEnabled(False)

    # ------------------------------------------------------------ autosave
    def _restart_autosave(self):
        m = settings.get_int("autosave_min", 10)
        self.autosave_timer.stop()
        if m > 0:
            self.autosave_timer.start(m * 60 * 1000)

    def autosave(self):
        d = Path(tempfile.gettempdir()) / "T2D-CAD" / "autosave"
        d.mkdir(parents=True, exist_ok=True)
        for t in self._tabs():
            if not t.doc.modified or t.manager.active:
                continue
            name = Path(self.tab_name(t)).stem + "_otomatik.dxf"
            try:
                t.doc.doc.saveas(str(d / name))
                self.statusBar().showMessage(f"Otomatik kaydedildi: {d / name}", 5000)
            except Exception as ex:
                print("autosave failed", ex)

    # ------------------------------------------------------------ drag & drop
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        for url in ev.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith((".dwg", ".dxf")):
                self.file_open(p)

    # ------------------------------------------------------------ status / layer bar
    def _cursor_moved(self, x, y):
        self.coord_label.setText(f"{x:.4f}, {y:.4f}, 0.0000")

    def refresh_layer_combo(self):
        tab = self.current_tab()
        cb = self.layer_combo
        cb.blockSignals(True)
        cb.clear()
        self.lt_combo.clear()
        if tab is None:
            cb.blockSignals(False)
            return
        dxf = tab.doc.doc
        for l in sorted(dxf.layers, key=lambda l: (l.dxf.name != "0", l.dxf.name.lower())):
            state = ("" if l.is_on() else " (kapalı)") + (" (donuk)" if l.is_frozen() else "") + \
                    (" (kilitli)" if l.is_locked() else "")
            cb.addItem(color_icon(aci_qcolor(abs(l.dxf.color))), l.dxf.name + state, l.dxf.name)
        i = cb.findData(tab.doc.current_layer)
        cb.setCurrentIndex(max(0, i))
        cb.blockSignals(False)
        self.lt_combo.addItem("KatmanaGöre", "BYLAYER")
        self.lt_combo.addItem("BlokaGöre", "BYBLOCK")
        for lt in dxf.linetypes:
            if lt.dxf.name.upper() not in ("BYLAYER", "BYBLOCK"):
                self.lt_combo.addItem(lt.dxf.name, lt.dxf.name)
        self._sync_prop_combos()

    def _layer_combo_changed(self, i):
        tab = self.current_tab()
        if tab is None:
            return
        name = self.layer_combo.itemData(i)
        if tab.canvas.selection:
            ents = tab.ctx.entities(tab.canvas.selection)
            tab.doc.begin("LAYER CHANGE")
            new = [tab.doc.modify(e, lambda c: c.dxf.set("layer", name)) for e in ents]
            tab.doc.commit()
            tab.canvas.set_selection([e.dxf.handle for e in new])
        else:
            layer = tab.doc.doc.layers.get(name)
            if layer is not None and layer.is_frozen():
                QMessageBox.warning(self, "Katman", "Donmuş katman geçerli yapılamaz.")
            else:
                tab.doc.current_layer = name
        tab.canvas.setFocus()
        self.refresh_layer_combo()

    def _prop_combo(self, what, value):
        tab = self.current_tab()
        if tab is None:
            return
        if tab.canvas.selection:
            ents = tab.ctx.entities(tab.canvas.selection)
            tab.doc.begin("CHPROP")
            new = []
            for e in ents:
                def fn(c):
                    if (what == "color" and value == 256) or (what == "linetype" and str(value).upper() == "BYLAYER"):
                        c.dxf.discard(what)
                    else:
                        c.dxf.set(what, value)
                new.append(tab.doc.modify(e, fn))
            tab.doc.commit()
            tab.canvas.set_selection([e.dxf.handle for e in new])
        else:
            h = tab.doc.doc.header
            key = {"color": "$CECOLOR", "linetype": "$CELTYPE", "lineweight": "$CELWEIGHT"}[what]
            h[key] = value
        tab.canvas.setFocus()
        self.on_selection_changed()

    def _sync_prop_combos(self):
        tab = self.current_tab()
        if tab is None:
            return
        ents = tab.ctx.entities(tab.canvas.selection)
        h = tab.doc.doc.header
        if ents:
            e = ents[0]
            color = e.dxf.get("color", 256)
            lt = e.dxf.get("linetype", "BYLAYER")
            lw = e.dxf.get("lineweight", -1)
            layer = e.dxf.layer
        else:
            color = h.get("$CECOLOR", 256)
            lt = h.get("$CELTYPE", "BYLAYER")
            lw = h.get("$CELWEIGHT", -1)
            layer = tab.doc.current_layer
        self.color_combo.set_value(color)
        self.lw_combo.set_value(lw)
        for k in range(self.lt_combo.count()):
            if str(self.lt_combo.itemData(k)).upper() == str(lt).upper():
                self.lt_combo.setCurrentIndex(k)
                break
        i = self.layer_combo.findData(layer)
        if i >= 0:
            self.layer_combo.blockSignals(True)
            self.layer_combo.setCurrentIndex(i)
            self.layer_combo.blockSignals(False)

    def on_selection_changed(self):
        tab = self.current_tab()
        if self.props_dock.isVisible():
            self.props.refresh(tab)
        self._sync_prop_combos()

    def update_ui_state(self):
        self.on_selection_changed()

    # ------------------------------------------------------------ dialogs
    def show_properties(self):
        self.props_dock.show()
        self.props_dock.raise_()
        self.props.refresh(self.current_tab())

    def toggle_properties(self):
        if self.props_dock.isVisible():
            self.props_dock.hide()
        else:
            self.show_properties()

    def layer_dialog(self):
        tab = self.current_tab()
        if tab is None:
            return
        from t2dcad.ui.layers import LayerDialog
        LayerDialog(tab, self).exec()
        tab.regen()
        self.refresh_layer_combo()

    def osnap_settings(self):
        from t2dcad.ui.dialogs import OsnapDialog
        tab = self.current_tab()
        inc = tab.canvas.polar_inc if tab else settings.get_float("polar_inc", 45.0)
        dlg = OsnapDialog(self.osnap_modes, self.osnap_on, inc, self)
        if dlg.exec():
            modes, on, inc = dlg.result_values()
            self.osnap_modes = modes
            self.osnap_on = on
            settings.set("osnap_modes", sorted(modes))
            settings.set("osnap_modes_set", True)
            settings.set("osnap", on)
            settings.set("polar_inc", inc)
            for t in self._tabs():
                t.snap.modes = set(modes)
                t.snap.enabled = on
                t.canvas.polar_inc = inc
            self._sync_toggles()

    def options_dialog(self):
        from t2dcad.ui.dialogs import OptionsDialog
        dlg = OptionsDialog(self)
        if dlg.exec():
            dlg.save()
            for t in self._tabs():
                c = t.canvas
                c.bg_color = QColor(settings.get("bg_color", "#212830"))
                c.cursor_size = settings.get_int("cursor_size", 5)
                c.pickbox = settings.get_int("pickbox", 5)
                c.aperture = settings.get_int("aperture", 10)
                c.grid_unit = settings.get_float("grid_unit", 10.0)
                t.regen()
            self._restart_autosave()

    def edit_text(self, tab, e):
        t = e.dxftype()
        if t == "MTEXT":
            content, h = self.ask_mtext(e.text.replace("\\P", "\n"), e.dxf.char_height)
            if content is None:
                return
            tab.doc.modify(e, lambda c: (setattr(c, "text", content.replace("\n", "\\P")),
                                         c.dxf.set("char_height", h)))
        else:
            old = e.dxf.text if t != "ATTDEF" else e.dxf.tag
            txt, ok = QInputDialog.getText(self, "Yazıyı düzenle", "Yazı:", text=old)
            if ok and txt != old:
                tab.doc.modify(e, lambda c: c.dxf.set("text" if t != "ATTDEF" else "tag", txt))
        tab.canvas.clear_selection()

    def ask_mtext(self, text, height):
        from t2dcad.ui.dialogs import MTextDialog
        dlg = MTextDialog(text, height, self)
        if dlg.exec():
            return dlg.edit.toPlainText(), dlg.height.value()
        return None, height

    def ask_text(self, title, label, default=""):
        txt, ok = QInputDialog.getText(self, title, label, text=default)
        return txt if ok else None

    def confirm(self, msg) -> bool:
        return QMessageBox.question(self, APP_NAME, msg) == QMessageBox.Yes

    def insert_dialog(self, tab):
        from t2dcad.ui.dialogs import InsertDialog
        dlg = InsertDialog(self, tab, self)
        if dlg.exec():
            return dlg.result_values()
        return None

    def hatch_dialog(self, tab):
        from t2dcad.ui.dialogs import HatchDialog
        dlg = HatchDialog(tab.ctx.get("hatch_opts"), self)
        if dlg.exec():
            return dlg.result_values()
        return None

    def dimstyle_dialog(self, tab):
        from t2dcad.ui.dialogs import DimStyleDialog
        dlg = DimStyleDialog(tab, self)
        if dlg.exec():
            dlg.apply()

    def show_help(self):
        from t2dcad.ui.dialogs import HELP_HTML
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{APP_NAME} Yardım")
        dlg.resize(820, 640)
        v = QVBoxLayout(dlg)
        b = QTextBrowser()
        b.setHtml(HELP_HTML)
        v.addWidget(b)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        dlg.exec()

    def about(self):
        QMessageBox.about(self, APP_NAME,
                          f"<b>{APP_NAME} {__version__}</b><br>AutoCAD benzeri 2B çizim programı.<br><br>"
                          "DXF: ezdxf kütüphanesi · DWG: ODA File Converter (ücretsiz)<br>"
                          "Arayüz: Qt (PySide6)")

    # ------------------------------------------------------------ clipboard / import
    def set_clipboard(self, tab, ents, base: Vec2):
        self.clipboard = (tab, tab.doc.doc, list(ents), base)

    def import_entities(self, tab, src_doc, ents, m):
        from ezdxf.addons import Importer
        msp = tab.doc.msp
        before = {id(e) for e in msp}
        imp = Importer(src_doc, tab.doc.doc)
        imp.import_entities(ents, target_layout=msp)
        imp.finalize()
        new = [e for e in msp if id(e) not in before]
        tab.doc.begin("PASTE")
        for e in new:
            try:
                e.transform(m)
            except Exception:
                pass
            tab.doc.added(e)
        tab.doc.commit()
        return new

    def import_file_as_block(self, tab, path) -> str | None:
        from ezdxf.addons import Importer
        try:
            src = CadDocument.open(path).doc
        except Exception as ex:
            QMessageBox.critical(self, "Blok ekle", str(ex))
            return None
        dxf = tab.doc.doc
        base = Path(path).stem
        name = base
        k = 1
        while name in dxf.blocks:
            k += 1
            name = f"{base}_{k}"
        blk = dxf.blocks.new(name)
        try:
            ib = src.header.get("$INSBASE", (0, 0, 0))
            blk.block.dxf.base_point = ib
        except Exception:
            pass
        imp = Importer(src, dxf)
        imp.import_modelspace(target_layout=blk)
        imp.finalize()
        tab.doc.layers_changed.emit()
        return name


def apply_dark_theme(app: QApplication):
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    base = QColor(43, 48, 56)
    alt = QColor(52, 58, 67)
    text = QColor(225, 228, 232)
    pal.setColor(QPalette.Window, base)
    pal.setColor(QPalette.WindowText, text)
    pal.setColor(QPalette.Base, QColor(33, 37, 43))
    pal.setColor(QPalette.AlternateBase, alt)
    pal.setColor(QPalette.ToolTipBase, QColor(60, 66, 76))
    pal.setColor(QPalette.ToolTipText, text)
    pal.setColor(QPalette.Text, text)
    pal.setColor(QPalette.Button, alt)
    pal.setColor(QPalette.ButtonText, text)
    pal.setColor(QPalette.BrightText, QColor(255, 80, 80))
    pal.setColor(QPalette.Highlight, QColor(42, 110, 200))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.Link, QColor(110, 170, 255))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 120, 120))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
    pal.setColor(QPalette.PlaceholderText, QColor(130, 135, 140))
    app.setPalette(pal)
    app.setStyleSheet("""
        QToolBar { spacing: 2px; border: none; }
        QDockWidget::title { padding: 3px; background: #343a43; }
        QTabBar::tab { padding: 5px 14px; }
        QStatusBar QToolButton { padding: 1px 6px; }
    """)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("T2D.T2D-CAD")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("T2D")
    apply_dark_theme(app)
    w = MainWindow()
    w.show()
    files = [a for a in sys.argv[1:] if a.lower().endswith((".dwg", ".dxf"))]
    if files:
        for f in files:
            w.file_open(f)
    else:
        w.file_new()
    sys.exit(app.exec())
