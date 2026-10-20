"""Modify commands."""
from __future__ import annotations

import math

from ezdxf.math import Vec2, Vec3, Matrix44

from t2dcad import geom, curves
from t2dcad.curves import Curve, CURVE_TYPES, common_attribs
from t2dcad.engine import (command, GetPoint, GetDistance, GetAngle, GetNumber, GetKeyword,
                           GetSelection, GetEntity, fmt)
from t2dcad.geom import Seg, Arc


def _handles(ents):
    return [e.dxf.handle for e in ents]


def transform_entities(ctx, ents, m: Matrix44, copy=False, mirror=False) -> list:
    out = []
    failed = 0
    mirrtext = int(ctx.header("$MIRRTEXT", 0))
    for e in ents:
        try:
            c = ctx.doc.clone(e)
            if mirror and not mirrtext and e.dxftype() in ("TEXT", "MTEXT"):
                # MIRRTEXT=0: keep the text readable, mirror only its position
                p = Vec3(e.dxf.insert)
                q = m.transform(p)
                c.transform(Matrix44.translate(q.x - p.x, q.y - p.y, 0))
            else:
                c.transform(m)
        except Exception as ex:
            failed += 1
            print("transform failed:", e, ex)
            continue
        if copy:
            ctx.doc.add_entity(c)
        else:
            ctx.doc.replace(e, c)
        out.append(c)
    if failed:
        ctx.print(f"{failed} nesne dönüştürülemedi.")
    return out


