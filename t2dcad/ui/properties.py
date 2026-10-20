"""Properties palette (Ctrl+1)."""
from __future__ import annotations

import math

from ezdxf.math import Vec2, Vec3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, QLabel,
                               QScrollArea, QGroupBox, QPlainTextEdit, QCheckBox, QPushButton)

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
            self._lay.addStretch(1)
            self._fit()
            return
        types = sorted({e.dxftype() for e in ents})
        if len(types) == 1:
            self.header.addItem(f"{TYPE_NAMES.get(types[0], types[0])} ({len(ents)})")
        else:
            self.header.addItem(f"Tümü ({len(ents)})")
        self._build_general(ents)
        if len(ents) == 1:
            self._build_geometry(ents[0])
        elif all(e.dxftype() == "DIMENSION" for e in ents):
            self._build_dimension(self._group("Ölçü"), ents[0])
        self._lay.addStretch(1)
        self._fit()

    def _fit(self):
        """Let the scroll area scroll instead of squeezing the rows (new child
        widgets become visible only in the next event loop cycle)."""
        from PySide6.QtCore import QTimer

        def apply():
            self._lay.activate()
            self.body.setMinimumHeight(self._lay.minimumSize().height())
        QTimer.singleShot(0, apply)

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
        elif t in ("TEXT", "MTEXT"):
            if t == "TEXT":
                te = QLineEdit(d.text)
                te.editingFinished.connect(
                    lambda: self._apply(lambda x: x.dxf.set("text", te.text())) if te.text() != d.text else None)
                f.addRow("İçerik", te)
            else:
                b = QPushButton(e.plain_text()[:40] + ("…" if len(e.plain_text()) > 40 else ""))
                b.clicked.connect(lambda: self.main.edit_text(self.tab, e))
                f.addRow("İçerik", b)
            self._style_rows(f, d.get("style", "Standard"), lambda x, v: x.dxf.set("style", v))
            hname = "height" if t == "TEXT" else "char_height"
            self._edit(f, "Yükseklik", d.get(hname, 2.5), lambda x, v, n=hname: x.dxf.set(n, v))
            self._edit(f, "Dönme", d.get("rotation", 0.0), lambda x, v: x.dxf.set("rotation", v))
            if t == "TEXT":
                self._edit(f, "Genişlik faktörü", d.get("width", 1.0), lambda x, v: x.dxf.set("width", v))
                self._edit(f, "Eğiklik", d.get("oblique", 0.0), lambda x, v: x.dxf.set("oblique", v))
                al = QComboBox()
                names = list(_JUSTIFY.keys())
                al.addItems(names)
                cur = _text_alignment(e)
                al.setCurrentText(cur)
                al.activated.connect(lambda i: self._apply(lambda x: _set_alignment(x, al.currentText())))
                f.addRow("Hizalama", al)
            else:
                self._edit(f, "Tanımlı genişlik", d.get("width", 0.0), lambda x, v: x.dxf.set("width", v))
                at = QComboBox()
                at.addItems(_ATTACH)
                at.setCurrentIndex(max(0, d.get("attachment_point", 1) - 1))
                at.activated.connect(lambda i: self._apply(lambda x: x.dxf.set("attachment_point", i + 1)))
                f.addRow("Hizalama", at)
        elif t == "INSERT":
            self._ro(f, "Blok adı", d.name)
            ins = Vec2(d.insert)
            self._edit(f, "Konum X", ins.x, lambda x, v: x.dxf.set("insert", Vec3(v, x.dxf.insert.y, 0)))
            self._edit(f, "Konum Y", ins.y, lambda x, v: x.dxf.set("insert", Vec3(x.dxf.insert.x, v, 0)))
            self._edit(f, "Ölçek X", d.xscale, lambda x, v: x.dxf.set("xscale", v))
            self._edit(f, "Ölçek Y", d.yscale, lambda x, v: x.dxf.set("yscale", v))
            self._edit(f, "Dönme", d.rotation, lambda x, v: x.dxf.set("rotation", v))
        elif t == "DIMENSION":
            self._build_dimension(f, e)
        elif t == "HATCH":
            self._ro(f, "Desen", d.pattern_name)
            if not d.solid_fill:
                self._edit(f, "Desen ölçeği", d.get("pattern_scale", 1.0), _set_hatch_scale)
                self._edit(f, "Desen açısı", d.get("pattern_angle", 0.0), _set_hatch_angle)
        elif t == "POINT":
            p = Vec2(d.location)
            self._edit(f, "X", p.x, lambda x, v: x.dxf.set("location", Vec3(v, x.dxf.location.y, 0)))
            self._edit(f, "Y", p.y, lambda x, v: x.dxf.set("location", Vec3(x.dxf.location.x, v, 0)))

    # ------------------------------------------------------------ dimensions
    def _build_dimension(self, f, e):
        d = e.dxf
        ov = e.override()

        def get(name, default):
            try:
                v = ov.get(name, None)
            except Exception:
                v = None
            return default if v is None else v
        try:
            m = e.get_measurement()
            m = m if isinstance(m, (int, float)) else m.magnitude
            self._ro(f, "Ölçü değeri", fmt(m))
        except Exception:
            pass
        st = QComboBox()
        st.addItems([x.dxf.name for x in self.tab.doc.doc.dimstyles])
        st.setCurrentText(d.get("dimstyle", "Standard"))
        st.activated.connect(lambda i: self._apply_dim(lambda c, ov: c.dxf.set("dimstyle", st.currentText())))
        f.addRow("Ölçü stili", st)

        g = self._group("Çizgiler ve oklar")
        arrows = ["Kapalı dolu", "Mimari çentik", "Eğik", "Nokta", "Açık", "Yok"]
        codes = ["", "ARCHTICK", "OBLIQUE", "DOT", "OPEN", "NONE"]
        for label, key in (("Ok 1", "dimblk1"), ("Ok 2", "dimblk2")):
            cb = QComboBox()
            cb.addItems(arrows)
            cur = (get(key, "") or get("dimblk", "") or "").upper().lstrip("_")
            cb.setCurrentIndex(codes.index(cur) if cur in codes else 0)
            cb.activated.connect(lambda i, k=key: self._apply_dim(
                lambda c, ov, k=k, i=i: _set_arrow(ov, k, codes[i])))
            g.addRow(label, cb)
        self._dim_num(g, "Ok boyutu", get("dimasz", 2.5), "dimasz")
        self._dim_num(g, "Uzatma çizgisi taşması", get("dimexe", 1.25), "dimexe")
        self._dim_num(g, "Uzatma çizgisi ofseti", get("dimexo", 0.625), "dimexo")
        for label, key in (("Uzatma çizgisi 1 gizle", "dimse1"), ("Uzatma çizgisi 2 gizle", "dimse2"),
                           ("Ölçü çizgisi 1 gizle", "dimsd1"), ("Ölçü çizgisi 2 gizle", "dimsd2")):
            cb = QCheckBox()
            cb.setChecked(bool(get(key, 0)))
            cb.toggled.connect(lambda v, k=key: self._apply_dim(lambda c, ov, k=k, v=v: ov.update({k: 1 if v else 0})))
            g.addRow(label, cb)
        clr = ColorCombo()
        clr.set_value(get("dimclrd", 0) or 0)
        clr.changed.connect(lambda v: self._apply_dim(lambda c, ov, v=v: ov.update({"dimclrd": v, "dimclre": v})))
        g.addRow("Çizgi rengi", clr)

        g = self._group("Yazı")
        tst = QComboBox()
        tst.addItems([x.dxf.name for x in self.tab.doc.doc.styles if x.dxf.name])
        tst.setCurrentText(get("dimtxsty", "Standard") or "Standard")
        tst.activated.connect(lambda i: self._apply_dim(lambda c, ov: ov.update({"dimtxsty": tst.currentText()})))
        g.addRow("Yazı stili", tst)
        self._font_row(g, get("dimtxsty", "Standard") or "Standard",
                       lambda style: self._apply_dim(lambda c, ov, s=style: ov.update({"dimtxsty": s})))
        self._dim_num(g, "Yazı yüksekliği", get("dimtxt", 2.5), "dimtxt")
        self._dim_num(g, "Yazı ofseti", get("dimgap", 0.625), "dimgap")
        tc = ColorCombo()
        tc.set_value(get("dimclrt", 0) or 0)
        tc.changed.connect(lambda v: self._apply_dim(lambda c, ov, v=v: ov.update({"dimclrt": v})))
        g.addRow("Yazı rengi", tc)
        pos = QComboBox()
        pos.addItems(["Ortada", "Üstte", "Dışta", "JIS", "Altta"])
        pos.setCurrentIndex(min(4, int(get("dimtad", 1))))
        pos.activated.connect(lambda i: self._apply_dim(lambda c, ov, i=i: ov.update({"dimtad": i})))
        g.addRow("Dikey konum", pos)
        hz = QCheckBox()
        hz.setChecked(bool(get("dimtih", 0)))
        hz.toggled.connect(lambda v: self._apply_dim(lambda c, ov, v=v: ov.update({"dimtih": int(v), "dimtoh": int(v)})))
        g.addRow("Yazı hep yatay", hz)
        te = QLineEdit(d.get("text", "<>") or "<>")
        te.setToolTip("<> = ölçülen değer. Örnek: Ø<> veya 2x<> H7")
        te.editingFinished.connect(lambda: self._apply_dim(lambda c, ov, t=te.text(): c.dxf.set("text", t or "<>")))
        g.addRow("Metin geçersiz kıl", te)

        g = self._group("Birincil birimler")
        post = get("dimpost", "") or ""
        prefix, suffix = (post.split("<>", 1) + [""])[:2] if "<>" in post else ("", post)
        pre = QLineEdit(prefix)
        suf = QLineEdit(suffix)

        def set_post():
            p, s_ = pre.text(), suf.text()
            val = f"{p}<>{s_}" if (p or s_) else ""
            self._apply_dim(lambda c, ov, v=val: ov.update({"dimpost": v}))
        pre.editingFinished.connect(set_post)
        suf.editingFinished.connect(set_post)
        g.addRow("Önek", pre)
        g.addRow("Sonek", suf)
        dec = QComboBox()
        dec.addItems(["0", "0.0", "0.00", "0.000", "0.0000", "0.00000", "0.000000"])
        dec.setCurrentIndex(min(6, int(get("dimdec", 2))))
        dec.activated.connect(lambda i: self._apply_dim(lambda c, ov, i=i: ov.update({"dimdec": i})))
        g.addRow("Hassasiyet", dec)
        self._dim_num(g, "Ölçü ölçek faktörü", get("dimlfac", 1.0), "dimlfac")
        self._dim_num(g, "Yuvarlama", get("dimrnd", 0.0), "dimrnd")
        tz = QCheckBox()
        tz.setChecked(bool(int(get("dimzin", 8)) & 8))
        tz.toggled.connect(lambda v: self._apply_dim(lambda c, ov, v=v: ov.update({"dimzin": 8 if v else 0})))
        g.addRow("Sondaki sıfırları gizle", tz)
        sep = QComboBox()
        sep.addItems([". (nokta)", ", (virgül)"])
        sep.setCurrentIndex(1 if int(get("dimdsep", 46)) == 44 else 0)
        sep.activated.connect(lambda i: self._apply_dim(lambda c, ov, i=i: ov.update({"dimdsep": 44 if i else 46})))
        g.addRow("Ondalık ayırıcı", sep)

        g = self._group("Sığdır")
        self._dim_num(g, "Genel ölçek (DIMSCALE)", get("dimscale", 1.0), "dimscale")

    def _dim_num(self, f, label, value, key):
        l = QLineEdit(fmt(float(value or 0)))
        l.editingFinished.connect(lambda: self._on_dim_num(l, key, value))
        f.addRow(label, l)

    def _on_dim_num(self, widget, key, old):
        v = _num(widget.text(), None)
        if v is None or (old is not None and abs(v - float(old or 0)) < 1e-12):
            return
        self._apply_dim(lambda c, ov, v=v: ov.update({key: v}))

    def _apply_dim(self, fn):
        """fn(dimension copy, DimStyleOverride) - the geometry block is rebuilt."""
        tab = self.tab
        if tab is None:
            return
        doc = tab.doc
        doc.begin("PROPERTIES")
        new = []
        for e in self._ents:
            if not e.is_alive or e.dxftype() != "DIMENSION":
                continue
            try:
                c = doc.clone(e)
                ov = c.override()
                fn(c, ov)
                ov.commit()
                ov = c.override()
                ov.render()
                doc.replace(e, c)
                new.append(c)
            except Exception as ex:
                print("dimension change failed:", ex)
        doc.commit()
        if new:
            tab.canvas.set_selection([x.dxf.handle for x in new])
        self.main.on_selection_changed()

    # ------------------------------------------------------------ text styles / fonts
    def _style_rows(self, f, style_name, setter):
        st = QComboBox()
        st.addItems([s.dxf.name for s in self.tab.doc.doc.styles if s.dxf.name])
        st.setCurrentText(style_name)
        st.activated.connect(lambda i: self._apply(lambda x: setter(x, st.currentText())))
        f.addRow("Stil", st)
        self._font_row(f, style_name, lambda new_style: self._apply(lambda x: setter(x, new_style)))

    def _font_row(self, f, style_name, on_style):
        """Font combo: picking a font assigns a text style using that font
        (the style is created if necessary, like AutoCAD users do with STYLE)."""
        from t2dcad import fonts
        doc = self.tab.doc.doc
        st = doc.styles.get(style_name) if style_name in doc.styles else None
        cur = (st.dxf.get("font", "txt") if st is not None else "txt") or "txt"
        if "." not in cur:
            cur += ".shx"
        cb = QComboBox()
        cb.setMaxVisibleItems(25)
        cad, ttf = fonts.font_list()
        cb.addItems(cad)
        cb.insertSeparator(cb.count())
        cb.addItems(ttf)
        cb.setCurrentText(cur)

        def picked(i):
            font = cb.currentText()
            if not font or font.lower() == cur.lower():
                return
            on_style(style_for_font(doc, font, st))
        cb.activated.connect(picked)
        f.addRow("Yazı tipi", cb)

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


