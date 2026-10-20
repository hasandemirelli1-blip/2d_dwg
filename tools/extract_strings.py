import ast, sys, json, re
from pathlib import Path
TR = set("çğıöşüÇĞİÖŞÜ")
out = {}
EXTRA = {"kaydet","renk","katman","stil","yeni","kopya","tamam","merkez","nokta","hedef","kaynak","mesafe","sayfa","desen","ekle","seri","liste","modu","mod","kalem","birim","ofset","dizi","resim","model","alan","adet","sadece","veya","olarak","ile","gibi","bulundu","dosya","komut","ayar","seviye","ince","kalin","kopyala","tekrarla","temizle","ortala","sabit","dikey","yatay","sol","orta","alt","ust","kenar"}
def interesting(s):
    if not s or not s.strip():
        return False
    if any(c in TR for c in s):
        return True
    words = re.findall(r"[A-Za-zçğıöşüÇĞİÖŞÜ]+", s)
    tr_words = {"ve","ile","bir","bu","için","yok","seçin","nokta","nesne","katman","yazı","komut","dosya","resim",
                "belirtin","girin","açık","kapalı","sayfa","ölçek","ayarlar","tamam","iptal","yeni","aç","kaydet","kapat",
                "renk","genişlik","yükseklik","dönme","konum","alan","uzunluk","stil","blok","çizgi","yay","çember",
                "elips","tarama","boyut","Uzat","Buda","Kır","Dizi","Ofset","Taşı","Kopyala","Döndür","Ölçekle","Aynala",
                "Sil","Patlat","Gerdir","Pah","Birleştir","Hizala","Yapıştır","Kes","Kopyala","Liste","Ekle","Görünüm",
                "Çıktı","Yönet","Giriş","Açıklama","Dosya","Düzen","Biçim","Araçlar","Yardım","Değiştir","Çiz","Ölçü",
                "Izgara","Kutupsal","Başlangıç","Özellikler","Önizleme","Çizdir","Monokrom","Renkli","Dikey","Yatay",
                "Pencere","Ekran","Kapsam","Sürüm","Uyarı","Hata","Geri","Yinele","Tümünü","seç","Varsayılan","KatmanaGöre",
                "BlokaGöre","Kırmızı","Sarı","Yeşil","Mavi","Beyaz","Siyah","Camgöbeği","Eflatun","Diğer"}
    lw = {x.lower() for x in tr_words}
    return any(w.lower() in lw for w in words) or any(w.lower() in EXTRA for w in words)
for f in sorted(Path(sys.argv[1]).rglob("*.py")):
    src = f.read_text(encoding="utf8")
    tree = ast.parse(src)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and node.body:
            b = node.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                docs.add(id(b.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value).replace("{", "{{").replace("}", "}}"))
                else:
                    parts.append("{}")
            t = "".join(parts)
            for v in node.values:
                if isinstance(v, ast.Constant):
                    v._skip = True
            if interesting(t.replace("{}", "")):
                out.setdefault(t, f"{f.name}:{node.lineno} F")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docs or getattr(node, "_skip", False):
                continue
            if interesting(node.value):
                out.setdefault(node.value, f"{f.name}:{node.lineno}")
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=0)
print(len(out), sum(1 for v in out.values() if v.endswith("F")))
