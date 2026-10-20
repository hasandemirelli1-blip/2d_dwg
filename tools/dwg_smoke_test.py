"""CI check: write a DWG with the bundled ODA File Converter and read it back.

    python tools/dwg_smoke_test.py dist/T2D-CAD/oda
"""
import glob
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exe = glob.glob(os.path.join(sys.argv[1], "**", "ODAFileConverter.exe"), recursive=True)
if not exe:
    sys.exit("ODAFileConverter.exe not found")
from t2dcad import settings  # noqa: E402
settings.set("oda_path", exe[0])
from t2dcad.docmodel import CadDocument  # noqa: E402

d = CadDocument.new()
d.msp.add_line((0, 0), (100, 50))
d.msp.add_circle((50, 50), 20)
d.msp.add_text("Türkçe ŞĞÜİÖÇ", dxfattribs={"height": 5})
out = os.path.join(tempfile.mkdtemp(), "test.dwg")
d.save(out, "R2018")
print("DWG written:", out, os.path.getsize(out), "bytes")
d2 = CadDocument.open(out)
types = sorted(e.dxftype() for e in d2.msp)
print("read back:", types)
assert types == ["CIRCLE", "LINE", "TEXT"], types
print("DWG round trip OK")
