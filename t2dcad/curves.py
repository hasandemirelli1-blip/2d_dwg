"""Parametric view of curve entities (LINE, ARC, CIRCLE, LWPOLYLINE) used by
TRIM, EXTEND, BREAK, OFFSET, FILLET and JOIN."""
from __future__ import annotations

import math
from typing import Optional

from ezdxf.math import Vec2, Vec3

from t2dcad import geom
from t2dcad.geom import Seg, Arc, TAU

CURVE_TYPES = ("LINE", "ARC", "CIRCLE", "LWPOLYLINE")
BREAK_TYPES = ("LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "ELLIPSE")


def common_attribs(e) -> dict:
    out = {}
    for name in ("layer", "color", "linetype", "lineweight", "ltscale", "true_color", "transparency"):
        if e.dxf.hasattr(name):
            out[name] = e.dxf.get(name)
    return out


class Curve:
    """Curve with parameter s in [0, n]; prim i covers [i, i+1]."""

    def __init__(self, e):
        self.e = e
        self.type = e.dxftype()
        self.periodic = False
        if self.type in ("LWPOLYLINE", "POLYLINE"):
            self.type = "LWPOLYLINE"  # 2D POLYLINE pieces become LWPOLYLINEs
            self.verts = geom.lwpoly_points(e)
            self.closed = bool(e.closed if e.dxftype() == "LWPOLYLINE" else e.is_closed)
            self.periodic = self.closed
            n = len(self.verts)
            self.prims = []
            seg_count = n if self.closed else n - 1
            for i in range(seg_count):
                p1, b = self.verts[i]
                p2 = self.verts[(i + 1) % n][0]
                self.prims.append(geom.bulge_prim(p1, p2, b))
        else:
            self.prims = geom.entity_prims(e)
            self.periodic = self.type == "CIRCLE"
        self.n = len(self.prims)

    # ------------------------------------------------------------ params
    def point(self, s: float) -> Vec2:
        if self.periodic:
            s = s % self.n
        i = min(int(s), self.n - 1)
        return self.prims[i].point(s - i)

    def param(self, p: Vec2) -> float:
        best, best_s = float("inf"), 0.0
        for i, prim in enumerate(self.prims):
            q = prim.nearest(p)
            d = q.distance(p)
            if d < best:
                best = d
                t = prim.param(q)
                if isinstance(prim, Arc) and prim.full:
                    t = t % 1.0
                best_s = i + min(1.0, max(0.0, t))
        return best_s

    def intersection_params(self, cutters: list, self_cut=False) -> list[float]:
        out = []
        for i, prim in enumerate(self.prims):
            for c in cutters:
                for p in geom.intersect(prim, c):
                    t = prim.param(p)
                    if isinstance(prim, Arc):
                        t = t % 1.0 if prim.full else t
                    out.append(i + min(1.0, max(0.0, t)))
        out.sort()
        # unique
        res = []
        for s in out:
            if not res or abs(s - res[-1]) > 1e-9:
                res.append(s)
        return res

    # ------------------------------------------------------------ pieces
    def piece(self, msp, s0: float, s1: float, attribs: dict):
        """Create a new entity covering [s0, s1] (s1 may exceed n for periodic
        curves). Returns the new entity or None."""
        if s1 - s0 < 1e-9:
            return None
        if self.type == "LINE":
            a, b = self.point(s0), self.point(s1)
            if a.isclose(b):
                return None
            return msp.add_line(a, b, dxfattribs=attribs)
        if self.type in ("ARC", "CIRCLE"):
            arc = self.prims[0]
            a0 = arc.a0 + arc.span * s0
            a1 = arc.a0 + arc.span * s1
            if abs(a1 - a0) >= TAU - 1e-9:
                return msp.add_circle(arc.c, arc.r, dxfattribs=attribs)
            return msp.add_arc(arc.c, arc.r, math.degrees(a0), math.degrees(a1), dxfattribs=attribs)
        # LWPOLYLINE
        pts = self.sub_vertices(s0, s1)
        if len(pts) < 2:
            return None
        a = dict(attribs)
        for name in (("const_width", "elevation", "extrusion") if self.e.dxftype() == "LWPOLYLINE" else ()):
            if self.e.dxf.hasattr(name):
                a[name] = self.e.dxf.get(name)
        return msp.add_lwpolyline([(p.x, p.y, b) for p, b in pts], format="xyb", dxfattribs=a)

    def sub_vertices(self, s0: float, s1: float) -> list[tuple[Vec2, float]]:
        out: list[tuple[Vec2, float]] = []
        s = s0
        while s < s1 - 1e-9:
            i = int(math.floor(s + 1e-12))
            seg_end = min(float(i + 1), s1)
            idx = i % self.n
            p1, b = self.verts[idx]
            t0 = s - i
            t1 = seg_end - i
            out.append((self.point(s), geom.sub_bulge(b, t0, t1)))
            s = seg_end
        out.append((self.point(s1), 0.0))
        # remove duplicates
        res = []
        for p, b in out:
            if res and res[-1][0].isclose(p, abs_tol=1e-9):
                res[-1] = (res[-1][0], b if b else res[-1][1])
                continue
            res.append((p, b))
        return res


def to_vertices(e) -> Optional[list[tuple[Vec2, float]]]:
    """Vertex/bulge list of an open curve (for JOIN)."""
    t = e.dxftype()
    if t == "LINE":
        return [(Vec2(e.dxf.start), 0.0), (Vec2(e.dxf.end), 0.0)]
    if t == "ARC":
        arc = geom.entity_prims(e)[0]
        return [(arc.start, math.tan(arc.span / 4)), (arc.end, 0.0)]
    if t == "LWPOLYLINE" and not e.closed:
        return [(p, b) for p, b in geom.lwpoly_points(e)]
    return None


def reverse_vertices(vs):
    n = len(vs)
    out = []
    for k in range(n - 1, -1, -1):
        p = vs[k][0]
        b = -vs[k - 1][1] if k > 0 else 0.0
        out.append((p, b))
    return out


# ---------------------------------------------------------------- offset
def _left_normal(d: Vec2) -> Vec2:
    return Vec2(-d.y, d.x)


def offset_vertices(verts: list[tuple[Vec2, float]], closed: bool, dist: float):
    """Offset a polyline to the left by `dist` (negative = right).
    Returns new vertex list or None."""
    n = len(verts)
    nseg = n if closed else n - 1
    segs = []  # (p1, p2, bulge, center or None)
    for i in range(nseg):
        p1, b = verts[i]
        p2 = verts[(i + 1) % n][0]
        if p1.isclose(p2):
            continue
        if abs(b) < 1e-12:
            nrm = _left_normal((p2 - p1).normalize()) * dist
            segs.append([p1 + nrm, p2 + nrm, 0.0, None])
        else:
            arc = geom.bulge_prim(p1, p2, b)
            c, r = arc.c, arc.r
            r2 = r - dist if b > 0 else r + dist
            if r2 <= 1e-9:
                continue
            q1 = c + (p1 - c).normalize() * r2
            q2 = c + (p2 - c).normalize() * r2
            segs.append([q1, q2, b, (c, r2)])
    if not segs:
        return None

    def as_prim(sg, ext=True):
        if sg[3] is None:
            return Seg(sg[0], sg[1])
        c, r = sg[3]
        return Arc(c, r, 0, TAU, full=True)

    def fix_bulge(sg):
        if sg[3] is None:
            return
        c, r = sg[3]
        a0 = (sg[0] - c).angle
        a1 = (sg[1] - c).angle
        if sg[2] > 0:
            span = geom.norm_angle(a1 - a0)
        else:
            span = -geom.norm_angle(a0 - a1)
        sg[2] = math.tan(span / 4)

    out_pts: list[list] = []
    m = len(segs)
    joints = range(m) if closed else range(m - 1)
    for k in joints:
        s1 = segs[k]
        s2 = segs[(k + 1) % m]
        if s1[1].isclose(s2[0], abs_tol=1e-7):
            continue
        cands = geom.intersect(as_prim(s1), as_prim(s2), True, True)
        if cands:
            ref = s1[1].lerp(s2[0])
            p = min(cands, key=lambda q: q.distance(ref))
            if p.distance(ref) < 10 * abs(dist) + 1e-6:
                s1[1] = p
                s2[0] = p
                continue
        # gap: connect with a straight segment
        s1.append("gap")
    result: list[tuple[Vec2, float]] = []
    for k, sg in enumerate(segs):
        fix_bulge(sg)
        if not result or not result[-1][0].isclose(sg[0], abs_tol=1e-7):
            result.append((sg[0], sg[2]))
        else:
            result[-1] = (result[-1][0], sg[2])
        result.append((sg[1], 0.0))
    if closed and len(result) > 1 and result[0][0].isclose(result[-1][0], abs_tol=1e-7):
        result.pop()
    return result


def side_of(verts, closed, p: Vec2) -> float:
    """+1 if p is left of the polyline direction, -1 if right."""
    prims = geom.polyline_prims(verts, closed)
    best, side = float("inf"), 1.0
    n = len(verts)
    for i, prim in enumerate(prims):
        q = prim.nearest(p)
        d = q.distance(p)
        if d < best:
            best = d
            if isinstance(prim, Seg):
                dirv = prim.b - prim.a
                cr = dirv.x * (p.y - prim.a.y) - dirv.y * (p.x - prim.a.x)
                side = 1.0 if cr > 0 else -1.0
            else:
                b = verts[i][1]
                inside = p.distance(prim.c) < prim.r
                ccw = b > 0
                side = 1.0 if inside == ccw else -1.0
    return side
