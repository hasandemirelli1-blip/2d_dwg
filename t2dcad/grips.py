"""Grip points of entities and grip editing (stretch)."""
from __future__ import annotations

import math
from typing import Optional

from ezdxf.math import Vec2, Vec3, Matrix44

from t2dcad import geom


def entity_grips(e) -> list[tuple[Vec2, object]]:
    t = e.dxftype()
    out = []
    try:
        if t == "LINE":
            s, en = Vec2(e.dxf.start), Vec2(e.dxf.end)
            out = [(s, "start"), (en, "end"), (s.lerp(en), "move")]
        elif t == "CIRCLE":
            c, r = Vec2(e.dxf.center), e.dxf.radius
            out = [(c, "move")] + [(c + Vec2.from_deg_angle(a, r), ("rad", a)) for a in (0, 90, 180, 270)]
        elif t == "ARC":
            arc = geom.entity_prims(e)[0]
            out = [(arc.c, "move"), (arc.start, "astart"), (arc.end, "aend"), (arc.point(0.5), "amid")]
        elif t == "LWPOLYLINE":
            pts = geom.lwpoly_points(e)
            n = len(pts)
            for i, (p, b) in enumerate(pts):
                out.append((p, ("v", i)))
            segs = n if e.closed else n - 1
            for i in range(segs):
                p1, b = pts[i]
                p2 = pts[(i + 1) % n][0]
                prim = geom.bulge_prim(p1, p2, b)
                mid = prim.point(0.5)
                out.append((mid, ("m", i)))
        elif t == "POLYLINE" and e.is_2d_polyline:
            for i, v in enumerate(e.vertices):
                out.append((Vec2(v.dxf.location), ("pv", i)))
        elif t in ("TEXT", "MTEXT", "INSERT", "ATTDEF"):
            out = [(Vec2(e.dxf.insert), "move")]
        elif t == "POINT":
            out = [(Vec2(e.dxf.location), "move")]
        elif t == "ELLIPSE":
            c = Vec2(e.dxf.center)
            out = [(c, "move")]
            for v in e.vertices([0, math.pi / 2, math.pi, 1.5 * math.pi]):
                out.append((Vec2(v), "none"))
        elif t == "SPLINE":
            pts = e.fit_points if len(e.fit_points) else e.control_points
            key = "fit" if len(e.fit_points) else "cp"
            out = [(Vec2(p), (key, i)) for i, p in enumerate(pts)]
        elif t == "DIMENSION":
            if e.dxf.hasattr("text_midpoint"):
                out.append((Vec2(e.dxf.text_midpoint), "dimtext"))
            for name in ("defpoint2", "defpoint3"):
                if e.dxf.hasattr(name):
                    out.append((Vec2(e.dxf.get(name)), ("dimdef", name)))
            if e.dxf.hasattr("defpoint"):
                out.append((Vec2(e.dxf.defpoint), ("dimdef", "defpoint")))
        elif t in ("XLINE", "RAY"):
            out = [(Vec2(e.dxf.start), "move")]
        elif t == "HATCH":
            pass
        elif t in ("SOLID", "TRACE"):
            out = [(Vec2(v), ("solid", i)) for i, v in enumerate(e.wcs_vertices())]
    except Exception:
        return []
    return out


def apply_grip(e, key, base: Vec2, p: Vec2) -> None:
    """Modify entity `e` (a copy) by moving grip `key` from base to p."""
    t = e.dxftype()
    d = p - base
    if key == "move":
        e.transform(Matrix44.translate(d.x, d.y, 0))
        return
    if key == "none":
        return
    if t == "LINE":
        if key == "start":
            e.dxf.start = Vec3(p.x, p.y, e.dxf.start.z)
        elif key == "end":
            e.dxf.end = Vec3(p.x, p.y, e.dxf.end.z)
    elif t == "CIRCLE" and isinstance(key, tuple):
        e.dxf.radius = max(1e-6, Vec2(e.dxf.center).distance(p))
    elif t == "ARC":
        arc = geom.entity_prims(e)[0]
        s, m, en = arc.start, arc.point(0.5), arc.end
        if key == "astart":
            s = p
        elif key == "aend":
            en = p
        elif key == "amid":
            m = p
        new = geom.arc_3p(s, m, en)
        if new is not None:
            e.dxf.center = Vec3(new.c.x, new.c.y, 0)
            e.dxf.radius = new.r
            e.dxf.start_angle = math.degrees(new.a0)
            e.dxf.end_angle = math.degrees(new.a1)
    elif t == "LWPOLYLINE" and isinstance(key, tuple):
        pts = list(e.get_points("xyseb"))
        n = len(pts)
        ocs = e.ocs()
        lp = Vec2(ocs.from_wcs(Vec3(p))) if ocs.transform else p
        lb = Vec2(ocs.from_wcs(Vec3(base))) if ocs.transform else base
        ld = lp - lb
        if key[0] == "v":
            i = key[1]
            x, y, s, en, b = pts[i]
            pts[i] = (lp.x, lp.y, s, en, b)
        elif key[0] == "m":
            i = key[1]
            for j in (i, (i + 1) % n):
                x, y, s, en, b = pts[j]
                pts[j] = (x + ld.x, y + ld.y, s, en, b)
        e.set_points(pts, format="xyseb")
    elif t == "POLYLINE" and isinstance(key, tuple) and key[0] == "pv":
        v = list(e.vertices)[key[1]]
        v.dxf.location = Vec3(p.x, p.y, v.dxf.location.z)
    elif t == "SPLINE" and isinstance(key, tuple):
        if key[0] == "fit":
            fp = [Vec3(v) for v in e.fit_points]
            fp[key[1]] = Vec3(p)
            e.fit_points = fp
            e.control_points = []
        else:
            cp = [Vec3(v) for v in e.control_points]
            cp[key[1]] = Vec3(p)
            e.control_points = cp
    elif t == "DIMENSION":
        if key == "dimtext":
            e.dxf.text_midpoint = Vec3(p)
            e.dxf.dimtype = e.dxf.dimtype | 128  # user defined text location
        elif isinstance(key, tuple) and key[0] == "dimdef":
            e.dxf.set(key[1], Vec3(p))
    elif t in ("SOLID", "TRACE") and isinstance(key, tuple):
        names = ["vtx0", "vtx1", "vtx2", "vtx3"]
        e.dxf.set(names[key[1]], Vec3(p))


def rerender_dimension(doc, dim) -> None:
    """Regenerate the geometry block of a bound DIMENSION entity."""
    try:
        from ezdxf.render.dimension import DimensionRenderer  # noqa: F401
        override = dim.override()
        override.render()
    except Exception as ex:  # keep old block
        print("dimension render failed:", ex)
