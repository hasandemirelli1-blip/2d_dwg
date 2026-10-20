"""Functional tests: drive commands through the command line like a user.

Run:  QT_QPA_PLATFORM=offscreen python -m pytest tests
"""
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["T2D_TEST"] = "1"

from PySide6.QtWidgets import QApplication  # noqa: E402

from ezdxf.math import Vec2  # noqa: E402


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    from t2dcad import settings
    settings._s().clear()
    return a


@pytest.fixture
def tab(app):
    from t2dcad.app import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    t = w.file_new()
    t.canvas.resize(1000, 700)
    t.canvas.zoom_rect(-50, -50, 250, 200, push=False)
    yield t
    t.doc.set_modified(False)
    w.close()


def run(tab, *inputs):
    """Type inputs into the command line (each item = one Enter)."""
    mgr = tab.manager
    for x in inputs:
        if isinstance(x, tuple):  # click a point
            mgr.point_input(Vec2(*x)) if mgr.req is not None and not hasattr(mgr.req, "types") \
                else mgr.send((tab.doc.entity_by_handle(tab.renderer.pick(x[0], x[1], 1.0)), Vec2(*x)))
        else:
            mgr.text_input(x)


def types(tab):
    return sorted(e.dxftype() for e in tab.doc.msp)


def test_line_and_undo(tab):
    run(tab, "L", "0,0", "100,0", "@0,50", "C")
    assert types(tab) == ["LINE"] * 3
    run(tab, "U")
    assert len(tab.doc.msp) == 0
    run(tab, "REDO")
    assert len(tab.doc.msp) == 3


def test_polar_and_direct_distance(tab):
    run(tab, "L", "10,10", "@50<90", "")
    e = list(tab.doc.msp)[0]
    assert Vec2(e.dxf.end).isclose(Vec2(10, 60))


def test_circle_rect_polygon(tab):
    run(tab, "C", "0,0", "25")
    run(tab, "REC", "0,0", "@100,50")
    run(tab, "POL", "6", "200,0", "I", "30")
    assert types(tab) == ["CIRCLE", "LWPOLYLINE", "LWPOLYLINE"]


def test_trim(tab):
    run(tab, "L", "0,0", "100,0", "")
    run(tab, "L", "50,-20", "50,20", "")
    vertical = [e for e in tab.doc.msp if e.dxf.start.x == 50][0]
    horizontal = [e for e in tab.doc.msp if e.dxf.start.y == 0 and e.dxf.end.y == 0][0]
    run(tab, "TR")
    tab.manager.send((horizontal, Vec2(80, 0)))
    tab.manager.enter()
    lines = [e for e in tab.doc.msp if abs(e.dxf.start.y) < 1e-9 and abs(e.dxf.end.y) < 1e-9]
    assert len(lines) == 1
    assert max(lines[0].dxf.start.x, lines[0].dxf.end.x) == pytest.approx(50)


def test_offset_polyline(tab):
    run(tab, "REC", "0,0", "100,50")
    rect = list(tab.doc.msp)[0]
    run(tab, "O", "10")
    tab.manager.send((rect, Vec2(0, 25)))
    run(tab, "-50,25", "")
    polys = [e for e in tab.doc.msp if e.dxftype() == "LWPOLYLINE"]
    assert len(polys) == 2
    big = max(polys, key=lambda p: max(v[0] for v in p.get_points()))
    xs = [v[0] for v in big.get_points()]
    assert min(xs) == pytest.approx(-10) and max(xs) == pytest.approx(110)


def test_fillet_lines(tab):
    run(tab, "L", "0,0", "100,0", "")
    run(tab, "L", "0,0", "0,100", "")
    a, b = list(tab.doc.msp)
    run(tab, "F", "R", "10")
    run(tab, "F")
    tab.manager.send((a, Vec2(50, 0)))
    tab.manager.send((b, Vec2(0, 50)))
    assert "ARC" in types(tab)


