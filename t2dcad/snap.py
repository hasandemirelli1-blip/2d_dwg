"""Object snap (OSNAP) engine."""
from __future__ import annotations

import math
from typing import Optional

from ezdxf.math import Vec2

from t2dcad import geom
from t2dcad.geom import (END, MID, CEN, QUA, INT, PER, NEA, NOD, INS, TAN, Seg, Arc)

ALL_MODES = [END, MID, CEN, NOD, QUA, INT, INS, PER, TAN, NEA]
DEFAULT_MODES = {END, MID, CEN, INT, QUA, NOD, INS, PER}

OVERRIDE_WORDS = {
    "END": END, "ENDP": END, "MID": MID, "CEN": CEN, "QUA": QUA, "INT": INT,
    "PER": PER, "NEA": NEA, "NOD": NOD, "NODE": NOD, "INS": INS, "TAN": TAN,
    "NON": "none", "NONE": "none",
}

# lower value = higher priority when several snaps are equally close
PRIORITY = {END: 0, INT: 0, NOD: 0, INS: 1, MID: 1, CEN: 1, QUA: 1, PER: 2, TAN: 2, NEA: 5}


class SnapEngine:
    def __init__(self, cad_doc, renderer):
        self.cad_doc = cad_doc
        self.renderer = renderer
        self.modes: set[str] = set(DEFAULT_MODES)
        self.enabled = True
        self._pts: dict[str, list] = {}
        self._prims: dict[str, list] = {}

    def invalidate(self, handles=None):
        if handles is None:
            self._pts.clear()
            self._prims.clear()
        else:
            for h in handles:
                self._pts.pop(h, None)
                self._prims.pop(h, None)

    def snap_points(self, h: str, e) -> list:
        pts = self._pts.get(h)
        if pts is None:
            pts = geom.entity_snap_points(e)
            self._pts[h] = pts
        return pts

    def prims(self, h: str, e) -> list:
        ps = self._prims.get(h)
        if ps is None:
            ps = [(p, geom.prim_bbox(p)) for p in geom.entity_prims(e)]
            self._prims[h] = ps
        return ps

    def find(self, cursor: Vec2, aperture: float, base: Optional[Vec2] = None,
             override: Optional[set] = None, exclude: Optional[set] = None
             ) -> Optional[tuple[str, Vec2]]:
        modes = override if override is not None else (self.modes if self.enabled else set())
        if not modes:
            return None
        x, y = cursor.x, cursor.y
        handles = self.renderer.handles_in_rect(x - aperture, y - aperture, x + aperture, y + aperture)
        if exclude:
            handles -= exclude
        if not handles:
            return None
        best = None  # (prio_class, dist, kind, point)

        def consider(kind, p, d=None):
            nonlocal best
            if d is None:
                d = p.distance(cursor)
            if d > aperture:
                return
            key = (1 if kind == NEA else 0, d + PRIORITY.get(kind, 3) * aperture * 0.02)
            if best is None or key < best[0]:
                best = (key, kind, p)

        near_prims = []
        for h in list(handles)[:300]:
            e = self.cad_doc.entity_by_handle(h)
            if e is None:
                continue
            for kind, p in self.snap_points(h, e):
                if kind in modes:
                    consider(kind, p)
            for prim, (bx0, by0, bx1, by1) in self.prims(h, e):
                if bx1 < x - aperture or bx0 > x + aperture or by1 < y - aperture or by0 > y + aperture:
                    continue
                n = prim.nearest(cursor)
                if n.distance(cursor) > aperture:
                    continue
                near_prims.append(prim)
                if NEA in modes:
                    consider(NEA, n)
                if isinstance(prim, Arc):
                    if CEN in modes:
                        consider(CEN, prim.c, n.distance(cursor) + aperture * 0.3)
                    if TAN in modes and base is not None:
                        for t in geom.tangent_points(base, prim):
                            consider(TAN, t)
                if PER in modes and base is not None:
                    if isinstance(prim, Seg):
                        tp = prim.param(base)
                        if -1e-9 <= tp <= 1 + 1e-9:
                            consider(PER, prim.point(tp))
                    else:
                        d = base - prim.c
                        if d.magnitude > 1e-9:
                            a = d.angle
                            for ang in (a, a + math.pi):
                                if prim.contains_angle(ang):
                                    consider(PER, prim.point_at(ang))
        if INT in modes and len(near_prims) > 1:
            near_prims = near_prims[:60]
            for i in range(len(near_prims)):
                for j in range(i + 1, len(near_prims)):
                    for p in geom.intersect(near_prims[i], near_prims[j]):
                        consider(INT, p)
        if best is None:
            return None
        return best[1], best[2]
