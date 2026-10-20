"""BLOCK, INSERT and HATCH commands."""
from __future__ import annotations

import math

from ezdxf.math import Vec2, Vec3, Matrix44

from t2dcad import geom, hatchbound
from t2dcad.engine import (command, GetPoint, GetSelection, GetString, GetDistance, GetAngle,
                           GetKeyword, fmt)


# ---------------------------------------------------------------- BLOCK
@command("BLOCK", "B", pickfirst=True)
def block(ctx):
    name = ctx.main.ask_text("Blok tanımla", "Blok adı:", "")
    if not name:
        return
    name = name.strip()
    if name in ctx.dxf.blocks:
        if not ctx.main.confirm(f'"{name}" bloğu zaten var. Yeniden tanımlansın mı?'):
            return
    base = yield GetPoint("Temel noktayı belirtin")
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        ctx.print("Nesne seçilmedi.")
        return
    doc = ctx.dxf
    if name in doc.blocks:
        blk = doc.blocks.get(name)
        for e in list(blk):
            blk.delete_entity(e)
        blk.block.dxf.base_point = Vec3(base)
    else:
        blk = doc.blocks.new(name, base_point=Vec3(base))
    for e in ents:
        c = ctx.doc.clone(e)
        blk.add_entity(c)
    ctx.doc.erase(ents)
    ins = ctx.msp.add_blockref(name, base, dxfattribs=ctx.attribs())
    ctx.created(ins)
    ctx.print(f'"{name}" bloğu oluşturuldu ({len(ents)} nesne).')


def block_prims(doc, name) -> list:
    blk = doc.blocks.get(name)
    if blk is None:
        return [], Vec2()
    base = Vec2(blk.block.dxf.base_point)
    out = []
    for e in blk:
        for p in geom.entity_prims(e):
            out.append(p)
    return out, base


def _move_prims(prims, base: Vec2, p: Vec2, scale: float, rot: float):
    out = []
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def tr(v: Vec2) -> Vec2:
        v = (v - base) * scale
        return Vec2(v.x * ca - v.y * sa, v.x * sa + v.y * ca) + p
    for pr in prims[:3000]:
        if isinstance(pr, geom.Seg):
            out.append(geom.Seg(tr(pr.a), tr(pr.b)))
        else:
            out.append(geom.Arc(tr(pr.c), pr.r * abs(scale), pr.a0 + math.radians(rot),
                                pr.a1 + math.radians(rot), pr.full))
    return out


@command("INSERT", "I", "DDINSERT")
def insert(ctx):
    res = ctx.main.insert_dialog(ctx.tab)
    if not res:
        return
    name, scale, rot = res
    prims, base = block_prims(ctx.dxf, name)
    p = yield GetPoint("Yerleştirme noktasını belirtin", keywords=("Scale", "Rotate"),
                       preview=lambda q: [("prims", _move_prims(prims, base, q, scale, rot))])
    while p in ("Scale", "Rotate"):
        if p == "Scale":
            scale = yield GetDistance("Ölçek faktörü", default=scale)
        else:
            rot = yield GetAngle("Dönme açısı", default=rot)
        p = yield GetPoint("Yerleştirme noktasını belirtin", keywords=("Scale", "Rotate"),
                           preview=lambda q: [("prims", _move_prims(prims, base, q, scale, rot))])
    ins = ctx.msp.add_blockref(name, p, dxfattribs=ctx.attribs(xscale=scale, yscale=scale, zscale=scale,
                                                              rotation=rot))
    blk = ctx.dxf.blocks.get(name)
    attdefs = [e for e in blk if e.dxftype() == "ATTDEF"]
    if attdefs:
        values = {}
        for ad in attdefs:
            v = yield GetString(ad.dxf.get("prompt", ad.dxf.tag) or ad.dxf.tag, spaces=True,
                                default=ad.dxf.text or None)
            values[ad.dxf.tag] = v if v else ad.dxf.text
        ins.add_auto_attribs(values)
    ctx.created(ins)


