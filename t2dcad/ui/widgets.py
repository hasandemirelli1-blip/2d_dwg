"""Shared small widgets: ACI color combo, linetype and lineweight combos."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QColorDialog, QInputDialog

from ezdxf.colors import aci2rgb

from t2dcad.ui.icons import color_icon

ACI_NAMES = {1: "Kırmızı", 2: "Sarı", 3: "Yeşil", 4: "Camgöbeği", 5: "Mavi", 6: "Eflatun", 7: "Beyaz/Siyah",
             8: "8", 9: "9"}
LINEWEIGHTS = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140,
               158, 200, 211]


def aci_qcolor(aci: int) -> QColor:
    if aci in (0, 256, None):
        return QColor(200, 200, 200)
    if aci == 7:
        return QColor(255, 255, 255)
    r, g, b = aci2rgb(int(aci))
    return QColor(r, g, b)


def aci_name(aci: int) -> str:
    if aci == 256:
        return "KatmanaGöre"
    if aci == 0:
        return "BlokaGöre"
    return ACI_NAMES.get(aci, f"Renk {aci}")


def lw_name(lw: int) -> str:
    if lw == -1:
        return "KatmanaGöre"
    if lw == -2:
        return "BlokaGöre"
    if lw == -3:
        return "Varsayılan"
    return f"{lw / 100:.2f} mm"


class ColorCombo(QComboBox):
    """ACI color selection; value() returns ACI index (256 = ByLayer)."""
    changed = Signal(int)

    def __init__(self, bylayer=True, parent=None):
        super().__init__(parent)
        self._bylayer = bylayer
        self._fill()
        self.activated.connect(self._on_activated)

    def _fill(self, extra: int | None = None):
        self.blockSignals(True)
        self.clear()
        if self._bylayer:
            self.addItem(color_icon(QColor(200, 200, 200)), "KatmanaGöre", 256)
            self.addItem(color_icon(QColor(200, 200, 200)), "BlokaGöre", 0)
        for i in range(1, 10):
            self.addItem(color_icon(aci_qcolor(i)), aci_name(i), i)
        if extra and not (1 <= extra <= 9) and extra not in (0, 256):
            self.addItem(color_icon(aci_qcolor(extra)), aci_name(extra), extra)
        self.addItem("Diğer renk...", -100)
        self.blockSignals(False)

    def set_value(self, aci: int):
        i = self.findData(aci)
        if i < 0:
            self._fill(aci)
            i = self.findData(aci)
        self.blockSignals(True)
        self.setCurrentIndex(max(0, i))
        self.blockSignals(False)

    def value(self) -> int:
        return int(self.currentData())

    def _on_activated(self, idx):
        if self.itemData(idx) == -100:
            v, ok = QInputDialog.getInt(self, "Renk seç", "AutoCAD renk indeksi (1-255):", 1, 1, 255)
            if ok:
                self.set_value(v)
                self.changed.emit(v)
            else:
                self.setCurrentIndex(0)
            return
        self.changed.emit(self.value())


class LinetypeCombo(QComboBox):
    changed = Signal(str)

    def __init__(self, doc, bylayer=True, parent=None):
        super().__init__(parent)
        self.doc = doc
        self._bylayer = bylayer
        self.refresh()
        self.activated.connect(lambda i: self.changed.emit(self.value()))

    def refresh(self):
        cur = self.currentData()
        self.blockSignals(True)
        self.clear()
        if self._bylayer:
            self.addItem("KatmanaGöre", "BYLAYER")
            self.addItem("BlokaGöre", "BYBLOCK")
        for lt in self.doc.linetypes:
            n = lt.dxf.name
            if n.upper() in ("BYLAYER", "BYBLOCK"):
                continue
            self.addItem(n, n)
        if cur is not None:
            i = self.findData(cur)
            if i >= 0:
                self.setCurrentIndex(i)
        self.blockSignals(False)

    def set_value(self, name: str):
        i = -1
        for k in range(self.count()):
            if str(self.itemData(k)).upper() == str(name).upper():
                i = k
                break
        self.blockSignals(True)
        self.setCurrentIndex(max(0, i))
        self.blockSignals(False)

    def value(self) -> str:
        return str(self.currentData())


class LineweightCombo(QComboBox):
    changed = Signal(int)

    def __init__(self, bylayer=True, parent=None):
        super().__init__(parent)
        if bylayer:
            self.addItem("KatmanaGöre", -1)
            self.addItem("BlokaGöre", -2)
        self.addItem("Varsayılan", -3)
        for lw in LINEWEIGHTS:
            self.addItem(lw_name(lw), lw)
        self.activated.connect(lambda i: self.changed.emit(self.value()))

    def set_value(self, lw: int):
        i = self.findData(int(lw))
        self.blockSignals(True)
        self.setCurrentIndex(max(0, i))
        self.blockSignals(False)

    def value(self) -> int:
        return int(self.currentData())
