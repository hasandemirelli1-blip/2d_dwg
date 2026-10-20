"""Dimension and leader commands."""
from __future__ import annotations

import math

from ezdxf.math import Vec2

from t2dcad import geom
from t2dcad.engine import command, GetPoint, GetEntity, GetKeyword, GetString, fmt


def dimstyle(ctx) -> str:
    name = ctx.header("$DIMSTYLE", "T2D")
    if name not in ctx.dxf.dimstyles:
        name = "T2D" if "T2D" in ctx.dxf.dimstyles else "Standard"
    return name


def _finish(ctx, ov):
    ov.render()
    ctx.created(ov.dimension)
    return ov.dimension


def _linear_angle(p1: Vec2, p2: Vec2, loc: Vec2) -> float:
    x0, x1 = sorted((p1.x, p2.x))
    y0, y1 = sorted((p1.y, p2.y))
    if (loc.x < x0 or loc.x > x1) and (y0 <= loc.y <= y1):
        return 90.0
    return 0.0


def _dim_preview(p1, p2, loc, angle):
    u = Vec2.from_deg_angle(angle)
    n = u.orthogonal()
    d1 = p1 + n * (loc - p1).dot(n)
    d2 = p2 + n * (loc - p2).dot(n)
    return [("line", p1, d1), ("line", p2, d2), ("line", d1, d2)]


@command("DIMLINEAR", "DLI", "DIMLIN")
def dimlinear(ctx):
    p1 = yield GetPoint("İlk uzatma çizgisi başlangıcını belirtin", keywords=("Object",))
    if p1 == "Object":
        r = yield GetEntity("Ölçülendirilecek nesneyi seçin", types=("LINE",))
        e, _ = r
        p1, p2 = Vec2(e.dxf.start), Vec2(e.dxf.end)
    else:
        p2 = yield GetPoint("İkinci uzatma çizgisi başlangıcını belirtin", base=p1)
    forced = None
    while True:
        loc = yield GetPoint("Ölçü çizgisi konumunu belirtin", keywords=("Horizontal", "Vertical", "Rotated"),
                             rubber=False,
                             preview=lambda p: _dim_preview(p1, p2, p, forced if forced is not None
                                                            else _linear_angle(p1, p2, p)))
        if loc == "Horizontal":
            forced = 0.0
            continue
        if loc == "Vertical":
            forced = 90.0
            continue
        if loc == "Rotated":
            from t2dcad.engine import GetAngle
            forced = yield GetAngle("Ölçü çizgisi açısını belirtin", default=0.0)
            continue
        break
    angle = forced if forced is not None else _linear_angle(p1, p2, loc)
    ov = ctx.msp.add_linear_dim(base=loc, p1=p1, p2=p2, angle=angle, dimstyle=dimstyle(ctx),
                                dxfattribs=ctx.attribs())
    _finish(ctx, ov)
    ctx.set("last_dim", (p1, p2, loc, angle))
    ctx.print(f"Ölçü metni = {fmt(abs((p2 - p1).dot(Vec2.from_deg_angle(angle))), 4)}")


@command("DIMALIGNED", "DAL", "DIMALI")
def dimaligned(ctx):
    p1 = yield GetPoint("İlk uzatma çizgisi başlangıcını belirtin")
    p2 = yield GetPoint("İkinci uzatma çizgisi başlangıcını belirtin", base=p1)
    ang = math.degrees((p2 - p1).angle)
    loc = yield GetPoint("Ölçü çizgisi konumunu belirtin", rubber=False,
                         preview=lambda p: _dim_preview(p1, p2, p, ang))
    ov = ctx.msp.add_linear_dim(base=loc, p1=p1, p2=p2, angle=ang, dimstyle=dimstyle(ctx),
                                dxfattribs=ctx.attribs())
    ov.dimension.dxf.dimtype = 1  # aligned
    _finish(ctx, ov)
    ctx.set("last_dim", (p1, p2, loc, ang))
    ctx.print(f"Ölçü metni = {fmt(p1.distance(p2), 4)}")


def _next_dim(ctx, baseline: bool):
    last = ctx.get("last_dim")
    if not last:
        ctx.print("Önce DIMLINEAR veya DIMALIGNED ile bir ölçü oluşturun.")
        return
    p1, p2, loc, angle = last
    u = Vec2.from_deg_angle(angle)
    n = u.orthogonal()
    step = 3.75
    try:
        ds = ctx.dxf.dimstyles.get(dimstyle(ctx))
        step = ds.dxf.get("dimdli", 3.75) * (ds.dxf.get("dimscale", 1.0) or 1.0)
    except Exception:
        pass
    while True:
        start = p1 if baseline else p2
        q = yield GetPoint("İkinci uzatma çizgisi başlangıcını belirtin", base=start, allow_none=True,
                           rubber=False,
                           preview=lambda p: _dim_preview(start, p, loc, angle))
        if q is None:
            return
        side = 1 if (loc - p1).dot(n) >= 0 else -1
        new_loc = loc + n * (step * side) if baseline else loc
        ov = ctx.msp.add_linear_dim(base=new_loc, p1=start, p2=q, angle=angle, dimstyle=dimstyle(ctx),
                                    dxfattribs=ctx.attribs())
        _finish(ctx, ov)
        if baseline:
            loc = new_loc
            p2 = q
        else:
            p1, p2 = p2, q
        ctx.set("last_dim", (p1, p2, loc, angle))


