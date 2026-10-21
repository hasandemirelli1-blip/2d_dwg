# T2D-CAD

AutoCAD benzeri, **sadece 2B** çalışan, ücretsiz bir çizim programı (Windows).
DWG/DXF dosyalarını açar, düzenler ve kaydeder. Komutlar, kısayollar, OSNAP, ORTHO,
katmanlar ve yazdırma AutoCAD'deki gibi çalışır.

> Kişisel kullanım içindir. Programda kullanılan tüm bileşenler ücretsizdir.

---

## 1. Kurulum (Windows)

### A) Hazır program (önerilen)
1. GitHub'da bu deponun **Actions** sekmesine girin → en son başarılı **"Windows build"** çalışmasını açın.
2. Sayfanın altındaki **Artifacts** bölümünden `T2D-CAD-windows` dosyasını indirin.
3. ZIP'i bir klasöre açın (ör. `C:\T2D-CAD`) ve **`T2D-CAD.exe`** dosyasını çalıştırın.
   İsterseniz exe'ye sağ tıklayıp masaüstüne kısayol gönderin.

### B) Kaynak koddan çalıştırma
1. [python.org](https://www.python.org/downloads/) adresinden Python 3.12 kurun ("Add python.exe to PATH" seçili olsun).
2. Bu klasördeki **`T2D-CAD_kaynaktan_calistir.bat`** dosyasına çift tıklayın.
   İlk açılışta gerekli paketleri kurar (birkaç dakika), sonra her seferinde doğrudan açılır.

### DWG desteği
DWG kapalı bir formattır; bu işi ücretsiz **ODA File Converter** yapar.
* GitHub'dan indirilen hazır pakette ODA File Converter **zaten içinde** (`oda` klasörü) gelir, ayrıca bir şey kurmanız gerekmez.
* Paket içinde yoksa ilk DWG açılışında T2D-CAD bunu **otomatik indirip kurmayı** önerir
  (Başlangıç sayfasında ve Araçlar menüsünde "DWG desteğini kur" düğmesi de vardır).
* ODA File Converter'ı Open Design Alliance ücretsiz dağıtır; ticari olmayan kullanım içindir.

---

## 2. Kullanım – AutoCAD'deki gibi

* Komutu klavyeden yazın (ekranın herhangi bir yerinde yazmaya başlamanız yeterli), **Enter** veya **Boşluk** ile çalıştırın.
* Boş **Enter / Boşluk / sağ tık** komutu bitirir. Komut yokken son komutu tekrarlar.
* **Esc** komutu iptal eder ve seçimi temizler.
* **Fare tekerleği** imlecin olduğu yere doğru yakınlaştırır. **Orta tuşla sürüklemek** kaydırır.
  **Orta tuşa çift tık** = Zoom Kapsam.

### Arayüz
* **Şerit (Ribbon)** veya **Klasik menü**: Görünüm menüsünden, durum çubuğundaki ☰ düğmesinden ya da
  `RIBBON` / `MENUBAR` komutlarıyla seçilir. Seçim hatırlanır.
* Şerit progeCAD/AutoCAD gibi kompakttır: küçük düğmeler üçlü sıralanır, ▾ oklu düğmeler seçenekleri gruplar
  (Çember: merkez-yarıçap / çap / 2P / 3P / TTR, Buda/Uzat, Kavis/Pah, ölçü türleri...). Panel başlığındaki ▾ ek
  komutları açar. Pencere dar ise sağdaki paneller tek düğmeye küçülür, kaydırma gerekmez.
* **Başlangıç sayfası**: son açılan çizimler küçük resimleriyle listelenir (sağ tık → listeden kaldır).
* **Otomatik tamamlama**: komut yazmaya başlayınca (ör. `R`, `RE`) AutoCAD'deki gibi öneri listesi açılır.
  ↑/↓ ile seçin, Enter/Boşluk ile çalıştırın.

### Koordinat girişi
| Yazım | Anlamı |
|---|---|
| `100,50` | mutlak nokta |
| `@100,50` | son noktaya göre |
| `@100<30` | son noktadan 100 birim, 30° |
| `250` | imleç yönünde 250 birim (doğrudan mesafe; ORTHO ile çok pratik) |
| `END`, `MID`, `CEN`, `INT`, `PER`, `TAN`, `NEA`, `QUA`, `NOD`, `INS` | tek seferlik nesne yakalama (Shift + sağ tık menüsü de var) |
| `FROM` | referans noktasından ofset: önce referans noktayı tıklayın, sonra `@10,5` yazın |
| `M2P` | iki noktanın ortası |

### Nesne yakalama izleme (OTRACK, F11)
Nokta isterken imleci bir yakalama noktasının (uç, orta, merkez...) üzerinde kısa süre bekletin:
küçük turuncu **+** işareti çıkar (nokta "alındı"). Sonra imleci yatay/dikey (KUTUPSAL açıksa onun açılarında)
hizalayınca yeşil kesikli izleme çizgisi görünür. Bu durumda sadece bir sayı yazarsanız nokta, alınan
noktadan o mesafede oluşur. İki izleme çizgisinin kesişimine de yakalanır.

### Kısayol tuşları
| Tuş | İşlev | Tuş | İşlev |
|---|---|---|---|
| F1 | Yardım | Ctrl+N / O / S | Yeni / Aç / Kaydet |
| F2 | Komut geçmişi penceresi | Ctrl+Shift+S | Farklı kaydet |
| F3 | OSNAP aç/kapa | Ctrl+P | Çizdir (yazıcı / PDF) |
| F7 | Izgara | Ctrl+Z / Ctrl+Y | Geri al / Yinele |
| F8 | ORTHO | Ctrl+C / X / V | Pano: kopyala / kes / yapıştır |
| F9 | SNAP (ızgaraya yakalama) | Ctrl+Shift+C | Temel noktayla kopyala |
| F10 | Kutupsal izleme (POLAR) | Ctrl+A | Tümünü seç |
| F11 | Nesne yakalama izleme (OTRACK) | | |
| Ctrl+1 | Özellikler paneli | Delete | Seçileni sil |
| Ctrl+9 | Komut satırını gizle/göster | Ctrl+F4 | Çizimi kapat |

### Seçim
* Nesneye tıklama → seçer. **Shift + tıklama** → seçimden çıkarır.
* Boş alana tıklayıp **soldan sağa** çekmek: *Pencere* (tamamı içinde kalanlar, mavi).
  **Sağdan sola**: *Kesişen* (değen her şey, yeşil).
* Seçim isterken `ALL`, `L` (son), `P` (önceki), `R` (çıkar), `A` (ekle) yazılabilir.
* Seçili nesnelerin **mavi tutamaçlarına (grip)** tıklayıp nesneyi gerdirebilir/taşıyabilirsiniz.
* Önce seçip sonra komut vermek (ör. seç → `M`) desteklenir.

### Komutlar
| Grup | Komutlar (kısaltma) |
|---|---|
| Çizim | LINE (L), PLINE (PL), CIRCLE (C), ARC (A), RECTANG (REC), POLYGON (POL), ELLIPSE (EL), POINT (PO), XLINE (XL), RAY, DONUT (DO), TEXT (DT), MTEXT (T/MT), HATCH (H), BLOCK (B), INSERT (I) |
| Değiştirme | ERASE (E), MOVE (M), COPY (CO/CP), ROTATE (RO), SCALE (SC), MIRROR (MI), OFFSET (O), TRIM (TR), EXTEND (EX), FILLET (F), CHAMFER (CHA), BREAK (BR), BREAKATPOINT (BRP), ALIGN (AL), JOIN (J), EXPLODE (X), STRETCH (S), ARRAY (AR), LENGTHEN (LEN), MATCHPROP (MA), TEXTEDIT (ED), PROPERTIES (PR / Ctrl+1) |
| Ölçülendirme | DIMLINEAR (DLI), DIMALIGNED (DAL), DIMANGULAR (DAN), DIMRADIUS (DRA), DIMDIAMETER (DDI), DIMCONTINUE (DCO), DIMBASELINE (DBA), QLEADER (LE), DIMSTYLE (D) |
| Görünüm | ZOOM (Z: E/W/P/A/C/S), ZE, ZW, ZP, PAN (P), REGEN (RE) |
| Sorgulama | DIST (DI), AREA (AA), ID, LIST (LI) |
| Katman | LAYER (LA), LAYOFF, LAYON, LAYFRZ, LAYTHW, LAYLCK, LAYULK, LAYISO, LAYUNISO, LAYMCUR, LAYMCH |
| Dosya | NEW, OPEN, QSAVE, SAVEAS, PLOT (Ctrl+P), EXPORTPDF, CLOSE, QUIT |
| Resim | IMAGEATTACH (IAT/IM): PNG/JPG/BMP resim ekleme (sürükle-bırak da olur) |
| Yazı | STYLE (ST): yazı stili ve yazı tipi seçimi, FONTIMPORT: yazı tipi içe aktarma |
| Diğer | U, REDO, OSNAP (OS/DS), OPTIONS (OP), LTSCALE (LTS), PURGE (PU), COPYCLIP, PASTECLIP, HELP |

### Bloklar (AutoCAD gibi yerinde düzenleme)
* Bir bloğa **çift tıklayın** veya `REFEDIT` (`BEDIT`) yazın: blok yerinde düzenlenir, diğer her şey soluklaşır.
* Normal komutlarla çizin/değiştirin; yeni çizdikleriniz bloğa dahil olur.
* Üstteki şeritten **Bloğa ekle** (`REFADD`): çizimdeki bir nesneyi bloğun içine alır.
  **Bloktan çıkar** (`REFREMOVE`): bloktaki bir nesneyi bloktan çıkarıp çizimde bırakır.
* **Değişiklikleri kaydet** (`REFCLOSE`): bloğun tüm kopyaları güncellenir. **Vazgeç**: hiçbir şey değişmez.

### PDF içe aktarma (PDFIMPORT)
* `PDFIMPORT` yazın, menüden (Dosya / Ekle sekmesi) seçin veya PDF dosyasını pencereye sürükleyin.
* AutoCAD / progeCAD'deki gibi: çizgiler, yaylar, daireler, elipsler, polyline'lar, dolu alanlar (SOLID tarama)
  ve TrueType yazılar **düzenlenebilir nesneler** olarak gelir. Renkler, çizgi kalınlıkları ve kesikli çizgiler korunur.
* Ölçek: 1 = kağıt üzerindeki gerçek boyut (mm). Çizim 1:50 çizdirildiyse 50 yazın, gerçek ölçüler gelir.
* Katmanlar: nesne türüne göre (PDF_Geometri / PDF_Dolgu / PDF_Yazi), PDF'nin kendi katmanları veya geçerli katman.
* PDF içindeki resimler (antetteki logolar vb.) PNG olarak `<pdf adı>_resimler` klasörüne çıkarılır ve PDF_Resim katmanına yerleştirilir.
* SHX yazıların metne dönüştürülmesi desteklenmez (SHX yazılar çizgi olarak gelir).

### Resim ekleme ve hizalama (IMAGEATTACH, ALIGN)
* `IMAGEATTACH` (IAT): eklenecek noktayı, ölçeği (genişlik) ve açıyı verin. Resim her zaman çizgilerin arkasında kalır.
* Resmi çizime oturtmak için `ALIGN` (AL): resmi seçin, resimdeki 2 noktayı çizimdeki karşılıklarına gösterin, ölçeklensin mi sorusuna Yes deyin.
* Özellikler panelinde resmin dosyası, konumu, genişliği ve dönmesi değiştirilebilir.

### BREAK (BR) – AutoCAD gibi
* Nesneyi seçtiğiniz nokta 1. kırma noktasıdır; 2. noktayı gösterin (nesne dışında da olabilir, nesneye izdüşürülür).
* `F` (İlk nokta): 1. noktayı yeniden seçer. `@`: aynı noktadan ikiye böler (BREAKATPOINT gibi).
* Daire ve kapalı polyline'larda saatin tersi yönündeki parça silinir. Çizgi, yay, daire, elips, polyline desteklenir.

### Dil / Language
* Görünüm menüsü > **Dil / Language** veya Seçenekler (OPTIONS) > Dil: Türkçe veya English. Program yeniden açıldığında geçerli olur.

### Özellikler paneli (Ctrl+1)
* Yazılarda stil, **yazı tipi**, yükseklik, dönme, genişlik faktörü, eğiklik, hizalama.
* Ölçülerde AutoCAD'deki gruplar: Çizgiler ve oklar (ok tipleri, ok boyutu, uzatma çizgileri),
  Yazı (yazı stili/tipi, yükseklik, renk, konum, metin geçersiz kılma), Birincil birimler
  (**önek, sonek**, hassasiyet, ölçek faktörü, yuvarlama, ondalık ayırıcı), Sığdır (DIMSCALE).

### Yazdırma (PLOT – Ctrl+P)
* Yazıcı listesinde Windows'a kurulu tüm yazıcılar ve **Microsoft Print to PDF** görünür.
  Ayrıca dahili **"PDF dosyası (T2D-CAD dahili)"** seçeneği vardır.
* Kağıt boyutu (A4–A0, Letter...), yatay/dikey, alan (**Kapsam / Ekran / Pencere**), ölçek
  (**Kağıda sığdır** veya 1:1, 1:50, 1:100 ... çizim birimi mm kabul edilir), ortalama.
* Çizim stili: **Monokrom (siyah)**, Renkli veya Gri tonlama. Çizgi kalınlıkları basılabilir.
* **Önizleme** düğmesiyle kağıt üzerinde nasıl çıkacağını görebilirsiniz.
* Katman yöneticisinde "Çizdir" işareti kaldırılan katmanlar basılmaz (Defpoints hiç basılmaz).

---

## 3. Bilinen sınırlamalar (sürüm 0.1)

* Sadece **Model** alanı açılıp düzenlenir. Dosyadaki *Layout* (kağıt alanı) sayfaları korunur
  ve kaydedilir, ama görüntülenmez/düzenlenmez. Yazdırma model alanından yapılır.
* Dinamik giriş kutuları (DYN, F12) yok; koordinatlar komut satırına yazılır,
  imleç yanında uzunluk/açı gösterilir.
* FILLET/CHAMFER: çizgiler ve 2B çoklu çizgiler (Polyline seçeneği) destekleniyor.
* OFFSET: çizgi, yay, çember, 2B çoklu çizgi. Elips/spline ofseti yok.
* Yazı tipleri: AutoCAD SHX fontlarının benzerleri (txt, simplex, romans, isocp, italic...) programla gelir
  (LibreCAD çizgi fontları, Türkçe karakterler eklendi). Bilgisayarda AutoCAD kuruluysa gerçek SHX
  fontları otomatik kullanılır. Windows TrueType fontları ve içe aktarılan fontlar da seçilebilir.

---

## 4. Geliştirici notları

* Python 3.10+, [PySide6](https://doc.qt.io/qtforpython-6/) (Qt arayüzü),
  [ezdxf](https://ezdxf.readthedocs.io/) (DXF okuma/yazma ve çizim motoru).
* Klasörler:
  * `t2dcad/engine.py` – komut motoru (komutlar `yield GetPoint(...)` ile kullanıcıdan girdi ister)
  * `t2dcad/commands/` – tüm komutlar (çizim, değiştirme, ölçü, blok/tarama, dosya/görünüm/katman)
  * `t2dcad/canvas.py` – çizim alanı (zoom/pan, imleç, OSNAP/ORTHO/POLAR, seçim, grip)
  * `t2dcad/render.py` – ezdxf ile çizim; `t2dcad/snap.py` – nesne yakalama
  * `t2dcad/docmodel.py` – dosya açma/kaydetme (DXF/DWG) ve geri al/yinele
  * `t2dcad/ui/` – komut satırı, katman yöneticisi, özellikler paneli, yazdırma, diyaloglar
* Testler: `QT_QPA_PLATFORM=offscreen python -m pytest tests`
* Windows exe: `pyinstaller T2D-CAD.spec` (GitHub Actions bunu her push'ta otomatik yapar).
