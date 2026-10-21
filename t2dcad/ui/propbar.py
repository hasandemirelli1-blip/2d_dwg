"""Layer and property (color / linetype / lineweight) selectors used by the
classic toolbars and by the ribbon. Several instances can exist; the main
window keeps all of them in sync."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QComboBox

from t2dcad.ui.icons import color_icon
from t2dcad.ui.widgets import ColorCombo, LineweightCombo, aci_qcolor
from t2dcad.i18n import tr


class PropertyBar(QWidget):
    def __init__(self, main, layer=True, props=True, vertical=False):
        super().__init__()
        self.main = main
        lay = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(3)
        self.layer_combo = self.color_combo = self.lt_combo = self.lw_combo = None
        if layer:
            self.layer_combo = QComboBox()
            self.layer_combo.setMinimumWidth(220)
            self.layer_combo.setToolTip("Geçerli katman (nesne seçiliyse nesnenin katmanı)")
            self.layer_combo.activated.connect(lambda i: main.layer_combo_changed(self.layer_combo.itemData(i)))
            lay.addWidget(self.layer_combo)
        if props:
            self.color_combo = ColorCombo()
            self.color_combo.setMinimumWidth(130)
            self.color_combo.setToolTip("Renk")
            self.color_combo.changed.connect(lambda v: main.prop_combo("color", v))
            self.lt_combo = QComboBox()
            self.lt_combo.setMinimumWidth(140)
            self.lt_combo.setToolTip("Çizgi tipi")
            self.lt_combo.activated.connect(lambda i: main.prop_combo("linetype", self.lt_combo.currentData()))
            self.lw_combo = LineweightCombo()
            self.lw_combo.setMinimumWidth(120)
            self.lw_combo.setToolTip("Çizgi kalınlığı")
            self.lw_combo.changed.connect(lambda v: main.prop_combo("lineweight", v))
            for w in (self.color_combo, self.lt_combo, self.lw_combo):
                lay.addWidget(w)

    def refresh(self, tab):
        cb = self.layer_combo
        if cb is not None:
            cb.blockSignals(True)
            cb.clear()
            if tab is not None:
                for l in sorted(tab.doc.doc.layers, key=lambda l: (l.dxf.name != "0", l.dxf.name.lower())):
                    state = ("" if l.is_on() else " (kapalı)") + (" (donuk)" if l.is_frozen() else "") + \
                            (" (kilitli)" if l.is_locked() else "")
                    cb.addItem(color_icon(aci_qcolor(abs(l.dxf.color))), l.dxf.name + state, l.dxf.name)
                cb.setCurrentIndex(max(0, cb.findData(tab.doc.current_layer)))
            cb.blockSignals(False)
        if self.lt_combo is not None:
            self.lt_combo.blockSignals(True)
            self.lt_combo.clear()
            if tab is not None:
                self.lt_combo.addItem(tr("KatmanaGöre"), "BYLAYER")
                self.lt_combo.addItem(tr("BlokaGöre"), "BYBLOCK")
                for lt in tab.doc.doc.linetypes:
                    if lt.dxf.name.upper() not in ("BYLAYER", "BYBLOCK"):
                        self.lt_combo.addItem(lt.dxf.name, lt.dxf.name)
            self.lt_combo.blockSignals(False)

    def show_values(self, layer, color, lt, lw):
        if self.color_combo is not None:
            self.color_combo.set_value(color)
            self.lw_combo.set_value(lw)
            self.lt_combo.blockSignals(True)
            for k in range(self.lt_combo.count()):
                if str(self.lt_combo.itemData(k)).upper() == str(lt).upper():
                    self.lt_combo.setCurrentIndex(k)
                    break
            self.lt_combo.blockSignals(False)
        if self.layer_combo is not None:
            i = self.layer_combo.findData(layer)
            if i >= 0:
                self.layer_combo.blockSignals(True)
                self.layer_combo.setCurrentIndex(i)
                self.layer_combo.blockSignals(False)
