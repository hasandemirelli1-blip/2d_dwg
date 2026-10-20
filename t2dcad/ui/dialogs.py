"""Small dialogs: OSNAP settings, options, text, insert, hatch, dimension style."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QCheckBox,
                               QDialogButtonBox, QGroupBox, QLineEdit, QPushButton, QFileDialog, QSpinBox,
                               QDoubleSpinBox, QComboBox, QPlainTextEdit, QListWidget, QLabel,
                               QColorDialog, QMessageBox, QTextBrowser)

from t2dcad import settings, geom
from t2dcad.snap import ALL_MODES


class OsnapDialog(QDialog):
    def __init__(self, modes: set, enabled: bool, polar_inc: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Çizim Ayarları - Nesne Yakalama")
        v = QVBoxLayout(self)
        self.on = QCheckBox("Nesne yakalama açık (F3)")
        self.on.setChecked(enabled)
        v.addWidget(self.on)
        g = QGroupBox("Nesne yakalama modları")
        grid = QGridLayout(g)
        self.boxes = {}
        for i, m in enumerate(ALL_MODES):
            cb = QCheckBox(geom.SNAP_NAMES[m])
            cb.setChecked(m in modes)
            self.boxes[m] = cb
            grid.addWidget(cb, i % 5, i // 5)
        v.addWidget(g)
        row = QHBoxLayout()
        b_all = QPushButton("Tümünü seç")
        b_none = QPushButton("Tümünü temizle")
        b_all.clicked.connect(lambda: [c.setChecked(True) for c in self.boxes.values()])
        b_none.clicked.connect(lambda: [c.setChecked(False) for c in self.boxes.values()])
        row.addWidget(b_all)
        row.addWidget(b_none)
        row.addStretch(1)
        v.addLayout(row)
        g2 = QGroupBox("Kutupsal izleme (F10)")
        f2 = QFormLayout(g2)
        self.polar = QComboBox()
        self.polar.setEditable(True)
        self.polar.addItems(["90", "45", "30", "22.5", "18", "15", "10", "5"])
        self.polar.setCurrentText(f"{polar_inc:g}")
        f2.addRow("Artış açısı:", self.polar)
        v.addWidget(g2)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def result_values(self):
        modes = {m for m, cb in self.boxes.items() if cb.isChecked()}
        try:
            inc = float(self.polar.currentText().replace(",", "."))
        except ValueError:
            inc = 45.0
        return modes, self.on.isChecked(), inc


class OptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seçenekler")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        g1 = QGroupBox("DWG desteği (ODA File Converter)")
        f1 = QFormLayout(g1)
        row = QHBoxLayout()
        from t2dcad.docmodel import find_oda_converter
        self.oda = QLineEdit(settings.get("oda_path", "") or find_oda_converter())
        b = QPushButton("Gözat...")
        b.clicked.connect(self._browse)
        row.addWidget(self.oda, 1)
        row.addWidget(b)
        f1.addRow("ODAFileConverter.exe:", row)
        info = QLabel('Ücretsiz indirme: <a href="https://www.opendesign.com/guestfiles/oda_file_converter">'
                      'opendesign.com/guestfiles/oda_file_converter</a>')
        info.setOpenExternalLinks(True)
        f1.addRow(info)
        self.dwgver = QComboBox()
        from t2dcad.docmodel import DWG_VERSIONS
        for k, txt in DWG_VERSIONS.items():
            self.dwgver.addItem(txt, k)
        i = self.dwgver.findData(settings.get("save_version", "R2018"))
        self.dwgver.setCurrentIndex(max(0, i))
        f1.addRow("Yeni çizimler için DWG sürümü:", self.dwgver)
        v.addWidget(g1)

        g2 = QGroupBox("Görünüm")
        f2 = QFormLayout(g2)
        self.bg = QPushButton(settings.get("bg_color", "#212830"))
        self.bg.clicked.connect(self._pick_bg)
        f2.addRow("Model arka plan rengi:", self.bg)
        self.cursor = QSpinBox()
        self.cursor.setRange(1, 100)
        self.cursor.setValue(settings.get_int("cursor_size", 5))
        f2.addRow("İmleç boyutu (% ekran, 100 = tam ekran):", self.cursor)
        self.pickbox = QSpinBox()
        self.pickbox.setRange(1, 20)
        self.pickbox.setValue(settings.get_int("pickbox", 5))
        f2.addRow("Seçim kutusu boyutu (px):", self.pickbox)
        self.aperture = QSpinBox()
        self.aperture.setRange(2, 50)
        self.aperture.setValue(settings.get_int("aperture", 10))
        f2.addRow("Yakalama hassasiyeti (px):", self.aperture)
        self.antialias = QCheckBox("Kenar yumuşatma (antialiasing)")
        self.antialias.setChecked(settings.get_bool("antialias", True))
        f2.addRow(self.antialias)
        self.grid = QDoubleSpinBox()
        self.grid.setRange(0.001, 100000)
        self.grid.setDecimals(3)
        self.grid.setValue(settings.get_float("grid_unit", 10.0))
        f2.addRow("Izgara/Snap aralığı:", self.grid)
        v.addWidget(g2)

        g0 = QGroupBox("Dil / Language")
        f0 = QFormLayout(g0)
        from t2dcad import i18n
        self.language = QComboBox()
        for code, name in i18n.LANGUAGES:
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(i18n.lang())))
        f0.addRow("Arayüz dili:", self.language)
        v.addWidget(g0)

        g3 = QGroupBox("Kaydetme")
        f3 = QFormLayout(g3)
        self.bak = QCheckBox("Kaydederken yedek (.bak) oluştur")
        self.bak.setChecked(settings.get_bool("create_bak", True))
        f3.addRow(self.bak)
        self.autosave = QSpinBox()
        self.autosave.setRange(0, 120)
        self.autosave.setSuffix(" dk (0 = kapalı)")
        self.autosave.setValue(settings.get_int("autosave_min", 10))
        f3.addRow("Otomatik kaydetme aralığı:", self.autosave)
        v.addWidget(g3)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "ODAFileConverter.exe seçin", "C:/Program Files/ODA",
                                           "ODAFileConverter (ODAFileConverter*);;Tüm dosyalar (*)")
        if p:
            self.oda.setText(p)

    def _pick_bg(self):
        c = QColorDialog.getColor(QColor(self.bg.text()), self, "Arka plan rengi")
        if c.isValid():
            self.bg.setText(c.name())

    def save(self):
        settings.set("oda_path", self.oda.text().strip())
        settings.set("save_version", self.dwgver.currentData())
        settings.set("bg_color", self.bg.text())
        settings.set("cursor_size", self.cursor.value())
        settings.set("pickbox", self.pickbox.value())
        settings.set("aperture", self.aperture.value())
        settings.set("antialias", self.antialias.isChecked())
        settings.set("grid_unit", self.grid.value())
        settings.set("create_bak", self.bak.isChecked())
        settings.set("autosave_min", self.autosave.value())
        from t2dcad import i18n
        code = self.language.currentData()
        if code != i18n.lang():
            i18n.set_language(code)
            QMessageBox.information(self, "Dil / Language",
                                    "Dil değişikliği programı yeniden başlattığınızda uygulanır.\n"
                                    "The language change is applied when you restart the program.")


class MTextDialog(QDialog):
    def __init__(self, text: str, height: float, parent=None, styles=None, style=None):
        super().__init__(parent)
        self.setWindowTitle("Çok Satırlı Yazı")
        self.resize(520, 300)
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.height = QDoubleSpinBox()
        self.height.setRange(0.001, 100000)
        self.height.setDecimals(3)
        self.height.setValue(height)
        f.addRow("Yazı yüksekliği:", self.height)
        self.style = QComboBox()
        self.style.addItems(styles or ["Standard"])
        if style:
            self.style.setCurrentText(style)
        f.addRow("Yazı stili:", self.style)
        v.addLayout(f)
        self.edit = QPlainTextEdit(text)
        v.addWidget(self.edit, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.edit.setFocus()


class InsertDialog(QDialog):
    def __init__(self, main, tab, parent=None):
        super().__init__(parent)
        self.main = main
        self.tab = tab
        self.setWindowTitle("Blok Ekle")
        self.resize(420, 420)
        v = QVBoxLayout(self)
        self.list = QListWidget()
        v.addWidget(QLabel("Çizimdeki bloklar:"))
        v.addWidget(self.list, 1)
        b = QPushButton("Dosyadan ekle (DWG/DXF)...")
        b.clicked.connect(self._from_file)
        v.addWidget(b)
        f = QFormLayout()
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.0001, 100000)
        self.scale.setDecimals(4)
        self.scale.setValue(1.0)
        self.rot = QDoubleSpinBox()
        self.rot.setRange(-360, 360)
        f.addRow("Ölçek:", self.scale)
        f.addRow("Dönme açısı:", self.rot)
        v.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        self._fill()

    def _fill(self, select=None):
        self.list.clear()
        names = sorted(b.name for b in self.tab.doc.doc.blocks
                       if not b.name.startswith("*") and not b.block_record.is_any_layout)
        self.list.addItems(names)
        if select and select in names:
            self.list.setCurrentRow(names.index(select))
        elif names:
            self.list.setCurrentRow(0)

    def _from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Blok olarak eklenecek çizim", settings.get("last_dir", ""),
                                              "Çizimler (*.dwg *.dxf)")
        if not path:
            return
        name = self.main.import_file_as_block(self.tab, path)
        if name:
            self._fill(name)

    def result_values(self):
        it = self.list.currentItem()
        if it is None:
            return None
        return it.text(), self.scale.value(), self.rot.value()


class HatchDialog(QDialog):
    def __init__(self, last, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tarama")
        v = QVBoxLayout(self)
        f = QFormLayout()
        from ezdxf.tools.pattern import ISO_PATTERN
        self.pattern = QComboBox()
        self.pattern.addItems(["SOLID"] + sorted(ISO_PATTERN.keys()))
        self.pattern.setEditable(True)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.0001, 100000)
        self.scale.setDecimals(4)
        self.angle = QDoubleSpinBox()
        self.angle.setRange(-360, 360)
        p, s, a = last or ("ANSI31", 1.0, 0.0)
        self.pattern.setCurrentText(p)
        self.scale.setValue(s)
        self.angle.setValue(a)
        f.addRow("Desen:", self.pattern)
        f.addRow("Ölçek:", self.scale)
        f.addRow("Açı:", self.angle)
        v.addLayout(f)
        v.addWidget(QLabel("Tamam'a bastıktan sonra kapalı alanların içine tıklayın,\n"
                           "bitirmek için Enter'a basın."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def result_values(self):
        return self.pattern.currentText().strip() or "SOLID", self.scale.value(), self.angle.value()


class DimStyleDialog(QDialog):
    FIELDS = [
        ("dimtxt", "Yazı yüksekliği", 2.5),
        ("dimasz", "Ok boyutu", 2.5),
        ("dimexe", "Uzatma çizgisi taşması", 1.25),
        ("dimexo", "Uzatma çizgisi başlangıç boşluğu", 0.625),
        ("dimgap", "Yazı ile çizgi arası boşluk", 0.625),
        ("dimdli", "Taban çizgisi aralığı", 3.75),
        ("dimscale", "Genel ölçek (DIMSCALE)", 1.0),
        ("dimlfac", "Ölçü ölçek faktörü (DIMLFAC)", 1.0),
    ]

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.doc = tab.doc.doc
        self.setWindowTitle("Ölçü Stili Yöneticisi")
        v = QVBoxLayout(self)
        f = QFormLayout()
        self.style = QComboBox()
        self.style.addItems([d.dxf.name for d in self.doc.dimstyles])
        cur = self.doc.header.get("$DIMSTYLE", "T2D")
        self.style.setCurrentText(cur if cur in self.doc.dimstyles else "T2D")
        self.style.currentTextChanged.connect(self._load)
        f.addRow("Geçerli ölçü stili:", self.style)
        self.spins = {}
        for key, label, default in self.FIELDS:
            sp = QDoubleSpinBox()
            sp.setRange(0, 100000)
            sp.setDecimals(4)
            self.spins[key] = sp
            f.addRow(label + ":", sp)
        self.dec = QSpinBox()
        self.dec.setRange(0, 8)
        f.addRow("Ondalık basamak:", self.dec)
        self.txsty = QComboBox()
        self.txsty.addItems([st.dxf.name for st in self.doc.styles if st.dxf.name])
        f.addRow("Yazı stili:", self.txsty)
        self.arrow = QComboBox()
        self.arrow.addItems(["Kapalı dolu (varsayılan)", "ARCHTICK (mimari çentik)", "OBLIQUE (eğik)",
                             "DOT (nokta)", "OPEN (açık)"])
        f.addRow("Ok tipi:", self.arrow)
        v.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._load(self.style.currentText())

    def _load(self, name):
        ds = self.doc.dimstyles.get(name)
        if ds is None:
            return
        for key, label, default in self.FIELDS:
            self.spins[key].setValue(float(ds.dxf.get(key, default) or default))
        self.dec.setValue(int(ds.dxf.get("dimdec", 2)))
        self.txsty.setCurrentText(ds.dxf.get("dimtxsty", "Standard") or "Standard")
        blk = (ds.dxf.get("dimblk", "") or "").upper()
        idx = {"": 0, "ARCHTICK": 1, "OBLIQUE": 2, "DOT": 3, "OPEN": 4}.get(blk, 0)
        self.arrow.setCurrentIndex(idx)

    def apply(self):
        name = self.style.currentText()
        ds = self.doc.dimstyles.get(name)
        for key, label, default in self.FIELDS:
            ds.dxf.set(key, self.spins[key].value())
        ds.dxf.dimdec = self.dec.value()
        ds.dxf.dimtxsty = self.txsty.currentText() or "Standard"
        arrow = ["", "ARCHTICK", "OBLIQUE", "DOT", "OPEN"][self.arrow.currentIndex()]
        try:
            ds.set_arrows(blk=arrow)
        except Exception:
            ds.dxf.dimblk = arrow
        if arrow == "ARCHTICK" or arrow == "OBLIQUE":
            ds.dxf.dimtsz = 0
        self.doc.header["$DIMSTYLE"] = name
        self.tab.doc.set_modified(True)


HELP_HTML = """
<h2>T2D-CAD Hızlı Yardım</h2>
<p>Komutları AutoCAD'deki gibi klavyeden yazıp <b>Enter</b> veya <b>Boşluk</b> ile çalıştırın.
Boş Enter/Boşluk/sağ tık son komutu tekrarlar. <b>Esc</b> komutu iptal eder.</p>
<h3>Koordinat girişi</h3>
<ul><li><b>x,y</b> mutlak &nbsp; <b>@dx,dy</b> göreceli &nbsp; <b>@uzunluk&lt;açı</b> kutupsal</li>
<li>Sadece sayı yazmak: imleç yönünde o uzunlukta nokta (doğrudan mesafe girişi, ORTHO ile çok kullanışlı)</li>
<li>Nokta isterken <b>END, MID, CEN, INT, PER, NEA, QUA, TAN, NOD, INS</b> yazarak tek seferlik yakalama; Shift+sağ tık yakalama menüsü</li></ul>
<h3>Fonksiyon tuşları</h3>
<p>F2 metin penceresi · F3 OSNAP · F7 Izgara · F8 ORTHO · F9 SNAP · F10 Kutupsal · Ctrl+1 Özellikler ·
Ctrl+Z/Ctrl+Y geri al/yinele · Ctrl+C/V/X pano · Ctrl+A tümünü seç · Ctrl+P çizdir · Delete sil</p>
<h3>Komutlar (kısayol)</h3>
<table cellspacing=4>
<tr><td><b>Çizim</b></td><td>LINE (L), PLINE (PL), CIRCLE (C), ARC (A), RECTANG (REC), POLYGON (POL), ELLIPSE (EL),
POINT (PO), XLINE (XL), RAY, DONUT (DO), TEXT (DT), MTEXT (MT/T), HATCH (H), BLOCK (B), INSERT (I)</td></tr>
<tr><td><b>Değiştir</b></td><td>ERASE (E), MOVE (M), COPY (CO/CP), ROTATE (RO), SCALE (SC), MIRROR (MI), OFFSET (O),
TRIM (TR), EXTEND (EX), FILLET (F), CHAMFER (CHA), BREAK (BR), BREAKATPOINT (BRP), JOIN (J), EXPLODE (X), STRETCH (S),
ARRAY (AR), LENGTHEN (LEN), MATCHPROP (MA), TEXTEDIT (ED)</td></tr>
<tr><td><b>Ölçü</b></td><td>DIMLINEAR (DLI), DIMALIGNED (DAL), DIMRADIUS (DRA), DIMDIAMETER (DDI), DIMANGULAR (DAN),
DIMCONTINUE (DCO), DIMBASELINE (DBA), QLEADER (LE), DIMSTYLE (D)</td></tr>
<tr><td><b>Görünüm</b></td><td>ZOOM (Z: E/W/P/A), PAN (P), REGEN (RE) — fare tekerleği yakınlaştırır, orta tuş kaydırır,
orta tuşa çift tık = Zoom Kapsam</td></tr>
<tr><td><b>Sorgu</b></td><td>DIST (DI), AREA (AA), ID, LIST (LI)</td></tr>
<tr><td><b>Katman</b></td><td>LAYER (LA), LAYOFF, LAYON, LAYFRZ, LAYTHW, LAYLCK, LAYULK, LAYISO, LAYUNISO, LAYMCUR, LAYMCH</td></tr>
<tr><td><b>Dosya</b></td><td>NEW, OPEN, QSAVE, SAVEAS, PLOT (Ctrl+P), EXPORTPDF, CLOSE, QUIT</td></tr>
<tr><td><b>Ayarlar</b></td><td>OSNAP (OS), OPTIONS (OP), LTSCALE (LTS), PROPERTIES (PR), PURGE (PU), U, REDO</td></tr>
</table>
<h3>Seçim</h3>
<p>Nesneye tıklayın. Boş alana tıklayıp soldan sağa çekin: <b>Pencere</b> (tamamen içindekiler);
sağdan sola: <b>Kesişen</b> (değenler). Shift+tıklama seçimden çıkarır. Seçim isterken ALL, L (son), P (önceki)
yazılabilir. Seçili nesnelerin mavi tutamaçlarına (grip) tıklayıp gerdirebilirsiniz.</p>
"""


class TextStyleDialog(QDialog):
    """STYLE: text styles with an AutoCAD like font library and font import."""

    def __init__(self, main, tab, parent=None):
        super().__init__(parent)
        self.main = main
        self.tab = tab
        self.doc = tab.doc.doc
        self.setWindowTitle("Yazı Stili")
        self.resize(560, 360)
        from t2dcad import fonts
        self.fonts = fonts
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumWidth(180)
        top.addWidget(self.list)
        right = QFormLayout()
        self.font = QComboBox()
        self.font.setEditable(True)
        self.font.setMaxVisibleItems(25)
        right.addRow("Yazı tipi:", self.font)
        self.height = QDoubleSpinBox()
        self.height.setRange(0, 100000)
        self.height.setDecimals(3)
        right.addRow("Yükseklik (0 = değişken):", self.height)
        self.width = QDoubleSpinBox()
        self.width.setRange(0.01, 100)
        self.width.setDecimals(3)
        right.addRow("Genişlik faktörü:", self.width)
        self.oblique = QDoubleSpinBox()
        self.oblique.setRange(-85, 85)
        right.addRow("Eğiklik açısı:", self.oblique)
        self.preview = QLabel("AaBbÇçĞğİıÖöŞşÜü 0123")
        self.preview.setMinimumHeight(40)
        right.addRow("Önizleme:", self.preview)
        top.addLayout(right, 1)
        v.addLayout(top)
        row = QHBoxLayout()
        b_new = QPushButton("Yeni...")
        b_cur = QPushButton("Geçerli yap")
        b_imp = QPushButton("Yazı tipi içe aktar...")
        b_apply = QPushButton("Uygula")
        for b in (b_new, b_cur, b_imp, b_apply):
            row.addWidget(b)
        v.addLayout(row)
        b_new.clicked.connect(self._new)
        b_cur.clicked.connect(self._make_current)
        b_imp.clicked.connect(self._import)
        b_apply.clicked.connect(self._apply)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.list.currentTextChanged.connect(self._load)
        self.font.currentTextChanged.connect(self._preview)
        self._fill_fonts()
        self._fill(self.doc.header.get("$TEXTSTYLE", "Standard"))

    def _fill_fonts(self, select=None):
        cad, ttf = self.fonts.font_list()
        self.font.blockSignals(True)
        self.font.clear()
        for f in cad:
            self.font.addItem(f"{f}", f)
        self.font.insertSeparator(self.font.count())
        for f in ttf:
            self.font.addItem(f, f)
        self.font.blockSignals(False)
        if select:
            self.font.setCurrentText(select)

    def _fill(self, select=None):
        self.list.clear()
        names = [s.dxf.name for s in self.doc.styles if s.dxf.name]
        self.list.addItems(names)
        cur = self.doc.header.get("$TEXTSTYLE", "Standard")
        for i in range(self.list.count()):
            if self.list.item(i).text() == cur:
                self.list.item(i).setText(cur)
                f = self.list.item(i).font()
                f.setBold(True)
                self.list.item(i).setFont(f)
        items = self.list.findItems(select or cur, Qt.MatchExactly)
        if items:
            self.list.setCurrentItem(items[0])

    def _style(self):
        it = self.list.currentItem()
        return self.doc.styles.get(it.text()) if it else None

    def _load(self, name):
        st = self.doc.styles.get(name) if name else None
        if st is None:
            return
        font = st.dxf.get("font", "txt") or "txt"
        if "." not in font:
            font += ".shx"
        self.font.setCurrentText(font)
        self.height.setValue(st.dxf.get("height", 0.0))
        self.width.setValue(st.dxf.get("width", 1.0) or 1.0)
        self.oblique.setValue(st.dxf.get("oblique", 0.0))
        self._preview(font)

    def _preview(self, font):
        from PySide6.QtGui import QFont
        name = font.lower()
        if name.endswith((".ttf", ".otf", ".ttc")):
            f = QFont(font.rsplit(".", 1)[0])
        else:
            f = QFont("Consolas")
        f.setPointSize(14)
        self.preview.setFont(f)

    def _apply(self):
        st = self._style()
        if st is None:
            return
        old = (st.dxf.get("font", "txt"), st.dxf.get("height", 0.0), st.dxf.get("width", 1.0),
               st.dxf.get("oblique", 0.0))
        new = (self.font.currentText().strip() or "txt.shx", self.height.value(), self.width.value(),
               self.oblique.value())

        def set_(vals):
            st.dxf.font, st.dxf.height, st.dxf.width, st.dxf.oblique = vals
        set_(new)
        self.tab.doc.custom(lambda: set_(old), lambda: set_(new))

    def _new(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Yeni yazı stili", "Stil adı:", text="Stil1")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self.doc.styles:
            QMessageBox.warning(self, "Yazı stili", "Bu adda bir stil zaten var.")
            return
        self.doc.styles.add(name, font=self.font.currentText() or "txt.shx")
        self.tab.doc.set_modified(True)
        self._fill(name)

    def _make_current(self):
        st = self._style()
        if st is not None:
            self.doc.header["$TEXTSTYLE"] = st.dxf.name
            self._fill(st.dxf.name)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Yazı tipi seçin", "",
                                              "Yazı tipleri (*.ttf *.otf *.ttc *.shx *.lff)")
        if not path:
            return
        try:
            name = self.fonts.import_font(path)
        except Exception as ex:
            QMessageBox.critical(self, "Yazı tipi", f"İçe aktarılamadı:\n{ex}")
            return
        if name.lower().endswith(".lff"):
            name = name[:-4] + ".shx"
        self._fill_fonts(name)
        QMessageBox.information(self, "Yazı tipi", f'"{name}" yazı tipi eklendi.')


class PdfImportDialog(QDialog):
    """PDFIMPORT options (like AutoCAD / progeCAD)."""

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        from t2dcad import pdfimport
        self.pdfimport = pdfimport
        self.setWindowTitle("PDF içe aktar")
        self.setMinimumWidth(480)
        v = QVBoxLayout(self)
        row = QHBoxLayout()
        self.path = QLineEdit(path)
        b = QPushButton("Gözat...")
        b.clicked.connect(self._browse)
        row.addWidget(self.path, 1)
        row.addWidget(b)
        v.addLayout(row)
        f = QFormLayout()
        self.page = QSpinBox()
        self.page.setMinimum(1)
        self.page.valueChanged.connect(self._info)
        self.info = QLabel()
        f.addRow("Sayfa:", self.page)
        f.addRow("", self.info)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.0001, 100000)
        self.scale.setDecimals(4)
        self.scale.setValue(settings.get_float("pdf_scale", 1.0))
        self.scale.setToolTip("1 = kağıt üzerindeki gerçek boyut (mm).\n"
                              "Çizim 1:50 çizdirildiyse 50 yazın, gerçek ölçüler gelir.")
        f.addRow("Ölçek:", self.scale)
        v.addLayout(f)
        g = QGroupBox("İçe aktarılacaklar")
        gl = QVBoxLayout(g)
        self.vectors = QCheckBox("Vektörel geometri (çizgi, yay, daire, polyline)")
        self.fills = QCheckBox("Dolu alanlar (SOLID tarama)")
        self.text = QCheckBox("TrueType yazılar")
        self.lw = QCheckBox("Çizgi kalınlıklarını uygula")
        self.join = QCheckBox("Birleşik çizgi ve yay parçalarını polyline yap")
        self.arcs = QCheckBox("Eğrilerden yay ve daire tanı")
        self.colors = QCheckBox("PDF renklerini koru")
        self.images = QCheckBox("Raster resimler (PNG olarak PDF'nin yanına kaydedilir)")
        for cb, key in ((self.vectors, "pdf_vectors"), (self.fills, "pdf_fills"), (self.text, "pdf_text"),
                        (self.images, "pdf_images"),
                        (self.lw, "pdf_lw"), (self.join, "pdf_join"), (self.arcs, "pdf_arcs"),
                        (self.colors, "pdf_colors")):
            cb.setChecked(settings.get_bool(key, True))
            cb.setProperty("key", key)
            gl.addWidget(cb)
        v.addWidget(g)
        f2 = QFormLayout()
        self.layers = QComboBox()
        self.layers.addItems(["Nesne türüne göre (PDF_Geometri, PDF_Dolgu, PDF_Yazi)",
                              "PDF katmanlarını kullan", "Geçerli katman"])
        self.layers.setCurrentIndex(settings.get_int("pdf_layers", 0))
        f2.addRow("Katmanlar:", self.layers)
        v.addLayout(f2)
        v.addWidget(QLabel("Tamam'dan sonra yerleştirme noktasını gösterin (Enter = 0,0)."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._load_pages()

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "PDF dosyası", settings.get("last_dir", ""), "PDF (*.pdf)")
        if p:
            self.path.setText(p)
            self._load_pages()

    def _load_pages(self):
        try:
            w, h, n = self.pdfimport.page_size_mm(self.path.text(), 0)
            self.page.setMaximum(max(1, n))
            self._info()
        except Exception as ex:
            self.info.setText(f"PDF okunamadı: {ex}")

    def _info(self):
        try:
            w, h, n = self.pdfimport.page_size_mm(self.path.text(), self.page.value() - 1)
            self.info.setText(f"{n} sayfa · bu sayfa {w:.0f} x {h:.0f} mm")
        except Exception as ex:
            self.info.setText(f"PDF okunamadı: {ex}")

    def options(self):
        o = self.pdfimport.PdfImportOptions(
            page=self.page.value() - 1, scale=self.scale.value(), vectors=self.vectors.isChecked(),
            fills=self.fills.isChecked(), text=self.text.isChecked(), lineweights=self.lw.isChecked(),
            join=self.join.isChecked(), arcs=self.arcs.isChecked(), colors=self.colors.isChecked(),
            images=self.images.isChecked(),
            layer_mode=["type", "pdf", "current"][self.layers.currentIndex()])
        for cb in (self.vectors, self.fills, self.text, self.lw, self.join, self.arcs, self.colors, self.images):
            settings.set(cb.property("key"), cb.isChecked())
        settings.set("pdf_scale", self.scale.value())
        settings.set("pdf_layers", self.layers.currentIndex())
        return o
