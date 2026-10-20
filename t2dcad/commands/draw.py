"""Draw commands."""
from __future__ import annotations

import math

from ezdxf.math import Vec2, Vec3
from ezdxf.enums import TextEntityAlignment

from t2dcad import geom
from t2dcad.engine import (command, GetPoint, GetDistance, GetAngle, GetNumber, GetString,
                           GetKeyword, Cancel, fmt)
from t2dcad.geom import Seg, Arc


def _arc_prim(c: Vec2, r: float, a0: float, a1: float) -> Arc:
    return Arc(c, r, a0, a1)


# ---------------------------------------------------------------- LINE
@command("LINE", "L")
def line(ctx):
    p1 = yield GetPoint("İlk noktayı belirtin", allow_none=True)
    if p1 is None:
        if ctx.last_point is None:
            return
        p1 = ctx.last_point
    pts = [p1]
    segs = []
    while True:
        kws = ("Close", "Undo") if len(pts) >= 3 else ("Undo",)
        p = yield GetPoint("Sonraki noktayı belirtin", base=pts[-1], keywords=kws, allow_none=True)
        if p is None:
            return
        if p == "Undo":
            if segs:
                ctx.doc.erase([segs.pop()])
                pts.pop()
            else:
                ctx.print("Geri alınacak çizgi yok.")
            continue
        if p == "Close":
            e = ctx.msp.add_line(pts[-1], pts[0], dxfattribs=ctx.attribs())
            ctx.created(e)
            ctx.last_point = pts[0]
            return
        if p.isclose(pts[-1]):
            continue
        e = ctx.msp.add_line(pts[-1], p, dxfattribs=ctx.attribs())
        ctx.created(e)
        segs.append(e)
        pts.append(p)


# ---------------------------------------------------------------- PLINE
def _end_tangent(p1: Vec2, p2: Vec2, bulge: float) -> float:
    phi = (p2 - p1).angle
    theta = 4 * math.atan(bulge)
    return phi + theta / 2


def _tangent_bulge(start: Vec2, tangent: float, end: Vec2) -> float:
    chord = end - start
    if chord.magnitude < 1e-12:
        return 0.0
    alpha = chord.angle - tangent
    alpha = math.atan2(math.sin(alpha), math.cos(alpha))
    return math.tan(alpha / 2)


@command("PLINE", "PL")
def pline(ctx):
    start = yield GetPoint("Başlangıç noktasını belirtin")
    ctx.print(f"Geçerli çizgi genişliği {fmt(ctx.get('pl_width', 0.0))}")
    verts: list[list] = [[start, 0.0]]  # (point, bulge to next)
    arc_mode = False
    width = ctx.get("pl_width", 0.0)
    closed = False

    def prims_of(vs, extra=None):
        pts = [(v[0], v[1]) for v in vs]
        if extra is not None:
            pts = pts[:-1] + [(pts[-1][0], extra[1]), (extra[0], 0.0)]
        return geom.polyline_prims(pts, False)

    def cur_tangent():
        if len(verts) >= 2:
            return _end_tangent(verts[-2][0], verts[-1][0], verts[-2][1])
        return 0.0

    while True:
        last = verts[-1][0]
        if arc_mode:
            kws = ("Close", "Line", "Undo", "Width") if len(verts) >= 2 else ("Line", "Undo", "Width")

            def preview(p, last=last):
                b = _tangent_bulge(last, cur_tangent(), p)
                return [("prims", prims_of(verts, (p, b)))]
            p = yield GetPoint("Yayın son noktasını belirtin", base=last, keywords=kws,
                               allow_none=True, preview=preview, rubber=False)
        else:
            kws = ("Arc", "Close", "Undo", "Width") if len(verts) >= 3 else ("Arc", "Undo", "Width")

            def preview(p, last=last):
                return [("prims", prims_of(verts)), ("line", last, p)]
            p = yield GetPoint("Sonraki noktayı belirtin", base=last, keywords=kws,
                               allow_none=True, preview=preview, rubber=False)
        if p is None:
            break
        if p == "Arc":
            arc_mode = True
            continue
        if p == "Line":
            arc_mode = False
            continue
        if p == "Close":
            if arc_mode and len(verts) >= 2:
                verts[-1][1] = _tangent_bulge(last, cur_tangent(), verts[0][0])
            closed = True
            break
        if p == "Undo":
            if len(verts) > 1:
                verts.pop()
                verts[-1][1] = 0.0
            continue
        if p == "Width":
            w = yield GetDistance("Başlangıç genişliği", default=width)
            width = w
            ctx.set("pl_width", w)
            continue
        if p.isclose(last):
            continue
        if arc_mode:
            verts[-1][1] = _tangent_bulge(last, cur_tangent(), p)
        verts.append([p, 0.0])
    if len(verts) < 2:
        return
    attribs = ctx.attribs()
    if width:
        attribs["const_width"] = width
    pts = [(v[0].x, v[0].y, v[1]) for v in verts]
    e = ctx.msp.add_lwpolyline(pts, format="xyb", close=closed, dxfattribs=attribs)
    ctx.created(e)


