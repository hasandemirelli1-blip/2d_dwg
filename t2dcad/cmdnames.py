"""Turkish descriptions of commands (shown in the auto-complete list) and the
ranking of frequently used commands."""

DESCRIPTIONS = {
    "LINE": "Çizgi", "PLINE": "Çoklu çizgi", "CIRCLE": "Çember", "ARC": "Yay", "RECTANG": "Dikdörtgen",
    "POLYGON": "Çokgen", "ELLIPSE": "Elips", "POINT": "Nokta", "XLINE": "Yapı çizgisi", "RAY": "Işın",
    "DONUT": "Halka", "TEXT": "Tek satır yazı", "MTEXT": "Çok satırlı yazı", "HATCH": "Tarama",
    "BLOCK": "Blok tanımla", "INSERT": "Blok ekle", "TEXTEDIT": "Yazı düzenle",
    "ERASE": "Sil", "MOVE": "Taşı", "COPY": "Kopyala", "ROTATE": "Döndür", "SCALE": "Ölçekle",
    "MIRROR": "Aynala", "OFFSET": "Ofset", "TRIM": "Buda", "EXTEND": "Uzat", "BREAK": "Kır",
    "BREAKATPOINT": "Noktadan kır", "FILLET": "Kavis", "CHAMFER": "Pah", "EXPLODE": "Patlat",
    "STRETCH": "Gerdir", "ARRAY": "Dizi", "JOIN": "Birleştir", "MATCHPROP": "Özellik eşle",
    "LENGTHEN": "Uzunluk değiştir",
    "DIMLINEAR": "Doğrusal ölçü", "DIMALIGNED": "Hizalı ölçü", "DIMRADIUS": "Yarıçap ölçüsü",
    "DIMDIAMETER": "Çap ölçüsü", "DIMANGULAR": "Açı ölçüsü", "DIMCONTINUE": "Ölçüye devam",
    "DIMBASELINE": "Taban çizgisi ölçüsü", "QLEADER": "Kılavuz (not)", "DIMSTYLE": "Ölçü stili",
    "STYLE": "Yazı stili", "ZOOM": "Yakınlaştır", "ZE": "Zoom kapsam", "ZW": "Zoom pencere",
    "ZP": "Zoom önceki", "PAN": "Kaydır", "REGEN": "Yeniden oluştur", "REDRAW": "Yeniden çiz",
    "NEW": "Yeni çizim", "OPEN": "Aç", "QSAVE": "Kaydet", "SAVEAS": "Farklı kaydet", "CLOSE": "Kapat",
    "QUIT": "Çıkış", "PLOT": "Çizdir / yazdır", "EXPORTPDF": "PDF olarak dışa aktar",
    "U": "Geri al", "REDO": "Yinele", "COPYCLIP": "Panoya kopyala", "COPYBASE": "Temel noktayla kopyala",
    "CUTCLIP": "Kes", "PASTECLIP": "Yapıştır", "SELECTALL": "Tümünü seç",
    "DIST": "Uzaklık ölç", "ID": "Nokta koordinatı", "AREA": "Alan ölç", "LIST": "Liste",
    "LAYER": "Katman yöneticisi", "OSNAP": "Nesne yakalama ayarları", "OPTIONS": "Seçenekler",
    "PROPERTIES": "Özellikler", "LTSCALE": "Çizgi tipi ölçeği", "ORTHO": "Dik mod", "UNITS": "Birimler",
    "HELP": "Yardım", "TEXTSCR": "Metin penceresi", "LAYOFF": "Katmanı kapat", "LAYON": "Katmanları aç",
    "LAYFRZ": "Katmanı dondur", "LAYTHW": "Katmanları çöz", "LAYLCK": "Katmanı kilitle",
    "LAYULK": "Katman kilidini aç", "LAYISO": "Katmanı yalıt", "LAYUNISO": "Yalıtmayı kaldır",
    "LAYMCUR": "Nesnenin katmanını geçerli yap", "LAYMCH": "Katmanı eşle", "PURGE": "Temizle",
    "FONTIMPORT": "Yazı tipi içe aktar", "RIBBON": "Şerit menü", "MENUBAR": "Klasik menü",
    "STARTPAGE": "Başlangıç sayfası", "PDFIMPORT": "PDF içe aktar", "REFEDIT": "Bloğu yerinde düzenle",
    "REFADD": "Bloğa ekle", "REFREMOVE": "Bloktan çıkar", "REFCLOSE": "Blok düzenlemeyi kapat",
}

# frequently used commands first (AutoCAD-like suggestion order)
POPULAR = [
    "LINE", "CIRCLE", "COPY", "MOVE", "TRIM", "OFFSET", "ERASE", "PLINE", "RECTANG", "ROTATE",
    "MIRROR", "EXTEND", "FILLET", "SCALE", "ARC", "HATCH", "DIMLINEAR", "TEXT", "MTEXT", "LAYER",
    "STRETCH", "EXPLODE", "ARRAY", "ZOOM", "PAN", "REGEN", "DIST", "MATCHPROP", "JOIN", "BREAK",
    "CHAMFER", "POLYGON", "ELLIPSE", "INSERT", "BLOCK", "DIMALIGNED", "DIMRADIUS", "DIMCONTINUE",
    "PLOT", "QSAVE", "PROPERTIES",
]
