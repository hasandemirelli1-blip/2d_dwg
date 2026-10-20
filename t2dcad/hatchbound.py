"""Boundary detection for HATCH 'pick internal point'.

Walks the face which contains the picked point through the planar graph
formed by all curves near the point (always turning as far left as possible,
so the face stays on the left side)."""
from __future__ import annotations

import math
from typing import Optional

from ezdxf.math import Vec2

from t2dcad import geom
from t2dcad.geom import Seg, Arc, TAU


class _P:
    """Prim wrapper with id, bbox and cached intersections."""
    __slots__ = ("prim", "bbox", "cuts", "idx")

    def __init__(self, prim, idx):
        self.prim = prim
        self.idx = idx
        self.bbox = geom.prim_bbox(prim)
        self.cuts: Optional[list[float]] = None


def _tangent(prim, t: float) -> Vec2:
    if isinstance(prim, Seg):
        return (prim.b - prim.a).normalize()
    a = prim.a0 + prim.span * t
    return Vec2.from_angle(a + math.pi / 2)


def _param(prim, p: Vec2) -> float:
    t = prim.param(p)
    if isinstance(prim, Arc) and prim.full:
        t %= 1.0
    return t


class Boundary:
    def __init__(self, prims: list, tol: float):
        self.ps = [_P(p, i) for i, p in enumerate(prims)]
        self.tol = tol
        # simple grid index
        xs = [p.bbox[0] for p in self.ps] + [p.bbox[2] for p in self.ps]
        ys = [p.bbox[1] for p in self.ps] + [p.bbox[3] for p in self.ps]
        if not xs:
            self.cell = 1.0
            self.grid = {}
            return
        w = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
        self.cell = w / max(4, int(math.sqrt(len(self.ps)) * 2))
        self.grid: dict[tuple[int, int], list[_P]] = {}
        for p in self.ps:
            for key in self._cells(p.bbox):
                self.grid.setdefault(key, []).append(p)

    def _cells(self, bbox):
        c = self.cell
        i0, j0 = int(math.floor(bbox[0] / c)), int(math.floor(bbox[1] / c))
        i1, j1 = int(math.floor(bbox[2] / c)), int(math.floor(bbox[3] / c))
        if (i1 - i0 + 1) * (j1 - j0 + 1) > 4000:
            # huge primitive (xline...) - put into the coarse list
            return [("big", 0)]
        return [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]

    def near(self, bbox) -> set:
        out = set()
        for key in self._cells(bbox):
            out.update(self.grid.get(key, ()))
        out.update(self.grid.get(("big", 0), ()))
        return out

    def cuts(self, p: _P) -> list[float]:
        if p.cuts is None:
            ts = {0.0, 1.0} if not (isinstance(p.prim, Arc) and p.prim.full) else {0.0}
            b = p.bbox
            grown = (b[0] - self.tol, b[1] - self.tol, b[2] + self.tol, b[3] + self.tol)
            for q in self.near(grown):
                if q is p:
                    continue
                qb = q.bbox
                if qb[2] < grown[0] or qb[0] > grown[2] or qb[3] < grown[1] or qb[1] > grown[3]:
                    continue
                for pt in geom.intersect(p.prim, q.prim):
                    ts.add(_param(p.prim, pt))
                # touching endpoints (T-junctions within tolerance)
                for pt in _endpoints(q.prim):
                    n = p.prim.nearest(pt)
                    if n.distance(pt) <= self.tol:
                        ts.add(_param(p.prim, n))
            p.cuts = sorted(ts)
        return p.cuts

    def nodes_at(self, pt: Vec2) -> list[tuple[_P, float]]:
        """All (prim, param) passing through pt."""
        out = []
        tol = self.tol
        for q in self.near((pt.x - tol, pt.y - tol, pt.x + tol, pt.y + tol)):
            b = q.bbox
            if b[2] < pt.x - tol or b[0] > pt.x + tol or b[3] < pt.y - tol or b[1] > pt.y + tol:
                continue
            n = q.prim.nearest(pt)
            if n.distance(pt) <= tol:
                out.append((q, _param(q.prim, n)))
        return out

    # ------------------------------------------------------------ ray cast
    def ray_hit(self, origin: Vec2, min_x: float) -> Optional[tuple[_P, float, Vec2]]:
        far = Vec2(origin.x + 1e9, origin.y)
        ray = Seg(origin, far)
        best = None
        for p in self.ps:
            b = p.bbox
            if b[2] < min_x or b[1] > origin.y + self.tol or b[3] < origin.y - self.tol:
                continue
            for pt in geom.intersect(ray, p.prim):
                if pt.x <= min_x + 1e-12:
                    continue
                if best is None or pt.x < best[2].x:
                    best = (p, _param(p.prim, pt), pt)
        return best

    # ------------------------------------------------------------ walking
    def walk(self, start_p: _P, start_t: float, direction: int, max_steps=20000):
        """Walk along prims keeping the face on the left. Returns list of
        pieces (prim, t0, t1) or None."""
        pieces = []
        cur, t, dirn = start_p, start_t, direction
        start_pt = cur.prim.point(start_t)
        for _ in range(max_steps):
            cuts = self.cuts(cur)
            full = isinstance(cur.prim, Arc) and cur.prim.full
            if dirn > 0:
                nxt = [c for c in cuts if c > t + 1e-9]
                t_next = nxt[0] if nxt else (cuts[0] + 1.0 if full else None)
            else:
                nxt = [c for c in cuts if c < t - 1e-9]
                t_next = nxt[-1] if nxt else (cuts[-1] - 1.0 if full and cuts else None)
            if t_next is None:
                return None
            # does the start point lie on this piece?
            if pieces and cur is start_p:
                lo, hi = (t, t_next) if dirn > 0 else (t_next, t)
                st = start_t
                if full:
                    while st < lo - 1e-12:
                        st += 1.0
                    while st > hi + 1e-12:
                        st -= 1.0
                if lo - 1e-9 <= st <= hi + 1e-9:
                    pieces.append((cur.prim, t, st))
                    return pieces
            pieces.append((cur.prim, t, t_next))
            node_t = t_next % 1.0 if full else t_next
            node = cur.prim.point(node_t)
            if node.distance(start_pt) <= self.tol and pieces and len(pieces) > 1 and cur is not start_p:
                pass
            d_in = _tangent(cur.prim, node_t) * dirn
            best = None
            for q, qt in self.nodes_at(node):
                qfull = isinstance(q.prim, Arc) and q.prim.full
                for dq in (1, -1):
                    if not qfull:
                        if dq > 0 and qt >= 1.0 - 1e-9:
                            continue
                        if dq < 0 and qt <= 1e-9:
                            continue
                    if q is cur and dq == -dirn:
                        continue  # going back
                    d_out = _tangent(q.prim, qt) * dq
                    turn = math.atan2(d_in.x * d_out.y - d_in.y * d_out.x, d_in.dot(d_out))
                    # curvature tie-break for tangent arcs
                    key = turn
                    if best is None or key > best[0] + 1e-12:
                        best = (key, q, qt, dq)
            if best is None:
                return None
            _, cur, t, dirn = best
            if cur is start_p and dirn == direction:
                # back on the start prim: check whether we pass the start
                pass
        return None