# ---------------------------------------------------------------- CIRCLE
@command("CIRCLE", "C")
def circle(ctx):
    r0 = ctx.get("circle_r", 10.0)
    c = yield GetPoint("Çemberin merkez noktasını belirtin", keywords=("3P", "2P", "Ttr"))
    if c == "3P":
        p1 = yield GetPoint("Çemberdeki ilk nokta")
        p2 = yield GetPoint("Çemberdeki ikinci nokta", base=p1)

        def pv(p):
            res = geom.circle_3p(p1, p2, p)
            return [("circle", res[0], res[1])] if res else []
        p3 = yield GetPoint("Çemberdeki üçüncü nokta", preview=pv, rubber=False)
        res = geom.circle_3p(p1, p2, p3)
        if not res:
            ctx.print("Noktalar aynı doğru üzerinde.")
            return
        center, r = res
    elif c == "2P":
        p1 = yield GetPoint("Çap üzerindeki ilk uç nokta")
        p2 = yield GetPoint("Çap üzerindeki ikinci uç nokta", base=p1,
                            preview=lambda p: [("circle", p1.lerp(p), p1.distance(p) / 2)])
        center, r = p1.lerp(p2), p1.distance(p2) / 2
    elif c == "Ttr":
        ctx.print("TTR henüz desteklenmiyor, merkez-yarıçap kullanın.")
        return
    else:
        center = c
        r = yield GetDistance("Yarıçapı belirtin", base=center, keywords=("Diameter",), default=r0,
                              preview=lambda p: [("circle", center, center.distance(p)), ("line", center, p)])
        if r == "Diameter":
            d = yield GetDistance("Çapı belirtin", base=center, default=r0 * 2,
                                  preview=lambda p: [("circle", center, center.distance(p) / 2)])
            r = d / 2
    if r <= 0:
        ctx.print("Yarıçap sıfırdan büyük olmalı.")
        return
    ctx.set("circle_r", r)
    ctx.created(ctx.msp.add_circle(center, r, dxfattribs=ctx.attribs()))


# ---------------------------------------------------------------- ARC
def _add_arc(ctx, arc: Arc):
    e = ctx.msp.add_arc(arc.c, arc.r, math.degrees(arc.a0), math.degrees(arc.a0 + arc.span),
                        dxfattribs=ctx.attribs())
    ctx.created(e)


@command("ARC", "A")
def arc(ctx):
    p1 = yield GetPoint("Yayın başlangıç noktasını belirtin", keywords=("Center",))
    if p1 == "Center":
        c = yield GetPoint("Yayın merkezini belirtin")
        s = yield GetPoint("Yayın başlangıç noktasını belirtin", base=c)
        r = c.distance(s)
        a0 = (s - c).angle

        def pv(p):
            return [("prim", Arc(c, r, a0, (p - c).angle)), ("dline", c, p)]
        e = yield GetPoint("Yayın bitiş noktasını belirtin (saat yönü tersine)", base=c, preview=pv,
                           keywords=("Angle",), rubber=False)
        if e == "Angle":
            ang = yield GetAngle("Kapsanan açıyı belirtin", base=c)
            a1 = a0 + math.radians(ang)
            if ang < 0:
                a0, a1 = a1, a0
        else:
            a1 = (e - c).angle
        _add_arc(ctx, Arc(c, r, a0, a1))
        return
    p2 = yield GetPoint("Yayın ikinci noktasını belirtin", base=p1, keywords=("Center", "End"))
    if p2 == "End":
        e = yield GetPoint("Yayın bitiş noktasını belirtin", base=p1)
        c = yield GetPoint("Yayın merkezini belirtin", base=p1,
                           preview=lambda p: [("prim", Arc(p, p.distance(p1), (p1 - p).angle, (e - p).angle))])
        _add_arc(ctx, Arc(c, c.distance(p1), (p1 - c).angle, (e - c).angle))
        return
    if p2 == "Center":
        c = yield GetPoint("Yayın merkezini belirtin", base=p1)
        r = c.distance(p1)
        a0 = (p1 - c).angle
        e = yield GetPoint("Yayın bitiş noktasını belirtin", base=c, rubber=False,
                           preview=lambda p: [("prim", Arc(c, r, a0, (p - c).angle)), ("dline", c, p)])
        _add_arc(ctx, Arc(c, r, a0, (e - c).angle))
        return

    def pv(p):
        a = geom.arc_3p(p1, p2, p)
        return [("prim", a)] if a else [("line", p1, p)]
    p3 = yield GetPoint("Yayın bitiş noktasını belirtin", base=p2, preview=pv, rubber=False)
    a = geom.arc_3p(p1, p2, p3)
    if a is None:
        ctx.print("Noktalar aynı doğru üzerinde.")
        return
    _add_arc(ctx, a)