# ---------------------------------------------------------------- ERASE
@command("ERASE", "E", pickfirst=True)
def erase(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if ents:
        ctx.doc.erase(ents)


# ---------------------------------------------------------------- MOVE / COPY
@command("MOVE", "M", pickfirst=True)
def move(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        return
    hs = _handles(ents)
    base = yield GetPoint("Temel noktayı belirtin", keywords=("Displacement",))
    if base == "Displacement":
        d = yield GetPoint("Yer değiştirmeyi belirtin (x,y)", default=Vec2(0, 0))
        base, target = Vec2(0, 0), d
    else:
        target = yield GetPoint("İkinci noktayı belirtin", base=base, allow_none=True,
                                preview=lambda p: [("ghost", hs, Matrix44.translate(p.x - base.x, p.y - base.y, 0)),
                                                   ("line", base, p)])
        if target is None:  # use base point as displacement
            base, target = Vec2(0, 0), base
    d = target - base
    new = transform_entities(ctx, ents, Matrix44.translate(d.x, d.y, 0))
    ctx.last_created = new


@command("COPY", "CO", "CP", pickfirst=True)
def copy(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        return
    hs = _handles(ents)
    base = yield GetPoint("Temel noktayı belirtin", keywords=("Displacement",))
    if base == "Displacement":
        d = yield GetPoint("Yer değiştirmeyi belirtin (x,y)")
        transform_entities(ctx, ents, Matrix44.translate(d.x, d.y, 0), copy=True)
        return
    while True:
        target = yield GetPoint("İkinci noktayı belirtin", base=base, allow_none=True,
                                keywords=("Array",),
                                preview=lambda p: [("ghost", hs, Matrix44.translate(p.x - base.x, p.y - base.y, 0)),
                                                   ("line", base, p)])
        if target is None:
            return
        if target == "Array":
            n = yield GetNumber("Diziye girecek öğe sayısı", integer=True, default=2)
            p = yield GetPoint("İkinci noktayı belirtin", base=base,
                               preview=lambda p: [("ghost", hs, Matrix44.translate(p.x - base.x, p.y - base.y, 0))])
            d = p - base
            for k in range(1, max(2, n)):
                transform_entities(ctx, ents, Matrix44.translate(d.x * k, d.y * k, 0), copy=True)
            return
        d = target - base
        ctx.last_created = transform_entities(ctx, ents, Matrix44.translate(d.x, d.y, 0), copy=True)


# ---------------------------------------------------------------- ROTATE
def _rot(base: Vec2, ang_deg: float) -> Matrix44:
    return (Matrix44.translate(-base.x, -base.y, 0) @ Matrix44.z_rotate(math.radians(ang_deg))
            @ Matrix44.translate(base.x, base.y, 0))


@command("ROTATE", "RO", pickfirst=True)
def rotate(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        return
    hs = _handles(ents)
    base = yield GetPoint("Temel noktayı belirtin")
    do_copy = False
    while True:
        a = yield GetAngle("Dönme açısını belirtin", base=base, keywords=("Copy", "Reference"),
                           default=ctx.get("rot_angle", 0.0),
                           preview=lambda p: [("ghost", hs, _rot(base, math.degrees((p - base).angle))),
                                              ("line", base, p)])
        if a == "Copy":
            do_copy = True
            ctx.print("Seçili nesnelerin kopyası döndürülecek.")
            continue
        if a == "Reference":
            ref = yield GetAngle("Referans açıyı belirtin", default=0.0)
            new = yield GetAngle("Yeni açıyı belirtin", base=base,
                                 preview=lambda p: [("ghost", hs, _rot(base, math.degrees((p - base).angle) - ref))])
            a = new - ref
        break
    ctx.set("rot_angle", a)
    transform_entities(ctx, ents, _rot(base, a), copy=do_copy)


# ---------------------------------------------------------------- SCALE
def _scl(base: Vec2, f: float) -> Matrix44:
    return (Matrix44.translate(-base.x, -base.y, 0) @ Matrix44.scale(f, f, f)
            @ Matrix44.translate(base.x, base.y, 0))


@command("SCALE", "SC", pickfirst=True)
def scale(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        return
    hs = _handles(ents)
    base = yield GetPoint("Temel noktayı belirtin")
    do_copy = False
    while True:
        f = yield GetDistance("Ölçek faktörünü belirtin", base=base, keywords=("Copy", "Reference"),
                              default=ctx.get("scale_f", 1.0),
                              preview=lambda p: [("ghost", hs, _scl(base, max(1e-6, base.distance(p)))),
                                                 ("line", base, p)])
        if f == "Copy":
            do_copy = True
            continue
        if f == "Reference":
            r = yield GetDistance("Referans uzunluğu belirtin", default=1.0)
            n = yield GetDistance("Yeni uzunluğu belirtin", base=base,
                                  preview=lambda p: [("ghost", hs, _scl(base, max(1e-6, base.distance(p) / r)))])
            f = n / r if r else 1.0
        break
    if f <= 0:
        ctx.print("Ölçek faktörü pozitif olmalı.")
        return
    ctx.set("scale_f", f)
    transform_entities(ctx, ents, _scl(base, f), copy=do_copy)


# ---------------------------------------------------------------- MIRROR
def _mirror(a: Vec2, b: Vec2) -> Matrix44:
    ang = (b - a).angle
    return (Matrix44.translate(-a.x, -a.y, 0) @ Matrix44.z_rotate(-ang) @ Matrix44.scale(1, -1, 1)
            @ Matrix44.z_rotate(ang) @ Matrix44.translate(a.x, a.y, 0))


@command("MIRROR", "MI", pickfirst=True)
def mirror(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        return
    hs = _handles(ents)
    a = yield GetPoint("Ayna çizgisinin ilk noktasını belirtin")
    b = yield GetPoint("Ayna çizgisinin ikinci noktasını belirtin", base=a,
                       preview=lambda p: [("ghost", hs, _mirror(a, p)), ("line", a, p)] if not p.isclose(a) else [])
    if a.isclose(b):
        return
    k = yield GetKeyword("Kaynak nesneler silinsin mi?", keywords=("Yes", "No"), default="No")
    transform_entities(ctx, ents, _mirror(a, b), copy=(k != "Yes"), mirror=True)


# ---------------------------------------------------------------- OFFSET
def offset_entity(ctx, e, dist: float, side: Vec2):
    t = e.dxftype()
    attribs = common_attribs(e)
    msp = ctx.msp
    if t == "CIRCLE":
        c = Vec2(e.dxf.center)
        r = e.dxf.radius
        r2 = r + dist if side.distance(c) > r else r - dist
        if r2 <= 1e-9:
            return None
        return msp.add_circle(c, r2, dxfattribs=attribs)
    if t == "ARC":
        arc = geom.entity_prims(e)[0]
        r2 = arc.r + dist if side.distance(arc.c) > arc.r else arc.r - dist
        if r2 <= 1e-9:
            return None
        return msp.add_arc(arc.c, r2, e.dxf.start_angle, e.dxf.end_angle, dxfattribs=attribs)
    if t == "ELLIPSE":
        ctx.print("Elips ofseti desteklenmiyor.")
        return None
    if t in ("LINE", "LWPOLYLINE"):
        if t == "LINE":
            verts = [(Vec2(e.dxf.start), 0.0), (Vec2(e.dxf.end), 0.0)]
            closed = False
        else:
            verts = geom.lwpoly_points(e)
            closed = bool(e.closed)
        s = curves.side_of(verts, closed, side)
        res = curves.offset_vertices(verts, closed, dist * s)
        if not res:
            return None
        if t == "LINE":
            return msp.add_line(res[0][0], res[-1][0], dxfattribs=attribs)
        for name in ("const_width",):
            if e.dxf.hasattr(name):
                attribs[name] = e.dxf.get(name)
        return msp.add_lwpolyline([(p.x, p.y, b) for p, b in res], format="xyb", close=closed,
                                  dxfattribs=attribs)
    if t == "SPLINE":
        ctx.print("Spline ofseti desteklenmiyor.")
        return None
    ctx.print(f"{t} ofsetlenemez.")
    return None


@command("OFFSET", "O")
def offset(ctx):
    dist = ctx.get("offset_dist", None)
    d = yield GetDistance("Ofset mesafesini belirtin", keywords=("Through",),
                          default=dist if dist else None)
    through = d == "Through"
    if not through:
        if d is None or d <= 0:
            ctx.print("Mesafe sıfırdan büyük olmalı.")
            return
        ctx.set("offset_dist", d)
    created = []
    while True:
        r = yield GetEntity("Ofsetlenecek nesneyi seçin", keywords=("Exit", "Undo"), allow_none=True,
                            types=("LINE", "ARC", "CIRCLE", "LWPOLYLINE", "ELLIPSE", "SPLINE"))
        if r is None or r == "Exit":
            return
        if r == "Undo":
            if created:
                ctx.doc.erase([created.pop()])
            continue
        e, _ = r
        ctx.canvas.set_selection([e.dxf.handle])
        if through:
            p = yield GetPoint("Geçiş noktasını belirtin")
            prims = geom.entity_prims(e)
            dist_ = min(pr.nearest(p).distance(p) for pr in prims) if prims else 0
            side = p
        else:
            dist_ = d
            side = yield GetPoint("Ofset yönü için taraftaki bir noktayı belirtin", no_snap=True,
                                  preview=lambda p: _offset_preview(e, d, p))
        ctx.canvas.clear_selection()
        if dist_ <= 0:
            continue
        new = offset_entity(ctx, e, dist_, side)
        if new is not None:
            ctx.created(new)
            created.append(new)


def _offset_preview(e, d, p):
    try:
        t = e.dxftype()
        if t in ("LINE", "LWPOLYLINE"):
            if t == "LINE":
                verts = [(Vec2(e.dxf.start), 0.0), (Vec2(e.dxf.end), 0.0)]
                closed = False
            else:
                verts = geom.lwpoly_points(e)
                closed = bool(e.closed)
            s = curves.side_of(verts, closed, p)
            res = curves.offset_vertices(verts, closed, d * s)
            if res:
                return [("prims", geom.polyline_prims(res, closed))]
        if t in ("CIRCLE", "ARC"):
            arc = geom.entity_prims(e)[0]
            r2 = arc.r + d if p.distance(arc.c) > arc.r else arc.r - d
            if r2 > 0:
                return [("prim", Arc(arc.c, r2, arc.a0, arc.a1, arc.full))]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------- TRIM / EXTEND
def _cutter_prims(ctx, exclude_handle, bbox, edges=None):
    """Primitives of all (visible) entities near bbox or of the given edges."""
    snap = ctx.tab.snap
    out = []
    if edges is not None:
        hs = [h for h in edges if h != exclude_handle]
    else:
        x0, y0, x1, y1 = bbox
        hs = ctx.tab.renderer.handles_in_rect(x0, y0, x1, y1)
        hs.discard(exclude_handle)
    for h in hs:
        e = ctx.doc.entity_by_handle(h)
        if e is None or e.dxf.owner != ctx.msp.layout_key:
            continue
        if e.dxftype() in ("TEXT", "MTEXT", "HATCH", "POINT", "IMAGE"):
            continue
        out.extend(p for p, _ in snap.prims(h, e))
    return out


def _curve_bbox(cv: Curve, grow=0.0):
    xs, ys = [], []
    for p in cv.prims:
        b = geom.prim_bbox(p)
        xs += [b[0], b[2]]
        ys += [b[1], b[3]]
    return (min(xs) - grow, min(ys) - grow, max(xs) + grow, max(ys) + grow)


def trim_entity(ctx, e, pick: Vec2, edges=None) -> tuple[list, list] | None:
    """Returns (removed, added) or None."""
    if e.dxftype() not in CURVE_TYPES:
        ctx.print(f"{e.dxftype()} budanamaz.")
        return None
    cv = Curve(e)
    if cv.n == 0:
        return None
    cutters = _cutter_prims(ctx, e.dxf.handle, _curve_bbox(cv), edges)
    params = cv.intersection_params(cutters)
    if e.dxftype() == "LWPOLYLINE":
        # self intersections are cutting edges too (except shared vertices)
        pass
    sp = cv.param(pick)
    attribs = common_attribs(e)
    new = []
    if cv.periodic:
        params = [s for s in params if 0 <= s < cv.n]
        if len(params) < 2:
            if not params:
                ctx.doc.erase([e])
                return [e], []
            ctx.print("Kapalı nesneyi budamak için en az iki kesişim gerekir.")
            return None
        lo = max([s for s in params if s < sp], default=params[-1] - cv.n)
        hi = min([s for s in params if s > sp], default=params[0] + cv.n)
        piece = cv.piece(ctx.msp, hi, lo + cv.n, attribs)
        if piece is not None:
            new.append(piece)
    else:
        inner = [s for s in params if 1e-9 < s < cv.n - 1e-9]
        lo = max([s for s in inner if s < sp], default=0.0)
        hi = min([s for s in inner if s > sp], default=float(cv.n))
        if lo <= 1e-9 and hi >= cv.n - 1e-9:
            ctx.doc.erase([e])
            return [e], []
        if lo > 1e-9:
            p = cv.piece(ctx.msp, 0.0, lo, attribs)
            if p is not None:
                new.append(p)
        if hi < cv.n - 1e-9:
            p = cv.piece(ctx.msp, hi, float(cv.n), attribs)
            if p is not None:
                new.append(p)
    for n_ in new:
        ctx.doc.added(n_)
    ctx.doc.erase([e])
    return [e], new


def extend_entity(ctx, e, pick: Vec2, edges=None):
    t = e.dxftype()
    if t not in ("LINE", "ARC", "LWPOLYLINE"):
        ctx.print(f"{t} uzatılamaz.")
        return None
    if t == "LWPOLYLINE" and e.closed:
        ctx.print("Kapalı çoklu çizgi uzatılamaz.")
        return None
    cv = Curve(e)
    sp = cv.param(pick)
    at_start = sp < cv.n / 2
    prim = cv.prims[0] if at_start else cv.prims[-1]
    vis = ctx.canvas.visible_rect()
    w = max(vis[2] - vis[0], vis[3] - vis[1])
    bbox = _curve_bbox(cv, grow=w * 2)
    cutters = _cutter_prims(ctx, e.dxf.handle, bbox, edges)
    best = None
    if isinstance(prim, Seg):
        end = prim.a if at_start else prim.b
        other = prim.b if at_start else prim.a
        dirv = (end - other).normalize()
        for c in cutters:
            for p in geom.intersect(Seg(other, end), c, True, False):
                d = (p - end).dot(dirv)
                if d > 1e-9 and (best is None or d < best[0]):
                    best = (d, p)
    else:
        full = Arc(prim.c, prim.r, 0, geom.TAU, full=True)
        end_a = prim.a0 if at_start else prim.a0 + prim.span
        for c in cutters:
            for p in geom.intersect(full, c, False, False):
                a = (p - prim.c).angle
                if at_start:
                    d = geom.norm_angle(end_a - a)
                else:
                    d = geom.norm_angle(a - end_a)
                if 1e-9 < d < geom.TAU - prim.span and (best is None or d < best[0]):
                    best = (d, p)
    if best is None:
        ctx.print("Nesne bir sınır kenarıyla kesişmiyor.")
        return None
    p = best[1]

    def fn(c):
        if t == "LINE":
            if at_start:
                c.dxf.start = Vec3(p)
            else:
                c.dxf.end = Vec3(p)
        elif t == "ARC":
            ang = math.degrees((p - prim.c).angle)
            if at_start:
                c.dxf.start_angle = ang
            else:
                c.dxf.end_angle = ang
        else:
            pts = list(c.get_points("xyseb"))
            ocs = c.ocs()
            lp = Vec2(ocs.from_wcs(Vec3(p))) if ocs.transform else p
            if at_start:
                x, y, s, en, b = pts[0]
                if abs(b) > 1e-12:
                    a2 = geom.Arc(prim.c, prim.r, (p - prim.c).angle, prim.a0 + prim.span)
                    b = math.tan(a2.span / 4) * (1 if b > 0 else -1)
                pts[0] = (lp.x, lp.y, s, en, b)
            else:
                if abs(pts[-2][4]) > 1e-12:
                    x, y, s, en, b = pts[-2]
                    a2 = geom.Arc(prim.c, prim.r, prim.a0, (p - prim.c).angle)
                    pts[-2] = (x, y, s, en, math.tan(a2.span / 4) * (1 if b > 0 else -1))
                x, y, s, en, b = pts[-1]
                pts[-1] = (lp.x, lp.y, s, en, b)
            c.set_points(pts, format="xyseb")
    new = ctx.doc.modify(e, fn)
    return [e], [new]


def _trim_extend(ctx, extend: bool):
    edges = None
    history = []
    name = "uzatılacak" if extend else "budanacak"
    while True:
        r = yield GetEntity(f"{name.capitalize()} nesneyi seçin (Shift ile {'budama' if extend else 'uzatma'})",
                            keywords=("cuTting edges" if not extend else "Boundary edges", "Undo"),
                            allow_none=True)
        if r is None:
            return
        if r in ("cuTting edges", "Boundary edges"):
            edges_ents = yield GetSelection("Kenar olarak kullanılacak nesneleri seçin (Enter = tümü)")
            edges = [x.dxf.handle for x in edges_ents] if edges_ents else None
            continue
        if r == "Undo":
            if history:
                removed, added = history.pop()
                ctx.doc.erase(added)
                for x in removed:
                    ctx.doc.restore(x)
            continue
        e, pick = r
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        shift = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
        do_extend = extend != shift
        res = extend_entity(ctx, e, pick, edges) if do_extend else trim_entity(ctx, e, pick, edges)
        if res:
            history.append(res)


@command("TRIM", "TR")
def trim(ctx):
    ctx.print("Hızlı mod: tüm nesneler kesme kenarıdır.")
    yield from _trim_extend(ctx, False)


@command("EXTEND", "EX")
def extend(ctx):
    ctx.print("Hızlı mod: tüm nesneler sınır kenarıdır.")
    yield from _trim_extend(ctx, True)


# ---------------------------------------------------------------- BREAK
@command("BREAK", "BR")
def break_(ctx):
    r = yield GetEntity("Nesneyi seçin", types=CURVE_TYPES)
    e, p1 = r
    p2 = yield GetPoint("İkinci kesme noktasını belirtin", keywords=("First",), base=None)
    if p2 == "First":
        p1 = yield GetPoint("İlk kesme noktasını belirtin")
        p2 = yield GetPoint("İkinci kesme noktasını belirtin", base=p1)
    _break_at(ctx, e, p1, p2)


@command("BREAKATPOINT", "BRP")
def break_at_point(ctx):
    r = yield GetEntity("Nesneyi seçin", types=("LINE", "ARC", "LWPOLYLINE"))
    e, _ = r
    p = yield GetPoint("Kesme noktasını belirtin")
    _break_at(ctx, e, p, p)


def _break_at(ctx, e, p1: Vec2, p2: Vec2):
    cv = Curve(e)
    s1, s2 = cv.param(p1), cv.param(p2)
    attribs = common_attribs(e)
    new = []
    if cv.periodic:
        if abs(s1 - s2) < 1e-9:
            ctx.print("Kapalı nesne tek noktadan kırılamaz.")
            return
        # remove CCW from s1 to s2 -> keep s2 .. s1(+n)
        hi = s2 if s2 > s1 else s2 + cv.n
        keep0, keep1 = hi, s1 + cv.n
        if keep1 < keep0:
            keep1 += cv.n
        p = cv.piece(ctx.msp, keep0, keep1, attribs)
        if p is not None:
            new.append(p)
    else:
        a, b = sorted((s1, s2))
        for s0, s1_ in ((0.0, a), (b, float(cv.n))):
            if s1_ - s0 > 1e-9:
                p = cv.piece(ctx.msp, s0, s1_, attribs)
                if p is not None:
                    new.append(p)
    for x in new:
        ctx.doc.added(x)
    ctx.doc.erase([e])


# ---------------------------------------------------------------- FILLET / CHAMFER
def _line_corner(l1, pick1: Vec2, l2, pick2: Vec2):
    s1 = Seg(Vec2(l1.dxf.start), Vec2(l1.dxf.end))
    s2 = Seg(Vec2(l2.dxf.start), Vec2(l2.dxf.end))
    ip = geom.intersect(s1, s2, True, True)
    if not ip:
        return None
    I = ip[0]

    def keep_dir(seg, pick):
        q = seg.nearest(pick, infinite=True)
        u = q - I
        if u.magnitude < 1e-9:
            far = seg.a if seg.a.distance(I) > seg.b.distance(I) else seg.b
            u = far - I
        u = u.normalize()
        far = max((seg.a, seg.b), key=lambda v: (v - I).dot(u))
        return u, far
    u1, far1 = keep_dir(s1, pick1)
    u2, far2 = keep_dir(s2, pick2)
    return I, u1, far1, u2, far2


def _fillet_lines(ctx, l1, p1, l2, p2, radius, chamfer=None):
    res = _line_corner(l1, p1, l2, p2)
    if res is None:
        ctx.print("Çizgiler paralel.")
        return
    I, u1, far1, u2, far2 = res
    cosang = max(-1.0, min(1.0, u1.dot(u2)))
    theta = math.acos(cosang)
    if theta < 1e-9 or abs(theta - math.pi) < 1e-9:
        ctx.print("Çizgiler paralel/çakışık.")
        return
    if chamfer is not None:
        d1, d2 = chamfer
        t1, t2 = I + u1 * d1, I + u2 * d2
    else:
        d = radius / math.tan(theta / 2) if radius > 0 else 0.0
        t1, t2 = I + u1 * d, I + u2 * d
    for line, t, far in ((l1, t1, far1), (l2, t2, far2)):
        def fn(c, t=t, far=far):
            c.dxf.start = Vec3(far)
            c.dxf.end = Vec3(t)
        if far.isclose(t):
            ctx.doc.erase([line])
        else:
            ctx.doc.modify(line, fn)
    attribs = common_attribs(l1)
    if chamfer is not None:
        if not t1.isclose(t2):
            ctx.created(ctx.msp.add_line(t1, t2, dxfattribs=attribs))
    elif radius > 0:
        bis = (u1 + u2).normalize()
        c = I + bis * (radius / math.sin(theta / 2))
        a1 = (t1 - c).angle
        a2 = (t2 - c).angle
        if geom.norm_angle(a2 - a1) <= math.pi:
            arc = (a1, a2)
        else:
            arc = (a2, a1)
        ctx.created(ctx.msp.add_arc(c, radius, math.degrees(arc[0]), math.degrees(arc[1]), dxfattribs=attribs))


def _fillet_polyline(ctx, e, radius, chamfer=None):
    verts = geom.lwpoly_points(e)
    closed = bool(e.closed)
    n = len(verts)
    out = []
    count = 0
    for i in range(n):
        p, b = verts[i]
        has_prev = closed or i > 0
        has_next = closed or i < n - 1
        prev_b = verts[i - 1][1] if has_prev else 0
        if not (has_prev and has_next) or abs(b) > 1e-12 or abs(prev_b) > 1e-12:
            out.append([p, b])
            continue
        pp = verts[i - 1][0]
        pn = verts[(i + 1) % n][0]
        u1 = (pp - p)
        u2 = (pn - p)
        if u1.magnitude < 1e-9 or u2.magnitude < 1e-9:
            out.append([p, b])
            continue
        L1, L2 = u1.magnitude, u2.magnitude
        u1, u2 = u1.normalize(), u2.normalize()
        theta = math.acos(max(-1.0, min(1.0, u1.dot(u2))))
        if theta < 1e-6 or abs(theta - math.pi) < 1e-6:
            out.append([p, b])
            continue
        if chamfer is not None:
            d1, d2 = chamfer
            bulge = 0.0
        else:
            d1 = d2 = radius / math.tan(theta / 2)
            turn = (p - pp).x * (pn - p).y - (p - pp).y * (pn - p).x
            bulge = math.tan((math.pi - theta) / 4) * (1 if turn > 0 else -1)
        if d1 > L1 + 1e-9 or d2 > L2 + 1e-9:
            out.append([p, b])
            continue
        out.append([p + u1 * d1, bulge])
        out.append([p + u2 * d2, 0.0])
        count += 1

    def fn(c):
        c.set_points([(v[0].x, v[0].y, 0, 0, v[1]) for v in out], format="xyseb")
    if count:
        ctx.doc.modify(e, fn)
    ctx.print(f"{count} köşe işlendi.")


def _fillet_cmd(ctx, chamfer_mode: bool):
    while True:
        if chamfer_mode:
            d1 = ctx.get("chamfer_d1", 0.0)
            d2 = ctx.get("chamfer_d2", 0.0)
            ctx.print(f"(PAH modu) Pah Mes1 = {fmt(d1)}, Mes2 = {fmt(d2)}")
            r = yield GetEntity("İlk çizgiyi seçin", keywords=("Polyline", "Distance"),
                                types=("LINE", "LWPOLYLINE"))
        else:
            rad = float(ctx.header("$FILLETRAD", 0.0))
            ctx.print(f"Geçerli ayarlar: Mod = BUDA, Yarıçap = {fmt(rad)}")
            r = yield GetEntity("İlk nesneyi seçin", keywords=("Polyline", "Radius"),
                                types=("LINE", "LWPOLYLINE"))
        if r == "Radius":
            v = yield GetDistance("Pah/kavis yarıçapını belirtin", default=float(ctx.header("$FILLETRAD", 0.0)))
            ctx.set_header("$FILLETRAD", v)
            continue
        if r == "Distance":
            a = yield GetDistance("İlk pah mesafesi", default=ctx.get("chamfer_d1", 0.0))
            b = yield GetDistance("İkinci pah mesafesi", default=a)
            ctx.set("chamfer_d1", a)
            ctx.set("chamfer_d2", b)
            continue
        if r == "Polyline":
            r2 = yield GetEntity("2B çoklu çizgiyi seçin", types=("LWPOLYLINE",))
            e, _ = r2
            if chamfer_mode:
                _fillet_polyline(ctx, e, 0, (ctx.get("chamfer_d1", 0.0), ctx.get("chamfer_d2", 0.0)))
            else:
                _fillet_polyline(ctx, e, float(ctx.header("$FILLETRAD", 0.0)))
            return
        e1, p1 = r
        if e1.dxftype() != "LINE":
            ctx.print("Şu an yalnızca çizgiler (LINE) veya Polyline seçeneği destekleniyor.")
            continue
        ctx.canvas.set_selection([e1.dxf.handle])
        r2 = yield GetEntity("İkinci çizgiyi seçin", types=("LINE",))
        ctx.canvas.clear_selection()
        e2, p2 = r2
        if e2 is e1:
            ctx.print("Aynı nesne seçildi.")
            return
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        shift = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
        if chamfer_mode:
            _fillet_lines(ctx, e1, p1, e2, p2, 0, (ctx.get("chamfer_d1", 0.0), ctx.get("chamfer_d2", 0.0)))
        else:
            _fillet_lines(ctx, e1, p1, e2, p2, 0.0 if shift else float(ctx.header("$FILLETRAD", 0.0)))
        return


@command("FILLET", "F")
def fillet(ctx):
    yield from _fillet_cmd(ctx, False)


@command("CHAMFER", "CHA")
def chamfer(ctx):
    yield from _fillet_cmd(ctx, True)


# ---------------------------------------------------------------- EXPLODE
@command("EXPLODE", "X", pickfirst=True)
def explode(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    count = 0
    for e in ents:
        t = e.dxftype()
        if t not in ("INSERT", "LWPOLYLINE", "POLYLINE", "DIMENSION", "MTEXT", "LEADER",
                     "MLINE", "HATCH", "ARC_DIMENSION", "MULTILEADER", "MLEADER", "REGION"):
            continue
        try:
            if t == "HATCH":
                continue
            virt = list(e.virtual_entities())
        except Exception as ex:
            ctx.print(f"{t} patlatılamadı: {ex}")
            continue
        if t == "INSERT":
            for a in e.attribs:
                try:
                    txt = ctx.msp.add_text(a.dxf.text, dxfattribs={
                        "layer": a.dxf.layer, "height": a.dxf.height, "rotation": a.dxf.rotation,
                        "style": a.dxf.style, "insert": a.dxf.insert,
                        "halign": a.dxf.halign, "valign": a.dxf.valign,
                    })
                    if a.dxf.hasattr("align_point"):
                        txt.dxf.align_point = a.dxf.align_point
                    ctx.doc.added(txt)
                except Exception:
                    pass
        for v in virt:
            if v.dxftype() == "ATTDEF":
                continue
            try:
                ctx.doc.add_entity(v)
            except Exception as ex:
                print("explode add failed", v, ex)
        ctx.doc.erase([e])
        count += 1
    ctx.print(f"{count} nesne patlatıldı.")


# ---------------------------------------------------------------- STRETCH
@command("STRETCH", "S")
def stretch(ctx):
    ctx.print("Gerdirilecek nesneleri çapraz pencere (crossing) ile seçin...")
    a = yield GetPoint("İlk köşe", no_snap=True)
    b = yield GetPoint("Karşı köşe", base=a, no_snap=True, rubber=False,
                       preview=lambda p: [("rect", a, p)])
    x0, x1 = sorted((a.x, b.x))
    y0, y1 = sorted((a.y, b.y))
    hs = ctx.tab.renderer.select_window(x0, y0, x1, y1, crossing=True)
    hs = [h for h in hs if not ctx.tab.is_locked(h)]
    ents = ctx.entities(hs)
    if not ents:
        ctx.print("Nesne bulunamadı.")
        return
    ctx.canvas.set_selection(hs)

    def inside(p):
        return x0 <= p.x <= x1 and y0 <= p.y <= y1
    base = yield GetPoint("Temel noktayı belirtin")
    target = yield GetPoint("İkinci noktayı belirtin", base=base,
                            preview=lambda p: _stretch_preview(ents, inside, p - base))
    ctx.canvas.clear_selection()
    d = target - base
    for e in ents:
        _stretch_entity(ctx, e, inside, d)


def _stretch_apply(c, inside, d: Vec2) -> bool:
    """Apply stretch to copy c, returns False if nothing to do."""
    t = c.dxftype()
    if t == "LINE":
        s, e = Vec2(c.dxf.start), Vec2(c.dxf.end)
        si, ei = inside(s), inside(e)
        if not (si or ei):
            return False
        if si:
            c.dxf.start = Vec3(s + d)
        if ei:
            c.dxf.end = Vec3(e + d)
        return True
    if t == "LWPOLYLINE":
        pts = list(c.get_points("xyseb"))
        wpts = geom.lwpoly_points(c)
        changed = False
        for i, (wp, _) in enumerate(wpts):
            if inside(wp):
                x, y, s, en, b = pts[i]
                pts[i] = (x + d.x, y + d.y, s, en, b)
                changed = True
        if changed:
            c.set_points(pts, format="xyseb")
        return changed
    if t == "ARC":
        arc = geom.entity_prims(c)[0]
        s, m, e = arc.start, arc.point(0.5), arc.end
        si, ei = inside(s), inside(e)
        if si and ei:
            c.transform(Matrix44.translate(d.x, d.y, 0))
            return True
        if not (si or ei):
            return False
        # keep the arc height (sagitta) like AutoCAD
        s2 = s + d if si else s
        e2 = e + d if ei else e
        chord_mid = s.lerp(e)
        h = m - chord_mid
        new_mid = s2.lerp(e2) + h
        a = geom.arc_3p(s2, new_mid, e2)
        if a is None:
            return False
        c.dxf.center = Vec3(a.c)
        c.dxf.radius = a.r
        c.dxf.start_angle = math.degrees(a.a0)
        c.dxf.end_angle = math.degrees(a.a1)
        return True
    if t == "DIMENSION":
        changed = False
        for name in ("defpoint", "defpoint2", "defpoint3", "defpoint4", "text_midpoint"):
            if c.dxf.hasattr(name):
                p = Vec2(c.dxf.get(name))
                if inside(p):
                    c.dxf.set(name, Vec3(p + d))
                    changed = True
        return changed
    # other entities: move if their reference point is inside
    ref = None
    for name in ("insert", "center", "location", "start"):
        if c.dxf.hasattr(name):
            ref = Vec2(c.dxf.get(name))
            break
    if ref is not None and inside(ref):
        c.transform(Matrix44.translate(d.x, d.y, 0))
        return True
    return False


def _stretch_entity(ctx, e, inside, d):
    c = e.copy()
    if not _stretch_apply(c, inside, d):
        return
    if e.dxftype() == "DIMENSION":
        new = ctx.doc.clone(e)
        _stretch_apply(new, inside, d)
        ctx.doc.replace(e, new)
        from t2dcad.grips import rerender_dimension
        rerender_dimension(ctx.dxf, new)
        ctx.doc.changed.emit([new], [], False)
        return
    ctx.doc.modify(e, lambda x: _stretch_apply(x, inside, d))


def _stretch_preview(ents, inside, d):
    out = []
    for e in ents:
        if e.dxftype() in ("LINE", "LWPOLYLINE", "ARC", "CIRCLE"):
            c = e.copy()
            if _stretch_apply(c, inside, d):
                out.append(("prims", geom.entity_prims(c)))
    return out


# ---------------------------------------------------------------- ARRAY
@command("ARRAY", "AR", "ARRAYCLASSIC", pickfirst=True)
def array(ctx):
    ents = yield GetSelection("Nesneleri seçin")
    if not ents:
        return
    hs = _handles(ents)
    k = yield GetKeyword("Dizi türünü girin", keywords=("Rectangular", "Polar"),
                         default=ctx.get("array_type", "Rectangular"))
    k = k or "Rectangular"
    ctx.set("array_type", k)
    if k == "Rectangular":
        rows = yield GetNumber("Satır sayısı", integer=True, default=ctx.get("ar_rows", 1))
        cols = yield GetNumber("Sütun sayısı", integer=True, default=ctx.get("ar_cols", 4))
        rd = 0.0
        if rows > 1:
            rd = yield GetDistance("Satırlar arası mesafe", default=ctx.get("ar_rd", 10.0))
        cd = 0.0
        if cols > 1:
            cd = yield GetDistance("Sütunlar arası mesafe", default=ctx.get("ar_cd", 10.0))
        ctx.set("ar_rows", rows)
        ctx.set("ar_cols", cols)
        ctx.set("ar_rd", rd)
        ctx.set("ar_cd", cd)
        for i in range(max(1, rows)):
            for j in range(max(1, cols)):
                if i == 0 and j == 0:
                    continue
                transform_entities(ctx, ents, Matrix44.translate(j * cd, i * rd, 0), copy=True)
    else:
        c = yield GetPoint("Dizinin merkez noktasını belirtin")
        n = yield GetNumber("Öğe sayısı", integer=True, default=ctx.get("ar_n", 6))
        fill = yield GetAngle("Doldurma açısı (+=saat yönü tersi)", default=360.0)
        rot = yield GetKeyword("Öğeler döndürülsün mü?", keywords=("Yes", "No"), default="Yes")
        ctx.set("ar_n", n)
        if n < 2:
            return
        step = fill / n if abs(abs(fill) - 360) < 1e-9 else fill / (n - 1)
        for i in range(1, n):
            ang = step * i
            if rot == "No":
                # move only by the rotated reference point
                ref = _ref_point(ents[0])
                rp = c + (ref - c).rotate_deg(ang)
                m = Matrix44.translate(rp.x - ref.x, rp.y - ref.y, 0)
            else:
                m = _rot(c, ang)
            transform_entities(ctx, ents, m, copy=True)


def _ref_point(e) -> Vec2:
    for name in ("insert", "center", "start", "location"):
        if e.dxf.hasattr(name):
            return Vec2(e.dxf.get(name))
    prims = geom.entity_prims(e)
    if prims:
        p = prims[0]
        return p.a if isinstance(p, Seg) else p.c
    return Vec2()


# ---------------------------------------------------------------- JOIN
@command("JOIN", "J", pickfirst=True)
def join(ctx):
    ents = yield GetSelection("Birleştirilecek nesneleri seçin")
    items = []
    for e in ents:
        vs = curves.to_vertices(e)
        if vs:
            items.append((e, vs))
    if len(items) < 2:
        ctx.print("Birleştirmek için en az iki açık çizgi/yay/çoklu çizgi seçin.")
        return
    tol = 1e-6 * max(1.0, max(abs(c) for _, vs in items for p, _b in vs for c in p))
    # collinear lines -> one line
    if all(e.dxftype() == "LINE" for e, _ in items):
        d0 = (items[0][1][1][0] - items[0][1][0][0]).normalize()
        a0 = items[0][1][0][0]
        ok = True
        for e, vs in items:
            for p, _ in vs:
                v = p - a0
                if abs(v.x * d0.y - v.y * d0.x) > 1e-6 * max(1.0, v.magnitude):
                    ok = False
            d = (vs[1][0] - vs[0][0]).normalize()
            if abs(abs(d.dot(d0)) - 1) > 1e-9:
                ok = False
        if ok:
            pts = [p for _, vs in items for p, _ in vs]
            ts = [(p - a0).dot(d0) for p in pts]
            pmin = pts[ts.index(min(ts))]
            pmax = pts[ts.index(max(ts))]
            new = ctx.msp.add_line(pmin, pmax, dxfattribs=common_attribs(items[0][0]))
            ctx.created(new)
            ctx.doc.erase([e for e, _ in items])
            ctx.print(f"{len(items)} çizgi tek çizgiye birleştirildi.")
            return
    chain = list(items[0][1])
    used = [items[0][0]]
    rest = items[1:]
    progress = True
    while rest and progress:
        progress = False
        for k, (e, vs) in enumerate(rest):
            if chain[-1][0].isclose(vs[0][0], abs_tol=tol):
                chain = chain[:-1] + vs
            elif chain[-1][0].isclose(vs[-1][0], abs_tol=tol):
                chain = chain[:-1] + curves.reverse_vertices(vs)
            elif chain[0][0].isclose(vs[-1][0], abs_tol=tol):
                chain = vs[:-1] + chain
            elif chain[0][0].isclose(vs[0][0], abs_tol=tol):
                chain = curves.reverse_vertices(vs)[:-1] + chain
            else:
                continue
            used.append(e)
            rest.pop(k)
            progress = True
            break
    closed = len(chain) > 2 and chain[0][0].isclose(chain[-1][0], abs_tol=tol)
    if closed:
        chain = chain[:-1]
    attribs = common_attribs(used[0])
    new = ctx.msp.add_lwpolyline([(p.x, p.y, b) for p, b in chain], format="xyb", close=closed,
                                 dxfattribs=attribs)
    ctx.created(new)
    ctx.doc.erase(used)
    ctx.print(f"{len(used)} nesne birleştirildi" + (f", {len(rest)} nesne bağlanamadı." if rest else "."))


# ---------------------------------------------------------------- MATCHPROP
@command("MATCHPROP", "MA", "PAINTER")
def matchprop(ctx):
    r = yield GetEntity("Kaynak nesneyi seçin")
    src, _ = r
    props = {}
    for name in ("layer", "color", "linetype", "lineweight", "ltscale", "true_color"):
        props[name] = src.dxf.get(name) if src.dxf.hasattr(name) else None
    ctx.print("Geçerli etkin ayarlar: Renk Katman Çizgi tipi Çizgi tipi ölçeği Çizgi kalınlığı")
    while True:
        r = yield GetEntity("Hedef nesneyi seçin", allow_none=True)
        if r is None:
            return
        e, _ = r

        def fn(c):
            for name, v in props.items():
                if v is None:
                    c.dxf.discard(name)
                else:
                    c.dxf.set(name, v)
            if src.dxftype() in ("TEXT", "MTEXT") and c.dxftype() == src.dxftype():
                for name in ("style", "height", "char_height"):
                    if src.dxf.hasattr(name):
                        c.dxf.set(name, src.dxf.get(name))
        ctx.doc.modify(e, fn)


# ---------------------------------------------------------------- LENGTHEN (DElta)
@command("LENGTHEN", "LEN")
def lengthen(ctx):
    d = yield GetDistance("Uzatma miktarı (Delta, negatif = kısalt)", default=ctx.get("len_delta", 10.0))
    ctx.set("len_delta", d)
    while True:
        r = yield GetEntity("Değiştirilecek çizgiyi seçin (uç tarafından)", types=("LINE", "ARC"),
                            allow_none=True)
        if r is None:
            return
        e, pick = r
        if e.dxftype() == "LINE":
            s, en = Vec2(e.dxf.start), Vec2(e.dxf.end)
            at_start = pick.distance(s) < pick.distance(en)

            def fn(c, s=s, en=en, at_start=at_start):
                u = (en - s).normalize()
                if at_start:
                    c.dxf.start = Vec3(s - u * d)
                else:
                    c.dxf.end = Vec3(en + u * d)
            ctx.doc.modify(e, fn)
        else:
            arc = geom.entity_prims(e)[0]
            at_start = pick.distance(arc.start) < pick.distance(arc.end)
            da = math.degrees(d / arc.r)

            def fn(c, at_start=at_start):
                if at_start:
                    c.dxf.start_angle = c.dxf.start_angle - da
                else:
                    c.dxf.end_angle = c.dxf.end_angle + da
            ctx.doc.modify(e, fn)
