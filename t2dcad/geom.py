"""2D geometry helpers: primitives (segments/arcs) of DXF entities,
intersections, nearest points and snap point extraction."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional

from ezdxf.math import Vec2, bulge_to_arc, arc_to_bulge

TAU = math.tau
EPS = 1e-9
XLINE_LEN = 1e7


def norm_angle(a: float) -> float:
    a = math.fmod(a, TAU)
    return a + TAU if a < 0 else a


def angle_in_arc(a: float, a0: float, a1: float, tol: float = 1e-9) -> bool:
    """True if angle `a` lies on the CCW arc from a0 to a1."""
    span = norm_angle(a1 - a0)
    if span < tol:
        span = TAU
    return norm_angle(a - a0) <= span + tol


@dataclass
class Seg:
    a: Vec2
    b: Vec2

    def length(self) -> float:
        return self.a.distance(self.b)

    def point(self, t: float) -> Vec2:
        return self.a + (self.b - self.a) * t

    def param(self, p: Vec2) -> float:
        d = self.b - self.a
        l2 = d.dot(d)
        if l2 < EPS:
            return 0.0
        return (p - self.a).dot(d) / l2

    def nearest(self, p: Vec2, infinite=False) -> Vec2:
        t = self.param(p)
        if not infinite:
            t = min(1.0, max(0.0, t))
        return self.point(t)


@dataclass
class Arc:
    c: Vec2
    r: float
    a0: float  # start angle in radians
    a1: float  # end angle in radians (CCW)
    full: bool = False

    @property
    def span(self) -> float:
        if self.full:
            return TAU
        s = norm_angle(self.a1 - self.a0)
        return s if s > EPS else TAU

    def point_at(self, a: float) -> Vec2:
        return self.c + Vec2.from_angle(a, self.r)

    @property
    def start(self) -> Vec2:
        return self.point_at(self.a0)

    @property
    def end(self) -> Vec2:
        return self.point_at(self.a0 + self.span)

    def contains_angle(self, a: float) -> bool:
        return self.full or angle_in_arc(a, self.a0, self.a1)

    def param(self, p: Vec2) -> float:
        """Fraction 0..1 along the arc (CCW)."""
        a = (p - self.c).angle
        return norm_angle(a - self.a0) / self.span

    def point(self, t: float) -> Vec2:
        return self.point_at(self.a0 + self.span * t)

    def nearest(self, p: Vec2, infinite=False) -> Vec2:
        d = p - self.c
        if d.magnitude < EPS:
            return self.start
        a = d.angle
        if infinite or self.contains_angle(a):
            return self.point_at(a)
        s, e = self.start, self.end
        return s if s.distance(p) < e.distance(p) else e

    def length(self) -> float:
        return self.r * self.span


Prim = Seg | Arc


# ---------------------------------------------------------------- intersections
def _line_line(a: Seg, b: Seg, ext_a=False, ext_b=False) -> list[Vec2]:
    d1 = a.b - a.a
    d2 = b.b - b.a
    den = d1.x * d2.y - d1.y * d2.x
    if abs(den) < EPS * max(1.0, d1.magnitude * d2.magnitude):
        return []
    w = b.a - a.a
    t = (w.x * d2.y - w.y * d2.x) / den
    u = (w.x * d1.y - w.y * d1.x) / den
    tol = 1e-9
    if not ext_a and not (-tol <= t <= 1 + tol):
        return []
    if not ext_b and not (-tol <= u <= 1 + tol):
        return []
    return [a.point(t)]


def _line_circle(s: Seg, arc: Arc, ext_s=False, ext_arc=False) -> list[Vec2]:
    d = s.b - s.a
    f = s.a - arc.c
    A = d.dot(d)
    if A < EPS:
        return []
    B = 2 * f.dot(d)
    C = f.dot(f) - arc.r * arc.r
    disc = B * B - 4 * A * C
    if disc < -1e-9 * max(1.0, B * B):
        return []
    disc = max(disc, 0.0)
    sq = math.sqrt(disc)
    ts = {(-B - sq) / (2 * A), (-B + sq) / (2 * A)}
    out = []
    for t in ts:
        if not ext_s and not (-1e-9 <= t <= 1 + 1e-9):
            continue
        p = s.point(t)
        if ext_arc or arc.contains_angle((p - arc.c).angle):
            out.append(p)
    return out


def _circle_circle(a: Arc, b: Arc, ext_a=False, ext_b=False) -> list[Vec2]:
    d = a.c.distance(b.c)
    if d < EPS or d > a.r + b.r + 1e-9 or d < abs(a.r - b.r) - 1e-9:
        return []
    x = (d * d + a.r * a.r - b.r * b.r) / (2 * d)
    h2 = a.r * a.r - x * x
    h = math.sqrt(max(h2, 0.0))
    u = (b.c - a.c) / d
    base = a.c + u * x
    pts = [base + u.orthogonal() * h]
    if h > 1e-9:
        pts.append(base - u.orthogonal() * h)
    out = []
    for p in pts:
        if (ext_a or a.contains_angle((p - a.c).angle)) and (
            ext_b or b.contains_angle((p - b.c).angle)
        ):
            out.append(p)
    return out


def intersect(p: Prim, q: Prim, ext_p=False, ext_q=False) -> list[Vec2]:
    if isinstance(p, Seg):
        if isinstance(q, Seg):
            return _line_line(p, q, ext_p, ext_q)
        return _line_circle(p, q, ext_p, ext_q)
    if isinstance(q, Seg):
        return _line_circle(q, p, ext_q, ext_p)
    return _circle_circle(p, q, ext_p, ext_q)


def prim_bbox(p: Prim) -> tuple[float, float, float, float]:
    if isinstance(p, Seg):
        return (min(p.a.x, p.b.x), min(p.a.y, p.b.y), max(p.a.x, p.b.x), max(p.a.y, p.b.y))
    pts = [p.start, p.end]
    for k in range(4):
        a = k * math.pi / 2
        if p.contains_angle(a):
            pts.append(p.point_at(a))
    xs = [v.x for v in pts]
    ys = [v.y for v in pts]
    return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------- entity -> prims
def bulge_prim(p1: Vec2, p2: Vec2, bulge: float) -> Prim:
    if abs(bulge) < 1e-12 or p1.isclose(p2):
        return Seg(p1, p2)
    c, sa, ea, r = bulge_to_arc(p1, p2, bulge)
    return Arc(Vec2(c), r, sa, ea)


def lwpoly_points(e) -> list[tuple[Vec2, float]]:
    """(vertex, bulge) in WCS for 2D polylines (LWPOLYLINE / POLYLINE 2D)."""
    t = e.dxftype()
    if t == "LWPOLYLINE":
        ocs = e.ocs()
        elev = e.dxf.elevation
        out = []
        for x, y, s, en, b in e.get_points("xyseb"):
            p = Vec2(ocs.to_wcs((x, y, elev))) if ocs.transform else Vec2(x, y)
            out.append((p, b))
        if ocs.transform and ocs.uz.z < 0:
            out = [(p, -b) for p, b in out]
        return out
    out = []
    for v in e.vertices:
        out.append((Vec2(v.dxf.location), v.dxf.get("bulge", 0.0)))
    return out


def polyline_prims(pts: list[tuple[Vec2, float]], closed: bool) -> list[Prim]:
    prims = []
    n = len(pts)
    if n < 2:
        return prims
    last = n if closed else n - 1
    for i in range(last):
        p1, b = pts[i]
        p2 = pts[(i + 1) % n][0]
        if p1.isclose(p2):
            continue
        prims.append(bulge_prim(p1, p2, b))
    return prims


def entity_prims(e, depth=0) -> list[Prim]:
    """Decompose an entity into 2D primitives (WCS, xy-plane)."""
    t = e.dxftype()
    try:
        if t == "LINE":
            return [Seg(Vec2(e.dxf.start), Vec2(e.dxf.end))]
        if t == "CIRCLE":
            return [Arc(Vec2(e.dxf.center), e.dxf.radius, 0.0, TAU, full=True)]
        if t == "ARC":
            return [Arc(Vec2(e.dxf.center), e.dxf.radius,
                        math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle))]
        if t == "LWPOLYLINE":
            return polyline_prims(lwpoly_points(e), e.closed)
        if t == "POLYLINE":
            if e.is_2d_polyline:
                return polyline_prims(lwpoly_points(e), e.is_closed)
            pts = [Vec2(v.dxf.location) for v in e.vertices]
            segs = [Seg(a, b) for a, b in zip(pts, pts[1:])]
            if e.is_closed and len(pts) > 2:
                segs.append(Seg(pts[-1], pts[0]))
            return segs
        if t in ("ELLIPSE", "SPLINE"):
            pts = [Vec2(p) for p in e.flattening(0.01)]
            return [Seg(a, b) for a, b in zip(pts, pts[1:]) if not a.isclose(b)]
        if t == "XLINE":
            s = Vec2(e.dxf.start)
            d = Vec2(e.dxf.unit_vector).normalize()
            return [Seg(s - d * XLINE_LEN, s + d * XLINE_LEN)]
        if t == "RAY":
            s = Vec2(e.dxf.start)
            d = Vec2(e.dxf.unit_vector).normalize()
            return [Seg(s, s + d * XLINE_LEN)]
        if t in ("SOLID", "TRACE", "3DFACE"):
            vs = [Vec2(v) for v in e.wcs_vertices()]
            return [Seg(a, b) for a, b in zip(vs, vs[1:] + vs[:1]) if not a.isclose(b)]
        if t in ("IMAGE", "WIPEOUT"):
            vs = [Vec2(v) for v in e.boundary_path_wcs()]
            return [Seg(a, b) for a, b in zip(vs, vs[1:] + vs[:1]) if not a.isclose(b)]
        if t in ("INSERT", "DIMENSION", "ARC_DIMENSION", "LEADER") and depth < 4:
            out = []
            for v in e.virtual_entities():
                out.extend(entity_prims(v, depth + 1))
            return out
    except Exception:
        return []
    return []


# ---------------------------------------------------------------- snap points
END, MID, CEN, QUA, INT, PER, NEA, NOD, INS, TAN, EXT, APP = (
    "end", "mid", "cen", "qua", "int", "per", "nea", "nod", "ins", "tan", "ext", "app")

SNAP_NAMES = {
    END: "Uç nokta (Endpoint)", MID: "Orta nokta (Midpoint)", CEN: "Merkez (Center)",
    QUA: "Çeyrek (Quadrant)", INT: "Kesişim (Intersection)", PER: "Dik (Perpendicular)",
    NEA: "En yakın (Nearest)", NOD: "Nokta (Node)", INS: "Yerleşim (Insertion)",
    TAN: "Teğet (Tangent)",
}


def entity_snap_points(e, depth=0) -> list[tuple[str, Vec2]]:
    t = e.dxftype()
    out: list[tuple[str, Vec2]] = []
    try:
        if t == "LINE":
            s, en = Vec2(e.dxf.start), Vec2(e.dxf.end)
            out += [(END, s), (END, en), (MID, s.lerp(en))]
        elif t in ("CIRCLE", "ARC", "LWPOLYLINE", "POLYLINE"):
            prims = entity_prims(e)
            for p in prims:
                if isinstance(p, Seg):
                    out += [(END, p.a), (END, p.b), (MID, p.point(0.5))]
                else:
                    out.append((CEN, p.c))
                    if not p.full:
                        out += [(END, p.start), (END, p.end), (MID, p.point(0.5))]
                    for k in range(4):
                        a = k * math.pi / 2
                        if p.contains_angle(a):
                            out.append((QUA, p.point_at(a)))
        elif t == "ELLIPSE":
            c = Vec2(e.dxf.center)
            out.append((CEN, c))
            for v in e.vertices([0, math.pi / 2, math.pi, 1.5 * math.pi]):
                out.append((QUA, Vec2(v)))
            if not math.isclose(abs(e.dxf.end_param - e.dxf.start_param), TAU):
                out += [(END, Vec2(e.start_point)), (END, Vec2(e.end_point))]
        elif t == "SPLINE":
            pts = [Vec2(p) for p in e.flattening(0.05)]
            if pts:
                out += [(END, pts[0]), (END, pts[-1])]
        elif t == "POINT":
            out.append((NOD, Vec2(e.dxf.location)))
        elif t in ("TEXT", "MTEXT", "ATTDEF", "ATTRIB"):
            out.append((INS, Vec2(e.dxf.insert)))
            if t == "TEXT" and (e.dxf.get("halign", 0) or e.dxf.get("valign", 0)):
                if e.dxf.hasattr("align_point"):
                    out.append((INS, Vec2(e.dxf.align_point)))
        elif t in ("SOLID", "TRACE", "3DFACE"):
            for v in e.wcs_vertices():
                out.append((END, Vec2(v)))
        elif t == "INSERT":
            out.append((INS, Vec2(e.dxf.insert)))
            if depth < 3:
                for v in e.virtual_entities():
                    out.extend(entity_snap_points(v, depth + 1))
        elif t in ("DIMENSION", "LEADER") and depth < 3:
            for v in e.virtual_entities():
                if v.dxftype() in ("LINE", "POINT"):
                    out.extend(entity_snap_points(v, depth + 1))
            if t == "DIMENSION":
                for name in ("defpoint", "defpoint2", "defpoint3"):
                    if e.dxf.hasattr(name):
                        out.append((NOD, Vec2(e.dxf.get(name))))
        elif t in ("IMAGE", "WIPEOUT"):
            vs = [Vec2(v) for v in e.boundary_path_wcs()]
            for a, b in zip(vs, vs[1:] + vs[:1]):
                out += [(END, a), (MID, a.lerp(b))]
            out.append((INS, Vec2(e.dxf.insert)))
        elif t == "XLINE" or t == "RAY":
            out.append((END, Vec2(e.dxf.start)))
        elif t == "HATCH":
            for path in e.paths:
                if hasattr(path, "vertices"):
                    for v in path.vertices:
                        out.append((END, Vec2(v[0], v[1])))
    except Exception:
        pass
    return out


def tangent_points(p: Vec2, arc: Arc) -> list[Vec2]:
    d = p.distance(arc.c)
    if d <= arc.r + EPS:
        return []
    a = (p - arc.c).angle
    beta = math.acos(arc.r / d)
    out = []
    for s in (1, -1):
        ang = a + s * beta
        if arc.contains_angle(ang):
            out.append(arc.point_at(ang))
    return out


# ---------------------------------------------------------------- misc helpers
def polar(p: Vec2, angle_rad: float, dist: float) -> Vec2:
    return p + Vec2.from_angle(angle_rad, dist)


def circle_3p(p1: Vec2, p2: Vec2, p3: Vec2) -> Optional[tuple[Vec2, float]]:
    ax, ay = p1.x, p1.y
    bx, by = p2.x, p2.y
    cx, cy = p3.x, p3.y
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < EPS:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    c = Vec2(ux, uy)
    return c, c.distance(p1)


def arc_3p(p1: Vec2, p2: Vec2, p3: Vec2) -> Optional[Arc]:
    res = circle_3p(p1, p2, p3)
    if res is None:
        return None
    c, r = res
    a1 = (p1 - c).angle
    a2 = (p2 - c).angle
    a3 = (p3 - c).angle
    # CCW from p1 to p3 must pass p2, otherwise reverse
    if angle_in_arc(a2, a1, a3):
        return Arc(c, r, a1, a3)
    return Arc(c, r, a3, a1)


def polygon_area(pts: list[Vec2]) -> float:
    s = 0.0
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        s += a.x * b.y - b.x * a.y
    return s / 2.0


def prims_length(prims: Iterable[Prim]) -> float:
    return sum(p.length() for p in prims)


def flatten_prims(prims: list[Prim], seg_angle=math.radians(5)) -> list[Vec2]:
    """Chain of points along the primitives (assumes connected order)."""
    pts: list[Vec2] = []
    for p in prims:
        if isinstance(p, Seg):
            seq = [p.a, p.b]
        else:
            n = max(2, int(p.span / seg_angle) + 1)
            seq = [p.point(i / (n - 1)) for i in range(n)]
        if pts and pts[-1].isclose(seq[0], abs_tol=1e-6):
            seq = seq[1:]
        pts.extend(seq)
    return pts


def sub_bulge(bulge: float, t0: float, t1: float) -> float:
    """Bulge of the part [t0, t1] of an arc segment with `bulge`."""
    if abs(bulge) < 1e-12:
        return 0.0
    theta = 4 * math.atan(bulge)
    return math.tan(theta * (t1 - t0) / 4)


__all__ = [
    "Seg", "Arc", "Prim", "intersect", "entity_prims", "entity_snap_points",
    "arc_to_bulge", "Vec2",
]