def test_move_copy_rotate_mirror(tab):
    run(tab, "L", "0,0", "10,0", "")
    e = list(tab.doc.msp)[0]
    tab.canvas.set_selection([e.dxf.handle])
    run(tab, "M", "0,0", "5,5")
    e = list(tab.doc.msp)[0]
    assert Vec2(e.dxf.start).isclose(Vec2(5, 5))
    tab.canvas.set_selection([e.dxf.handle])
    run(tab, "CO", "0,0", "0,10", "0,20", "")
    assert len(tab.doc.msp) == 3
    tab.canvas.set_selection([e.dxf.handle])
    run(tab, "RO", "5,5", "90")
    tab.canvas.set_selection([list(tab.doc.msp)[-1].dxf.handle])
    run(tab, "MI", "0,0", "0,10", "N")
    assert len(tab.doc.msp) == 4


def test_dimensions_text_hatch(tab):
    run(tab, "REC", "0,0", "100,50")
    run(tab, "DLI", "0,0", "100,0", "50,-15")
    run(tab, "DT", "10,10", "5", "0", "Merhaba ŞĞÜİ", "")
    from t2dcad import hatchbound, geom
    rect = [e for e in tab.doc.msp if e.dxftype() == "LWPOLYLINE"][0]
    prims = geom.entity_prims(rect)
    res = hatchbound.find_boundary(prims, Vec2(50, 25), 1e-6)
    assert res is not None and len(res[0]) == 4
    assert "DIMENSION" in types(tab) and "TEXT" in types(tab)


def test_hatch_boundary_from_lines(tab):
    run(tab, "L", "0,0", "100,0", "100,100", "0,100", "C")
    run(tab, "C", "50,50", "10")
    from t2dcad import hatchbound
    prims = []
    for e in tab.doc.msp:
        prims += [p for p, _ in tab.snap.prims(e.dxf.handle, e)]
    outer, islands = hatchbound.find_boundary(prims, Vec2(20, 50), 1e-6)
    assert len(outer) == 4
    assert len(islands) == 1


def test_save_and_reopen(tab, tmp_path):
    run(tab, "L", "0,0", "100,0", "")
    run(tab, "C", "0,0", "5")
    path = str(tmp_path / "test.dxf")
    tab.doc.save(path)
    from t2dcad.docmodel import CadDocument
    d2 = CadDocument.open(path)
    assert sorted(e.dxftype() for e in d2.msp) == ["CIRCLE", "LINE"]


def test_plot_pdf(tab, tmp_path):
    run(tab, "REC", "0,0", "297,210")
    run(tab, "C", "148,105", "50")
    from t2dcad.ui.plot import make_printer, render_plot, PDF_PRINTER
    state = {"printer": PDF_PRINTER, "paper": 0, "landscape": True, "area": 0, "scale": "Kağıda sığdır"}
    out = str(tmp_path / "plot.pdf")
    printer = make_printer(state, pdf_path=out)
    render_plot(tab, state, printer)
    assert os.path.getsize(out) > 1000


def test_snap_endpoint(tab):
    run(tab, "L", "0,0", "100,0", "")
    hit = tab.snap.find(Vec2(99.5, 0.3), 2.0)
    assert hit is not None and hit[0] == "end" and hit[1].isclose(Vec2(100, 0))


def test_from_reference_point(tab):
    run(tab, "L", "FROM", "100,100", "@10,5", "@20,0", "")
    e = list(tab.doc.msp)[0]
    assert Vec2(e.dxf.start).isclose(Vec2(110, 105))
    assert Vec2(e.dxf.end).isclose(Vec2(130, 105))


def test_m2p(tab):
    run(tab, "L", "M2P", "0,0", "100,50", "0,0", "")
    e = list(tab.doc.msp)[0]
    assert Vec2(e.dxf.start).isclose(Vec2(50, 25))


def test_object_snap_tracking(tab):
    c = tab.canvas
    c.otrack = True
    run(tab, "L")
    c.acquired = [Vec2(100, 0)]
    # cursor nearly on the vertical through (100, 0)
    p = c._track(Vec2(100.0 + c.px(2), 40))
    assert p is not None and p.isclose(Vec2(100, 40))
    # typed distance goes along the tracking line from the acquired point
    c.cursor_world = p
    run(tab, "25")
    run(tab, "@10,0", "")
    e = list(tab.doc.msp)[0]
    assert Vec2(e.dxf.start).isclose(Vec2(100, 25))


def test_autocomplete():
    from t2dcad.ui.cmdline import suggestions
    words = [w for w, c in suggestions("RE")]
    assert words[0] == "RE"
    assert "RECTANG" in words
    assert all(w.startswith("RE") for w in words)