# ---------------------------------------------------------------- HATCH
def _closed_entity_vertices(e):
    t = e.dxftype()
    if t == "CIRCLE":
        c = Vec2(e.dxf.center)
        r = e.dxf.radius
        return [(c + Vec2(r, 0), 1.0), (c - Vec2(r, 0), 1.0)]
    if t == "LWPOLYLINE" and e.closed:
        return geom.lwpoly_points(e)
    if t == "POLYLINE" and e.is_2d_polyline and e.is_closed:
        return geom.lwpoly_points(e)
    if t in ("ELLIPSE", "SPLINE"):
        pts = [Vec2(p) for p in e.flattening(0.01)]
        if len(pts) > 2 and pts[0].isclose(pts[-1], abs_tol=1e-6):
            return [(p, 0.0) for p in pts[:-1]]
    return None


def _bbox_of(verts):
    xs = [p.x for p, _ in verts]
    ys = [p.y for p, _ in verts]
    return min(xs), min(ys), max(xs), max(ys)


@command("HATCH", "H", "BH", "BHATCH")
def hatch(ctx):
    opts = ctx.main.hatch_dialog(ctx.tab)
    if not opts:
        return
    pattern, scale, angle = opts
    loops: list[tuple[list, bool]] = []  # (vertices, outer)
    previews = []
    while True:
        r = yield GetPoint("İç noktayı seçin", keywords=("Select objects", "Undo"), allow_none=True,
                           no_snap=True, rubber=False, preview=lambda p: list(previews))
        if r is None:
            break
        if r == "Undo":
            if loops:
                loops.pop()
                previews.pop()
            continue
        if r == "Select objects":
            ents = yield GetSelection("Kapalı nesneleri seçin")
            for e in ents:
                vs = _closed_entity_vertices(e)
                if vs:
                    loops.append((vs, True))
                    previews.append(("prims", geom.polyline_prims(vs, True)))
                else:
                    ctx.print(f"{e.dxftype()} kapalı bir sınır değil, atlandı.")
            continue
        p = r
        ctx.print("Seçilen her şey analiz ediliyor...")
        x0, y0, x1, y1 = ctx.canvas.visible_rect()
        hs = ctx.tab.renderer.handles_in_rect(x0, y0, x1, y1)
        prims = []
        closed_ents = []
        for h in hs:
            e = ctx.doc.entity_by_handle(h)
            if e is None or e.dxftype() in ("TEXT", "MTEXT", "HATCH", "DIMENSION", "POINT", "INSERT",
                                            "IMAGE", "LEADER"):
                continue
            if not ctx.tab.is_visible(e):
                continue
            prims.extend(p_ for p_, _ in ctx.tab.snap.prims(h, e))
            vs = _closed_entity_vertices(e)
            if vs:
                closed_ents.append(vs)
        tol = max(1e-6, ctx.canvas.px(0.5))
        res = hatchbound.find_boundary(prims, p, tol)
        if res is None:
            ctx.print("Geçerli bir sınır bulunamadı. Alanın kapalı olduğundan emin olun.")
            continue
        outer, islands = res
        loops.append((outer, True))
        previews.append(("prims", geom.polyline_prims(outer, True)))
        # islands: closed entities fully inside the outer boundary
        obox = _bbox_of(outer)
        found = [_bbox_of(i) for i in islands]
        for vs in closed_ents:
            b = _bbox_of(vs)
            if b[0] <= obox[0] + tol and b[2] >= obox[2] - tol and b[1] <= obox[1] + tol and b[3] >= obox[3] - tol:
                continue  # this is the outer boundary itself
            if not (obox[0] <= b[0] and obox[1] <= b[1] and b[2] <= obox[2] and b[3] <= obox[3]):
                continue
            if all(hatchbound.point_in_vertices(v, outer) for v, _ in vs[:8]) and \
                    not hatchbound.point_in_vertices(p, vs):
                if not any(all(abs(a - c) < tol * 10 for a, c in zip(b, fb)) for fb in found):
                    islands.append(vs)
                    found.append(b)
        for isl in islands:
            loops.append((isl, False))
            previews.append(("prims", geom.polyline_prims(isl, True)))
        ctx.print(f"Sınır bulundu ({len(islands)} ada).")
    if not loops:
        return
    attribs = ctx.attribs()
    h = ctx.msp.add_hatch(dxfattribs=attribs)
    if pattern.upper() == "SOLID":
        h.set_solid_fill(color=attribs.get("color", 256))
    else:
        h.set_pattern_fill(pattern.upper(), color=attribs.get("color", 256), angle=angle, scale=scale)
    for vs, outer in loops:
        flags = 1 if outer else 16
        h.paths.add_polyline_path([(p.x, p.y, b) for p, b in vs], is_closed=True, flags=flags)
    ctx.created(h)
    ctx.set("hatch_opts", (pattern, scale, angle))


