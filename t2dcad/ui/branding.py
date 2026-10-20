"""T2D-CAD logo, colors and splash screen (TDD Technic palette)."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QPainter, QColor, QPixmap, QIcon, QLinearGradient, QRadialGradient, QFont, QPen,
                           QBrush, QPainterPath)

from t2dcad import APP_NAME, __version__

BLUE = QColor(47, 98, 153)       # TDD Technic blue
BLUE_LIGHT = QColor(110, 160, 215)
ORANGE = QColor(220, 110, 45)    # TDD Technic orange
NAVY = QColor(18, 36, 60)
NAVY2 = QColor(30, 62, 100)
WHITE = QColor(255, 255, 255)


def draw_logo(p: QPainter, rect: QRectF, disc: bool = True, alpha: int = 255) -> None:
    """2D CAD mark: ring with four ticks, orange crosshair arms and a pickbox."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    c = rect.center()
    R = min(rect.width(), rect.height()) / 2
    blue = QColor(BLUE)
    blue.setAlpha(alpha)
    orange = QColor(ORANGE)
    orange.setAlpha(alpha)
    if disc:
        w = QColor(WHITE)
        w.setAlpha(alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(w)
        p.drawEllipse(c, R, R)
    ring_w = R * 0.13
    r_mid = R - ring_w / 2 - (R * 0.03 if disc else 0)
    pen = QPen(blue, ring_w)
    pen.setCapStyle(Qt.FlatCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c, r_mid, r_mid)
    # four ticks pointing inwards (like the TDD Technic spokes)
    r_in = r_mid - ring_w / 2
    tick_len = R * 0.13
    tick_w = R * 0.07
    p.setPen(Qt.NoPen)
    p.setBrush(blue)
    for k in range(4):
        p.save()
        p.translate(c)
        p.rotate(90 * k)
        p.drawRect(QRectF(-tick_w / 2, -r_in - 1, tick_w, tick_len + 1))
        p.restore()
    # orange crosshair arms (blocks)
    gap = R * 0.24
    arm_len = R * 0.40
    arm_w = R * 0.24
    p.setBrush(orange)
    for k in range(4):
        p.save()
        p.translate(c)
        p.rotate(90 * k + 45)
        p.drawRect(QRectF(-arm_w / 2, -(gap + arm_len), arm_w, arm_len))
        p.restore()
    # pickbox in the centre
    box = R * 0.30
    pen = QPen(blue, R * 0.06)
    pen.setJoinStyle(Qt.MiterJoin)
    p.setPen(pen)
    p.setBrush(QColor(255, 255, 255, alpha) if disc else Qt.NoBrush)
    p.drawRect(QRectF(c.x() - box / 2, c.y() - box / 2, box, box))
    p.restore()


def logo_pixmap(size: int = 256, disc: bool = True) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_logo(p, QRectF(2, 2, size - 4, size - 4), disc)
    p.end()
    return pm


_icon = None


def logo_icon() -> QIcon:
    global _icon
    if _icon is None:
        ic = QIcon()
        for s in (16, 24, 32, 48, 64, 128, 256):
            ic.addPixmap(logo_pixmap(s))
        _icon = ic
    return _icon


def draw_wordmark(p: QPainter, x: float, baseline: float, px: int) -> float:
    """'T2D' white + '-CAD' orange. Returns the end x."""
    f = QFont("Segoe UI")
    f.setPixelSize(px)
    f.setWeight(QFont.Black)
    p.setFont(f)
    fm = p.fontMetrics()
    p.setPen(WHITE)
    p.drawText(QPointF(x, baseline), "T2D")
    x2 = x + fm.horizontalAdvance("T2D")
    p.setPen(ORANGE)
    p.drawText(QPointF(x2, baseline), "-CAD")
    return x2 + fm.horizontalAdvance("-CAD")


def splash_pixmap(w: int = 720, h: int = 405, scale: float = 2.0) -> QPixmap:
    pm = QPixmap(int(w * scale), int(h * scale))
    pm.setDevicePixelRatio(scale)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0.0, QColor(14, 30, 52))
    g.setColorAt(1.0, QColor(31, 66, 106))
    p.fillRect(QRectF(0, 0, w, h), g)
    # drafting grid
    for i, step in enumerate((20, 100)):
        p.setPen(QPen(QColor(255, 255, 255, 14 if i == 0 else 26), 1))
        x = 0
        while x <= w:
            p.drawLine(QPointF(x, 0), QPointF(x, h))
            x += step
        y = 0
        while y <= h:
            p.drawLine(QPointF(0, y), QPointF(w, y))
            y += step
    # big watermark logo on the right
    draw_logo(p, QRectF(w - 300, h / 2 - 190, 380, 380), disc=False, alpha=40)
    # dimension line decoration
    p.setPen(QPen(QColor(255, 255, 255, 60), 1))
    p.drawLine(QPointF(48, 330), QPointF(470, 330))
    for xx in (48, 470):
        p.drawLine(QPointF(xx, 322), QPointF(xx, 338))
    # logo
    draw_logo(p, QRectF(48, 98, 116, 116), disc=True)
    end = draw_wordmark(p, 188, 186, 74)
    f = QFont("Segoe UI")
    f.setPixelSize(17)
    p.setFont(f)
    p.setPen(QColor(200, 214, 232))
    p.drawText(QPointF(192, 216), "2B Teknik Çizim  ·  DWG / DXF Düzenleme")
    p.fillRect(QRectF(48, 246, 120, 4), ORANGE)
    f.setPixelSize(14)
    p.setFont(f)
    p.setPen(QColor(235, 240, 248))
    p.drawText(QPointF(48, 280), "Çizim  ·  Düzenleme  ·  Ölçülendirme  ·  Katmanlar  ·  Çizdirme")
    f.setPixelSize(12)
    p.setFont(f)
    p.setPen(QColor(170, 185, 205))
    p.drawText(QPointF(48, h - 22), f"Sürüm {__version__}")
    p.drawText(QRectF(w - 260, h - 36, 236, 20), Qt.AlignRight | Qt.AlignVCenter, f"© 2026 {APP_NAME}")
    p.fillRect(QRectF(0, h - 5, w, 5), ORANGE)
    p.end()
    return pm
