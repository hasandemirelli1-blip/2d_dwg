"""T2D-CAD logo, colors and splash screen (TDD Technic palette)."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QPainter, QColor, QPixmap, QIcon, QLinearGradient, QFont, QPen, QPainterPath,
                           QPolygonF)

from t2dcad import APP_NAME, __version__
from t2dcad.i18n import tr

BLUE = QColor(47, 98, 153)       # TDD Technic blue
BLUE_DARK = QColor(31, 66, 108)
ORANGE = QColor(220, 110, 45)    # TDD Technic orange
NAVY = QColor(24, 40, 62)
PAPER = QColor(246, 244, 239)
WHITE = QColor(255, 255, 255)


def draw_logo(p: QPainter, rect: QRectF, mono: bool = False) -> None:
    """App mark: blue tile, orange drafting corner (L) and a white line with
    grip squares - "a line drawn in 2D"."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    s = min(rect.width(), rect.height())
    x0 = rect.center().x() - s / 2
    y0 = rect.center().y() - s / 2

    def P(u, v):
        return QPointF(x0 + u * s, y0 + v * s)

    tile = QRectF(x0 + s * 0.03, y0 + s * 0.03, s * 0.94, s * 0.94)
    g = QLinearGradient(tile.topLeft(), tile.bottomRight())
    g.setColorAt(0, QColor(58, 116, 178))
    g.setColorAt(1, BLUE_DARK)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(tile, s * 0.2, s * 0.2)
    # orange drafting corner (x/y axes)
    pen = QPen(ORANGE, s * 0.1)
    pen.setCapStyle(Qt.SquareCap)
    pen.setJoinStyle(Qt.MiterJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF([P(0.25, 0.27), P(0.25, 0.75), P(0.73, 0.75)]))
    # white line with grips
    pen = QPen(WHITE, s * 0.065)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    a, b = P(0.42, 0.58), P(0.76, 0.24)
    p.drawLine(a, b)
    g_size = s * 0.13
    p.setPen(QPen(BLUE_DARK, max(1.0, s * 0.03)))
    p.setBrush(WHITE)
    for c in (a, b):
        p.drawRect(QRectF(c.x() - g_size / 2, c.y() - g_size / 2, g_size, g_size))
    p.restore()


def logo_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_logo(p, QRectF(0, 0, size, size))
    p.end()
    return pm


_icon = None


def logo_icon() -> QIcon:
    global _icon
    if _icon is None:
        ic = QIcon()
        for s in (16, 20, 24, 32, 48, 64, 128, 256):
            ic.addPixmap(logo_pixmap(s))
        _icon = ic
    return _icon


def draw_wordmark(p: QPainter, x: float, baseline: float, px: int, dark: bool = True) -> float:
    """'T2D' bold + 'CAD' light orange with letter spacing. Returns end x."""
    f = QFont("Segoe UI")
    f.setPixelSize(px)
    f.setWeight(QFont.Bold)
    p.setFont(f)
    p.setPen(NAVY if dark else WHITE)
    p.drawText(QPointF(x, baseline), "T2D")
    x2 = x + p.fontMetrics().horizontalAdvance("T2D") + px * 0.12
    f2 = QFont("Segoe UI")
    f2.setPixelSize(px)
    f2.setWeight(QFont.Light)
    f2.setLetterSpacing(QFont.AbsoluteSpacing, px * 0.04)
    p.setFont(f2)
    p.setPen(ORANGE)
    p.drawText(QPointF(x2, baseline), "CAD")
    return x2 + p.fontMetrics().horizontalAdvance("CAD")


# ---------------------------------------------------------------- splash
def _arrow(p: QPainter, tip: QPointF, direction: float, size: float):
    a1 = direction + math.radians(160)
    a2 = direction - math.radians(160)
    pts = [tip, tip + QPointF(math.cos(a1) * size, math.sin(a1) * size),
           tip + QPointF(math.cos(a2) * size, math.sin(a2) * size)]
    p.drawPolygon(QPolygonF(pts))


def _dim_h(p, x1, x2, y, y_ref, text, color):
    p.setPen(QPen(color, 0.9))
    p.drawLine(QPointF(x1, y_ref + (2 if y > y_ref else -2)), QPointF(x1, y + (4 if y > y_ref else -4)))
    p.drawLine(QPointF(x2, y_ref + (2 if y > y_ref else -2)), QPointF(x2, y + (4 if y > y_ref else -4)))
    p.drawLine(QPointF(x1, y), QPointF(x2, y))
    p.setBrush(color)
    _arrow(p, QPointF(x1, y), math.pi, 7)
    _arrow(p, QPointF(x2, y), 0, 7)
    f = QFont("Segoe UI")
    f.setPixelSize(11)
    p.setFont(f)
    p.drawText(QRectF(x1, y - 16, x2 - x1, 14), Qt.AlignCenter, text)


def _dim_v(p, y1, y2, x, x_ref, text, color):
    p.setPen(QPen(color, 0.9))
    p.drawLine(QPointF(x_ref + 2, y1), QPointF(x + 4, y1))
    p.drawLine(QPointF(x_ref + 2, y2), QPointF(x + 4, y2))
    p.drawLine(QPointF(x, y1), QPointF(x, y2))
    p.setBrush(color)
    _arrow(p, QPointF(x, y1), -math.pi / 2, 7)
    _arrow(p, QPointF(x, y2), math.pi / 2, 7)
    p.save()
    p.translate(x + 14, (y1 + y2) / 2)
    p.rotate(-90)
    f = QFont("Segoe UI")
    f.setPixelSize(11)
    p.setFont(f)
    p.drawText(QRectF(-40, -12, 80, 14), Qt.AlignCenter, text)
    p.restore()


