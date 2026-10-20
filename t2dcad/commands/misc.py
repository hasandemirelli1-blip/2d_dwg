"""File, edit, view, inquiry, layer and settings commands."""
from __future__ import annotations

import math

from ezdxf.math import Vec2, Matrix44

from t2dcad import geom
from t2dcad.engine import (command, GetPoint, GetSelection, GetEntity, GetKeyword, GetNumber,
                           GetDistance, fmt, fmt_pt)


# ---------------------------------------------------------------- file
@command("NEW", "QNEW", undoable=False, repeatable=False)
def new(ctx):
    ctx.main.file_new()


@command("OPEN", undoable=False, repeatable=False)
def open_(ctx):
    ctx.main.file_open()


@command("QSAVE", "SAVE", undoable=False, repeatable=False)
def qsave(ctx):
    ctx.main.file_save()


@command("SAVEAS", undoable=False, repeatable=False)
def saveas(ctx):
    ctx.main.file_save_as()


@command("CLOSE", undoable=False, repeatable=False)
def close(ctx):
    ctx.main.close_tab(ctx.tab)


@command("QUIT", "EXIT", undoable=False, repeatable=False)
def quit_(ctx):
    ctx.main.close()


def _plot(ctx, state):
    from t2dcad.ui.plot import PlotDialog, run_plot
    while True:
        dlg = PlotDialog(ctx.tab, state, ctx.main)
        res = dlg.exec()
        if res == 2:
            state.pop("pick", None)
            a = yield GetPoint("Çizdirme alanının ilk köşesi", no_snap=False)
            b = yield GetPoint("Karşı köşe", base=a, rubber=False, preview=lambda p: [("rect", a, p)])
            state["window"] = (a, b)
            state["area"] = 2
            continue
        if res:
            run_plot(ctx.main, ctx.tab, state)
        return


@command("PLOT", "PRINT", undoable=False)
def plot(ctx):
    state = ctx.get("plot_state", {})
    ctx.set("plot_state", state)
    yield from _plot(ctx, state)


@command("EXPORTPDF", "PDF", undoable=False)
def exportpdf(ctx):
    from t2dcad.ui.plot import PDF_PRINTER
    state = ctx.get("plot_state", {})
    ctx.set("plot_state", state)
    state["printer"] = PDF_PRINTER
    yield from _plot(ctx, state)


# ---------------------------------------------------------------- undo
@command("U", "UNDO", undoable=False)
def undo(ctx):
    name = ctx.doc.undo()
    ctx.print(f"Geri alındı: {name}" if name else "Geri alınacak bir şey yok.")


@command("REDO", "MREDO", undoable=False)
def redo(ctx):
    name = ctx.doc.redo()
    ctx.print(f"Yinelendi: {name}" if name else "Yinelenecek bir şey yok.")


# ---------------------------------------------------------------- view
@command("ZOOM", "Z", undoable=False, transparent=True)
def zoom(ctx):
    c = ctx.canvas
    r = yield GetPoint("Pencere köşesini belirtin, ölçek faktörü (nX) girin veya", no_snap=True,
                       keywords=("All", "Extents", "Previous", "Window", "Center", "Scale"),
                       allow_none=True, default=None)
    if r is None:
        ctx.print("Fare tekerleği ile yakınlaştırın, orta tuş ile kaydırın.")
        return
    if r in ("All", "Extents"):
        c.zoom_extents()
    elif r == "Previous":
        c.zoom_previous()
    elif r == "Window":
        a = yield GetPoint("İlk köşe", no_snap=True)
        b = yield GetPoint("Karşı köşe", base=a, no_snap=True, rubber=False,
                           preview=lambda p: [("rect", a, p)])
        c.zoom_rect(a.x, a.y, b.x, b.y)
    elif r == "Center":
        p = yield GetPoint("Merkez noktası")
        c.push_view()
        c.cx, c.cy = p.x, p.y
        c.invalidate()
    elif r == "Scale":
        f = yield GetNumber("Ölçek faktörü", default=2.0)
        c.zoom_factor(f)
    else:
        a = r
        b = yield GetPoint("Karşı köşe", base=a, no_snap=True, rubber=False,
                           preview=lambda p: [("rect", a, p)])
        c.zoom_rect(a.x, a.y, b.x, b.y)