def _endpoints(prim):
    if isinstance(prim, Seg):
        return (prim.a, prim.b)
    if prim.full:
        return ()
    return (prim.start, prim.end)


def pieces_to_vertices(pieces) -> list[tuple[Vec2, float]]:
    verts = []
    for prim, t0, t1 in pieces:
        if abs(t1 - t0) < 1e-12:
            continue
        p0 = prim.point(t0 % 1.0 if isinstance(prim, Arc) and prim.full else t0)
        if isinstance(prim, Seg):
            b = 0.0
        else:
            ang = prim.span * (t1 - t0)
            b = math.tan(ang / 4)
        verts.append((p0, b))
    # drop vertices between collinear straight segments (e.g. the start point)
    changed = True
    while changed and len(verts) > 3:
        changed = False
        n = len(verts)
        for i in range(n):
            pv, bv = verts[i - 1]
            pc, bc = verts[i]
            pn = verts[(i + 1) % n][0]
            if abs(bv) < 1e-12 and abs(bc) < 1e-12:
                d1, d2 = pc - pv, pn - pc
                if d1.magnitude > 0 and d2.magnitude > 0 and \
                        abs(d1.x * d2.y - d1.y * d2.x) <= 1e-9 * d1.magnitude * d2.magnitude and d1.dot(d2) > 0:
                    verts.pop(i)
                    changed = True
                    break
    return verts


def point_in_vertices(p: Vec2, verts) -> bool:
    pts = geom.flatten_prims(geom.polyline_prims(verts, True))
    inside = False
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if (a.y > p.y) != (b.y > p.y):
            x = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y)
            if x > p.x:
                inside = not inside
    return inside


def find_boundary(prims: list, point: Vec2, tol: float):
    """Returns (outer vertices, [island vertices]) or None."""
    bd = Boundary(prims, tol)
    min_x = point.x
    islands = []
    for _ in range(50):
        hit = bd.ray_hit(point, min_x)
        if hit is None:
            return None
        p, t, pt = hit
        tan = _tangent(p.prim, t % 1.0 if isinstance(p.prim, Arc) and p.prim.full else t)
        v = point - pt
        cr = tan.x * v.y - tan.y * v.x
        direction = 1 if cr > 0 else -1
        pieces = bd.walk(p, t, direction)
        if pieces:
            verts = pieces_to_vertices(pieces)
            if len(verts) >= 2:
                if point_in_vertices(point, verts):
                    return verts, islands
                islands.append(verts)
                xs = [v[0].x for v in verts]
                min_x = max(xs) + tol
                continue
        min_x = pt.x + tol
    return None
