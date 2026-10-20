"""Rendering of DXF entities into a QGraphicsScene by the ezdxf drawing add-on.

Every graphics item stores the handle of its top level DXF entity, which makes
incremental updates and picking possible."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Optional

import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainterPath, QColor
from PySide6.QtWidgets import QGraphicsScene, QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem

from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing.properties import RenderContext, LayoutProperties
from ezdxf.addons.drawing.config import (
    Configuration, BackgroundPolicy, ColorPolicy, LineweightPolicy, HatchPolicy,
)
from ezdxf.addons.drawing.pyqt import _PyQtBackend

HANDLE_KEY = Qt.UserRole + 10
MODEL_BG = "#212830"


class TrackingBackend(_PyQtBackend):
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.items: dict[str, list] = defaultdict(list)

    def set_item_data(self, item, entity_handle: str) -> None:
        item.setData(HANDLE_KEY, entity_handle)
        self.items[entity_handle].append(item)

    def finalize(self) -> None:
        # keep the scene rect unbounded (no setSceneRect)
        pass

    def set_background(self, color) -> None:
        # the canvas paints the background (and the grid below the entities)
        self._scene.setBackgroundBrush(Qt.NoBrush)

    def clear(self) -> None:
        self._scene.clear()
        self.items.clear()


class PrintBackend(TrackingBackend):
    """Pens with real line widths in device pixels for printing."""

    def __init__(self, scene, dpi: float, use_lineweights: bool, default_mm: float = 0.25):
        super().__init__(scene)
        self.dpi = dpi
        self.use_lineweights = use_lineweights
        self.default_mm = default_mm

    def _get_pen(self, properties):
        from PySide6.QtGui import QPen
        mm = properties.lineweight if self.use_lineweights else self.default_mm
        mm = max(mm, 0.09)
        pen = QPen(self._get_color(properties.color), mm * self.dpi / 25.4)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        return pen


class EntityGeometry:
    """Flattened geometry of one entity for picking and highlighting."""

    __slots__ = ("lines", "fills", "bbox", "is_text")

    def __init__(self, items: list, is_text=False):
        polylines = []
        fills = []
        x0 = y0 = float("inf")
        x1 = y1 = float("-inf")
        for it in items:
            r = it.sceneBoundingRect()
            x0, y0 = min(x0, r.left()), min(y0, r.top())
            x1, y1 = max(x1, r.right()), max(y1, r.bottom())
            if isinstance(it, QGraphicsLineItem):
                ln = it.line()
                polylines.append(np.array([[ln.x1(), ln.y1()], [ln.x2(), ln.y2()]]))
            elif isinstance(it, QGraphicsPathItem):
                path = it.path()
                if it.brush().style() != Qt.NoBrush:
                    fills.append(path)
                for poly in path.toSubpathPolygons():
                    if poly.size() > 1:
                        polylines.append(np.array([[p.x(), p.y()] for p in poly]))
            elif isinstance(it, QGraphicsPolygonItem):
                poly = it.polygon()
                path = QPainterPath()
                path.addPolygon(poly)
                fills.append(path)
                if poly.size() > 1:
                    pts = [[p.x(), p.y()] for p in poly]
                    pts.append(pts[0])
                    polylines.append(np.array(pts))
            else:  # points, images
                c = r.center()
                polylines.append(np.array([[c.x(), c.y()], [c.x(), c.y()]]))
        self.lines = polylines
        self.fills = fills
        self.bbox = (x0, y0, x1, y1) if x0 <= x1 else (0, 0, 0, 0)
        self.is_text = is_text

    # -------------------------------------------------------------- tests
    def distance(self, x: float, y: float) -> float:
        best = float("inf")
        if self.is_text:
            x0, y0, x1, y1 = self.bbox
            if x0 <= x <= x1 and y0 <= y <= y1:
                return 0.0
        for path in self.fills:
            if path.contains(QPointF(x, y)):
                return 0.0
        p = np.array([x, y])
        for pl in self.lines:
            a = pl[:-1]
            b = pl[1:]
            d = b - a
            l2 = (d * d).sum(axis=1)
            l2[l2 == 0] = 1e-30
            t = np.clip(((p - a) * d).sum(axis=1) / l2, 0.0, 1.0)
            proj = a + d * t[:, None]
            dist = np.sqrt(((proj - p) ** 2).sum(axis=1)).min()
            best = min(best, dist)
        return best

    def inside(self, x0, y0, x1, y1) -> bool:
        bx0, by0, bx1, by1 = self.bbox
        return bx0 >= x0 and by0 >= y0 and bx1 <= x1 and by1 <= y1

    def crosses(self, x0, y0, x1, y1) -> bool:
        bx0, by0, bx1, by1 = self.bbox
        if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
            return False
        if self.inside(x0, y0, x1, y1) or self.is_text:
            return True
        rect = QRectF(x0, y0, x1 - x0, y1 - y0)
        for path in self.fills:
            if path.intersects(rect):
                return True
        for pl in self.lines:
            if _polyline_hits_rect(pl, x0, y0, x1, y1):
                return True
        return False


def _polyline_hits_rect(pl: np.ndarray, x0, y0, x1, y1) -> bool:
    # any vertex inside?
    inside = (pl[:, 0] >= x0) & (pl[:, 0] <= x1) & (pl[:, 1] >= y0) & (pl[:, 1] <= y1)
    if inside.any():
        return True
    a = pl[:-1]
    b = pl[1:]
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    d = b - a
    for (ex0, ey0), (ex1, ey1) in edges:
        e = np.array([ex1 - ex0, ey1 - ey0])
        den = d[:, 0] * e[1] - d[:, 1] * e[0]
        with np.errstate(divide="ignore", invalid="ignore"):
            w0 = ex0 - a[:, 0]
            w1 = ey0 - a[:, 1]
            t = (w0 * e[1] - w1 * e[0]) / den
            u = (w0 * d[:, 1] - w1 * d[:, 0]) / den
        hit = (den != 0) & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
        if hit.any():
            return True
    return False


class Renderer:
    """Keeps a QGraphicsScene in sync with the modelspace of a document."""

    def __init__(self, cad_doc, background: str = MODEL_BG, backend_factory=None,
                 color_policy: ColorPolicy = ColorPolicy.COLOR):
        self.cad_doc = cad_doc
        self.scene = QGraphicsScene()
        self.scene.setItemIndexMethod(QGraphicsScene.BspTreeIndex)
        self.backend = backend_factory(self.scene) if backend_factory else TrackingBackend(self.scene)
        self.background = background
        self.color_policy = color_policy
        self.show_lineweight = False
        self._geom: dict[str, EntityGeometry] = {}
        self.frontend: Optional[Frontend] = None
        self._z = 0.0

    # -------------------------------------------------------------- config
    def make_config(self) -> Configuration:
        return Configuration(
            background_policy=BackgroundPolicy.CUSTOM,
            custom_bg_color=self.background,
            color_policy=self.color_policy,
            lineweight_policy=LineweightPolicy.ABSOLUTE,
            lineweight_scaling=1.0 if self.show_lineweight else 0.0,
            min_lineweight=0.24 if self.show_lineweight else 0.5,
            hatch_policy=HatchPolicy.NORMAL,
            max_flattening_distance=0.01,
            circle_approximation_count=128,
        )

    def _make_frontend(self):
        doc = self.cad_doc.doc
        ctx = RenderContext(doc)
        msp = doc.modelspace()
        ctx.set_current_layout(msp)
        props = LayoutProperties.from_layout(msp)
        props.set_colors(self.background)
        ctx.current_layout_properties = props
        self.frontend = Frontend(ctx, self.backend, config=self.make_config())

    # -------------------------------------------------------------- render
    def regen(self, plot_only: bool = False):
        self.backend.clear()
        self._geom.clear()
        self._make_frontend()
        self._z = 0.0
        doc = self.cad_doc.doc
        msp = doc.modelspace()
        filter_func = None
        if plot_only:
            no_plot = {l.dxf.name.lower() for l in doc.layers if not l.dxf.get("plot", 1)}
            no_plot.add("defpoints")
            filter_func = lambda e: e.dxf.layer.lower() not in no_plot  # noqa: E731
        try:
            self.frontend.draw_layout(msp, finalize=False, filter_func=filter_func)
        except Exception as ex:  # robustness against broken entities
            print("render error:", ex)
            self.backend.clear()
            for e in msp:
                if filter_func is None or filter_func(e):
                    self._draw_safe([e])
        self._z = float(len(self.scene.items()))

    def _draw_safe(self, entities: Iterable):
        for e in entities:
            try:
                self.frontend.draw_entities([e])
            except Exception as ex:
                print("render error:", e, ex)

    def add(self, entities: Iterable):
        if self.frontend is None:
            self._make_frontend()
        before = set()
        ents = [e for e in entities if e.is_alive]
        for e in ents:
            before.add(e.dxf.handle)
            self.remove_handle(e.dxf.handle)
        n_before = len(self.scene.items())
        self._draw_safe(ents)
        # new items on top
        for h in before:
            for it in self.backend.items.get(h, []):
                self._z += 1.0
                it.setZValue(self._z)

    def remove_handle(self, handle: str):
        items = self.backend.items.pop(handle, None)
        if items:
            for it in items:
                self.scene.removeItem(it)
        self._geom.pop(handle, None)

    def remove(self, entities: Iterable):
        for e in entities:
            self.remove_handle(e.dxf.handle)

    # -------------------------------------------------------------- queries
    def items_of(self, handle: str) -> list:
        return self.backend.items.get(handle, [])

    def geometry(self, handle: str) -> Optional[EntityGeometry]:
        g = self._geom.get(handle)
        if g is None:
            items = self.backend.items.get(handle)
            if not items:
                return None
            e = self.cad_doc.entity_by_handle(handle)
            is_text = e is not None and e.dxftype() in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF")
            g = EntityGeometry(items, is_text)
            self._geom[handle] = g
        return g

    def handles_in_rect(self, x0, y0, x1, y1) -> set[str]:
        # degenerated rects (e.g. bbox of a horizontal line) return no items
        eps = 1e-6 * max(1.0, abs(x0), abs(y0), abs(x1), abs(y1))
        rect = QRectF(x0 - eps, y0 - eps, x1 - x0 + 2 * eps, y1 - y0 + 2 * eps)
        out = set()
        for it in self.scene.items(rect, Qt.IntersectsItemBoundingRect):
            h = it.data(HANDLE_KEY)
            if h:
                out.add(h)
        return out

    def pick(self, x: float, y: float, tol: float) -> Optional[str]:
        best, best_d = None, tol
        for h in self.handles_in_rect(x - tol, y - tol, x + tol, y + tol):
            g = self.geometry(h)
            if g is None:
                continue
            d = g.distance(x, y)
            if d <= best_d:
                # prefer the topmost entity on ties
                best, best_d = h, d
        return best

    def select_window(self, x0, y0, x1, y1, crossing: bool) -> list[str]:
        out = []
        for h in self.handles_in_rect(x0, y0, x1, y1):
            g = self.geometry(h)
            if g is None:
                continue
            if (crossing and g.crosses(x0, y0, x1, y1)) or (not crossing and g.inside(x0, y0, x1, y1)):
                out.append(h)
        return out

    def extents(self) -> Optional[QRectF]:
        r = self.scene.itemsBoundingRect()
        if r.isNull() or not self.scene.items():
            return None
        return r