def _technical_drawing(p: QPainter, ox: float, oy: float):
    """A small flange plate drawing with centre lines and dimensions."""
    line = QColor(40, 78, 125)
    dim = QColor(90, 120, 155)
    center = QColor(220, 110, 45, 200)
    w, h = 230, 150
    # plate outline with rounded corners
    p.setPen(QPen(line, 1.8))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(ox, oy, w, h), 14, 14)
    # big bore + holes
    cx, cy = ox + w / 2, oy + h / 2
    p.drawEllipse(QPointF(cx, cy), 38, 38)
    p.drawEllipse(QPointF(cx, cy), 26, 26)
    holes = [(ox + 26, oy + 26), (ox + w - 26, oy + 26), (ox + 26, oy + h - 26), (ox + w - 26, oy + h - 26)]
    for hx, hy in holes:
        p.drawEllipse(QPointF(hx, hy), 9, 9)
    # centre lines (dash-dot)
    pen = QPen(center, 0.9, Qt.DashDotLine)
    p.setPen(pen)
    p.drawLine(QPointF(ox - 14, cy), QPointF(ox + w + 14, cy))
    p.drawLine(QPointF(cx, oy - 14), QPointF(cx, oy + h + 14))
    for hx, hy in holes:
        p.drawLine(QPointF(hx - 14, hy), QPointF(hx + 14, hy))
        p.drawLine(QPointF(hx, hy - 14), QPointF(hx, hy + 14))
    # dimensions
    _dim_h(p, ox, ox + w, oy + h + 30, oy + h, "230", dim)
    _dim_h(p, ox + 26, ox + w - 26, oy - 26, oy + 26, "178", dim)
    _dim_v(p, oy, oy + h, ox + w + 28, ox + w, "150", dim)
    # diameter of the bore
    f = QFont("Segoe UI")
    f.setPixelSize(11)
    p.setFont(f)
    p.setPen(dim)
    p.drawText(QRectF(cx - 24, cy - 20, 22, 14), Qt.AlignCenter, "Ø76")


def splash_pixmap(w: int = 720, h: int = 420, scale: float = 2.0, progress: float = 0.0,
                  message: str = "") -> QPixmap:
    pm = QPixmap(int(w * scale), int(h * scale))
    pm.setDevicePixelRatio(scale)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    # drawing sheet
    p.fillRect(QRectF(0, 0, w, h), PAPER)
    # light millimetre paper on the right part
    for step, alpha in ((10, 14), (50, 30)):
        p.setPen(QPen(QColor(47, 98, 153, alpha), 0.7))
        x = 330
        while x <= w:
            p.drawLine(QPointF(x, 0), QPointF(x, h))
            x += step
        y = 0
        while y <= h:
            p.drawLine(QPointF(330, y), QPointF(w, y))
            y += step
    # sheet border
    p.setPen(QPen(NAVY, 1.4))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(12, 12, w - 24, h - 24))
    _technical_drawing(p, 400, 100)
    # title block (bottom right)
    tb = QRectF(w - 262, h - 74, 250, 62)
    p.setPen(QPen(NAVY, 1.2))
    p.setBrush(QColor(255, 255, 255, 210))
    p.drawRect(tb)
    p.drawLine(QPointF(tb.left(), tb.top() + 26), QPointF(tb.right(), tb.top() + 26))
    p.drawLine(QPointF(tb.left() + 125, tb.top() + 26), QPointF(tb.left() + 125, tb.bottom()))
    f = QFont("Segoe UI")
    f.setPixelSize(12)
    f.setBold(True)
    p.setFont(f)
    p.setPen(NAVY)
    p.drawText(QRectF(tb.left() + 8, tb.top(), tb.width() - 16, 26), Qt.AlignVCenter | Qt.AlignLeft,
               tr(f"{APP_NAME}  ·  2B Teknik Çizim"))
    f.setBold(False)
    f.setPixelSize(10)
    p.setFont(f)
    p.drawText(QRectF(tb.left() + 8, tb.top() + 26, 117, 36), Qt.AlignVCenter, tr(f"Sürüm {__version__}"))
    p.drawText(QRectF(tb.left() + 133, tb.top() + 26, 110, 36), Qt.AlignVCenter, f"© 2026 {APP_NAME}")
    # left: identity
    draw_logo(p, QRectF(44, 70, 92, 92))
    draw_wordmark(p, 44, 228, 60, dark=True)
    f = QFont("Segoe UI")
    f.setPixelSize(15)
    p.setFont(f)
    p.setPen(QColor(85, 98, 115))
    p.drawText(QPointF(46, 256), tr("DWG / DXF çizim ve düzenleme"))
    p.fillRect(QRectF(46, 274, 54, 3), ORANGE)
    f.setPixelSize(12)
    p.setFont(f)
    p.setPen(QColor(105, 116, 130))
    for i, t in enumerate(tr(x) for x in ("Çizim ve düzenleme", "Ölçülendirme ve yazı", "Katmanlar ve bloklar",
                                          "Yazıcı ve PDF çıktısı")):
        y = 300 + i * 19
        p.setBrush(BLUE)
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(47, y - 7, 5, 5))
        p.setPen(QColor(95, 106, 120))
        p.drawText(QPointF(60, y), t)
    # progress
    if message:
        f.setPixelSize(11)
        p.setFont(f)
        p.setPen(QColor(120, 130, 142))
        p.drawText(QPointF(46, h - 30), message)
    p.fillRect(QRectF(12, h - 15, w - 24, 3), QColor(220, 215, 205))
    p.fillRect(QRectF(12, h - 15, (w - 24) * max(0.0, min(1.0, progress)), 3), ORANGE)
    p.end()
    return pm
