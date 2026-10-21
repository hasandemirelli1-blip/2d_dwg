"""Vector icons drawn with QPainter (no image files needed)."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QPolygonF, QFont, QBrush

FG = QColor(225, 228, 232)
ACC = QColor(90, 170, 255)
RED = QColor(240, 90, 80)
GRN = QColor(110, 200, 110)
YEL = QColor(240, 200, 60)

_cache: dict[str, QIcon] = {}


def _P(x, y):
    return QPointF(x, y)


def icon(name: str) -> QIcon:
    if name in _cache:
        return _cache[name]
    pm = QPixmap(48, 48)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(2, 2)
    pen = QPen(FG, 1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    fn = _DRAW.get(name)
    if fn:
        fn(p)
    else:
        p.setFont(QFont("Arial", 7, QFont.Bold))
        p.drawText(QRectF(0, 0, 24, 24), Qt.AlignCenter, name[:3].upper())
    p.end()
    ic = QIcon(pm)
    _cache[name] = ic
    return ic


def _pen(p, color, w=1.6, style=Qt.SolidLine):
    pen = QPen(color, w, style)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)


def _dot(p, x, y, color=ACC):
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRect(QRectF(x - 1.8, y - 1.8, 3.6, 3.6))
    p.restore()


def d_line(p):
    p.drawLine(_P(4, 20), _P(20, 4))
    _dot(p, 4, 20)
    _dot(p, 20, 4)


def d_pline(p):
    p.drawPolyline(QPolygonF([_P(3, 19), _P(9, 7), _P(15, 15)]))
    p.drawArc(QRectF(13, 5, 9, 12), -90 * 16, 180 * 16)
    _dot(p, 3, 19)
    _dot(p, 9, 7)


def d_circle(p):
    p.drawEllipse(QRectF(4, 4, 16, 16))
    _dot(p, 12, 12)


def d_arc(p):
    p.drawArc(QRectF(4, 6, 16, 16), 10 * 16, 160 * 16)
    _dot(p, 4.3, 12.5)
    _dot(p, 12, 6)
    _dot(p, 19.7, 12.5)


def d_rect(p):
    p.drawRect(QRectF(4, 6, 16, 12))
    _dot(p, 4, 18)
    _dot(p, 20, 6)


def d_polygon(p):
    pts = [QPointF(12 + 8 * math.cos(math.radians(90 + i * 60)), 12 - 8 * math.sin(math.radians(90 + i * 60)))
           for i in range(6)]
    p.drawPolygon(QPolygonF(pts))


def d_ellipse(p):
    p.drawEllipse(QRectF(3, 7, 18, 10))


def d_text(p):
    p.setFont(QFont("Times New Roman", 14, QFont.Bold))
    p.drawText(QRectF(0, 0, 24, 24), Qt.AlignCenter, "A")


def d_mtext(p):
    p.setFont(QFont("Arial", 9, QFont.Bold))
    p.drawText(QRectF(0, 1, 24, 10), Qt.AlignCenter, "Aa")
    for y in (14, 17, 20):
        p.drawLine(_P(5, y), _P(19, y))


def d_hatch(p):
    p.drawRect(QRectF(4, 4, 16, 16))
    _pen(p, ACC, 1)
    for k in range(-16, 16, 4):
        p.drawLine(_P(4 + max(0, k), 20 - max(0, -k)), _P(20 - max(0, -k), 4 + max(0, k)))


def d_point(p):
    p.drawEllipse(QRectF(9, 9, 6, 6))
    p.drawLine(_P(12, 4), _P(12, 20))
    p.drawLine(_P(4, 12), _P(20, 12))


def d_xline(p):
    p.drawLine(_P(1, 22), _P(23, 2))
    _dot(p, 12, 12)


def d_dimlinear(p):
    p.drawLine(_P(4, 6), _P(4, 18))
    p.drawLine(_P(20, 6), _P(20, 18))
    _pen(p, ACC)
    p.drawLine(_P(4, 10), _P(20, 10))
    p.drawPolygon(QPolygonF([_P(4, 10), _P(8, 8), _P(8, 12)]))
    p.drawPolygon(QPolygonF([_P(20, 10), _P(16, 8), _P(16, 12)]))


def d_dimaligned(p):
    p.drawLine(_P(4, 20), _P(9, 15))
    p.drawLine(_P(15, 9), _P(20, 4))
    _pen(p, ACC)
    p.drawLine(_P(3, 13), _P(13, 3))


def d_dimradius(p):
    p.drawArc(QRectF(2, 2, 20, 20), 0, 180 * 16)
    _pen(p, ACC)
    p.drawLine(_P(12, 12), _P(19, 5))
    _dot(p, 12, 12)


def d_dimangular(p):
    p.drawLine(_P(4, 20), _P(20, 20))
    p.drawLine(_P(4, 20), _P(16, 6))
    _pen(p, ACC)
    p.drawArc(QRectF(-6, 10, 20, 20), 0, 50 * 16)


def d_leader(p):
    p.drawLine(_P(4, 20), _P(12, 8))
    p.drawLine(_P(12, 8), _P(20, 8))
    p.setBrush(FG)
    p.drawPolygon(QPolygonF([_P(4, 20), _P(5, 15), _P(8, 17)]))


def d_erase(p):
    _pen(p, RED, 2.2)
    p.drawLine(_P(6, 6), _P(18, 18))
    p.drawLine(_P(18, 6), _P(6, 18))


def d_move(p):
    for a, b in ((_P(12, 3), _P(12, 21)), (_P(3, 12), _P(21, 12))):
        p.drawLine(a, b)
    for poly in ([_P(12, 2), _P(9, 6), _P(15, 6)], [_P(12, 22), _P(9, 18), _P(15, 18)],
                 [_P(2, 12), _P(6, 9), _P(6, 15)], [_P(22, 12), _P(18, 9), _P(18, 15)]):
        p.setBrush(FG)
        p.drawPolygon(QPolygonF(poly))


def d_copy(p):
    p.drawRect(QRectF(3, 3, 11, 11))
    _pen(p, ACC)
    p.drawRect(QRectF(10, 10, 11, 11))


def d_rotate(p):
    p.drawArc(QRectF(4, 4, 16, 16), 30 * 16, 280 * 16)
    p.setBrush(FG)
    p.drawPolygon(QPolygonF([_P(19, 6), _P(20, 11), _P(15, 9)]))


def d_scale(p):
    p.drawRect(QRectF(3, 11, 10, 10))
    _pen(p, ACC)
    p.drawRect(QRectF(3, 3, 18, 18))
    p.drawLine(_P(13, 11), _P(19, 5))


def d_mirror(p):
    _pen(p, ACC, 1, Qt.DashLine)
    p.drawLine(_P(12, 2), _P(12, 22))
    _pen(p, FG)
    p.drawPolygon(QPolygonF([_P(3, 18), _P(9, 18), _P(9, 6)]))
    _pen(p, ACC)
    p.drawPolygon(QPolygonF([_P(21, 18), _P(15, 18), _P(15, 6)]))


def d_offset(p):
    p.drawArc(QRectF(2, 6, 20, 20), 20 * 16, 140 * 16)
    _pen(p, ACC)
    p.drawArc(QRectF(7, 11, 10, 10), 20 * 16, 140 * 16)


def d_trim(p):
    p.drawLine(_P(12, 2), _P(12, 22))
    p.drawLine(_P(2, 12), _P(12, 12))
    _pen(p, RED, 1.4, Qt.DashLine)
    p.drawLine(_P(12, 12), _P(22, 12))


def d_extend(p):
    p.drawLine(_P(20, 2), _P(20, 22))
    p.drawLine(_P(2, 12), _P(10, 12))
    _pen(p, ACC, 1.4, Qt.DashLine)
    p.drawLine(_P(10, 12), _P(20, 12))


def d_fillet(p):
    p.drawLine(_P(4, 20), _P(4, 12))
    p.drawLine(_P(12, 4), _P(20, 4))
    _pen(p, ACC)
    p.drawArc(QRectF(4, 4, 16, 16), 90 * 16, 90 * 16)


def d_chamfer(p):
    p.drawLine(_P(4, 20), _P(4, 11))
    p.drawLine(_P(11, 4), _P(20, 4))
    _pen(p, ACC)
    p.drawLine(_P(4, 11), _P(11, 4))


def d_explode(p):
    for a, b in ((_P(12, 12), _P(12, 3)), (_P(12, 12), _P(20, 17)), (_P(12, 12), _P(4, 17)),
                 (_P(12, 12), _P(20, 6)), (_P(12, 12), _P(4, 6))):
        p.drawLine(a, b)
    _pen(p, YEL)
    p.drawEllipse(QRectF(9, 9, 6, 6))


def d_stretch(p):
    p.drawPolyline(QPolygonF([_P(3, 20), _P(3, 8), _P(12, 8)]))
    _pen(p, ACC)
    p.drawPolyline(QPolygonF([_P(12, 8), _P(21, 8), _P(21, 20)]))
    _pen(p, GRN, 1, Qt.DashLine)
    p.drawRect(QRectF(9, 4, 14, 18))


def d_array(p):
    for i in range(3):
        for j in range(3):
            p.drawRect(QRectF(3 + i * 7, 3 + j * 7, 4, 4))


def d_break(p):
    p.drawLine(_P(2, 12), _P(9, 12))
    p.drawLine(_P(15, 12), _P(22, 12))
    _dot(p, 9, 12, RED)
    _dot(p, 15, 12, RED)


def d_join(p):
    p.drawLine(_P(2, 16), _P(10, 8))
    p.drawLine(_P(14, 8), _P(22, 16))
    _pen(p, ACC)
    p.drawLine(_P(10, 8), _P(14, 8))


def d_new(p):
    p.drawPolygon(QPolygonF([_P(5, 2), _P(15, 2), _P(19, 6), _P(19, 22), _P(5, 22)]))
    p.drawPolyline(QPolygonF([_P(15, 2), _P(15, 6), _P(19, 6)]))


def d_open(p):
    _pen(p, YEL)
    p.drawPolygon(QPolygonF([_P(2, 6), _P(9, 6), _P(11, 8), _P(20, 8), _P(20, 20), _P(2, 20)]))


def d_save(p):
    p.drawRect(QRectF(3, 3, 18, 18))
    p.drawRect(QRectF(7, 3, 10, 6))
    _pen(p, ACC)
    p.drawRect(QRectF(6, 13, 12, 8))


def d_print(p):
    p.drawRect(QRectF(3, 9, 18, 9))
    p.drawRect(QRectF(7, 3, 10, 6))
    p.drawRect(QRectF(7, 15, 10, 7))


def d_undo(p):
    p.drawArc(QRectF(5, 6, 15, 13), 90 * 16, -200 * 16)
    p.setBrush(FG)
    p.drawPolygon(QPolygonF([_P(4, 8), _P(10, 4), _P(10, 11)]))


def d_redo(p):
    p.drawArc(QRectF(4, 6, 15, 13), 90 * 16, 200 * 16)
    p.setBrush(FG)
    p.drawPolygon(QPolygonF([_P(20, 8), _P(14, 4), _P(14, 11)]))


def d_zoomext(p):
    p.drawEllipse(QRectF(3, 3, 13, 13))
    p.drawLine(_P(14, 14), _P(21, 21))
    _pen(p, ACC, 1.2)
    p.drawRect(QRectF(6.5, 6.5, 6, 6))


def d_zoomwin(p):
    p.drawEllipse(QRectF(3, 3, 13, 13))
    p.drawLine(_P(14, 14), _P(21, 21))
    _pen(p, GRN, 1.2, Qt.DashLine)
    p.drawRect(QRectF(6, 7, 7, 5))


def d_zoomprev(p):
    p.drawEllipse(QRectF(3, 3, 13, 13))
    p.drawLine(_P(14, 14), _P(21, 21))
    _pen(p, ACC, 1.4)
    p.drawLine(_P(6, 9.5), _P(13, 9.5))


def d_pan(p):
    p.drawPolyline(QPolygonF([_P(7, 21), _P(5, 13), _P(7, 12), _P(9, 15), _P(9, 5), _P(11, 5),
                              _P(11, 12), _P(11, 4), _P(13, 4), _P(13, 12), _P(13, 5), _P(15, 5),
                              _P(15, 13), _P(15, 7), _P(17, 7), _P(17, 16), _P(15, 21)]))


def d_layer(p):
    for i, c in enumerate((ACC, GRN, YEL)):
        _pen(p, c)
        y = 6 + i * 5
        p.drawPolygon(QPolygonF([_P(12, y - 3), _P(21, y + 1), _P(12, y + 5), _P(3, y + 1)]))


def d_properties(p):
    p.drawRect(QRectF(3, 3, 18, 18))
    for y in (8, 12, 16):
        p.drawLine(_P(6, y), _P(10, y))
        _pen(p, ACC)
        p.drawLine(_P(12, y), _P(18, y))
        _pen(p, FG)


def d_matchprop(p):
    p.drawRect(QRectF(13, 3, 7, 7))
    p.drawLine(_P(16.5, 10), _P(16.5, 13))
    p.drawLine(_P(16.5, 13), _P(8, 13))
    _pen(p, YEL, 3)
    p.drawLine(_P(8, 13), _P(8, 21))


def d_block(p):
    p.drawRect(QRectF(3, 3, 12, 12))
    _pen(p, ACC)
    p.drawEllipse(QRectF(9, 9, 12, 12))


def d_insert(p):
    p.drawRect(QRectF(9, 3, 12, 12))
    _pen(p, ACC, 2)
    p.drawLine(_P(3, 21), _P(11, 13))
    p.drawLine(_P(11, 13), _P(6, 13))
    p.drawLine(_P(11, 13), _P(11, 18))


def d_dist(p):
    p.drawLine(_P(3, 18), _P(21, 18))
    for x in range(3, 22, 3):
        p.drawLine(_P(x, 18), _P(x, 14 if x % 6 == 0 else 16))
    _pen(p, ACC)
    p.drawLine(_P(3, 8), _P(21, 8))


_DRAW = {
    "line": d_line, "pline": d_pline, "circle": d_circle, "arc": d_arc, "rect": d_rect,
    "polygon": d_polygon, "ellipse": d_ellipse, "text": d_text, "mtext": d_mtext, "hatch": d_hatch,
    "point": d_point, "xline": d_xline, "dimlinear": d_dimlinear, "dimaligned": d_dimaligned,
    "dimradius": d_dimradius, "dimangular": d_dimangular, "leader": d_leader,
    "erase": d_erase, "move": d_move, "copy": d_copy, "rotate": d_rotate, "scale": d_scale,
    "mirror": d_mirror, "offset": d_offset, "trim": d_trim, "extend": d_extend, "fillet": d_fillet,
    "chamfer": d_chamfer, "explode": d_explode, "stretch": d_stretch, "array": d_array,
    "break": d_break, "join": d_join, "new": d_new, "open": d_open, "save": d_save,
    "print": d_print, "undo": d_undo, "redo": d_redo, "zoomext": d_zoomext, "zoomwin": d_zoomwin,
    "zoomprev": d_zoomprev, "pan": d_pan, "layer": d_layer, "properties": d_properties,
    "matchprop": d_matchprop, "block": d_block, "insert": d_insert, "dist": d_dist,
}


# ---------------------------------------------------------------- more icons
def _layers_base(p, dim=False):
    for i, c in enumerate((ACC, GRN, YEL)):
        _pen(p, QColor(130, 135, 140) if dim else c, 1.3)
        y = 9 + i * 4
        p.drawPolygon(QPolygonF([_P(9, y - 3), _P(17, y + 1), _P(9, y + 5), _P(1, y + 1)]))


def _badge(p, kind):
    """Small status badge drawn on the right of layer icons."""
    p.save()
    if kind == "check":
        _pen(p, GRN, 2.2)
        p.drawPolyline(QPolygonF([_P(14, 6), _P(17, 9), _P(23, 2)]))
    elif kind in ("bulb", "bulboff"):
        on = kind == "bulb"
        _pen(p, YEL if on else QColor(140, 140, 140), 1.3)
        p.setBrush(YEL if on else Qt.NoBrush)
        p.drawEllipse(QRectF(16, 1, 7, 7))
        p.setBrush(Qt.NoBrush)
        p.drawLine(_P(18, 9), _P(21, 9))
        if not on:
            _pen(p, RED, 1.6)
            p.drawLine(_P(15, 1), _P(23, 9))
    elif kind in ("lock", "unlock"):
        _pen(p, YEL, 1.3)
        p.drawRect(QRectF(16, 5, 7, 5))
        if kind == "lock":
            p.drawArc(QRectF(17, 1, 5, 7), 0, 180 * 16)
        else:
            p.drawArc(QRectF(19, 0, 5, 7), 0, 180 * 16)
    elif kind in ("freeze", "thaw"):
        _pen(p, QColor(140, 200, 255) if kind == "freeze" else YEL, 1.3)
        for a in (0, 60, 120):
            v = math.radians(a)
            p.drawLine(_P(19.5 - 4 * math.cos(v), 5 - 4 * math.sin(v)), _P(19.5 + 4 * math.cos(v), 5 + 4 * math.sin(v)))
    elif kind == "iso":
        _pen(p, ACC, 1.6)
        p.drawEllipse(QRectF(15, 1, 8, 8))
        _dot(p, 19, 5, ACC)
    elif kind == "uniso":
        _pen(p, ACC, 1.6, Qt.DashLine)
        p.drawEllipse(QRectF(15, 1, 8, 8))
    elif kind == "arrow":
        _pen(p, GRN, 1.8)
        p.drawLine(_P(14, 5), _P(22, 5))
        p.drawPolyline(QPolygonF([_P(19, 2), _P(22, 5), _P(19, 8)]))
    p.restore()


def _layer_icon(kind, dim=False):
    def f(p):
        _layers_base(p, dim)
        _badge(p, kind)
    return f


def d_brp(p):
    p.drawLine(_P(2, 12), _P(22, 12))
    _dot(p, 12, 12, RED)
    _pen(p, RED, 1.2)
    p.drawLine(_P(12, 5), _P(12, 19))


def d_align(p):
    p.drawRect(QRectF(3, 11, 9, 9))
    _pen(p, ACC)
    p.drawPolygon(QPolygonF([_P(14, 2), _P(22, 5), _P(19, 13), _P(11, 10)]))
    _pen(p, GRN, 1.2, Qt.DashLine)
    p.drawLine(_P(12, 11), _P(11, 10))
    p.drawLine(_P(3, 11), _P(14, 2))


def d_area(p):
    p.setBrush(QColor(90, 170, 255, 70))
    p.drawPolygon(QPolygonF([_P(3, 19), _P(6, 5), _P(16, 3), _P(21, 13), _P(13, 21)]))


def d_list(p):
    p.drawRect(QRectF(4, 3, 16, 18))
    _pen(p, ACC, 1.3)
    for y in (8, 12, 16):
        p.drawLine(_P(7, y), _P(17, y))


def d_id(p):
    p.drawLine(_P(12, 4), _P(12, 20))
    p.drawLine(_P(4, 12), _P(20, 12))
    _dot(p, 12, 12, YEL)
    p.setFont(QFont("Arial", 5, QFont.Bold))
    p.drawText(QRectF(13, 1, 11, 8), Qt.AlignCenter, "XY")


def d_selall(p):
    _pen(p, GRN, 1.2, Qt.DashLine)
    p.drawRect(QRectF(2, 2, 20, 20))
    _pen(p, FG)
    p.drawLine(_P(5, 18), _P(11, 6))
    p.drawEllipse(QRectF(12, 11, 7, 7))


def d_paste(p):
    p.drawRect(QRectF(4, 4, 14, 18))
    _pen(p, YEL)
    p.drawRect(QRectF(8, 2, 6, 4))
    _pen(p, ACC)
    p.drawRect(QRectF(10, 10, 11, 12))


def d_copyclip(p):
    p.drawRect(QRectF(3, 3, 12, 14))
    _pen(p, ACC)
    p.drawRect(QRectF(9, 8, 12, 14))


def d_copybase(p):
    d_copyclip(p)
    _dot(p, 9, 22, YEL)


def d_cut(p):
    p.drawEllipse(QRectF(3, 15, 6, 6))
    p.drawEllipse(QRectF(15, 15, 6, 6))
    p.drawLine(_P(8, 16), _P(17, 3))
    p.drawLine(_P(16, 16), _P(7, 3))


def d_tstyle(p):
    p.setFont(QFont("Times New Roman", 12, QFont.Bold))
    p.drawText(QRectF(0, 0, 16, 18), Qt.AlignCenter, "A")
    _pen(p, ACC, 1.3)
    p.drawLine(_P(14, 14), _P(22, 14))
    p.drawLine(_P(14, 18), _P(22, 18))
    p.drawLine(_P(14, 22), _P(22, 22))


def d_dimstyle(p):
    p.drawLine(_P(3, 4), _P(3, 14))
    p.drawLine(_P(21, 4), _P(21, 14))
    _pen(p, ACC)
    p.drawLine(_P(3, 9), _P(21, 9))
    _pen(p, YEL, 1.3)
    p.drawLine(_P(6, 18), _P(18, 18))
    p.drawLine(_P(6, 22), _P(18, 22))


def d_dimdiameter(p):
    p.drawEllipse(QRectF(3, 3, 18, 18))
    _pen(p, ACC)
    p.drawLine(_P(6, 18), _P(18, 6))


def d_dimcontinue(p):
    for x in (2, 12, 22):
        p.drawLine(_P(x, 8), _P(x, 20))
    _pen(p, ACC)
    p.drawLine(_P(2, 12), _P(22, 12))


def d_dimbaseline(p):
    for x in (2, 12, 22):
        p.drawLine(_P(x, 4), _P(x, 22))
    _pen(p, ACC)
    p.drawLine(_P(2, 10), _P(12, 10))
    p.drawLine(_P(2, 17), _P(22, 17))


def d_lengthen(p):
    p.drawLine(_P(2, 16), _P(14, 8))
    _pen(p, ACC, 1.4, Qt.DashLine)
    p.drawLine(_P(14, 8), _P(22, 3))


def d_image(p):
    p.drawRect(QRectF(2, 4, 20, 16))
    _pen(p, GRN)
    p.drawPolyline(QPolygonF([_P(4, 18), _P(10, 11), _P(14, 15), _P(17, 12), _P(21, 17)]))
    _pen(p, YEL)
    p.drawEllipse(QRectF(14, 6, 4, 4))


def d_pdfimport(p):
    p.drawPolygon(QPolygonF([_P(5, 2), _P(15, 2), _P(19, 6), _P(19, 22), _P(5, 22)]))
    p.setPen(RED)
    p.setFont(QFont("Arial", 5, QFont.Bold))
    p.drawText(QRectF(5, 7, 14, 8), Qt.AlignCenter, "PDF")
    _pen(p, ACC, 1.8)
    p.drawLine(_P(12, 15), _P(12, 21))
    p.drawPolyline(QPolygonF([_P(9, 18), _P(12, 21), _P(15, 18)]))


def d_refedit(p):
    d_block(p)
    _pen(p, YEL, 2)
    p.drawLine(_P(13, 21), _P(22, 12))


def d_circle2p(p):
    p.drawEllipse(QRectF(4, 4, 16, 16))
    _dot(p, 4, 12)
    _dot(p, 20, 12)


def d_circle3p(p):
    p.drawEllipse(QRectF(4, 4, 16, 16))
    _dot(p, 12, 4)
    _dot(p, 5, 16)
    _dot(p, 19, 16)


def d_circlettr(p):
    p.drawEllipse(QRectF(7, 3, 12, 12))
    _pen(p, ACC)
    p.drawLine(_P(2, 15), _P(22, 15))
    p.drawLine(_P(7, 2), _P(7, 22))


def d_circlecd(p):
    p.drawEllipse(QRectF(4, 4, 16, 16))
    _pen(p, ACC)
    p.drawLine(_P(4, 12), _P(20, 12))
    _dot(p, 12, 12)


def d_arccse(p):
    p.drawArc(QRectF(4, 4, 16, 16), 0, 120 * 16)
    _pen(p, ACC, 1)
    p.drawLine(_P(12, 12), _P(20, 12))
    _dot(p, 12, 12)
    _dot(p, 20, 12)
    _dot(p, 8, 5.1)


def d_ray(p):
    p.drawLine(_P(4, 20), _P(23, 1))
    _dot(p, 4, 20)


def d_donut(p):
    p.setBrush(QColor(225, 228, 232, 90))
    path_outer = QRectF(3, 3, 18, 18)
    p.drawEllipse(path_outer)
    p.setBrush(QColor(43, 49, 57))
    p.drawEllipse(QRectF(8, 8, 8, 8))


def d_regen(p):
    p.drawArc(QRectF(4, 4, 16, 16), 40 * 16, 260 * 16)
    p.setBrush(FG)
    p.drawPolygon(QPolygonF([_P(18, 4), _P(19, 10), _P(13, 8)]))


def d_options(p):
    for a in range(0, 360, 45):
        v = math.radians(a)
        p.drawLine(_P(12 + 6 * math.cos(v), 12 + 6 * math.sin(v)), _P(12 + 9.5 * math.cos(v), 12 + 9.5 * math.sin(v)))
    p.drawEllipse(QRectF(6, 6, 12, 12))
    _pen(p, ACC)
    p.drawEllipse(QRectF(10, 10, 4, 4))


def d_help(p):
    p.drawEllipse(QRectF(2, 2, 20, 20))
    p.setFont(QFont("Arial", 11, QFont.Bold))
    p.drawText(QRectF(0, 0, 24, 24), Qt.AlignCenter, "?")


def d_pdf(p):
    p.drawPolygon(QPolygonF([_P(5, 2), _P(15, 2), _P(19, 6), _P(19, 22), _P(5, 22)]))
    p.setPen(RED)
    p.setFont(QFont("Arial", 6, QFont.Bold))
    p.drawText(QRectF(4, 8, 16, 10), Qt.AlignCenter, "PDF")


def d_saveas(p):
    d_save(p)
    _pen(p, YEL, 2)
    p.drawLine(_P(14, 22), _P(23, 13))


def d_purge(p):
    p.drawPolygon(QPolygonF([_P(6, 8), _P(18, 8), _P(16, 22), _P(8, 22)]))
    p.drawLine(_P(4, 6), _P(20, 6))
    p.drawLine(_P(10, 3), _P(14, 3))


_DRAW.update({
    "brp": d_brp, "align": d_align, "area": d_area, "list": d_list, "id": d_id, "selall": d_selall,
    "paste": d_paste, "copyclip": d_copyclip, "copybase": d_copybase, "cut": d_cut, "tstyle": d_tstyle,
    "dimstyle": d_dimstyle, "dimdiameter": d_dimdiameter, "dimcontinue": d_dimcontinue,
    "dimbaseline": d_dimbaseline, "lengthen": d_lengthen, "image": d_image, "pdfimport": d_pdfimport,
    "refedit": d_refedit, "circle2p": d_circle2p, "circle3p": d_circle3p, "circlettr": d_circlettr,
    "circlecd": d_circlecd, "arccse": d_arccse, "ray": d_ray, "donut": d_donut, "regen": d_regen,
    "options": d_options, "help": d_help, "pdf": d_pdf, "saveas": d_saveas, "purge": d_purge,
    "laymcur": _layer_icon("check"), "layoff": _layer_icon("bulboff"), "layon": _layer_icon("bulb"),
    "layiso": _layer_icon("iso"), "layuniso": _layer_icon("uniso"), "layfrz": _layer_icon("freeze"),
    "laythw": _layer_icon("thaw"), "laylck": _layer_icon("lock"), "layulk": _layer_icon("unlock"),
    "laymch": _layer_icon("arrow"),
})


def color_icon(color: QColor, size=14) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setPen(QColor(120, 120, 120))
    p.setBrush(color)
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return QIcon(pm)


def app_icon() -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(30, 90, 170))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 40, 40)
    pen = QPen(QColor(120, 190, 255), 10)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(40, 200), QPointF(216, 200))
    p.drawLine(QPointF(40, 200), QPointF(40, 60))
    p.setPen(QColor(255, 255, 255))
    f = QFont("Arial")
    f.setPixelSize(92)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(30, 40, 216, 150), Qt.AlignCenter, "T2D")
    p.end()
    return QIcon(pm)
