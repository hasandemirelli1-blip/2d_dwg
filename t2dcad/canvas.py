"""Drawing area widget: view transform, cached rendering, cursor, osnap,
ortho/polar, selection and grips."""
from __future__ import annotations

import math
from typing import Optional

from ezdxf.math import Vec2, Matrix44
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint, Signal, QTimer
from PySide6.QtGui import (QPainter, QColor, QPen, QImage, QTransform, QPainterPath,
                           QBrush, QFont, QPolygonF, QCursor, QFontMetrics)
from PySide6.QtWidgets import QWidget, QMenu

from t2dcad import geom, settings
from t2dcad.engine import (GetPoint, GetDistance, GetAngle, GetSelection, GetEntity, fmt)
from t2dcad.geom import END, MID, CEN, QUA, INT, PER, NEA, NOD, INS, TAN, Seg, Arc
from t2dcad.grips import entity_grips

SEL_COLOR = QColor(80, 160, 255)
HOVER_COLOR = QColor(120, 190, 255)
GRIP_COLOR = QColor(40, 110, 255)
GRIP_HOT = QColor(255, 40, 40)
SNAP_COLOR = QColor(255, 220, 0)
PREVIEW_COLOR = QColor(230, 230, 230)
TRACK_COLOR = QColor(110, 200, 110)


