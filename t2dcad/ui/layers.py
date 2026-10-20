"""Layer Properties Manager."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                               QPushButton, QHeaderView, QMessageBox, QCheckBox, QWidget, QAbstractItemView,
                               QLineEdit)

from t2dcad.ui.widgets import ColorCombo, LinetypeCombo, LineweightCombo

COLS = ["Durum", "Ad", "Açık", "Dondur", "Kilit", "Renk", "Çizgi tipi", "Kalınlık", "Çizdir"]


def _check(checked: bool, cb) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setAlignment(Qt.AlignCenter)
    c = QCheckBox()
    c.setChecked(checked)
    c.toggled.connect(cb)
    h.addWidget(c)
    return w


class LayerDialog(QDialog):
    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.cad = tab.doc
        self.doc = tab.doc.doc
        self.setWindowTitle("Katman Özellikleri Yöneticisi")
        self.resize(900, 480)
        self._snapshot = self._take_snapshot()
        v = QVBoxLayout(self)
        row = QHBoxLayout()
        b_new = QPushButton("Yeni katman")
        b_del = QPushButton("Katmanı sil")
        b_cur = QPushButton("Geçerli yap")
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Katman ara...")
        self.filter.textChanged.connect(self.fill)
        b_new.clicked.connect(self.new_layer)
        b_del.clicked.connect(self.delete_layer)
        b_cur.clicked.connect(self.make_current)
        for b in (b_new, b_del, b_cur):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.filter)
        v.addLayout(row)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemChanged.connect(self._renamed)
        self.table.cellDoubleClicked.connect(lambda r, c: self.make_current() if c == 0 else None)
        v.addWidget(self.table)
        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(close)
        v.addLayout(h)
        self.fill()

    # ------------------------------------------------------------ undo support
    def _take_snapshot(self):
        snap = {}
        for l in self.doc.layers:
            d = l.dxf
            snap[l.dxf.handle] = (l, d.name, d.flags, d.color, d.linetype, d.get("lineweight", -3),
                                  d.get("plot", 1))
        return snap, self.cad.current_layer

    def _apply_snapshot(self, snapshot):
        snap, cur = snapshot
        for h, (l, name, flags, color, lt, lw, plot) in snap.items():
            if not l.is_alive:
                continue
            if l.dxf.name != name:
                try:
                    l.rename(name)
                except Exception:
                    pass
            l.dxf.flags = flags
            l.dxf.color = color
            l.dxf.linetype = lt
            l.dxf.lineweight = lw
            l.dxf.plot = plot
        self.doc.header["$CLAYER"] = cur
        self.cad.layers_changed.emit()

    def done(self, r):
        after = self._take_snapshot()
        before = self._snapshot
        if after != before:
            self.cad.custom(lambda: self._apply_snapshot(before), lambda: self._apply_snapshot(after))
            self.cad.layers_changed.emit()
        super().done(r)

    # ------------------------------------------------------------ table
    def layers(self):
        f = self.filter.text().strip().lower()
        out = sorted(self.doc.layers, key=lambda l: (l.dxf.name != "0", l.dxf.name.lower()))
        if f:
            out = [l for l in out if f in l.dxf.name.lower()]
        return out

    def fill(self):
        t = self.table
        t.blockSignals(True)
        layers = self.layers()
        t.setRowCount(len(layers))
        cur = self.cad.current_layer
        for r, l in enumerate(layers):
            name = l.dxf.name
            st = QTableWidgetItem("✔" if name == cur else "")
            st.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            st.setTextAlignment(Qt.AlignCenter)
            t.setItem(r, 0, st)
            it = QTableWidgetItem(name)
            it.setData(Qt.UserRole, name)
            if name in ("0", "Defpoints"):
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            t.setItem(r, 1, it)
            t.setCellWidget(r, 2, _check(l.is_on(), lambda v, l=l: self._set(l, "on", v)))
            t.setCellWidget(r, 3, _check(l.is_frozen(), lambda v, l=l: self._set(l, "freeze", v)))
            t.setCellWidget(r, 4, _check(l.is_locked(), lambda v, l=l: self._set(l, "lock", v)))
            cc = ColorCombo(bylayer=False)
            cc.set_value(abs(l.dxf.color) or 7)
            cc.changed.connect(lambda v, l=l: self._set(l, "color", v))
            t.setCellWidget(r, 5, cc)
            lc = LinetypeCombo(self.doc, bylayer=False)
            lc.set_value(l.dxf.linetype)
            lc.changed.connect(lambda v, l=l: self._set(l, "linetype", v))
            t.setCellWidget(r, 6, lc)
            wc = LineweightCombo(bylayer=False)
            wc.set_value(l.dxf.get("lineweight", -3))
            wc.changed.connect(lambda v, l=l: self._set(l, "lineweight", v))
            t.setCellWidget(r, 7, wc)
            t.setCellWidget(r, 8, _check(bool(l.dxf.get("plot", 1)), lambda v, l=l: self._set(l, "plot", v)))
        t.resizeColumnToContents(0)
        t.blockSignals(False)

    def _set(self, layer, what, v):
        if what == "on":
            if v:
                layer.on()
            else:
                layer.off()
        elif what == "freeze":
            if v and layer.dxf.name == self.cad.current_layer:
                QMessageBox.warning(self, "Katman", "Geçerli katman dondurulamaz.")
                self.fill()
                return
            if v:
                layer.freeze()
            else:
                layer.thaw()
        elif what == "lock":
            if v:
                layer.lock()
            else:
                layer.unlock()
        elif what == "color":
            on = layer.is_on()
            layer.dxf.color = v
            if not on:
                layer.off()
        elif what == "linetype":
            layer.dxf.linetype = v
        elif what == "lineweight":
            layer.dxf.lineweight = v
        elif what == "plot":
            layer.dxf.plot = 1 if v else 0
        self.cad.layers_changed.emit()
        self.tab.regen()

    def _renamed(self, item: QTableWidgetItem):
        if item.column() != 1:
            return
        old = item.data(Qt.UserRole)
        new = item.text().strip()
        if not new or new == old:
            item.setText(old)
            return
        if new in self.doc.layers:
            QMessageBox.warning(self, "Katman", f'"{new}" adında bir katman zaten var.')
            self.table.blockSignals(True)
            item.setText(old)
            self.table.blockSignals(False)
            return
        layer = self.doc.layers.get(old)
        try:
            layer.rename(new)
        except Exception as ex:
            QMessageBox.warning(self, "Katman", f"Yeniden adlandırılamadı: {ex}")
        if self.cad.current_layer == old or self.doc.header.get("$CLAYER") == old:
            self.doc.header["$CLAYER"] = new
        self.cad.layers_changed.emit()
        self.tab.regen()
        self.fill()

    def _selected_name(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        it = self.table.item(r, 1)
        return it.text() if it else None

    def new_layer(self):
        i = 1
        while f"Katman{i}" in self.doc.layers:
            i += 1
        name = f"Katman{i}"
        self.doc.layers.add(name, color=7)
        self.cad.layers_changed.emit()
        self.fill()
        for r in range(self.table.rowCount()):
            if self.table.item(r, 1).text() == name:
                self.table.setCurrentCell(r, 1)
                self.table.editItem(self.table.item(r, 1))
                break

    def make_current(self):
        name = self._selected_name()
        if not name:
            return
        layer = self.doc.layers.get(name)
        if layer.is_frozen():
            QMessageBox.warning(self, "Katman", "Donmuş katman geçerli yapılamaz.")
            return
        self.cad.current_layer = name
        self.fill()

    def delete_layer(self):
        name = self._selected_name()
        if not name:
            return
        if name in ("0", "Defpoints") or name == self.cad.current_layer:
            QMessageBox.warning(self, "Katman", "Bu katman silinemez (0, Defpoints veya geçerli katman).")
            return
        used = any(e.dxf.layer == name for e in self.doc.modelspace())
        if not used:
            for blk in self.doc.blocks:
                if any(e.dxf.layer == name for e in blk):
                    used = True
                    break
        if used:
            QMessageBox.warning(self, "Katman", "Katman kullanımda, silinemez. Önce nesneleri başka katmana taşıyın.")
            return
        self.doc.layers.remove(name)
        self._snapshot[0].pop(next((h for h, v in self._snapshot[0].items() if v[1] == name), None), None)
        self.cad.layers_changed.emit()
        self.cad.set_modified(True)
        self.fill()