# ---------------------------------------------------------------- RECTANG
def _rect_pts(a: Vec2, b: Vec2):
    return [a, Vec2(b.x, a.y), b, Vec2(a.x, b.y)]


@command("RECTANG", "REC", "RECTANGLE")
def rectang(ctx):
    a = yield GetPoint("İlk köşe noktasını belirtin")
    b = yield GetPoint("Diğer köşe noktasını belirtin", base=a, keywords=("Dimensions", "Area"),
                       preview=lambda p: [("poly", _rect_pts(a, p), True)], rubber=False)
    if b == "Dimensions":
        L = yield GetDistance("Dikdörtgen uzunluğu", default=ctx.get("rec_l", 10.0))
        W = yield GetDistance("Dikdörtgen genişliği", default=ctx.get("rec_w", 10.0))
        ctx.set("rec_l", L)
        ctx.set("rec_w", W)

        def corner(p):
            sx = 1 if p.x >= a.x else -1
            sy = 1 if p.y >= a.y else -1
            return a + Vec2(sx * L, sy * W)
        d = yield GetPoint("Diğer köşe yönünü belirtin", base=a, rubber=False,
                           preview=lambda p: [("poly", _rect_pts(a, corner(p)), True)])
        b = corner(d)
    elif b == "Area":
        area = yield GetNumber("Alan", default=100.0)
        L = yield GetDistance("Uzunluk", default=10.0)
        b = a + Vec2(L, area / L)
    pts = _rect_pts(a, b)
    e = ctx.msp.add_lwpolyline([(p.x, p.y) for p in pts], close=True, dxfattribs=ctx.attribs())
    ctx.created(e)


# ---------------------------------------------------------------- POLYGON
@command("POLYGON", "POL")
def polygon(ctx):
    n = yield GetNumber("Kenar sayısını girin", integer=True, default=ctx.get("pol_n", 4))
    if n < 3 or n > 1024:
        ctx.print("3 ile 1024 arasında olmalı.")
        return
    ctx.set("pol_n", n)
    c = yield GetPoint("Çokgenin merkezini belirtin", keywords=("Edge",))
    if c == "Edge":
        e1 = yield GetPoint("Kenarın ilk uç noktası")

        def pts_edge(e2):
            side = e2 - e1
            L = side.magnitude
            if L < 1e-12:
                return []
            pts = [e1, e2]
            ang = side.angle
            cur = e2
            for i in range(n - 2):
                ang += math.tau / n
                cur = cur + Vec2.from_angle(ang, L)
                pts.append(cur)
            return pts
        e2 = yield GetPoint("Kenarın ikinci uç noktası", base=e1, rubber=False,
                            preview=lambda p: [("poly", pts_edge(p), True)])
        pts = pts_edge(e2)
    else:
        mode = yield GetKeyword("Seçenek girin", keywords=("Inscribed", "Circumscribed"),
                                default=ctx.get("pol_mode", "Inscribed"))
        mode = mode or "Inscribed"
        ctx.set("pol_mode", mode)

        def pts_r(p):
            r = c.distance(p)
            if r < 1e-12:
                return []
            a0 = (p - c).angle
            if mode == "Circumscribed":
                r = r / math.cos(math.pi / n)
                a0 += math.pi / n
            return [c + Vec2.from_angle(a0 + i * math.tau / n, r) for i in range(n)]
        p = yield GetPoint("Çemberin yarıçapını belirtin", base=c, rubber=False,
                           preview=lambda q: [("poly", pts_r(q), True)])
        pts = pts_r(p)
    if not pts:
        return
    e = ctx.msp.add_lwpolyline([(p.x, p.y) for p in pts], close=True, dxfattribs=ctx.attribs())
    ctx.created(e)