class CadCanvas(QWidget):
    cursor_moved = Signal(float, float)
    selection_changed = Signal()

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab  # DocumentTab: doc, renderer, snap, manager, ctx
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.BlankCursor)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumSize(200, 150)
        # view
        self.cx = 0.0
        self.cy = 0.0
        self.scale = 1.0  # pixel per drawing unit
        self.view_history: list[tuple] = []
        # caches
        self._base: Optional[QImage] = None
        self._base_dirty = True
        self._sel_img: Optional[QImage] = None
        self._sel_dirty = True
        # state
        self.cursor_screen = QPointF(-100, -100)
        self.cursor_raw = Vec2()
        self.cursor_world = Vec2()  # snapped/constrained
        self.snap_hit: Optional[tuple[str, Vec2]] = None
        self.track_info: Optional[tuple] = None  # (base, angle_deg) polar tracking
        self.osnap_override: Optional[set] = None
        self.selection: list[str] = []
        self.prev_selection: list[str] = []
        self.hover: Optional[str] = None
        self.window_start: Optional[Vec2] = None
        self.window_press_screen: Optional[QPointF] = None
        self.sel_remove_mode = False
        self.pan_last: Optional[QPointF] = None
        self.realtime_pan = False
        self.hot_grip: Optional[Vec2] = None
        self.inside = False
        # toggles
        self.ortho = settings.get_bool("ortho", False)
        self.polar = settings.get_bool("polar", False)
        self.grid = settings.get_bool("grid", False)
        self.snap_grid = settings.get_bool("snapmode", False)
        self.polar_inc = settings.get_float("polar_inc", 45.0)
        self.grid_unit = settings.get_float("grid_unit", 10.0)
        self.cursor_size = settings.get_int("cursor_size", 5)
        self.pickbox = settings.get_int("pickbox", 5)
        self.aperture = settings.get_int("aperture", 10)
        self.bg_color = QColor(settings.get("bg_color", "#212830"))

    # ------------------------------------------------------------ helpers
    @property
    def renderer(self):
        return self.tab.renderer

    @property
    def manager(self):
        return self.tab.manager

    @property
    def snap(self):
        return self.tab.snap

    def to_screen(self, p) -> QPointF:
        return QPointF((p[0] - self.cx) * self.scale + self.width() / 2,
                       self.height() / 2 - (p[1] - self.cy) * self.scale)

    def to_world(self, sp: QPointF) -> Vec2:
        return Vec2((sp.x() - self.width() / 2) / self.scale + self.cx,
                    (self.height() / 2 - sp.y()) / self.scale + self.cy)

    def world_transform(self) -> QTransform:
        s = self.scale
        return QTransform(s, 0, 0, -s, self.width() / 2 - self.cx * s, self.height() / 2 + self.cy * s)

    def visible_rect(self) -> tuple[float, float, float, float]:
        a = self.to_world(QPointF(0, self.height()))
        b = self.to_world(QPointF(self.width(), 0))
        return a.x, a.y, b.x, b.y

    def px(self, n: float) -> float:
        """n pixels in world units"""
        return n / self.scale

    # ------------------------------------------------------------ view
    def push_view(self):
        self.view_history.append((self.cx, self.cy, self.scale))
        if len(self.view_history) > 50:
            self.view_history.pop(0)

    def zoom_previous(self):
        if self.view_history:
            self.cx, self.cy, self.scale = self.view_history.pop()
            self.invalidate()

    def zoom_rect(self, x0, y0, x1, y1, margin=1.0, push=True):
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        if w < 1e-9 and h < 1e-9:
            w = h = 10.0
        if push:
            self.push_view()
        self.cx = (x0 + x1) / 2
        self.cy = (y0 + y1) / 2
        sx = self.width() / max(w, 1e-9)
        sy = self.height() / max(h, 1e-9)
        self.scale = min(sx, sy) / margin
        self.scale = max(1e-6, min(self.scale, 1e7))
        self.invalidate()

    def zoom_extents(self, push=True):
        r = self.renderer.extents()
        if r is None:
            self.zoom_rect(0, 0, 420, 297, 1.05, push)
        else:
            self.zoom_rect(r.left(), r.top(), r.right(), r.bottom(), 1.05, push)

    def zoom_factor(self, f: float, at: Optional[QPointF] = None):
        at = at or QPointF(self.width() / 2, self.height() / 2)
        w = self.to_world(at)
        self.scale = max(1e-6, min(self.scale * f, 1e7))
        # keep world point under cursor
        self.cx = w.x - (at.x() - self.width() / 2) / self.scale
        self.cy = w.y - (self.height() / 2 - at.y()) / self.scale
        self.invalidate()

    def invalidate(self, base=True):
        if base:
            self._base_dirty = True
        self._sel_dirty = True
        self.update()

    def selection_dirty(self):
        self._sel_dirty = True
        self.update()

    # ------------------------------------------------------------ painting
    def _render_base(self):
        dpr = self.devicePixelRatioF()
        img = QImage(int(self.width() * dpr), int(self.height() * dpr), QImage.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(self.bg_color)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, settings.get_bool("antialias", True))
        if self.grid:
            self._paint_grid(p)
        x0, y0, x1, y1 = self.visible_rect()
        source = QRectF(x0, y0, x1 - x0, y1 - y0)
        p.translate(0, self.height())
        p.scale(1, -1)
        self.renderer.scene.render(p, QRectF(0, 0, self.width(), self.height()), source,
                                   Qt.IgnoreAspectRatio)
        p.end()
        self._base = img
        self._base_dirty = False

    def _paint_grid(self, p: QPainter):
        g = self.grid_unit
        if g <= 0:
            return
        while g * self.scale < 8:
            g *= 5
        x0, y0, x1, y1 = self.visible_rect()
        minor = QPen(QColor(255, 255, 255, 18))
        major = QPen(QColor(255, 255, 255, 40))
        i0 = math.floor(x0 / g)
        i1 = math.ceil(x1 / g)
        for i in range(i0, i1 + 1):
            sx = self.to_screen((i * g, 0)).x()
            p.setPen(major if i % 5 == 0 else minor)
            p.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
        j0 = math.floor(y0 / g)
        j1 = math.ceil(y1 / g)
        for j in range(j0, j1 + 1):
            sy = self.to_screen((0, j * g)).y()
            p.setPen(major if j % 5 == 0 else minor)
            p.drawLine(QPointF(0, sy), QPointF(self.width(), sy))

    def _render_selection(self):
        dpr = self.devicePixelRatioF()
        img = QImage(int(self.width() * dpr), int(self.height() * dpr), QImage.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.transparent)
        if self.selection:
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(SEL_COLOR, 1.6, Qt.DashLine)
            pen.setCosmetic(True)
            self._draw_entities(p, self.selection, pen)
            # grips
            if len(self.selection) <= settings.get_int("grip_limit", 200):
                p.setTransform(QTransform())
                p.setPen(QPen(QColor(0, 0, 0), 1))
                p.setBrush(GRIP_COLOR)
                gs = 4
                for h in self.selection:
                    e = self.tab.doc.entity_by_handle(h)
                    if e is None:
                        continue
                    for gp, key in entity_grips(e):
                        sp = self.to_screen(gp)
                        p.drawRect(QRectF(sp.x() - gs, sp.y() - gs, 2 * gs, 2 * gs))
            p.end()
        self._sel_img = img
        self._sel_dirty = False

    def _draw_entities(self, p: QPainter, handles, pen: QPen, transform: Optional[QTransform] = None):
        wt = self.world_transform()
        if transform is not None:
            wt = transform * wt
        p.setTransform(wt)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        x0, y0, x1, y1 = self.visible_rect()
        for h in handles:
            g = self.renderer.geometry(h)
            if g is None:
                continue
            if transform is None:
                bx0, by0, bx1, by1 = g.bbox
                if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
                    continue
            for pl in g.lines:
                if len(pl) == 2:
                    p.drawLine(QPointF(*pl[0]), QPointF(*pl[1]))
                else:
                    p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pl]))
        p.setTransform(QTransform())

    def paintEvent(self, ev):
        if self._base is None or self._base_dirty or self._base.size() != self.size() * self.devicePixelRatioF():
            self._render_base()
        if self._sel_dirty or self._sel_img is None or self._sel_img.size() != self._base.size():
            self._render_selection()
        p = QPainter(self)
        p.drawImage(0, 0, self._base)
        p.drawImage(0, 0, self._sel_img)
        p.setRenderHint(QPainter.Antialiasing, True)
        self._paint_hover(p)
        self._paint_preview(p)
        self._paint_window(p)
        self._paint_ucs(p)
        if self.inside:
            self._paint_tracking(p)
            self._paint_cursor(p)
            self._paint_snap(p)
            self._paint_tooltip(p)
        p.end()

    def _paint_hover(self, p: QPainter):
        if self.hover and self.hover not in self.selection:
            pen = QPen(HOVER_COLOR, 2.5)
            pen.setCosmetic(True)
            self._draw_entities(p, [self.hover], pen)

    def _preview_shapes(self) -> list:
        r = self.manager.req
        shapes = []
        if r is None:
            return shapes
        cw = self.cursor_world
        fn = getattr(r, "preview", None)
        if fn is not None:
            try:
                shapes = list(fn(cw) or [])
            except Exception as ex:  # preview must never crash the UI
                print("preview error:", ex)
                shapes = []
        base = self.manager.rubber_base
        if base is not None and getattr(r, "rubber", True) and not shapes:
            shapes.append(("line", base, cw))
        return shapes

    def _paint_preview(self, p: QPainter):
        shapes = self._preview_shapes()
        if not shapes:
            return
        pen = QPen(PREVIEW_COLOR, 1)
        pen.setCosmetic(True)
        dashed = QPen(PREVIEW_COLOR, 1, Qt.DashLine)
        dashed.setCosmetic(True)
        wt = self.world_transform()
        for sh in shapes:
            kind = sh[0]
            p.setTransform(wt)
            p.setBrush(Qt.NoBrush)
            p.setPen(pen)
            if kind == "line":
                p.drawLine(QPointF(*sh[1]), QPointF(*sh[2]))
            elif kind == "dline":
                p.setPen(dashed)
                p.drawLine(QPointF(*sh[1]), QPointF(*sh[2]))
            elif kind == "poly":
                pts = QPolygonF([QPointF(*v) for v in sh[1]])
                if len(sh) > 2 and sh[2]:
                    p.drawPolygon(pts)
                else:
                    p.drawPolyline(pts)
            elif kind == "circle":
                c, r = sh[1], sh[2]
                p.drawEllipse(QPointF(*c), r, r)
            elif kind == "prim":
                self._draw_prim(p, sh[1])
            elif kind == "prims":
                for prim in sh[1]:
                    self._draw_prim(p, prim)
            elif kind == "ghost":
                handles, m = sh[1], sh[2]
                t = QTransform(*m.get_2d_transformation()) if isinstance(m, Matrix44) else m
                p.setTransform(QTransform())
                self._draw_entities(p, handles, pen, t)
            elif kind == "rect":
                a, b = sh[1], sh[2]
                p.drawRect(QRectF(QPointF(*a), QPointF(*b)).normalized())
            elif kind == "text":
                pos, txt, h = sh[1], sh[2], sh[3]
                p.setTransform(QTransform())
                sp = self.to_screen(pos)
                f = QFont("Arial")
                f.setPixelSize(max(4, int(h * self.scale)))
                p.setFont(f)
                p.setPen(PREVIEW_COLOR)
                p.drawText(sp, txt)
        p.setTransform(QTransform())

    def _draw_prim(self, p: QPainter, prim):
        if isinstance(prim, Seg):
            p.drawLine(QPointF(*prim.a), QPointF(*prim.b))
        else:
            n = max(8, int(prim.span / math.radians(3)))
            pts = [prim.point(i / n) for i in range(n + 1)]
            p.drawPolyline(QPolygonF([QPointF(v.x, v.y) for v in pts]))

    def _paint_window(self, p: QPainter):
        if self.window_start is None:
            return
        a = self.to_screen(self.window_start)
        b = self.cursor_screen
        crossing = b.x() < a.x()
        rect = QRectF(a, b).normalized()
        if crossing:
            p.setBrush(QColor(60, 200, 60, 50))
            pen = QPen(QColor(200, 255, 200), 1, Qt.DashLine)
        else:
            p.setBrush(QColor(60, 110, 255, 50))
            pen = QPen(QColor(200, 220, 255), 1)
        p.setPen(pen)
        p.drawRect(rect)

    def _paint_ucs(self, p: QPainter):
        o = QPointF(25, self.height() - 25)
        pen = QPen(QColor(230, 80, 80), 2)
        p.setPen(pen)
        p.drawLine(o, o + QPointF(40, 0))
        p.setPen(QPen(QColor(80, 200, 80), 2))
        p.drawLine(o, o + QPointF(0, -40))
        p.setPen(QColor(220, 220, 220))
        p.setFont(QFont("Arial", 8))
        p.drawText(o + QPointF(43, 4), "X")
        p.drawText(o + QPointF(-4, -44), "Y")

    def _cursor_mode(self) -> str:
        r = self.manager.req
        if self.realtime_pan:
            return "pan"
        if r is None:
            return "idle"
        if isinstance(r, (GetSelection, GetEntity)):
            return "pick"
        return "point"

    def _paint_cursor(self, p: QPainter):
        c = self.cursor_screen
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QPen(QColor(255, 255, 255), 1))
        mode = self._cursor_mode()
        if mode == "pan":
            p.drawText(c + QPointF(-5, 5), "✋")
            return
        if mode != "pick":
            size = self.cursor_size
            if size >= 100:
                p.drawLine(QPointF(0, c.y()), QPointF(self.width(), c.y()))
                p.drawLine(QPointF(c.x(), 0), QPointF(c.x(), self.height()))
            else:
                L = max(self.width(), self.height()) * size / 200.0
                p.drawLine(QPointF(c.x() - L, c.y()), QPointF(c.x() + L, c.y()))
                p.drawLine(QPointF(c.x(), c.y() - L), QPointF(c.x(), c.y() + L))
        if mode in ("idle", "pick"):
            b = self.pickbox
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(c.x() - b, c.y() - b, 2 * b, 2 * b))
        p.setRenderHint(QPainter.Antialiasing, True)

    def _paint_snap(self, p: QPainter):
        if not self.snap_hit or self._cursor_mode() != "point":
            return
        kind, pt = self.snap_hit
        c = self.to_screen(pt)
        s = 6
        pen = QPen(SNAP_COLOR, 2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        x, y = c.x(), c.y()
        if kind == END:
            p.drawRect(QRectF(x - s, y - s, 2 * s, 2 * s))
        elif kind == MID:
            p.drawPolygon(QPolygonF([QPointF(x - s, y + s), QPointF(x + s, y + s), QPointF(x, y - s)]))
        elif kind == CEN:
            p.drawEllipse(c, s, s)
        elif kind == QUA:
            p.drawPolygon(QPolygonF([QPointF(x, y - s), QPointF(x + s, y), QPointF(x, y + s), QPointF(x - s, y)]))
        elif kind == INT:
            p.drawLine(QPointF(x - s, y - s), QPointF(x + s, y + s))
            p.drawLine(QPointF(x - s, y + s), QPointF(x + s, y - s))
        elif kind == PER:
            p.drawLine(QPointF(x - s, y + s), QPointF(x + s, y + s))
            p.drawLine(QPointF(x - s, y + s), QPointF(x - s, y - s))
            p.drawLine(QPointF(x - s, y), QPointF(x, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + s))
        elif kind == NEA:
            p.drawPolygon(QPolygonF([QPointF(x - s, y - s), QPointF(x + s, y - s),
                                     QPointF(x - s, y + s), QPointF(x + s, y + s)]))
        elif kind == NOD:
            p.drawEllipse(c, s, s)
            p.drawLine(QPointF(x - s * .7, y - s * .7), QPointF(x + s * .7, y + s * .7))
            p.drawLine(QPointF(x - s * .7, y + s * .7), QPointF(x + s * .7, y - s * .7))
        elif kind == INS:
            p.drawRect(QRectF(x - s, y - s, s, s))
            p.drawRect(QRectF(x, y, s, s))
        elif kind == TAN:
            p.drawEllipse(c, s * .8, s * .8)
            p.drawLine(QPointF(x - s, y - s), QPointF(x + s, y - s))
        else:
            p.drawRect(QRectF(x - s, y - s, 2 * s, 2 * s))

    def _paint_tracking(self, p: QPainter):
        if not self.track_info or self._cursor_mode() != "point":
            return
        base, ang = self.track_info
        a = self.to_screen(base)
        far = base + Vec2.from_deg_angle(ang, 1e6 / max(self.scale, 1e-9) * 3)
        b = self.to_screen(far)
        pen = QPen(TRACK_COLOR, 1, Qt.DotLine)
        p.setPen(pen)
        p.drawLine(a, b)

    def _paint_tooltip(self, p: QPainter):
        lines = []
        mode = self._cursor_mode()
        if mode == "point":
            if self.snap_hit:
                lines.append(geom.SNAP_NAMES.get(self.snap_hit[0], self.snap_hit[0]))
            base = self.manager.rubber_base
            if base is not None:
                d = self.cursor_world - base
                ang = math.degrees(d.angle) % 360 if d.magnitude > 1e-12 else 0.0
                lines.append(f"{fmt(d.magnitude, 3)} < {fmt(ang, 2)}°")
        if not lines:
            return
        f = QFont("Segoe UI", 8)
        p.setFont(f)
        fm = QFontMetrics(f)
        w = max(fm.horizontalAdvance(t) for t in lines) + 8
        h = fm.height() * len(lines) + 4
        pos = self.cursor_screen + QPointF(18, 18)
        rect = QRectF(pos, QPointF(pos.x() + w, pos.y() + h))
        p.setPen(QColor(90, 90, 90))
        p.setBrush(QColor(40, 44, 52, 230))
        p.drawRect(rect)
        p.setPen(QColor(235, 235, 235))
        for i, t in enumerate(lines):
            p.drawText(QPointF(rect.left() + 4, rect.top() + 2 + fm.ascent() + i * fm.height()), t)

    # ------------------------------------------------------------ cursor logic
    def _locked(self, h: str) -> bool:
        return self.tab.is_locked(h)

    def pick(self, sp: Optional[QPointF] = None, allow_locked=False) -> Optional[str]:
        sp = sp or self.cursor_screen
        w = self.to_world(sp)
        h = self.renderer.pick(w.x, w.y, self.px(self.pickbox))
        if h and not allow_locked and self._locked(h):
            return None
        return h

    def update_cursor(self, sp: QPointF):
        self.cursor_screen = sp
        raw = self.to_world(sp)
        self.cursor_raw = raw
        self.snap_hit = None
        self.track_info = None
        mode = self._cursor_mode()
        pt = raw
        if mode == "point":
            r = self.manager.req
            base = self.manager.rubber_base
            no_snap = getattr(r, "no_snap", False)
            if not no_snap:
                override = self.osnap_override
                hit = self.snap.find(raw, self.px(self.aperture), base, override)
                if hit:
                    self.snap_hit = hit
                    pt = hit[1]
            if self.snap_hit is None:
                if base is not None and self.ortho:
                    d = raw - base
                    pt = base + (Vec2(d.x, 0) if abs(d.x) >= abs(d.y) else Vec2(0, d.y))
                elif base is not None and self.polar:
                    d = raw - base
                    if d.magnitude > 1e-12:
                        ang = math.degrees(d.angle)
                        inc = self.polar_inc or 45.0
                        k = round(ang / inc) * inc
                        tol = math.degrees(math.atan2(self.px(8), d.magnitude)) + 1.0
                        if abs(ang - k) <= max(tol, 2.0):
                            u = Vec2.from_deg_angle(k)
                            pt = base + u * d.dot(u)
                            self.track_info = (base, k)
                if self.snap_grid and pt is raw:
                    g = self.grid_unit
                    pt = Vec2(round(raw.x / g) * g, round(raw.y / g) * g)
        self.cursor_world = pt
        if mode in ("idle", "pick") and self.window_start is None:
            h = self.pick(sp)
            if h != self.hover:
                self.hover = h
        else:
            self.hover = None
        self.cursor_moved.emit(pt.x, pt.y)
        self.update()

    def constrained_direction(self, base: Vec2) -> Optional[Vec2]:
        d = self.cursor_world - base
        if d.magnitude < 1e-12:
            return None
        return d.normalize()

    # ------------------------------------------------------------ selection
    def set_selection(self, handles, add=False):
        if add:
            for h in handles:
                if h not in self.selection:
                    self.selection.append(h)
        else:
            self.selection = list(dict.fromkeys(handles))
        self.selection_dirty()
        self.selection_changed.emit()

    def remove_from_selection(self, handles):
        hs = set(handles)
        self.selection = [h for h in self.selection if h not in hs]
        self.selection_dirty()
        self.selection_changed.emit()

    def clear_selection(self):
        if self.selection:
            self.selection = []
            self.selection_dirty()
            self.selection_changed.emit()

    def prune_selection(self):
        doc = self.tab.doc
        sel = [h for h in self.selection if doc.entity_by_handle(h) is not None
               and doc.entity_by_handle(h).dxf.owner == doc.msp.layout_key]
        if sel != self.selection:
            self.selection = sel
            self.selection_changed.emit()
        self.selection_dirty()

    def _finish_window(self, end_sp: QPointF):
        a = self.window_start
        b = self.to_world(end_sp)
        crossing = end_sp.x() < self.to_screen(a).x()
        x0, x1 = sorted((a.x, b.x))
        y0, y1 = sorted((a.y, b.y))
        hs = self.renderer.select_window(x0, y0, x1, y1, crossing)
        hs = [h for h in hs if not self._locked(h)]
        self.window_start = None
        self.window_press_screen = None
        self._apply_pick(hs)

    def _apply_pick(self, hs):
        from PySide6.QtWidgets import QApplication
        mods = QApplication.keyboardModifiers()
        if (mods & Qt.ShiftModifier) or self.sel_remove_mode:
            self.remove_from_selection(hs)
        else:
            self.set_selection(hs, add=True)
        r = self.manager.req
        if isinstance(r, GetSelection):
            self.tab.ctx.print(f"{len(hs)} bulundu, toplam {len(self.selection)}")
            if r.single and self.selection:
                self.manager.send(self.tab.ctx.end_selection())

    # ------------------------------------------------------------ events
    def resizeEvent(self, ev):
        self.invalidate()
        super().resizeEvent(ev)

    def enterEvent(self, ev):
        self.inside = True
        self.update()

    def leaveEvent(self, ev):
        self.inside = False
        self.hover = None
        self.update()

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        if delta == 0:
            return
        f = 1.25 if delta > 0 else 1 / 1.25
        self.zoom_factor(f, ev.position())
        self.update_cursor(ev.position())

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MiddleButton:
            self.zoom_extents()
            return
        if ev.button() == Qt.LeftButton and self.manager.req is None:
            h = self.pick(ev.position())
            if h:
                self.tab.edit_entity(h)
                return
        self.mousePressEvent(ev)

    def mousePressEvent(self, ev):
        self.setFocus()
        pos = ev.position()
        btn = ev.button()
        if btn == Qt.MiddleButton:
            self.pan_last = pos
            self.setCursor(Qt.ClosedHandCursor)
            return
        if btn == Qt.RightButton:
            if ev.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier):
                self.tab.osnap_menu(ev.globalPosition().toPoint())
                return
            if self.window_start is not None:
                self.window_start = None
                self.update()
                return
            if self.realtime_pan:
                self.realtime_pan = False
                self.manager.cancel(quiet=True)
                return
            if self.manager.active:
                self.manager.enter()
            else:
                self.tab.context_menu(ev.globalPosition().toPoint())
            return
        if btn != Qt.LeftButton:
            return
        if self.realtime_pan:
            self.pan_last = pos
            return
        self.update_cursor(pos)
        r = self.manager.req
        mode = self._cursor_mode()
        if mode == "point":
            pt = self.cursor_world
            self.osnap_override = None
            self.manager.point_input(pt)
            self.update_cursor(pos)
            return
        if isinstance(r, GetEntity):
            h = self.pick(pos)
            if not h:
                self.tab.ctx.print("Nesne bulunamadı.")
                return
            e = self.tab.doc.entity_by_handle(h)
            if r.types and e.dxftype() not in r.types:
                self.tab.ctx.print(f"Bu nesne türü desteklenmiyor ({e.dxftype()}).")
                return
            self.manager.send((e, self.to_world(pos)))
            self.update_cursor(pos)
            return
        # idle or selection
        if mode == "idle" and self.selection and not (ev.modifiers() & Qt.ShiftModifier):
            g = self._grip_at(pos)
            if g is not None:
                handle, gp, key = g
                self.tab.start_grip_edit(handle, gp, key)
                self.update_cursor(pos)
                return
        if self.window_start is not None:
            self._finish_window(pos)
            self.update()
            return
        h = self.pick(pos)
        if h:
            self._apply_pick([h])
            self.update()
            return
        self.window_start = self.to_world(pos)
        self.window_press_screen = pos
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MiddleButton or (self.realtime_pan and ev.button() == Qt.LeftButton):
            self.pan_last = None
            self.setCursor(Qt.BlankCursor)
            self.invalidate()
            return
        if ev.button() == Qt.LeftButton and self.window_start is not None and self.window_press_screen is not None:
            d = ev.position() - self.window_press_screen
            if abs(d.x()) + abs(d.y()) > 8:
                self._finish_window(ev.position())
                self.update()

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        if self.pan_last is not None:
            d = pos - self.pan_last
            self.pan_last = pos
            self.cx -= d.x() / self.scale
            self.cy += d.y() / self.scale
            self.invalidate()
            self.cursor_screen = pos
            return
        self.update_cursor(pos)

    def _grip_at(self, sp: QPointF):
        if len(self.selection) > settings.get_int("grip_limit", 200):
            return None
        best = None
        for h in self.selection:
            e = self.tab.doc.entity_by_handle(h)
            if e is None or self._locked(h):
                continue
            for gp, key in entity_grips(e):
                s = self.to_screen(gp)
                d = abs(s.x() - sp.x()) + abs(s.y() - sp.y())
                if d <= 10 and (best is None or d < best[0]):
                    best = (d, h, gp, key)
        if best:
            return best[1], best[2], best[3]
        return None

    def keyPressEvent(self, ev):
        self.tab.key_press(ev)