# ---------------------------------------------------------------- in-place block editing
from t2dcad.engine import GetEntity as _GetEntity  # noqa: E402


@command("REFEDIT", "BEDIT", "BE", "REFE", pickfirst=True, undoable=False, repeatable=False)
def refedit(ctx):
    from t2dcad.refedit import RefEditSession, block_reference_at
    tab = ctx.tab
    if tab.refedit is not None:
        ctx.print("Zaten bir blok düzenleniyor. Önce kaydedin veya vazgeçin.")
        return
    sel = ctx.take_pickfirst()
    ins = None
    for e in sel:
        ins = block_reference_at(tab, e.dxf.handle)
        if ins:
            break
    if ins is None:
        r = yield _GetEntity("Düzenlenecek bloğu seçin", types=("INSERT",))
        ins = block_reference_at(tab, r[0].dxf.handle)
    if ins is None:
        ctx.print("Bu blok yerinde düzenlenemez.")
        return
    session = RefEditSession(tab, ins)
    problems = session.start()
    tab.refedit = session
    tab.refedit_changed()
    ctx.print(f'"{session.name}" bloğu yerinde düzenleniyor. Bitince "Değişiklikleri kaydet" (REFCLOSE).')
    for p in problems:
        ctx.print(f"Uyarı: {p}")


@command("REFADD", "REFSET", undoable=False)
def refadd(ctx):
    r = ctx.tab.refedit
    if r is None:
        ctx.print("Önce REFEDIT ile bir blok açın.")
        return
    r.adding = True
    try:
        ents = yield GetSelection("Bloğa eklenecek nesneleri seçin")
    finally:
        r.adding = False
    n = r.add(ents)
    ctx.canvas.invalidate()
    ctx.print(f"{n} nesne bloğa eklendi (kaydedince bloğun içine taşınır).")


@command("REFREMOVE", undoable=False)
def refremove(ctx):
    r = ctx.tab.refedit
    if r is None:
        ctx.print("Önce REFEDIT ile bir blok açın.")
        return
    ents = yield GetSelection("Bloktan çıkarılacak nesneleri seçin")
    n = r.remove(ents)
    ctx.canvas.invalidate()
    ctx.print(f"{n} nesne bloktan çıkarıldı (çizimde normal nesne olarak kalır).")


def _close(ctx, save: bool):
    tab = ctx.tab
    r = tab.refedit
    if r is None:
        ctx.print("Düzenlenen bir blok yok.")
        return
    if save:
        problems = r.save()
        for p in problems:
            ctx.print(f"Uyarı: {p}")
        ctx.print(f'"{r.name}" bloğu kaydedildi; tüm kopyaları güncellendi.')
    else:
        r.discard()
        ctx.print("Blok değişiklikleri atıldı.")
    tab.refedit = None
    tab.refedit_changed()
    tab.regen()


@command("REFCLOSE", "BCLOSE", undoable=False, repeatable=False)
def refclose(ctx):
    if ctx.tab.refedit is None:
        ctx.print("Düzenlenen bir blok yok.")
        return
    k = yield GetKeyword("Değişiklikler", keywords=("Save", "Discard"), default="Save")
    _close(ctx, k != "Discard")


@command("REFCLOSE_SAVE", undoable=False, repeatable=False)
def refclose_save(ctx):
    _close(ctx, True)


@command("REFCLOSE_DISCARD", undoable=False, repeatable=False)
def refclose_discard(ctx):
    _close(ctx, False)