@command("ZE", undoable=False, transparent=True, repeatable=False)
def zoom_extents(ctx):
    ctx.canvas.zoom_extents()


@command("ZW", undoable=False)
def zoom_window(ctx):
    a = yield GetPoint("İlk köşe", no_snap=True)
    b = yield GetPoint("Karşı köşe", base=a, no_snap=True, rubber=False, preview=lambda p: [("rect", a, p)])
    ctx.canvas.zoom_rect(a.x, a.y, b.x, b.y)


@command("ZP", undoable=False, transparent=True, repeatable=False)
def zoom_prev(ctx):
    ctx.canvas.zoom_previous()


@command("PAN", "P", undoable=False)
def pan(ctx):
    ctx.canvas.realtime_pan = True
    ctx.print("Sol tuşla sürükleyerek kaydırın. Çıkmak için Esc veya Enter.")
    yield GetKeyword("Çıkmak için Esc veya Enter tuşuna basın", keywords=("eXit",))
    ctx.canvas.realtime_pan = False


@command("REGEN", "RE", "REGENALL", "REA", undoable=False, transparent=True)
def regen(ctx):
    ctx.tab.regen()
    ctx.print("Model yeniden oluşturuluyor.")


@command("REDRAW", "R", undoable=False, transparent=True)
def redraw(ctx):
    ctx.canvas.invalidate()


