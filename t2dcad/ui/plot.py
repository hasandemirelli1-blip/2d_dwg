"""PLOT dialog: printers, PDF, paper size, plot area, scale and plot style."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QMarginsF, QSizeF
from PySide6.QtGui import QPainter, QPageSize, QPageLayout, QColor
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo, QPrintPreviewDialog
from PySide6.QtWidgets import (QDialog, QFormLayout, QComboBox, QCheckBox, QDialogButtonBox,
                               QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                               QDoubleSpinBox, QRadioButton, QFileDialog, QMessageBox, QGridLayout)

from ezdxf.addons.drawing.config import ColorPolicy

from t2dcad import settings
from t2dcad.render import Renderer, PrintBackend

PDF_PRINTER = "PDF dosyası (T2D-CAD dahili)"

PAPERS = [
    ("ISO A4 (210 x 297 mm)", QPageSize.A4),
    ("ISO A3 (297 x 420 mm)", QPageSize.A3),
    ("ISO A2 (420 x 594 mm)", QPageSize.A2),
    ("ISO A1 (594 x 841 mm)", QPageSize.A1),
    ("ISO A0 (841 x 1189 mm)", QPageSize.A0),
    ("ISO A5 (148 x 210 mm)", QPageSize.A5),
    ("Letter (8.5 x 11 in)", QPageSize.Letter),
    ("Legal (8.5 x 14 in)", QPageSize.Legal),
    ("Tabloid (11 x 17 in)", QPageSize.Tabloid),
]

SCALES = ["Kağıda sığdır", "1:1", "1:2", "1:5", "1:10", "1:20", "1:25", "1:50", "1:100", "1:200",
          "1:500", "1:1000", "2:1", "5:1", "10:1"]


class PlotDialog(QDialog):
    def __init__(self, tab, state: dict, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.state = state
        self.setWindowTitle("Çizdir (Plot) - Model")
        self.setMinimumWidth(520)
        v = QVBoxLayout(self)

        g1 = QGroupBox("Yazıcı / Çizici")
        f1 = QFormLayout(g1)
        self.printer = QComboBox()
        names = [PDF_PRINTER] + QPrinterInfo.availablePrinterNames()
        self.printer.addItems(names)
        f1.addRow("Ad:", self.printer)
        self.paper = QComboBox()
        for name, _ in PAPERS:
            self.paper.addItem(name)
        f1.addRow("Kağıt boyutu:", self.paper)
        orow = QHBoxLayout()
        self.landscape = QRadioButton("Yatay")
        self.portrait = QRadioButton("Dikey")
        orow.addWidget(self.landscape)
        orow.addWidget(self.portrait)
        f1.addRow("Yönlendirme:", orow)
        self.copies = QDoubleSpinBox()
        self.copies.setDecimals(0)
        self.copies.setRange(1, 99)
        f1.addRow("Kopya sayısı:", self.copies)
        v.addWidget(g1)

        g2 = QGroupBox("Çizdirme alanı")
        h2 = QHBoxLayout(g2)
        self.area = QComboBox()
        self.area.addItems(["Kapsam (Extents)", "Ekran (Display)", "Pencere (Window)"])
        self.pick_btn = QPushButton("Pencere seç <")
        self.pick_btn.clicked.connect(self._pick)
        self.win_label = QLabel("")
        h2.addWidget(self.area)
        h2.addWidget(self.pick_btn)
        h2.addWidget(self.win_label, 1)
        v.addWidget(g2)

        g3 = QGroupBox("Ölçek ve konum")
        f3 = QGridLayout(g3)
        self.scale = QComboBox()
        self.scale.setEditable(True)
        self.scale.addItems(SCALES)
        f3.addWidget(QLabel("Ölçek (mm = birim):"), 0, 0)
        f3.addWidget(self.scale, 0, 1)
        self.center = QCheckBox("Çizimi ortala")
        f3.addWidget(self.center, 1, 0, 1, 2)
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0, 50)
        self.margin.setSuffix(" mm")
        f3.addWidget(QLabel("Kenar boşluğu:"), 2, 0)
        f3.addWidget(self.margin, 2, 1)
        v.addWidget(g3)

        g4 = QGroupBox("Çizim stili")
        f4 = QFormLayout(g4)
        self.style = QComboBox()
        self.style.addItems(["Monokrom (siyah) - monochrome.ctb", "Renkli - acad.ctb",
                             "Gri tonlama - grayscale.ctb"])
        f4.addRow("Stil tablosu:", self.style)
        self.lw = QCheckBox("Nesne çizgi kalınlıklarını çizdir")
        f4.addRow(self.lw)
        self.default_lw = QDoubleSpinBox()
        self.default_lw.setRange(0.05, 2.0)
        self.default_lw.setSingleStep(0.05)
        self.default_lw.setSuffix(" mm")
        f4.addRow("Varsayılan kalınlık:", self.default_lw)
        v.addWidget(g4)

        bb = QDialogButtonBox()
        self.preview_btn = bb.addButton("Önizleme...", QDialogButtonBox.ActionRole)
        bb.addButton("Çizdir", QDialogButtonBox.AcceptRole)
        bb.addButton("İptal", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.preview_btn.clicked.connect(self._preview)
        v.addWidget(bb)
        self._load()

    # ------------------------------------------------------------ state
    def _load(self):
        st = self.state
        pr = st.get("printer", settings.get("plot_printer", PDF_PRINTER))
        i = self.printer.findText(pr)
        self.printer.setCurrentIndex(max(0, i))
        self.paper.setCurrentIndex(int(st.get("paper", settings.get_int("plot_paper", 0))))
        land = st.get("landscape", settings.get_bool("plot_landscape", True))
        self.landscape.setChecked(land)
        self.portrait.setChecked(not land)
        self.copies.setValue(st.get("copies", 1))
        self.area.setCurrentIndex(st.get("area", 0 if "window" not in st else 2))
        self.scale.setCurrentText(st.get("scale", settings.get("plot_scale", "Kağıda sığdır")))
        self.center.setChecked(st.get("center", True))
        self.margin.setValue(st.get("margin", settings.get_float("plot_margin", 5.0)))
        self.style.setCurrentIndex(st.get("style", settings.get_int("plot_style", 0)))
        self.lw.setChecked(st.get("lw", settings.get_bool("plot_lw", True)))
        self.default_lw.setValue(st.get("default_lw", settings.get_float("plot_default_lw", 0.25)))
        if "window" in st:
            a, b = st["window"]
            self.win_label.setText(f"({a.x:.1f},{a.y:.1f}) - ({b.x:.1f},{b.y:.1f})")

    def _store(self):
        st = self.state
        st["printer"] = self.printer.currentText()
        st["paper"] = self.paper.currentIndex()
        st["landscape"] = self.landscape.isChecked()
        st["copies"] = int(self.copies.value())
        st["area"] = self.area.currentIndex()
        st["scale"] = self.scale.currentText()
        st["center"] = self.center.isChecked()
        st["margin"] = self.margin.value()
        st["style"] = self.style.currentIndex()
        st["lw"] = self.lw.isChecked()
        st["default_lw"] = self.default_lw.value()
        settings.set("plot_printer", st["printer"])
        settings.set("plot_paper", st["paper"])
        settings.set("plot_landscape", st["landscape"])
        settings.set("plot_scale", st["scale"])
        settings.set("plot_margin", st["margin"])
        settings.set("plot_style", st["style"])
        settings.set("plot_lw", st["lw"])
        settings.set("plot_default_lw", st["default_lw"])

    def _pick(self):
        self._store()
        self.state["pick"] = True
        self.done(2)

    def accept(self):
        self._store()
        if self.state["area"] == 2 and "window" not in self.state:
            QMessageBox.information(self, "Çizdir", "Önce 'Pencere seç' ile alanı belirleyin.")
            return
        super().accept()

    def _preview(self):
        self._store()
        if self.state["area"] == 2 and "window" not in self.state:
            QMessageBox.information(self, "Çizdir", "Önce 'Pencere seç' ile alanı belirleyin.")
            return
        printer = make_printer(self.state, preview=True)
        dlg = QPrintPreviewDialog(printer, self)
        dlg.setWindowTitle("Çizdirme Önizlemesi")
        dlg.resize(1000, 750)
        dlg.paintRequested.connect(lambda p: render_plot(self.tab, self.state, p))
        dlg.exec()


# ---------------------------------------------------------------- printing
def make_printer(state: dict, preview=False, pdf_path: str = "") -> QPrinter:
    printer = QPrinter(QPrinter.HighResolution)
    name = state.get("printer", PDF_PRINTER)
    if name == PDF_PRINTER or pdf_path:
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setResolution(600)
        if pdf_path:
            printer.setOutputFileName(pdf_path)
    else:
        printer.setPrinterName(name)
    page_id = PAPERS[int(state.get("paper", 0))][1]
    printer.setPageSize(QPageSize(page_id))
    printer.setPageOrientation(QPageLayout.Landscape if state.get("landscape", True) else QPageLayout.Portrait)
    m = float(state.get("margin", 5.0))
    printer.setPageMargins(QMarginsF(m, m, m, m), QPageLayout.Millimeter)
    printer.setCopyCount(int(state.get("copies", 1)))
    printer.setDocName("T2D-CAD")
    return printer


def _parse_scale(text: str):
    t = text.strip().replace(",", ".")
    if not t or t.lower().startswith("kağıda") or t.lower().startswith("fit"):
        return None
    if ":" in t:
        a, b = t.split(":", 1)
        try:
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(t)
    except ValueError:
        return None


def plot_area(tab, state):
    area = state.get("area", 0)
    if area == 1:
        return tab.canvas.visible_rect()
    if area == 2 and "window" in state:
        a, b = state["window"]
        return min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y)
    r = tab.renderer.extents()
    if r is None:
        return 0, 0, 420, 297
    return r.left(), r.top(), r.right(), r.bottom()


def render_plot(tab, state: dict, printer: QPrinter):
    dpi = printer.resolution()
    style = int(state.get("style", 0))
    policy = {0: ColorPolicy.BLACK, 1: ColorPolicy.COLOR, 2: ColorPolicy.MONOCHROME_LIGHT_BG}[style]
    use_lw = bool(state.get("lw", True))
    default_lw = float(state.get("default_lw", 0.25))
    rnd = Renderer(tab.doc, "#ffffff",
                   backend_factory=lambda sc: PrintBackend(sc, dpi, use_lw, default_lw),
                   color_policy=policy)
    rnd.show_lineweight = True
    rnd.regen(plot_only=True)
    x0, y0, x1, y1 = plot_area(tab, state)
    w, h = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    page = printer.pageLayout().paintRectPixels(dpi)
    W, H = page.width(), page.height()
    k = _parse_scale(state.get("scale", ""))
    if k is None:
        s = min(W / w, H / h)
    else:
        s = k * dpi / 25.4  # drawing units are mm
    if state.get("center", True):
        tx = (W - w * s) / 2
        ty = (H - h * s) / 2
    else:
        tx = 0
        ty = H - h * s
    painter = QPainter(printer)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setClipRect(QRectF(0, 0, W, H))
    painter.translate(tx, ty + h * s)
    painter.scale(s, -s)
    painter.translate(-x0, -y0)
    src = QRectF(x0, y0, w, h)
    rnd.scene.render(painter, src, src, Qt.IgnoreAspectRatio)
    painter.end()


def run_plot(main, tab, state) -> bool:
    """Execute the plot (after the dialog). Returns True on success."""
    pdf_path = ""
    if state.get("printer") == PDF_PRINTER:
        default = str(Path(tab.doc.path).with_suffix(".pdf")) if tab.doc.path else \
            os.path.join(os.path.expanduser("~"), "Cizim.pdf")
        pdf_path, _ = QFileDialog.getSaveFileName(main, "PDF olarak kaydet", default, "PDF (*.pdf)")
        if not pdf_path:
            return False
    printer = make_printer(state, pdf_path=pdf_path)
    try:
        render_plot(tab, state, printer)
    except Exception as ex:
        QMessageBox.critical(main, "Çizdir", f"Yazdırma başarısız:\n{ex}")
        return False
    main.cmdline.add_history(f"Çizdirme tamamlandı{': ' + pdf_path if pdf_path else '.'}")
    return True