@command("DIMCONTINUE", "DCO", "DIMCONT")
def dimcontinue(ctx):
    yield from _next_dim(ctx, False)


@command("DIMBASELINE", "DBA", "DIMBASE")
def dimbaseline(ctx):
    yield from _next_dim(ctx, True)


def _circle_of(e):
    prims = geom.entity_prims(e)
    if prims and isinstance(prims[0], geom.Arc):
        return prims[0]
    return None


@command("DIMRADIUS", "DRA", "DIMRAD")
def dimradius(ctx):
    r = yield GetEntity("Yay veya çember seçin", types=("CIRCLE", "ARC"))
    e, pick = r
    arc = _circle_of(e)
    loc = yield GetPoint("Ölçü çizgisi konumunu belirtin", rubber=False,
                         preview=lambda p: [("line", arc.c, p)])
    ov = ctx.msp.add_radius_dim(center=arc.c, radius=arc.r, location=loc, dimstyle=dimstyle(ctx),
                                dxfattribs=ctx.attribs())
    _finish(ctx, ov)


@command("DIMDIAMETER", "DDI", "DIMDIA")
def dimdiameter(ctx):
    r = yield GetEntity("Yay veya çember seçin", types=("CIRCLE", "ARC"))
    e, pick = r
    arc = _circle_of(e)
    loc = yield GetPoint("Ölçü çizgisi konumunu belirtin", rubber=False,
                         preview=lambda p: [("line", arc.c - (p - arc.c).normalize() * arc.r, p)]
                         if not p.isclose(arc.c) else [])
    ov = ctx.msp.add_diameter_dim(center=arc.c, radius=arc.r, location=loc, dimstyle=dimstyle(ctx),
                                  dxfattribs=ctx.attribs())
    _finish(ctx, ov)


@command("DIMANGULAR", "DAN", "DIMANG")
def dimangular(ctx):
    r1 = yield GetEntity("İlk çizgiyi seçin", types=("LINE",))
    r2 = yield GetEntity("İkinci çizgiyi seçin", types=("LINE",))
    l1, l2 = r1[0], r2[0]
    s1 = (Vec2(l1.dxf.start), Vec2(l1.dxf.end))
    s2 = (Vec2(l2.dxf.start), Vec2(l2.dxf.end))
    loc = yield GetPoint("Ölçü yayı konumunu belirtin", rubber=False)
    ov = ctx.msp.add_angular_dim_2l(base=loc, line1=s1, line2=s2, dimstyle=dimstyle(ctx),
                                    dxfattribs=ctx.attribs())
    _finish(ctx, ov)


@command("QLEADER", "LE", "LEADER", "MLEADER", "MLD")
def qleader(ctx):
    pts = []
    p = yield GetPoint("Ok başı noktasını belirtin")
    pts.append(p)
    while True:
        q = yield GetPoint("Sonraki noktayı belirtin", base=pts[-1], allow_none=True,
                           preview=lambda q: [("poly", pts + [q], False)], rubber=False)
        if q is None:
            break
        pts.append(q)
        if len(pts) >= 3:
            break
    if len(pts) < 2:
        return
    txt = yield GetString("Not metnini girin", spaces=True)
    leader = ctx.msp.add_leader(pts, dimstyle=dimstyle(ctx), dxfattribs=ctx.attribs())
    ctx.created(leader)
    if txt:
        h = float(ctx.header("$TEXTSIZE", 2.5))
        try:
            ds = ctx.dxf.dimstyles.get(dimstyle(ctx))
            h = ds.dxf.get("dimtxt", h) * (ds.dxf.get("dimscale", 1.0) or 1.0)
        except Exception:
            pass
        right = pts[-1].x >= pts[-2].x
        pos = pts[-1] + Vec2(h * 0.5 if right else -h * 0.5, 0)
        m = ctx.msp.add_mtext(txt, dxfattribs=ctx.attribs(char_height=h))
        m.set_location(pos, attachment_point=4 if right else 6)
        ctx.created(m)


@command("DIMSTYLE", "D", "DST", "DDIM", undoable=False)
def dimstyle_cmd(ctx):
    ctx.main.dimstyle_dialog(ctx.tab)