# ---------------------------------------------------------------- PDF import
@command("PDFIMPORT", "IMPORTPDF", "PDFI", "PDFATTACH")
def pdfimport_cmd(ctx):
    from ezdxf.math import Vec2 as _V
    opts, path = ctx.main.pdf_import_dialog()
    if opts is None:
        return
    from t2dcad import pdfimport
    try:
        w, h, n = pdfimport.page_size_mm(path, opts.page)
    except Exception as ex:
        ctx.print(f"PDF okunamadı: {ex}")
        return
    w, h = w * opts.scale, h * opts.scale
    p = yield GetPoint("Yerleştirme noktasını belirtin <0,0>", allow_none=True,
                       preview=lambda q: [("rect", q, q + _V(w, h))], rubber=False)
    base = p if p is not None else _V(0, 0)
    from PySide6.QtWidgets import QApplication, QProgressDialog
    from PySide6.QtCore import Qt
    dlg = QProgressDialog("PDF okunuyor...", "Durdur", 0, 100, ctx.main)
    dlg.setWindowTitle("PDF içe aktar")
    dlg.setWindowModality(Qt.WindowModal)
    dlg.setMinimumDuration(400)

    def progress(f):
        dlg.setValue(int(f * 100))
        QApplication.processEvents()
        return not dlg.wasCanceled()
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        imp = pdfimport.PdfImporter(ctx.doc, opts, base, ctx.attribs())
        res = imp.run(path, progress)
        dlg.setLabelText("Çiziliyor...")
        dlg.setValue(92)
        QApplication.processEvents()
        ctx.doc.added_many(res.entities)
        ctx.doc.layers_changed.emit()
    finally:
        dlg.close()
        QApplication.restoreOverrideCursor()
    parts = ", ".join(f"{v} {k}" for k, v in res.counts.items()) or "hiç nesne"
    ctx.print(f"PDF içe aktarıldı: {parts}.")
    for wmsg in res.warnings:
        ctx.print(wmsg)
    if res.entities:
        ctx.canvas.zoom_rect(base.x, base.y, base.x + w, base.y + h, 1.05)


# ---------------------------------------------------------------- raster images
IMAGE_FILTER = "Resimler (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif)"


def image_size_px(path: str):
    from PySide6.QtGui import QImageReader
    s = QImageReader(path).size()
    return s.width(), s.height()


def add_image(ctx_doc, msp, path, insert, width_units, rotation=0.0, dxfattribs=None):
    """Create IMAGEDEF + IMAGE; height follows the aspect ratio."""
    import os
    w, h = image_size_px(path)
    if w <= 0 or h <= 0:
        raise ValueError("Resim okunamadı")
    path = os.path.abspath(path)
    idef = None
    for d in ctx_doc.doc.objects.query("IMAGEDEF"):
        if os.path.normcase(d.dxf.filename) == os.path.normcase(path):
            idef = d
            break
    if idef is None:
        idef = ctx_doc.doc.add_image_def(filename=path, size_in_pixel=(w, h))
    size = (width_units, width_units * h / w)
    return msp.add_image(image_def=idef, insert=insert, size_in_units=size, rotation=rotation,
                         dxfattribs=dxfattribs or {})


@command("IMAGEATTACH", "IAT", "IMAGE", "IM", "ATTACH")
def imageattach(ctx):
    import math as _m
    from ezdxf.math import Vec2 as _V
    path = ctx.main.ask_open_file("Resim ekle", IMAGE_FILTER)
    if not path:
        return
    w_px, h_px = image_size_px(path)
    if w_px <= 0:
        ctx.print("Resim okunamadı.")
        return
    aspect = h_px / w_px
    default_w = ctx.get("image_width", 100.0)

    def frame(p, width, rot=0.0):
        u = _V.from_deg_angle(rot)
        v = u.orthogonal()
        a = p
        b = p + u * width
        c = b + v * width * aspect
        d = p + v * width * aspect
        return [("poly", [a, b, c, d], True), ("line", a, c), ("line", b, d)]
    p = yield GetPoint("Yerleştirme noktasını belirtin", preview=lambda q: frame(q, default_w), rubber=False)
    width = yield GetDistance("Genişliği belirtin (ölçek)", base=p, default=default_w,
                              preview=lambda q: frame(p, max(p.distance(q), 1e-6)))
    rot = yield GetAngle("Dönme açısını belirtin", base=p, default=0.0,
                         preview=lambda q: frame(p, width, _m.degrees((q - p).angle)))
    ctx.set("image_width", width)
    img = add_image(ctx.doc, ctx.msp, path, p, width, rot, ctx.attribs())
    ctx.created(img)
    ctx.print(f"Resim eklendi: {path}  ({w_px} x {h_px} px). Hizalamak için ALIGN veya SCALE (Reference) kullanın.")
