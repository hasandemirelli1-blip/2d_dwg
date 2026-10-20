"""Rendering of DXF entities into a QGraphicsScene by the ezdxf drawing add-on.

Every graphics item stores the handle of its top level DXF entity, which makes
incremental updates and picking possible."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Optional

import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainterPath, QColor, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import (QGraphicsScene, QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem,
                               QGraphicsPixmapItem)

from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing.properties import RenderContext, LayoutProperties
from ezdxf.addons.drawing.config import (
    Configuration, BackgroundPolicy, ColorPolicy, LineweightPolicy, HatchPolicy,
)
from ezdxf.addons.drawing.pyqt import _PyQtBackend, _CosmeticPath
from ezdxf.npshapes import to_qpainter_path

HANDLE_KEY = Qt.UserRole + 10
IMAGE_Z = -1.0e9
MODEL_BG = "#212830"


class TrackingBackend(_PyQtBackend):
    """Collects all strokes/fills of one top level entity into a few
    QGraphicsPathItems (one per color/lineweight) instead of one item per line
    segment. Dashed lines, hatch patterns and blocks produce thousands of
    segments; batching them makes loading, painting and picking much faster."""

    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.items: dict[str, list] = defaultdict(list)
        self._cur: Optional[str] = None
        self._strokes: dict = {}
        self._fills: dict = {}
        self._pens: dict = {}

    def set_item_data(self, item, entity_handle: str) -> None:
        item.setData(HANDLE_KEY, entity_handle)
        self.items[entity_handle].append(item)

    # ------------------------------------------------------------ batching
    def _switch(self, handle) -> None:
        if handle != self._cur:
            self.flush()
            self._cur = handle

    def _stroke(self, properties) -> QPainterPath:
        self._switch(properties.handle)
        key = (properties.color, properties.lineweight)
        entry = self._strokes.get(key)
        if entry is None:
            pen = self._pens.get(key)
            if pen is None:
                pen = self._get_pen(properties)
                self._pens[key] = pen
            entry = [QPainterPath(), pen]
            self._strokes[key] = entry
        return entry[0]

    def _fill(self, properties, outline: bool) -> QPainterPath:
        self._switch(properties.handle)
        key = (properties.color, properties.lineweight, outline)
        entry = self._fills.get(key)
        if entry is None:
            pen = self._get_pen(properties) if outline else QPen(Qt.NoPen)
            entry = [QPainterPath(), pen, self._get_fill_brush(properties.color)]
            entry[0].setFillRule(Qt.OddEvenFill)
            self._fills[key] = entry
        return entry[0]

    def flush(self) -> None:
        h = self._cur
        if h is None:
            return
        scene = self._scene
        for path, pen, brush in self._fills.values():
            item = _CosmeticPath(path)
            item.setPen(pen)
            item.setBrush(brush)
            scene.addItem(item)
            self.set_item_data(item, h)
        for path, pen in self._strokes.values():
            item = QGraphicsPathItem(path)
            item.setPen(pen)
            item.setBrush(Qt.NoBrush)
            scene.addItem(item)
            self.set_item_data(item, h)
        self._fills = {}
        self._strokes = {}

    # ------------------------------------------------------------ primitives
    def draw_line(self, start, end, properties) -> None:
        if start.isclose(end):
            self._switch(properties.handle)
            self.draw_point(start, properties)
            return
        p = self._stroke(properties)
        p.moveTo(start.x, start.y)
        p.lineTo(end.x, end.y)

    def draw_solid_lines(self, lines, properties) -> None:
        p = self._stroke(properties)
        for s, e in lines:
            p.moveTo(s.x, s.y)
            p.lineTo(e.x, e.y)

    def draw_path(self, path, properties) -> None:
        if len(path) == 0:
            return
        self._stroke(properties).addPath(to_qpainter_path([path]))

    def draw_filled_paths(self, paths, properties) -> None:
        _paths = list(paths)
        if not _paths:
            return
        self._fill(properties, True).addPath(to_qpainter_path(_paths))

    def draw_filled_polygon(self, points, properties) -> None:
        poly = QPolygonF([QPointF(p.x, p.y) for p in points.vertices()])
        self._fill(properties, False).addPolygon(poly)

    def draw_image(self, image_data, properties) -> None:
        self._switch(properties.handle)
        super().draw_image(image_data, properties)
        items = self.items.get(properties.handle)
        if items:
            items[-1].setZValue(IMAGE_Z)  # raster images stay behind the drawing

    def finalize(self) -> None:
        # keep the scene rect unbounded (no setSceneRect)
        self.flush()

    def set_background(self, color) -> None:
        # the canvas paints the background (and the grid below the entities)
        self._scene.setBackgroundBrush(Qt.NoBrush)

    def clear(self) -> None:
        self._strokes = {}
        self._fills = {}
        self._pens = {}
        self._cur = None
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


class CachingFrontend(Frontend):
    """Draws the content of each block definition only once and reuses it
    (with a transformation) for all block references with the same properties."""

    def __init__(self, ctx, backend, config, renderer):
        super().__init__(ctx, backend, config=config)
        self.renderer = renderer
        self.block_cache: dict = {}

    def draw_entity(self, entity, properties) -> None:
        if (entity.dxftype() == "INSERT" and not entity.is_virtual
                and entity.dxf.get("row_count", 1) <= 1 and entity.dxf.get("column_count", 1) <= 1):
            try:
                if self._draw_cached_insert(entity, properties):
                    return
            except Exception as ex:  # fall back to the normal way
                print("block cache:", ex)
        super().draw_entity(entity, properties)

    def _block_content(self, insert, properties):
        key = (insert.dxf.name, properties.layer, properties.color, properties.linetype_name,
               properties.lineweight, properties.pen)
        content = self.block_cache.get(key)
        if content is not None:
            return content
        from ezdxf.entities import Insert
        attribs = insert.dxfattribs(drop={"handle", "owner", "insert", "xscale", "yscale", "zscale",
                                          "rotation", "extrusion", "row_count", "column_count",
                                          "row_spacing", "column_spacing"})
        ins0 = Insert.new(dxfattribs=attribs, doc=insert.doc)
        backend = self.renderer.backend
        main_scene, main_items = backend._scene, backend.items
        tmp = QGraphicsScene()
        backend.flush()
        backend._scene = tmp
        backend.items = defaultdict(list)
        backend._cur = None
        try:
            self.pipeline.set_current_entity_handle("__block__")
            super().draw_entity(ins0, properties)
            backend.flush()
            items = backend.items.get("__block__", [])
            content = []
            for it in items:
                if isinstance(it, QGraphicsPathItem):
                    content.append((QPainterPath(it.path()), QPen(it.pen()), it.brush(),
                                    isinstance(it, _CosmeticPath)))
        finally:
            backend._scene = main_scene
            backend.items = main_items
            backend._cur = None
            tmp.clear()
        m0 = ins0.matrix44()
        m0.inverse()
        content = (content, m0)
        self.block_cache[key] = content
        return content

    def _draw_cached_insert(self, insert, properties) -> bool:
        items, m0_inv = self._block_content(insert, properties)
        m = m0_inv @ insert.matrix44()
        qt = QTransform(*m.get_2d_transformation())
        backend = self.renderer.backend
        backend.flush()
        handle = insert.dxf.handle
        scene = backend._scene
        for path, pen, brush, cosmetic in items:
            it = _CosmeticPath(path) if cosmetic else QGraphicsPathItem(path)
            it.setPen(pen)
            it.setBrush(brush)
            it.setTransform(qt)
            scene.addItem(it)
            backend.set_item_data(it, handle)
        # attributes are drawn normally and assigned to the block reference
        attribs = [a for a in insert.attribs if not a.is_invisible]
        if attribs:
            self.draw_entities(attribs)
            backend.flush()
            for a in attribs:
                for it in backend.items.pop(a.dxf.handle, []):
                    backend.set_item_data(it, handle)
        backend._cur = None
        return True


class EntityGeometry:
    """Flattened geometry of one entity for picking and highlighting."""

    __slots__ = ("lines", "fills", "bbox", "is_text", "npts", "segs")

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
                if not it.transform().isIdentity():  # cached block content
                    path = it.sceneTransform().map(path)
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
            elif isinstance(it, QGraphicsPixmapItem):
                # image frame
                br = it.boundingRect()
                poly = it.mapToScene(br)
                pts = [[p.x(), p.y()] for p in poly]
                pts.append(pts[0])
                polylines.append(np.array(pts))
            else:  # points
                c = r.center()
                polylines.append(np.array([[c.x(), c.y()], [c.x(), c.y()]]))
        self.lines = polylines
        self.npts = sum(len(pl) for pl in polylines)
        # all segments in one array (N x 4) for fast vectorized tests
        if polylines:
            self.segs = np.vstack([np.hstack([pl[:-1], pl[1:]]) for pl in polylines if len(pl) > 1]) \
                if any(len(pl) > 1 for pl in polylines) else np.zeros((0, 4))
        else:
            self.segs = np.zeros((0, 4))
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
        if len(self.segs):
            a = self.segs[:, 0:2]
            d = self.segs[:, 2:4] - a
            p = np.array([x, y])
            l2 = (d * d).sum(axis=1)
            l2[l2 == 0] = 1e-30
            t = np.clip(((p - a) * d).sum(axis=1) / l2, 0.0, 1.0)
            proj = a + d * t[:, None]
            best = min(best, float(np.sqrt(((proj - p) ** 2).sum(axis=1)).min()))
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
        if len(self.segs) and _segments_hit_rect(self.segs, x0, y0, x1, y1):
            return True
        return False


def _segments_hit_rect(segs: np.ndarray, x0, y0, x1, y1) -> bool:
    a = segs[:, 0:2]
    b = segs[:, 2:4]
    for pts in (a, b):
        inside = (pts[:, 0] >= x0) & (pts[:, 0] <= x1) & (pts[:, 1] >= y0) & (pts[:, 1] <= y1)
        if inside.any():
            return True
    d = b - a
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    for (ex0, ey0), (ex1, ey1) in edges:
        e = np.array([ex1 - ex0, ey1 - ey0])
        den = d[:, 0] * e[1] - d[:, 1] * e[0]
        with np.errstate(divide="ignore", invalid="ignore"):
            w0 = ex0 - a[:, 0]
            w1 = ey0 - a[:, 1]
            t = (w0 * e[1] - w1 * e[0]) / den
            u = (w0 * d[:, 1] - w1 * d[:, 0]) / den
        if ((den != 0) & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)).any():
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
        if ctx.document_dir is None:
            # unsaved drawing: absolute image paths still work, relative ones use the home folder
            import pathlib
            base = self.cad_doc.path or ""
            ctx.document_dir = pathlib.Path(base).parent if base else pathlib.Path.home()
        msp = doc.modelspace()
        ctx.set_current_layout(msp)
        props = LayoutProperties.from_layout(msp)
        props.set_colors(self.background)
        ctx.current_layout_properties = props
        self.frontend = CachingFrontend(ctx, self.backend, self.make_config(), self)

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
            from ezdxf import reorder
            handle_mapping = list(msp.get_redraw_order())
            entities = reorder.ascending(msp, handle_mapping) if handle_mapping else msp
            self.fast_draw(entities, filter_func)
        except Exception as ex:  # robustness against broken entities
            print("render error:", ex)
            self.backend.clear()
            for e in msp:
                if filter_func is None or filter_func(e):
                    self._draw_safe([e])
        self._z = float(len(self.scene.items()))

    # -------------------------------------------------------------- fast path
    FAST_TYPES = frozenset(("LINE", "CIRCLE", "ARC", "LWPOLYLINE"))

    def fast_draw(self, entities, filter_func=None):
        """Draw simple entities (continuous LINE, CIRCLE, ARC, LWPOLYLINE)
        directly into the backend, everything else by the ezdxf frontend."""
        self._prop_cache = {}
        batch = []
        frontend = self.frontend
        for e in entities:
            if filter_func is not None and not filter_func(e):
                continue
            if e.dxftype() in self.FAST_TYPES:
                if batch:
                    frontend.draw_entities(batch)
                    self.backend.flush()
                    batch = []
                try:
                    if self._fast(e):
                        continue
                except Exception as ex:
                    print("fast draw:", e, ex)
            batch.append(e)
        if batch:
            frontend.draw_entities(batch)
        self.backend.flush()

    def _fast(self, e) -> bool:
        d = e.dxf
        if d.get("thickness", 0) or e.dxftype() == "LWPOLYLINE" and (
                d.get("const_width", 0) or any(sw or ew for sw, ew in e.get_points("se"))):
            return False
        ext = d.get("extrusion", None)
        if ext is not None and (abs(ext[0]) > 1e-12 or abs(ext[1]) > 1e-12 or ext[2] < 0):
            return False
        key = (d.layer, d.get("color", 256), d.get("true_color", None), d.get("linetype", "BYLAYER"),
               d.get("lineweight", -1), d.get("transparency", None))
        bp = self._prop_cache.get(key)
        if bp is None:
            frontend = self.frontend
            props = frontend.ctx.resolve_all(e)
            frontend.exec_property_override(e, props)
            if not props.is_visible:
                bp = "skip"
            elif props.linetype_pattern and len(props.linetype_pattern) > 0 \
                    and props.linetype_name.upper() not in ("CONTINUOUS", ""):
                bp = "slow"
            else:
                bp = frontend.pipeline.get_backend_properties(props)
            self._prop_cache[key] = bp
        if bp == "skip":
            return True
        if bp == "slow":
            return False
        bp = bp._replace(handle=d.handle)
        path = self.backend._stroke(bp)
        t = e.dxftype()
        if t == "LINE":
            s, en = d.start, d.end
            path.moveTo(s.x, s.y)
            path.lineTo(en.x, en.y)
        elif t == "CIRCLE":
            c, r = d.center, d.radius
            path.addEllipse(QPointF(c.x, c.y), r, r)
        elif t == "ARC":
            c, r = d.center, d.radius
            a0 = d.start_angle
            sweep = (d.end_angle - a0) % 360.0
            if sweep < 1e-9:
                sweep = 360.0
            rect = QRectF(c.x - r, c.y - r, 2 * r, 2 * r)
            path.arcMoveTo(rect, -a0)
            path.arcTo(rect, -a0, -sweep)
        else:  # LWPOLYLINE
            pts = list(e.get_points("xyb"))
            if not pts:
                return True
            closed = e.closed
            path.moveTo(pts[0][0], pts[0][1])
            n = len(pts)
            last = n if closed else n - 1
            for i in range(last):
                x1, y1, b = pts[i]
                x2, y2, _ = pts[(i + 1) % n]
                if abs(b) < 1e-12:
                    path.lineTo(x2, y2)
                    continue
                theta = 4.0 * math.atan(b)  # signed sweep, CCW positive
                dx, dy = x2 - x1, y2 - y1
                chord = math.hypot(dx, dy)
                if chord < 1e-12:
                    continue
                r = chord / (2.0 * abs(math.sin(theta / 2)))
                h = (chord / 2.0) / math.tan(theta / 2)
                cx = (x1 + x2) / 2 - dy / chord * h
                cy = (y1 + y2) / 2 + dx / chord * h
                a0 = math.degrees(math.atan2(y1 - cy, x1 - cx))
                path.arcTo(QRectF(cx - r, cy - r, 2 * r, 2 * r), -a0, -math.degrees(theta))
            if closed:
                path.closeSubpath()
        return True

    def _draw_safe(self, entities: Iterable):
        for e in entities:
            try:
                self.frontend.draw_entities([e])
            except Exception as ex:
                print("render error:", e, ex)
            self.backend.flush()

    def add(self, entities: Iterable):
        if self.frontend is None:
            self._make_frontend()
        ents = [e for e in entities if e.is_alive]
        handles = [e.dxf.handle for e in ents]
        for h in handles:
            self.remove_handle(h)
        try:
            self.fast_draw(ents)
        except Exception as ex:
            print("render error:", ex)
            for h in handles:
                self.remove_handle(h)
            self._draw_safe(ents)
        # new items on top
        for h in handles:
            for it in self.backend.items.get(h, []):
                if it.zValue() == IMAGE_Z:
                    continue
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
            is_text = e is not None and e.dxftype() in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "IMAGE")
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