_JUSTIFY = {
    "Sol": "LEFT", "Orta": "CENTER", "Sağ": "RIGHT", "Ortala": "MIDDLE",
    "Üst sol": "TOP_LEFT", "Üst orta": "TOP_CENTER", "Üst sağ": "TOP_RIGHT",
    "Orta sol": "MIDDLE_LEFT", "Orta orta": "MIDDLE_CENTER", "Orta sağ": "MIDDLE_RIGHT",
    "Alt sol": "BOTTOM_LEFT", "Alt orta": "BOTTOM_CENTER", "Alt sağ": "BOTTOM_RIGHT",
}
_ATTACH = ["Üst sol", "Üst orta", "Üst sağ", "Orta sol", "Orta orta", "Orta sağ",
           "Alt sol", "Alt orta", "Alt sağ"]


def _text_alignment(e) -> str:
    try:
        name = e.get_align_enum().name
    except Exception:
        return "Sol"
    for k, v in _JUSTIFY.items():
        if v == name:
            return k
    return "Sol"


def _set_alignment(x, label):
    from ezdxf.enums import TextEntityAlignment
    p1, p2 = x.get_placement()[1:] if hasattr(x, "get_placement") else (x.dxf.insert, None)
    align = TextEntityAlignment[_JUSTIFY[label]]
    x.set_placement(p1, p2 if align in (TextEntityAlignment.ALIGNED, TextEntityAlignment.FIT) else None,
                    align=align)


def _set_arrow(ov, key, code):
    blk = {"": "", "NONE": "NONE"}.get(code, code)
    if key == "dimblk1":
        ov.set_arrows(blk1=blk)
    else:
        ov.set_arrows(blk2=blk)
    ov.update({"dimsah": 1})


def style_for_font(doc, font: str, base_style=None) -> str:
    """Return the name of a text style using `font`, create it if needed."""
    for s in doc.styles:
        if (s.dxf.get("font", "") or "").lower() == font.lower() and not s.dxf.get("height", 0):
            return s.dxf.name
    stem = font.rsplit(".", 1)[0]
    name = stem.upper() if font.lower().endswith(".shx") else stem
    k = 1
    base = name
    while name in doc.styles:
        k += 1
        name = f"{base}_{k}"
    st = doc.styles.add(name, font=font)
    if base_style is not None:
        st.dxf.width = base_style.dxf.get("width", 1.0) or 1.0
    return name


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