# ---------------------------------------------------------------- clipboard
@command("COPYCLIP", undoable=False, pickfirst=True)
def copyclip(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        return
    xs, ys = [], []
    for e in ents:
        g = ctx.tab.renderer.geometry(e.dxf.handle)
        if g:
            xs += [g.bbox[0], g.bbox[2]]
            ys += [g.bbox[1], g.bbox[3]]
    base = Vec2(min(xs), min(ys)) if xs else Vec2()
    ctx.main.set_clipboard(ctx.tab, ents, base)
    ctx.print(f"{len(ents)} nesne panoya kopyalandı.")


@command("COPYBASE", undoable=False, pickfirst=True)
def copybase(ctx):
    base = yield GetPoint("Temel noktayı belirtin")
    ents = yield GetSelection("Nesneleri seçin")
    if ents:
        ctx.main.set_clipboard(ctx.tab, ents, base)
        ctx.print(f"{len(ents)} nesne panoya kopyalandı.")


@command("CUTCLIP", pickfirst=True)
def cutclip(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        return
    xs, ys = [], []
    for e in ents:
        g = ctx.tab.renderer.geometry(e.dxf.handle)
        if g:
            xs += [g.bbox[0], g.bbox[2]]
            ys += [g.bbox[1], g.bbox[3]]
    base = Vec2(min(xs), min(ys)) if xs else Vec2()
    ctx.main.set_clipboard(ctx.tab, ents, base)
    ctx.doc.erase(ents)


@command("PASTECLIP")
def pasteclip(ctx):
    clip = ctx.main.clipboard
    if not clip:
        ctx.print("Pano boş.")
        return
    src_tab, src_doc, entities, base = clip
    ents = [e for e in entities if e.is_alive]
    if not ents:
        ctx.print("Pano boş.")
        return
    prims = []
    for e in ents[:2000]:
        prims.extend(geom.entity_prims(e))

    def pv(p):
        d = p - base
        out = []
        for pr in prims[:5000]:
            if isinstance(pr, geom.Seg):
                out.append(geom.Seg(pr.a + d, pr.b + d))
            else:
                out.append(geom.Arc(pr.c + d, pr.r, pr.a0, pr.a1, pr.full))
        return [("prims", out)]
    p = yield GetPoint("Yerleştirme noktasını belirtin", preview=pv)
    d = p - base
    m = Matrix44.translate(d.x, d.y, 0)
    if src_doc is ctx.dxf:
        new = []
        for e in ents:
            try:
                c = ctx.doc.clone(e)
                c.transform(m)
                ctx.doc.add_entity(c)
                new.append(c)
            except Exception as ex:
                print("paste failed", e, ex)
    else:
        new = ctx.main.import_entities(ctx.tab, src_doc, ents, m)
    ctx.last_created = new
    ctx.canvas.set_selection([e.dxf.handle for e in new])


@command("SELECTALL", "AI_SELALL", undoable=False, repeatable=False)
def selectall(ctx):
    hs = [e.dxf.handle for e in ctx.msp if not ctx.tab.is_locked(e.dxf.handle) and ctx.tab.is_visible(e)]
    ctx.canvas.set_selection(hs)


# ---------------------------------------------------------------- inquiry
@command("DIST", "DI", undoable=False)
def dist(ctx):
    a = yield GetPoint("İlk noktayı belirtin")
    b = yield GetPoint("İkinci noktayı belirtin", base=a)
    d = b - a
    ang = math.degrees(d.angle) % 360
    ctx.print(f"Uzaklık = {fmt(d.magnitude)},  XY düzleminde açı = {fmt(ang, 2)}°")
    ctx.print(f"X farkı = {fmt(d.x)},  Y farkı = {fmt(d.y)}")


@command("ID", undoable=False)
def id_(ctx):
    p = yield GetPoint("Noktayı belirtin")
    ctx.print(f"X = {fmt(p.x)}     Y = {fmt(p.y)}")


@command("AREA", "AA", undoable=False)
def area(ctx):
    r = yield GetPoint("İlk köşe noktasını belirtin", keywords=("Object",))
    if r == "Object":
        rr = yield GetEntity("Nesneyi seçin", types=("CIRCLE", "LWPOLYLINE", "POLYLINE", "ELLIPSE", "HATCH",
                                                     "ARC", "LINE", "SPLINE"))
        e, _ = rr
        t = e.dxftype()
        if t == "CIRCLE":
            r_ = e.dxf.radius
            ctx.print(f"Alan = {fmt(math.pi * r_ * r_)},  Çevre = {fmt(2 * math.pi * r_)}")
            return
        if t == "HATCH":
            total = 0.0
            for path in e.paths:
                pts = []
                if hasattr(path, "vertices"):
                    vs = [(Vec2(v[0], v[1]), v[2] if len(v) > 2 else 0) for v in path.vertices]
                    pts = geom.flatten_prims(geom.polyline_prims(vs, True))
                if pts:
                    a = geom.polygon_area(pts)
                    total += abs(a) if path.path_type_flags & 1 else -abs(a)
            ctx.print(f"Alan = {fmt(abs(total))}")
            return
        prims = geom.entity_prims(e)
        pts = geom.flatten_prims(prims, math.radians(0.5))
        a = abs(geom.polygon_area(pts)) if len(pts) > 2 else 0.0
        ctx.print(f"Alan = {fmt(a)},  Uzunluk = {fmt(geom.prims_length(prims))}")
        return
    pts = [r]
    while True:
        q = yield GetPoint("Sonraki noktayı belirtin", base=pts[-1], allow_none=True,
                           preview=lambda q: [("poly", pts + [q], True)], rubber=False)
        if q is None:
            break
        pts.append(q)
    if len(pts) < 3:
        return
    a = abs(geom.polygon_area(pts))
    per = sum(pts[i].distance(pts[(i + 1) % len(pts)]) for i in range(len(pts)))
    ctx.print(f"Alan = {fmt(a)},  Çevre = {fmt(per)}")


@command("LIST", "LI", "LS", undoable=False, pickfirst=True)
def list_(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    for e in ents:
        d = e.dxf
        ctx.print(f"{e.dxftype():<12} Katman: \"{d.layer}\"  Tanıtıcı = {d.handle}")
        t = e.dxftype()
        if t == "LINE":
            s, en = Vec2(d.start), Vec2(d.end)
            ctx.print(f"   başlangıç {fmt_pt(s)}  bitiş {fmt_pt(en)}  uzunluk = {fmt(s.distance(en))}  "
                      f"açı = {fmt(math.degrees((en - s).angle) % 360, 2)}°")
        elif t == "CIRCLE":
            ctx.print(f"   merkez {fmt_pt(Vec2(d.center))}  yarıçap {fmt(d.radius)}  "
                      f"çevre {fmt(2 * math.pi * d.radius)}  alan {fmt(math.pi * d.radius ** 2)}")
        elif t == "ARC":
            ctx.print(f"   merkez {fmt_pt(Vec2(d.center))}  yarıçap {fmt(d.radius)}  "
                      f"başlangıç açısı {fmt(d.start_angle, 2)}  bitiş açısı {fmt(d.end_angle, 2)}")
        elif t in ("LWPOLYLINE", "POLYLINE"):
            prims = geom.entity_prims(e)
            ctx.print(f"   {'kapalı' if (e.closed if t == 'LWPOLYLINE' else e.is_closed) else 'açık'}  "
                      f"uzunluk = {fmt(geom.prims_length(prims))}")
        elif t in ("TEXT", "MTEXT"):
            txt = d.text if t == "TEXT" else e.plain_text()
            ctx.print(f"   yazı: \"{txt}\"  stil: {d.get('style', 'Standard')}")
        elif t == "INSERT":
            ctx.print(f"   blok: {d.name}  konum {fmt_pt(Vec2(d.insert))}  ölçek {fmt(d.xscale)}  "
                      f"açı {fmt(d.rotation, 2)}")


# ---------------------------------------------------------------- settings / dialogs
@command("LAYER", "LA", "DDLMODES", undoable=False, repeatable=False)
def layer(ctx):
    ctx.main.layer_dialog()


@command("OSNAP", "OS", "DDOSNAP", "DSETTINGS", "DS", "SE", undoable=False, transparent=True)
def osnap(ctx):
    ctx.main.osnap_settings()


@command("OPTIONS", "OP", "PREFERENCES", undoable=False)
def options(ctx):
    ctx.main.options_dialog()


@command("PROPERTIES", "PR", "CH", "MO", "PROPS", undoable=False, transparent=True)
def properties(ctx):
    ctx.main.show_properties()


@command("LTSCALE", "LTS", undoable=False)
def ltscale(ctx):
    v = yield GetNumber("Yeni çizgi tipi ölçek faktörünü girin", default=float(ctx.header("$LTSCALE", 1.0)))
    if v and v > 0:
        old = float(ctx.header("$LTSCALE", 1.0))
        ctx.set_header("$LTSCALE", v)
        ctx.doc.custom(lambda: ctx.set_header("$LTSCALE", old), lambda: ctx.set_header("$LTSCALE", v))


@command("ORTHO", undoable=False, transparent=True)
def ortho(ctx):
    ctx.main.toggle("ortho")


@command("UNITS", "UN", undoable=False)
def units(ctx):
    ctx.print("Çizim birimi: milimetre (mm). Ondalık basamak sayısı Seçenekler'den ayarlanabilir.")


@command("HELP", "?", undoable=False, transparent=True)
def help_(ctx):
    ctx.main.show_help()


@command("TEXTSCR", undoable=False, transparent=True)
def textscr(ctx):
    ctx.main.cmdline.show_history_window()


# ---------------------------------------------------------------- layer tools
def _layer_of(ctx, e):
    return ctx.dxf.layers.get(e.dxf.layer)


def _layer_change(ctx, names, fn, msg):
    layers = [ctx.dxf.layers.get(n) for n in names if n in ctx.dxf.layers]
    state = [(l, l.dxf.flags, l.dxf.color) for l in layers]

    def redo():
        for l in layers:
            fn(l)
        ctx.doc.layers_changed.emit()

    def undo_():
        for l, flags, color in state:
            l.dxf.flags = flags
            l.dxf.color = color
        ctx.doc.layers_changed.emit()
    redo()
    ctx.doc.custom(undo_, redo)
    ctx.print(msg)


@command("LAYOFF", undoable=True)
def layoff(ctx):
    while True:
        r = yield GetEntity("Kapatılacak katmanın nesnesini seçin", allow_none=True)
        if r is None:
            return
        name = r[0].dxf.layer
        if name == ctx.doc.current_layer:
            ctx.print("Geçerli katman kapatılamaz.")
            continue
        _layer_change(ctx, [name], lambda l: l.off(), f'"{name}" katmanı kapatıldı.')


@command("LAYON", undoable=True)
def layon(ctx):
    _layer_change(ctx, [l.dxf.name for l in ctx.dxf.layers], lambda l: l.on(), "Tüm katmanlar açıldı.")


@command("LAYFRZ", undoable=True)
def layfrz(ctx):
    while True:
        r = yield GetEntity("Dondurulacak katmanın nesnesini seçin", allow_none=True)
        if r is None:
            return
        name = r[0].dxf.layer
        if name == ctx.doc.current_layer:
            ctx.print("Geçerli katman dondurulamaz.")
            continue
        _layer_change(ctx, [name], lambda l: l.freeze(), f'"{name}" katmanı donduruldu.')


@command("LAYTHW", undoable=True)
def laythw(ctx):
    _layer_change(ctx, [l.dxf.name for l in ctx.dxf.layers], lambda l: l.thaw(), "Tüm katmanların dondurması çözüldü.")


@command("LAYLCK", undoable=True)
def laylck(ctx):
    r = yield GetEntity("Kilitlenecek katmanın nesnesini seçin")
    name = r[0].dxf.layer
    _layer_change(ctx, [name], lambda l: l.lock(), f'"{name}" katmanı kilitlendi.')


@command("LAYULK", undoable=True)
def layulk(ctx):
    r = yield GetEntity("Kilidi açılacak katmanın nesnesini seçin", allow_none=False)
    name = r[0].dxf.layer
    _layer_change(ctx, [name], lambda l: l.unlock(), f'"{name}" katmanının kilidi açıldı.')


@command("LAYISO", pickfirst=True)
def layiso(ctx):
    ents = yield GetSelection("Yalıtılacak katmanlardaki nesneleri seçin")
    names = {e.dxf.layer for e in ents}
    if not names:
        return
    others = [l.dxf.name for l in ctx.dxf.layers if l.dxf.name not in names and l.is_on()]
    ctx.set("layiso_prev", others)
    if ctx.doc.current_layer not in names:
        ctx.doc.current_layer = sorted(names)[0]
    _layer_change(ctx, others, lambda l: l.off(), f"{len(names)} katman yalıtıldı.")


@command("LAYUNISO")
def layuniso(ctx):
    names = ctx.get("layiso_prev", [])
    _layer_change(ctx, names, lambda l: l.on(), "Katmanlar geri açıldı.")


@command("LAYMCUR", undoable=False)
def laymcur(ctx):
    r = yield GetEntity("Katmanı geçerli yapılacak nesneyi seçin")
    ctx.doc.current_layer = r[0].dxf.layer
    ctx.print(f'"{r[0].dxf.layer}" artık geçerli katman.')


@command("LAYMCH", pickfirst=True)
def laymch(ctx):
    ents = yield GetSelection("Değiştirilecek nesneleri seçin")
    if not ents:
        return
    r = yield GetEntity("Hedef katmandaki nesneyi seçin")
    name = r[0].dxf.layer
    for e in ents:
        ctx.doc.modify(e, lambda c: c.dxf.set("layer", name))
    ctx.print(f'{len(ents)} nesne "{name}" katmanına taşındı.')


@command("PURGE", "PU", undoable=False)
def purge(ctx):
    doc = ctx.dxf
    used = set()
    for e in doc.modelspace():
        used.add(e.dxf.layer)
    for blk in doc.blocks:
        for e in blk:
            used.add(e.dxf.layer)
    removed = 0
    for l in list(doc.layers):
        n = l.dxf.name
        if n in used or n in ("0", "Defpoints") or n == ctx.doc.current_layer:
            continue
        try:
            doc.layers.remove(n)
            removed += 1
        except Exception:
            pass
    ctx.doc.layers_changed.emit()
    ctx.doc.set_modified(True)
    ctx.print(f"{removed} kullanılmayan katman temizlendi.")
