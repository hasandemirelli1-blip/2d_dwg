"""One open drawing: document + renderer + canvas + command manager."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QMenu, QFrame, QLabel, QPushButton

from ezdxf.math import Vec2

from t2dcad.canvas import CadCanvas
from t2dcad.context import CommandContext
from t2dcad.docmodel import CadDocument
from t2dcad.engine import CommandManager, GetPoint, GetString, CommandDef
from t2dcad.render import Renderer
from t2dcad.snap import SnapEngine
from t2dcad import grips, geom


class DocumentTab(QWidget):
    def __init__(self, main, doc: CadDocument):
        super().__init__()
        self.main = main
        self.doc = doc
        self.renderer = Renderer(doc, main.bg_color_name())
        self.renderer.show_lineweight = main.lwt
        self.snap = SnapEngine(doc, self.renderer)
        self.snap.modes = set(main.osnap_modes)
        self.snap.enabled = main.osnap_on
        self.ctx = CommandContext(self)
        self.manager = CommandManager(self.ctx)
        self.canvas = CadCanvas(self)
        self.refedit = None  # RefEditSession while a block is edited in place
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.refedit_bar = self._make_refedit_bar()
        lay.addWidget(self.refedit_bar)
        lay.addWidget(self.canvas)
        self._layer_cache = None
        doc.changed.connect(self.on_doc_changed)
        doc.layers_changed.connect(self.on_layers_changed)
        doc.modified_changed.connect(lambda m: main.update_tab_title(self))
        self.renderer.regen()
        self.canvas.selection_changed.connect(main.on_selection_changed)

    # ------------------------------------------------------------ doc events
    def on_doc_changed(self, added, removed, regen):
        if regen:
            self.regen()
            return
        self.renderer.remove(removed)
        self.renderer.add(added)
        self.snap.invalidate([e.dxf.handle for e in removed + added])
        self.canvas.prune_selection()
        self.canvas.invalidate()
        self.main.on_selection_changed()

    def on_layers_changed(self):
        self._layer_cache = None
        # new render context: layer properties are cached by ezdxf
        self.renderer.frontend = None
        self.main.refresh_layer_combo()

    def regen(self):
        self._layer_cache = None
        self.renderer.background = self.main.bg_color_name()
        self.renderer.show_lineweight = self.main.lwt
        self.renderer.regen()
        self.snap.invalidate()
        self.canvas.prune_selection()
        self.canvas.invalidate()

    # ------------------------------------------------------------ layers
    def _layers(self):
        if self._layer_cache is None:
            self._layer_cache = {l.dxf.name.lower(): l for l in self.doc.doc.layers}
        return self._layer_cache

    def is_locked(self, handle: str) -> bool:
        e = self.doc.entity_by_handle(handle)
        if e is None:
            return True
        r = self.refedit
        if r is not None and not r.adding and not r.is_working(handle):
            return True
        lay = self._layers().get(e.dxf.layer.lower())
        return bool(lay and lay.is_locked())

    def is_visible(self, e) -> bool:
        lay = self._layers().get(e.dxf.layer.lower())
        if lay is None:
            return True
        return lay.is_on() and not lay.is_frozen()

    # ------------------------------------------------------------ keyboard
    def key_press(self, ev):
        self.main.cmdline.handle_key(ev)

    # ------------------------------------------------------------ grips
    def start_grip_edit(self, handle, gp: Vec2, key):
        e = self.doc.entity_by_handle(handle)
        if e is None:
            return
        tab = self
        self.ctx.last_point = gp

        def grip_cmd(ctx):
            def preview(p):
                if e.dxftype() in ("LINE", "CIRCLE", "ARC", "LWPOLYLINE"):
                    c = e.copy()
                    grips.apply_grip(c, key, gp, p)
                    return [("prims", geom.entity_prims(c)), ("dline", gp, p)]
                return [("dline", gp, p)]
            p = yield GetPoint("** GERDİR ** Gerdirme noktasını belirtin", base=gp, preview=preview)
            if p is None:
                return

            def fn(c):
                grips.apply_grip(c, key, gp, p)
            new = ctx.doc.modify(e, fn)
            if new.dxftype() == "DIMENSION":
                grips.rerender_dimension(ctx.dxf, new)
                ctx.doc.changed.emit([new], [], False)
            tab.canvas.set_selection([new.dxf.handle])
        self.run_function("GRIP", grip_cmd)

    def run_function(self, name, func, undoable=True):
        """Run an ad-hoc command generator."""
        cd = CommandDef(name, func, (), False, False, False, undoable)
        keep = list(self.canvas.selection)
        mgr = self.manager
        last = mgr.last_command
        mgr.start_def(cd, echo=False)
        mgr.last_command = last
        if mgr.active and name == "GRIP":
            # keep the selection visible while stretching
            self.canvas.selection = keep
            self.canvas.selection_dirty()

    # ------------------------------------------------------------ editing
    def edit_entity(self, handle):
        e = self.doc.entity_by_handle(handle)
        if e is None:
            return
        if e.dxftype() in ("TEXT", "MTEXT", "ATTDEF"):
            self.main.edit_text(self, e)
        elif e.dxftype() == "INSERT" and self.refedit is None:
            self.canvas.set_selection([handle])
            self.manager.start("REFEDIT")
        else:
            self.canvas.set_selection([handle])
            self.main.show_properties()

    # ------------------------------------------------------------ in-place block editing
    def _make_refedit_bar(self):
        bar = QFrame()
        bar.setObjectName("refeditBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 3, 8, 3)
        self.refedit_label = QLabel()
        h.addWidget(self.refedit_label)
        h.addStretch(1)
        for text, cmd in (("Bloğa ekle", "REFADD"), ("Bloktan çıkar", "REFREMOVE"),
                          ("Değişiklikleri kaydet", "REFCLOSE_SAVE"), ("Vazgeç", "REFCLOSE_DISCARD")):
            b = QPushButton(text)
            b.clicked.connect(lambda checked=False, c=cmd: (self.canvas.setFocus(), self.manager.start(c)))
            h.addWidget(b)
        bar.setFixedHeight(40)
        bar.hide()
        return bar

    def refedit_changed(self):
        r = self.refedit
        if r is None:
            self.refedit_bar.hide()
        else:
            self.refedit_label.setText(f"<b>Blok düzenleniyor:</b> {r.name}  —  soluk nesneler bloğa dahil değil. "
                                       f"Çizdiğiniz yeni nesneler bloğa eklenir.")
            self.refedit_bar.show()
        self.canvas.invalidate()

    # ------------------------------------------------------------ menus
    def context_menu(self, gpos):
        m = QMenu(self)
        mgr = self.manager
        if mgr.last_command:
            m.addAction(f"Tekrarla {mgr.last_command}", mgr.repeat)
            m.addSeparator()
        if self.canvas.selection:
            for label, cmd in (("Sil", "ERASE"), ("Taşı", "MOVE"), ("Kopyala", "COPY"),
                               ("Döndür", "ROTATE"), ("Ölçekle", "SCALE"), ("Aynala", "MIRROR"),
                               ("Patlat", "EXPLODE")):
                m.addAction(label, lambda c=cmd: mgr.start(c))
            m.addSeparator()
            m.addAction("Pano: Kopyala (Ctrl+C)", lambda: mgr.start("COPYCLIP"))
            m.addAction("Seçimi kaldır", self.canvas.clear_selection)
            m.addAction("Özellikler (Ctrl+1)", self.main.show_properties)
        else:
            m.addAction("Geri al (Ctrl+Z)", lambda: mgr.start("U"))
            m.addAction("Yinele (Ctrl+Y)", lambda: mgr.start("REDO"))
            m.addSeparator()
            m.addAction("Kaydır (Pan)", lambda: mgr.start("PAN"))
            m.addAction("Zoom Kapsam", lambda: mgr.start("ZE"))
            m.addAction("Yapıştır (Ctrl+V)", lambda: mgr.start("PASTECLIP"))
        m.exec(gpos)

    def osnap_menu(self, gpos):
        from t2dcad.geom import SNAP_NAMES
        m = QMenu(self)
        for kind, name in SNAP_NAMES.items():
            m.addAction(name, lambda k=kind: self._set_override({k}))
        m.addSeparator()
        m.addAction("Referanstan (From)", lambda: self.manager.start_special("from"))
        m.addAction("İki nokta ortası (M2P)", lambda: self.manager.start_special("m2p"))
        m.addSeparator()
        m.addAction("Hiçbiri (None)", lambda: self._set_override(set()))
        m.addAction("Nesne yakalama ayarları...", self.main.osnap_settings)
        m.exec(gpos)

    def _set_override(self, s):
        self.canvas.osnap_override = s