# ---------------------------------------------------------------- ELLIPSE
@command("ELLIPSE", "EL")
def ellipse(ctx):
    p1 = yield GetPoint("Elipsin eksen uç noktasını belirtin", keywords=("Center",))
    if p1 == "Center":
        c = yield GetPoint("Elipsin merkezini belirtin")
        a = yield GetPoint("Eksen uç noktasını belirtin", base=c)
        major = a - c
    else:
        p2 = yield GetPoint("Eksenin diğer uç noktasını belirtin", base=p1)
        c = p1.lerp(p2)
        major = p2 - c
    if major.magnitude < 1e-12:
        return

    q = yield GetDistance("Diğer eksen uzunluğunu belirtin (yarı)", base=c,
                          preview=lambda p: [("poly", _ellipse_pts(c, major, _ratio(c, major, p)), True)])
    if q <= 1e-12:
        return
    ratio = q / major.magnitude
    if ratio > 1:
        ratio = major.magnitude / q
        major = Vec2.from_angle(major.angle + math.pi / 2, q)
    e = ctx.msp.add_ellipse(c, major=Vec3(major.x, major.y, 0), ratio=ratio, dxfattribs=ctx.attribs())
    ctx.created(e)


def _ratio(c, major, p):
    r = (p - c).magnitude / major.magnitude
    return max(1e-6, min(1.0, r))


def _ellipse_pts(c: Vec2, major: Vec2, ratio: float):
    minor = major.orthogonal() * ratio
    return [c + major * math.cos(t) + minor * math.sin(t) for t in
            (i * math.tau / 72 for i in range(72))]


# ---------------------------------------------------------------- POINT
@command("POINT", "PO")
def point(ctx):
    while True:
        p = yield GetPoint("Bir nokta belirtin", allow_none=True)
        if p is None:
            return
        ctx.created(ctx.msp.add_point(p, dxfattribs=ctx.attribs()))


# ---------------------------------------------------------------- XLINE / RAY
@command("XLINE", "XL")
def xline(ctx):
    p = yield GetPoint("Bir nokta belirtin", keywords=("Hor", "Ver", "Ang"))
    if p in ("Hor", "Ver", "Ang"):
        if p == "Ang":
            ang = yield GetAngle("Açıyı girin", default=0.0)
            d = Vec2.from_deg_angle(ang)
        else:
            d = Vec2(1, 0) if p == "Hor" else Vec2(0, 1)
        while True:
            q = yield GetPoint("Geçiş noktasını belirtin", allow_none=True,
                               preview=lambda q: [("line", q - d * 1e5, q + d * 1e5)])
            if q is None:
                return
            ctx.created(ctx.msp.add_xline(q, d, dxfattribs=ctx.attribs()))
    base = p
    while True:
        q = yield GetPoint("Geçiş noktasını belirtin", base=base, allow_none=True, rubber=False,
                           preview=lambda q: [("line", base - (q - base) * 1e5, base + (q - base) * 1e5)]
                           if not q.isclose(base) else [])
        if q is None:
            return
        if q.isclose(base):
            continue
        ctx.created(ctx.msp.add_xline(base, (q - base).normalize(), dxfattribs=ctx.attribs()))


@command("RAY")
def ray(ctx):
    base = yield GetPoint("Başlangıç noktasını belirtin")
    while True:
        q = yield GetPoint("Geçiş noktasını belirtin", base=base, allow_none=True)
        if q is None:
            return
        if q.isclose(base):
            continue
        ctx.created(ctx.msp.add_ray(base, (q - base).normalize(), dxfattribs=ctx.attribs()))


# ---------------------------------------------------------------- TEXT
JUSTIFY = {
    "Left": TextEntityAlignment.LEFT, "Center": TextEntityAlignment.CENTER,
    "Right": TextEntityAlignment.RIGHT, "Middle": TextEntityAlignment.MIDDLE,
    "TL": TextEntityAlignment.TOP_LEFT, "TC": TextEntityAlignment.TOP_CENTER,
    "TR": TextEntityAlignment.TOP_RIGHT, "ML": TextEntityAlignment.MIDDLE_LEFT,
    "MC": TextEntityAlignment.MIDDLE_CENTER, "MR": TextEntityAlignment.MIDDLE_RIGHT,
    "BL": TextEntityAlignment.BOTTOM_LEFT, "BC": TextEntityAlignment.BOTTOM_CENTER,
    "BR": TextEntityAlignment.BOTTOM_RIGHT,
}


