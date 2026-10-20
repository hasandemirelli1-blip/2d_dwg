"""Properties palette (Ctrl+1)."""
from __future__ import annotations

import math

from ezdxf.math import Vec2, Vec3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, QLabel,
                               QScrollArea, QGroupBox, QPlainTextEdit, QCheckBox)

from t2dcad import geom
from t2dcad.engine import fmt
from t2dcad.ui.widgets import ColorCombo, LinetypeCombo, LineweightCombo

TYPE_NAMES = {
    "LINE": "Çizgi", "CIRCLE": "Çember", "ARC": "Yay", "LWPOLYLINE": "Çoklu çizgi", "POLYLINE": "Çoklu çizgi (2B/3B)",
    "TEXT": "Yazı", "MTEXT": "Çok satırlı yazı", "INSERT": "Blok referansı", "DIMENSION": "Ölçü",
    "HATCH": "Tarama", "ELLIPSE": "Elips", "SPLINE": "Spline", "POINT": "Nokta", "XLINE": "Yapı çizgisi",
    "RAY": "Işın", "LEADER": "Kılavuz", "SOLID": "Katı",
}


class PropertiesPanel(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.tab = None
        self._ents = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        self.header = QComboBox()
        outer.addWidget(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)
        self.body = QWidget()
        self.scroll.setWidget(self.body)
        self._lay = QVBoxLayout(self.body)
        self._lay.setAlignment(Qt.AlignTop)

    # ------------------------------------------------------------ building
    def _clear(self):
        while self._lay.count():
            it = self._lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def refresh(self, tab):
        self.tab = tab
        self._clear()
        self.header.clear()
        if tab is None:
            return
        ents = tab.ctx.entities(tab.canvas.selection)
        self._ents = ents
        if not ents:
            self.header.addItem("Seçim yok")
            self._build_general(None)
            return
        types = sorted({e.dxftype() for e in ents})
        if len(types) == 1:
            self.header.addItem(f"{TYPE_NAMES.get(types[0], types[0])} ({len(ents)})")
        else:
            self.header.addItem(f"Tümü ({len(ents)})")
        self._build_general(ents)
        if len(ents) == 1:
            self._build_geometry(ents[0])

    def _group(self, title):
        g = QGroupBox(title)
        f = QFormLayout(g)
        f.setLabelAlignment(Qt.AlignLeft)
        self._lay.addWidget(g)
        return f

    def _common(self, ents, name, default=None):
        vals = {e.dxf.get(name, default) for e in ents}
        return vals.pop() if len(vals) == 1 else None

    def _build_general(self, ents):
        f = self._group("Genel")
        doc = self.tab.doc
        dxf = doc.doc
        color = ColorCombo()
        layer = QComboBox()
        for l in sorted(dxf.layers, key=lambda l: l.dxf.name.lower()):
            layer.addItem(l.dxf.name)
        lt = LinetypeCombo(dxf)
        lw = LineweightCombo()
        lts = QLineEdit()
        if ents is None:
            h = dxf.header
            color.set_value(h.get("$CECOLOR", 256))
            layer.setCurrentText(doc.current_layer)
            lt.set_value(h.get("$CELTYPE", "BYLAYER"))
            lw.set_value(h.get("$CELWEIGHT", -1))
            lts.setText(fmt(h.get("$CELTSCALE", 1.0)))
            color.changed.connect(lambda v: self._set_header("$CECOLOR", v))
            layer.activated.connect(lambda i: setattr(doc, "current_layer", layer.currentText()))
            lt.changed.connect(lambda v: self._set_header("$CELTYPE", v))
            lw.changed.connect(lambda v: self._set_header("$CELWEIGHT", v))
            lts.editingFinished.connect(lambda: self._set_header("$CELTSCALE", _num(lts.text(), 1.0)))
        else:
            c = self._common(ents, "color", 256)
            if c is not None:
                color.set_value(c)
            else:
                color.setCurrentIndex(-1)
            ln = self._common(ents, "layer", "0")
            layer.setCurrentText(ln if ln is not None else "")
            if ln is None:
                layer.setCurrentIndex(-1)
            t = self._common(ents, "linetype", "BYLAYER")
            if t is not None:
                lt.set_value(t)
            else:
                lt.setCurrentIndex(-1)
            w = self._common(ents, "lineweight", -1)
            if w is not None:
                lw.set_value(w)
            else:
                lw.setCurrentIndex(-1)
            s = self._common(ents, "ltscale", 1.0)
            lts.setText(fmt(s) if s is not None else "*çeşitli*")
            color.changed.connect(lambda v: self._apply(lambda e: _set_or_discard(e, "color", v, 256)))
            layer.activated.connect(lambda i: self._apply(lambda e: e.dxf.set("layer", layer.currentText())))
            lt.changed.connect(lambda v: self._apply(lambda e: _set_or_discard(e, "linetype", v, "BYLAYER")))
            lw.changed.connect(lambda v: self._apply(lambda e: e.dxf.set("lineweight", v)))
            lts.editingFinished.connect(lambda: self._apply(lambda e: e.dxf.set("ltscale", _num(lts.text(), 1.0))))
        f.addRow("Renk", color)
        f.addRow("Katman", layer)
        f.addRow("Çizgi tipi", lt)
        f.addRow("Ç. tipi ölçeği", lts)
        f.addRow("Çizgi kalınlığı", lw)

    def _ro(self, f, label, value):
        l = QLineEdit(value)
        l.setReadOnly(True)
        l.setStyleSheet("color:#9aa;")
        f.addRow(label, l)

    def _edit(self, f, label, value: float, setter):
        l = QLineEdit(fmt(value))
        l.editingFinished.connect(lambda: self._on_edit(l, value, setter))
        f.addRow(label, l)

    def _on_edit(self, widget, old, setter):
        v = _num(widget.text(), None)
        if v is None or abs(v - old) < 1e-12:
            return
        self._apply(lambda e: setter(e, v))

    def _build_geometry(self, e):
        t = e.dxftype()
        f = self._group("Geometri" if t not in ("TEXT", "MTEXT") else "Yazı")
        d = e.dxf
        if t == "LINE":
            s, en = Vec2(d.start), Vec2(d.end)
            self._edit(f, "Başlangıç X", s.x, lambda c, v: c.dxf.set("start", Vec3(v, c.dxf.start.y, c.dxf.start.z)))
            self._edit(f, "Başlangıç Y", s.y, lambda c, v: c.dxf.set("start", Vec3(c.dxf.start.x, v, c.dxf.start.z)))
            self._edit(f, "Bitiş X", en.x, lambda c, v: c.dxf.set("end", Vec3(v, c.dxf.end.y, c.dxf.end.z)))
            self._edit(f, "Bitiş Y", en.y, lambda c, v: c.dxf.set("end", Vec3(c.dxf.end.x, v, c.dxf.end.z)))
            self._edit(f, "Uzunluk", s.distance(en), _set_line_length)
            self._ro(f, "Açı", fmt(math.degrees((en - s).angle) % 360, 2) + "°")
            self._ro(f, "Delta X", fmt(en.x - s.x))
            self._ro(f, "Delta Y", fmt(en.y - s.y))
        elif t in ("CIRCLE", "ARC"):
            c = Vec2(d.center)
            self._edit(f, "Merkez X", c.x, lambda x, v: x.dxf.set("center", Vec3(v, x.dxf.center.y, 0)))
            self._edit(f, "Merkez Y", c.y, lambda x, v: x.dxf.set("center", Vec3(x.dxf.center.x, v, 0)))
            self._edit(f, "Yarıçap", d.radius, lambda x, v: x.dxf.set("radius", max(v, 1e-9)))
            self._edit(f, "Çap", d.radius * 2, lambda x, v: x.dxf.set("radius", max(v / 2, 1e-9)))
            if t == "CIRCLE":
                self._ro(f, "Çevre", fmt(2 * math.pi * d.radius))
                self._ro(f, "Alan", fmt(math.pi * d.radius ** 2))
            else:
                self._edit(f, "Başlangıç açısı", d.start_angle, lambda x, v: x.dxf.set("start_angle", v))
                self._edit(f, "Bitiş açısı", d.end_angle, lambda x, v: x.dxf.set("end_angle", v))
                arc = geom.entity_prims(e)[0]
                self._ro(f, "Yay uzunluğu", fmt(arc.length()))
        elif t == "LWPOLYLINE":
            prims = geom.entity_prims(e)
            self._ro(f, "Köşe sayısı", str(len(e)))
            self._edit(f, "Sabit genişlik", d.get("const_width", 0.0), lambda x, v: x.dxf.set("const_width", v))
            cb = QCheckBox()
            cb.setChecked(bool(e.closed))
            cb.toggled.connect(lambda v: self._apply(lambda x: setattr(x, "closed", v)))
            f.addRow("Kapalı", cb)
            self._ro(f, "Uzunluk", fmt(geom.prims_length(prims)))
            if e.closed:
                pts = geom.flatten_prims(prims, math.radians(1))
                self._ro(f, "Alan", fmt(abs(geom.polygon_area(pts))))
        elif t == "TEXT":
            te = QLineEdit(d.text)
            te.editingFinished.connect(lambda: self._apply(lambda x: x.dxf.set("text", te.text())) if te.text() != d.text else None)
            f.addRow("İçerik", te)
            self._edit(f, "Yükseklik", d.height, lambda x, v: x.dxf.set("height", v))
            self._edit(f, "Dönme", d.rotation, lambda x, v: x.dxf.set("rotation", v))
            self._edit(f, "Genişlik faktörü", d.get("width", 1.0), lambda x, v: x.dxf.set("width", v))
            st = QComboBox()
            st.addItems([s.dxf.name for s in self.tab.doc.doc.styles])
            st.setCurrentText(d.get("style", "Standard"))
            st.activated.connect(lambda i: self._apply(lambda x: x.dxf.set("style", st.currentText())))
            f.addRow("Stil", st)
        elif t == "MTEXT":
            self._edit(f, "Yükseklik", d.char_height, lambda x, v: x.dxf.set("char_height", v))
            self._edit(f, "Dönme", d.get("rotation", 0.0), lambda x, v: x.dxf.set("rotation", v))
            self._edit(f, "Genişlik", d.get("width", 0.0), lambda x, v: x.dxf.set("width", v))
            self._ro(f, "İçerik", e.plain_text()[:60])
        elif t == "INSERT":
            self._ro(f, "Blok adı", d.name)
            ins = Vec2(d.insert)
            self._edit(f, "Konum X", ins.x, lambda x, v: x.dxf.set("insert", Vec3(v, x.dxf.insert.y, 0)))
            self._edit(f, "Konum Y", ins.y, lambda x, v: x.dxf.set("insert", Vec3(x.dxf.insert.x, v, 0)))
            self._edit(f, "Ölçek X", d.xscale, lambda x, v: x.dxf.set("xscale", v))
            self._edit(f, "Ölçek Y", d.yscale, lambda x, v: x.dxf.set("yscale", v))
            self._edit(f, "Dönme", d.rotation, lambda x, v: x.dxf.set("rotation", v))
        elif t == "DIMENSION":
            try:
                m = e.get_measurement()
                m = m if isinstance(m, (int, float)) else m.magnitude
                self._ro(f, "Ölçü değeri", fmt(m))
            except Exception:
                pass
            te = QLineEdit(d.get("text", "<>"))
            te.editingFinished.connect(lambda: self._apply_dim_text(te.text()))
            f.addRow("Metin geçersiz kıl", te)
            self._ro(f, "Ölçü stili", d.get("dimstyle", "Standard"))
        elif t == "HATCH":
            self._ro(f, "Desen", d.pattern_name)
            if not d.solid_fill:
                self._edit(f, "Desen ölçeği", d.get("pattern_scale", 1.0), _set_hatch_scale)
                self._edit(f, "Desen açısı", d.get("pattern_angle", 0.0), _set_hatch_angle)
        elif t == "POINT":
            p = Vec2(d.location)
            self._edit(f, "X", p.x, lambda x, v: x.dxf.set("location", Vec3(v, x.dxf.location.y, 0)))
            self._edit(f, "Y", p.y, lambda x, v: x.dxf.set("location", Vec3(x.dxf.location.x, v, 0)))

    # ------------------------------------------------------------ apply
    def _set_header(self, name, value):
        try:
            self.tab.doc.doc.header[name] = value
        except Exception:
            pass

    def _apply(self, fn):
        tab = self.tab
        if tab is None or not self._ents:
            return
        doc = tab.doc
        doc.begin("PROPERTIES")
        new = []
        for e in self._ents:
            if not e.is_alive:
                continue
            try:
                if e.dxftype() == "DIMENSION":
                    c = doc.clone(e)
                    fn(c)
                    doc.replace(e, c)
                    new.append(c)
                else:
                    new.append(doc.modify(e, fn))
            except Exception as ex:
                print("property change failed:", ex)
        doc.commit()
        tab.canvas.set_selection([e.dxf.handle for e in new])
        self.main.on_selection_changed()

    def _apply_dim_text(self, text):
        def fn(c):
            c.dxf.text = text
        tab = self.tab
        doc = tab.doc
        doc.begin("PROPERTIES")
        new = []
        for e in self._ents:
            if e.dxftype() != "DIMENSION":
                continue
            c = doc.clone(e)
            fn(c)
            doc.replace(e, c)
            from t2dcad.grips import rerender_dimension
            rerender_dimension(doc.doc, c)
            doc.changed.emit([c], [], False)
            new.append(c)
        doc.commit()
        tab.canvas.set_selection([e.dxf.handle for e in new])


def _num(text, default):
    try:
        return float(str(text).replace(",", "."))
    except ValueError:
        return default


def _set_or_discard(e, name, v, default):
    if v == default or (isinstance(v, str) and v.upper() == str(default).upper()):
        e.dxf.discard(name)
    else:
        e.dxf.set(name, v)


def _set_line_length(c, v):
    s, en = Vec2(c.dxf.start), Vec2(c.dxf.end)
    if s.isclose(en):
        return
    u = (en - s).normalize()
    c.dxf.end = Vec3(s + u * v)


def _set_hatch_scale(c, v):
    c.set_pattern_scale(v)


def _set_hatch_angle(c, v):
    c.set_pattern_angle(v)