def text_style(ctx) -> str:
    st = ctx.header("$TEXTSTYLE", "Standard")
    return st if st in ctx.dxf.styles else "Standard"


@command("TEXT", "DT", "DTEXT")
def text(ctx):
    just = ctx.get("text_just", "Left")
    ctx.print(f"Geçerli yazı stili: \"{text_style(ctx)}\"  Yazı yüksekliği: {fmt(ctx.header('$TEXTSIZE', 2.5))}  Hizalama: {just}")
    p = yield GetPoint("Yazının başlangıç noktasını belirtin", keywords=("Justify", "Style"))
    while p in ("Justify", "Style"):
        if p == "Justify":
            j = yield GetKeyword("Hizalama seçin", keywords=tuple(JUSTIFY.keys()), default=just)
            just = j or just
            ctx.set("text_just", just)
        else:
            names = [s.dxf.name for s in ctx.dxf.styles]
            s = yield GetString(f"Stil adı ({', '.join(names)})", default=text_style(ctx))
            if s and s in ctx.dxf.styles:
                ctx.set_header("$TEXTSTYLE", s)
        p = yield GetPoint("Yazının başlangıç noktasını belirtin", keywords=("Justify", "Style"))
    h = yield GetDistance("Yüksekliği belirtin", base=p, default=float(ctx.header("$TEXTSIZE", 2.5)))
    ctx.set_header("$TEXTSIZE", h)
    rot = yield GetAngle("Yazının dönme açısını belirtin", base=p, default=float(ctx.get("text_rot", 0.0)))
    ctx.set("text_rot", rot)
    pos = p
    while True:
        s = yield GetString("Yazıyı girin", spaces=True)
        if not s:
            return
        attribs = ctx.attribs(height=h, rotation=rot, style=text_style(ctx))
        e = ctx.msp.add_text(s, dxfattribs=attribs)
        e.set_placement(pos, align=JUSTIFY.get(just, TextEntityAlignment.LEFT))
        ctx.created(e)
        pos = pos + Vec2.from_deg_angle(rot - 90, h * 1.6667)


@command("MTEXT", "MT", "T")
def mtext(ctx):
    h = float(ctx.header("$TEXTSIZE", 2.5))
    a = yield GetPoint("İlk köşeyi belirtin")
    b = yield GetPoint("Karşı köşeyi belirtin", base=a, rubber=False,
                       preview=lambda p: [("rect", a, p)])
    content, h, style = ctx.main.ask_mtext("", h)
    if not content:
        return
    ctx.set_header("$TEXTSIZE", h)
    x0, x1 = sorted((a.x, b.x))
    y1 = max(a.y, b.y)
    e = ctx.msp.add_mtext(content.replace("\n", "\\P"),
                          dxfattribs=ctx.attribs(char_height=h, width=x1 - x0, style=style or text_style(ctx)))
    e.set_location((x0, y1), attachment_point=1)
    ctx.created(e)


@command("TEXTEDIT", "ED", "DDEDIT")
def textedit(ctx):
    from t2dcad.engine import GetEntity
    while True:
        r = yield GetEntity("Düzenlenecek yazıyı seçin", types=("TEXT", "MTEXT", "ATTDEF"), allow_none=True)
        if r is None:
            return
        ctx.main.edit_text(ctx.tab, r[0])


# ---------------------------------------------------------------- REVCLOUD (simple)
@command("DONUT", "DO")
def donut(ctx):
    di = yield GetDistance("Halkanın iç çapı", default=ctx.get("donut_in", 0.5))
    do = yield GetDistance("Halkanın dış çapı", default=ctx.get("donut_out", 1.0))
    ctx.set("donut_in", di)
    ctx.set("donut_out", do)
    w = (do - di) / 2
    r = (do + di) / 4
    while True:
        c = yield GetPoint("Halkanın merkezi", allow_none=True,
                           preview=lambda p: [("circle", p, do / 2), ("circle", p, di / 2)])
        if c is None:
            return
        pts = [(c.x - r, c.y, 1.0), (c.x + r, c.y, 1.0)]
        e = ctx.msp.add_lwpolyline(pts, format="xyb", close=True,
                                   dxfattribs=ctx.attribs(const_width=w))
        ctx.created(e)
