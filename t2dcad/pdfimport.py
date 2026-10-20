"""PDF import (like AutoCAD / progeCAD PDFIMPORT).

Vector paths of a PDF page become editable LINE / ARC / CIRCLE / ELLIPSE /
LWPOLYLINE entities, filled areas become SOLID hatches and text becomes TEXT.
Curves (cubic Bézier) are recognised as arcs/circles when possible."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from ezdxf.math import Vec2

from t2dcad import geom

PT_TO_MM = 25.4 / 72.0
VALID_LW = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158,
            200, 211]


@dataclass
class PdfImportOptions:
    page: int = 0
    scale: float = 1.0          # 1 = real paper size in mm
    vectors: bool = True
    fills: bool = True
    text: bool = True
    lineweights: bool = True
    join: bool = True           # join connected segments into polylines
    arcs: bool = True           # recognise arcs / circles
    colors: bool = True         # keep PDF colors (black/white -> color 7)
    layer_mode: str = "type"    # "type", "pdf" (PDF layers), "current"
    skip_white_fills: bool = True
    images: bool = True         # raster images (saved as PNG next to the PDF)


@dataclass
class ImportResult:
    entities: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def open_pdf(path: str):
    import pymupdf
    return pymupdf.open(path)


def page_size_mm(path: str, page: int) -> tuple[float, float, int]:
    doc = open_pdf(path)
    try:
        pg = doc[page]
        r = pg.rect  # rotated page rectangle
        return r.width * PT_TO_MM, r.height * PT_TO_MM, doc.page_count
    finally:
        doc.close()


# ---------------------------------------------------------------- geometry helpers
def _bez(p0, p1, p2, p3, t):
    mt = 1 - t
    return p0 * (mt ** 3) + p1 * (3 * mt * mt * t) + p2 * (3 * mt * t * t) + p3 * (t ** 3)


def _arc_from_bezier(p0, p1, p2, p3, tol):
    """Return (center, radius, signed sweep angle) or None."""
    pm = _bez(p0, p1, p2, p3, 0.5)
    res = geom.circle_3p(p0, pm, p3)
    if res is None:
        return None
    c, r = res
    if r <= 0 or r > 1e7:
        return None
    for t in (0.25, 0.75):
        if abs(_bez(p0, p1, p2, p3, t).distance(c) - r) > max(tol, r * 0.004):
            return None
    a0 = (p0 - c).angle
    am = (pm - c).angle
    a3 = (p3 - c).angle
    ccw = geom.norm_angle(a3 - a0)
    if geom.angle_in_arc(am, a0, a3):
        sweep = ccw
    else:
        sweep = -(math.tau - ccw)
    return c, r, sweep


def _flatten_bezier(p0, p1, p2, p3, tol):
    length = p0.distance(p1) + p1.distance(p2) + p2.distance(p3)
    n = max(4, min(64, int(length / max(tol * 20, 1e-9))))
    return [_bez(p0, p1, p2, p3, i / n) for i in range(1, n + 1)]


def _rgb(c) -> Optional[tuple[int, int, int]]:
    if c is None:
        return None
    if isinstance(c, (int, float)) and not isinstance(c, tuple):
        v = int(c)
        return (v >> 16) & 255, (v >> 8) & 255, v & 255
    if len(c) == 1:
        g = int(round(c[0] * 255))
        return g, g, g
    if len(c) == 4:  # CMYK
        cc, m, y, k = c
        return (int(255 * (1 - cc) * (1 - k)), int(255 * (1 - m) * (1 - k)), int(255 * (1 - y) * (1 - k)))
    return tuple(int(round(v * 255)) for v in c[:3])


def _lineweight(width_pt: float) -> int:
    mm100 = width_pt * PT_TO_MM * 100
    return min(VALID_LW, key=lambda v: abs(v - mm100))


# ---------------------------------------------------------------- importer
class PdfImporter:
    def __init__(self, cad_doc, opts: PdfImportOptions, base: Vec2, attribs: dict):
        self.cad = cad_doc
        self.doc = cad_doc.doc
        self.msp = cad_doc.msp
        self.opts = opts
        self.base = base
        self.default_attribs = attribs
        self.k = PT_TO_MM * opts.scale
        self.tol = 1e-4 * max(1.0, opts.scale)
        self.result = ImportResult()
        self._styles: dict[str, str] = {}

    # ------------------------------------------------------------ transforms
    def _setup_page(self, page):
        m = page.rotation_matrix
        self.height = page.rect.height
        # x' = a*x + c*y + e ; y' = b*x + d*y + f, then PDF (y down, pt) -> WCS (y up, mm)
        k = self.k
        self._m = (m.a * k, m.c * k, m.e * k + self.base.x,
                   -m.b * k, -m.d * k, (self.height - m.f) * k + self.base.y)

    def P(self, pt) -> Vec2:
        a, c, e, b, d, f = self._m
        x, y = pt.x, pt.y
        return Vec2(a * x + c * y + e, b * x + d * y + f)

    # ------------------------------------------------------------ attributes
    def _layer(self, kind: str, pdf_layer: Optional[str]) -> str:
        mode = self.opts.layer_mode
        if mode == "current":
            return self.default_attribs.get("layer", "0")
        if mode == "pdf" and pdf_layer:
            name = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in pdf_layer)[:200] or "PDF"
        else:
            name = {"geom": "PDF_Geometri", "fill": "PDF_Dolgu", "text": "PDF_Yazi", "image": "PDF_Resim"}[kind]
        if name not in self.doc.layers:
            self.doc.layers.add(name, color=7)
        return name

    def _attribs(self, kind, color, width, pdf_layer, dashes=None) -> dict:
        a = {"layer": self._layer(kind, pdf_layer)}
        rgb = _rgb(color)
        if self.opts.colors and rgb is not None:
            r, g, b = rgb
            if max(rgb) < 40 or min(rgb) > 215:
                a["color"] = 7
            else:
                from ezdxf.colors import rgb2int
                a["true_color"] = rgb2int((r, g, b))
                a["color"] = 7
        elif self.opts.layer_mode == "current" and "color" in self.default_attribs:
            a["color"] = self.default_attribs["color"]
        if self.opts.lineweights and width is not None and kind != "text":
            a["lineweight"] = _lineweight(width)
        if dashes and dashes.strip() not in ("[] 0", "[]0", "[] 0.0"):
            try:
                nums = [float(v) for v in dashes.split("]")[0].strip(" [").split()]
                period = sum(nums) * self.k
                if period > 0 and "DASHED" in self.doc.linetypes:
                    a["linetype"] = "DASHED"
                    a["ltscale"] = max(0.001, period / 0.75)
            except ValueError:
                pass
        return a

    def _add(self, e, kind):
        self.result.entities.append(e)
        self.result.counts[kind] = self.result.counts.get(kind, 0) + 1

    # ------------------------------------------------------------ paths
    def _runs(self, items):
        """Split path items into connected runs of primitives in WCS.
        Primitive: ("L", a, b) or ("C", a, c1, c2, b)."""
        runs, cur = [], []
        last = None
        for it in items:
            op = it[0]
            prims = []
            if op == "l":
                prims.append(("L", self.P(it[1]), self.P(it[2])))
            elif op == "c":
                prims.append(("C", self.P(it[1]), self.P(it[2]), self.P(it[3]), self.P(it[4])))
            elif op == "re":
                r = it[1]
                pts = [self.P(r.tl), self.P(r.tr), self.P(r.br), self.P(r.bl)]
                if cur:
                    runs.append(cur)
                runs.append([("L", pts[i], pts[(i + 1) % 4]) for i in range(4)])
                cur, last = [], None
                continue
            elif op == "qu":
                q = it[1]
                pts = [self.P(q.ul), self.P(q.ur), self.P(q.lr), self.P(q.ll)]
                if cur:
                    runs.append(cur)
                runs.append([("L", pts[i], pts[(i + 1) % 4]) for i in range(4)])
                cur, last = [], None
                continue
            for pr in prims:
                # skip a segment which only goes back over the previous one
                if cur and pr[0] == "L" and cur[-1][0] == "L" and pr[1].isclose(cur[-1][2], abs_tol=self.tol) \
                        and pr[2].isclose(cur[-1][1], abs_tol=self.tol):
                    continue
                start = pr[1]
                if last is not None and not start.isclose(last, abs_tol=self.tol * 10):
                    runs.append(cur)
                    cur = []
                cur.append(pr)
                last = pr[-1]
        if cur:
            runs.append(cur)
        return [r for r in runs if r]

    def _run_vertices(self, run):
        """[(point, bulge)] for a run, bezier arcs as bulges."""
        verts: list[list] = [[run[0][1], 0.0]]
        for pr in run:
            if pr[0] == "L":
                verts.append([pr[2], 0.0])
            else:
                a, c1, c2, b = pr[1], pr[2], pr[3], pr[4]
                arc = _arc_from_bezier(a, c1, c2, b, self.tol) if self.opts.arcs else None
                if arc is not None:
                    verts[-1][1] = math.tan(arc[2] / 4)
                    verts.append([b, 0.0])
                else:
                    for q in _flatten_bezier(a, c1, c2, b, self.tol):
                        verts.append([q, 0.0])
        # remove duplicate points
        out = [verts[0]]
        for v in verts[1:]:
            if v[0].isclose(out[-1][0], abs_tol=self.tol):
                out[-1][1] = out[-1][1] or v[1]
                continue
            out.append(v)
        return out

    def _circle_of_run(self, run, closed):
        if not closed or not all(p[0] == "C" for p in run) or not self.opts.arcs:
            return None
        arcs = [_arc_from_bezier(p[1], p[2], p[3], p[4], self.tol) for p in run]
        if any(a is None for a in arcs):
            return None
        c0, r0 = arcs[0][0], arcs[0][1]
        if any(a[0].distance(c0) > max(self.tol * 10, r0 * 0.01) or abs(a[1] - r0) > max(self.tol * 10, r0 * 0.01)
               for a in arcs):
            return None
        if abs(abs(sum(a[2] for a in arcs)) - math.tau) > 0.05:
            return None
        return c0, r0

    def _ellipse_of_run(self, run, closed):
        if not closed or len(run) != 4 or not all(p[0] == "C" for p in run):
            return None
        pts = [p[1] for p in run]
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        c = Vec2((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if w < self.tol or h < self.tol:
            return None
        # points must be the 4 axis end points
        for p in pts:
            if not (abs(p.x - c.x) < w * 0.02 or abs(p.y - c.y) < h * 0.02):
                return None
        return c, w / 2, h / 2

    def _stroke(self, run, closed, attribs):
        msp = self.msp
        circle = self._circle_of_run(run, closed)
        if circle is not None:
            self._add(msp.add_circle(circle[0], circle[1], dxfattribs=attribs), "çember")
            return
        ell = self._ellipse_of_run(run, closed) if self.opts.arcs else None
        if ell is not None:
            c, a, b = ell
            major = (a, 0, 0) if a >= b else (0, b, 0)
            ratio = min(a, b) / max(a, b)
            self._add(msp.add_ellipse(c, major_axis=major, ratio=ratio, dxfattribs=attribs), "elips")
            return
        if not self.opts.join:
            for pr in run:
                self._single(pr, attribs)
            return
        if len(run) == 1:
            self._single(run[0], attribs)
            return
        verts = self._run_vertices(run)
        is_closed = closed or (len(verts) > 2 and verts[0][0].isclose(verts[-1][0], abs_tol=self.tol))
        if is_closed and len(verts) > 2 and verts[0][0].isclose(verts[-1][0], abs_tol=self.tol):
            verts = verts[:-1]
        if len(verts) < 2:
            return
        pl = msp.add_lwpolyline([(v[0].x, v[0].y, v[1]) for v in verts], format="xyb", close=is_closed,
                                dxfattribs=attribs)
        self._add(pl, "çoklu çizgi")

    def _single(self, pr, attribs):
        msp = self.msp
        if pr[0] == "L":
            if not pr[1].isclose(pr[2], abs_tol=self.tol):
                self._add(msp.add_line(pr[1], pr[2], dxfattribs=attribs), "çizgi")
            return
        a, c1, c2, b = pr[1], pr[2], pr[3], pr[4]
        arc = _arc_from_bezier(a, c1, c2, b, self.tol) if self.opts.arcs else None
        if arc is not None:
            c, r, sweep = arc
            s0 = (a - c).angle
            s1 = (b - c).angle
            if sweep < 0:
                s0, s1 = s1, s0
            self._add(msp.add_arc(c, r, math.degrees(s0), math.degrees(s1), dxfattribs=attribs), "yay")
        else:
            pts = [a] + _flatten_bezier(a, c1, c2, b, self.tol)
            self._add(msp.add_lwpolyline([(p.x, p.y) for p in pts], dxfattribs=attribs), "çoklu çizgi")

    def _fill(self, runs, color, pdf_layer):
        rgb = _rgb(color)
        if rgb is not None and self.opts.skip_white_fills and min(rgb) > 245:
            return
        attribs = self._attribs("fill", color, None, pdf_layer)
        loops = []
        for run in runs:
            verts = self._run_vertices(run)
            if len(verts) > 2 and verts[0][0].isclose(verts[-1][0], abs_tol=self.tol):
                verts = verts[:-1]
            if len(verts) >= 3:
                loops.append(verts)
        if not loops:
            return
        h = self.msp.add_hatch(dxfattribs=attribs)
        h.set_solid_fill(color=attribs.get("color", 7))
        if "true_color" in attribs:
            h.dxf.true_color = attribs["true_color"]
        for verts in loops:
            h.paths.add_polyline_path([(v[0].x, v[0].y, v[1]) for v in verts], is_closed=True)
        self._add(h, "dolgu")

    # ------------------------------------------------------------ text
    def _text_style(self, font: str) -> str:
        base = font.split("+")[-1]
        if base in self._styles:
            return self._styles[base]
        low = base.lower()
        ttf = "arial.ttf"
        for key, f in (("times", "times.ttf"), ("courier", "cour.ttf"), ("calibri", "calibri.ttf"),
                       ("verdana", "verdana.ttf"), ("tahoma", "tahoma.ttf"), ("segoe", "segoeui.ttf"),
                       ("isocp", "isocp.shx"), ("simplex", "simplex.shx"), ("romans", "romans.shx"),
                       ("txt", "txt.shx")):
            if key in low:
                ttf = f
                break
        name = "PDF_" + "".join(ch if ch.isalnum() else "_" for ch in base)[:60]
        if name not in self.doc.styles:
            self.doc.styles.add(name, font=ttf)
        self._styles[base] = name
        return name

    def _texts(self, page):
        data = page.get_text("dict")
        msp = self.msp
        for block in data.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                dx, dy = line.get("dir", (1, 0))
                # PDF y axis points down: rotate the direction like the points
                p0 = self.P(_pt(0, 0))
                p1 = self.P(_pt(dx, dy))
                ang = math.degrees((p1 - p0).angle)
                for span in line.get("spans", []):
                    txt = span.get("text", "")
                    if not txt.strip():
                        continue
                    ox, oy = span.get("origin", (0, 0))
                    pos = self.P(_pt(ox, oy))
                    size = span.get("size", 10) * self.k
                    attribs = self._attribs("text", span.get("color", 0), None, None)
                    attribs.update(height=max(size * 0.72, 1e-3), rotation=ang,
                                   style=self._text_style(span.get("font", "Arial")), insert=pos)
                    t = msp.add_text(txt, dxfattribs=attribs)
                    self._add(t, "yazı")

    # ------------------------------------------------------------ images
    def _images(self, pdf, page, path):
        import pymupdf
        imgs = page.get_images(full=True)
        if not imgs:
            return
        out_dir = None
        done = {}
        for info in imgs:
            xref, smask = info[0], info[1]
            try:
                rects = page.get_image_rects(xref, transform=True)
            except Exception:
                rects = []
            if not rects:
                continue
            fname = done.get(xref)
            if fname is None:
                try:
                    pix = pymupdf.Pixmap(pdf, xref)
                    if smask:
                        try:
                            pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(pdf, smask))
                        except Exception:
                            pass
                    if pix.n - pix.alpha >= 4:  # CMYK -> RGB
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    if pix.width < 2 or pix.height < 2:
                        continue
                    if out_dir is None:
                        out_dir = _image_dir(path)
                    fname = str(out_dir / f"sayfa{self.opts.page + 1}_resim{xref}.png")
                    pix.save(fname)
                    done[xref] = fname
                except Exception as ex:
                    self.result.warnings.append(f"Resim {xref} alınamadı: {ex}")
                    continue
            for rect, m in rects:
                # unit square of the image -> page; (0,1) is the lower left corner of the picture
                bl = self.P(pymupdf.Point(0, 1) * m)
                br = self.P(pymupdf.Point(1, 1) * m)
                tl = self.P(pymupdf.Point(0, 0) * m)
                u = br - bl
                v = tl - bl
                if u.magnitude < 1e-9 or v.magnitude < 1e-9:
                    continue
                try:
                    w_px, h_px = pix.width, pix.height
                except Exception:
                    from PySide6.QtGui import QImageReader
                    sz = QImageReader(fname).size()
                    w_px, h_px = sz.width(), sz.height()
                idef = self.doc.add_image_def(filename=fname, size_in_pixel=(w_px, h_px))
                attribs = {"layer": self._layer("image", None)}
                img = self.msp.add_image(image_def=idef, insert=bl, size_in_units=(u.magnitude, v.magnitude),
                                         rotation=math.degrees(u.angle), dxfattribs=attribs)
                self._add(img, "resim")
        if done:
            self.result.warnings.append(f"Resimler şu klasöre kaydedildi: {out_dir}")

    # ------------------------------------------------------------ main
    def run(self, path: str, progress=None) -> ImportResult:
        """progress(fraction) may return False to cancel."""
        pdf = open_pdf(path)
        try:
            page = pdf[self.opts.page]
            self._setup_page(page)
            if self.opts.vectors or self.opts.fills:
                drawings = page.get_drawings()
                total = max(1, len(drawings))
                for n, d in enumerate(drawings):
                    if progress is not None and n % 2000 == 0:
                        if progress(0.9 * n / total) is False:
                            self.result.warnings.append("İçe aktarma kullanıcı tarafından durduruldu.")
                            break
                    items = d.get("items", [])
                    if not items:
                        continue
                    typ = d.get("type", "s") or "s"
                    runs = self._runs(items)
                    pdf_layer = d.get("layer")
                    if "f" in typ and self.opts.fills:
                        self._fill(runs, d.get("fill"), pdf_layer)
                    if "s" in typ and self.opts.vectors:
                        attribs = self._attribs("geom", d.get("color"), d.get("width"), pdf_layer,
                                                d.get("dashes"))
                        close_path = bool(d.get("closePath"))
                        for i, run in enumerate(runs):
                            ends_meet = run[0][1].isclose(run[-1][-1], abs_tol=self.tol * 10)
                            self._stroke(run, ends_meet or (close_path and i == len(runs) - 1), attribs)
            if self.opts.text:
                self._texts(page)
            if self.opts.images:
                self._images(pdf, page, path)
        finally:
            pdf.close()
        return self.result


def _image_dir(pdf_path: str):
    import os
    from pathlib import Path
    p = Path(pdf_path)
    d = p.parent / f"{p.stem}_resimler"
    try:
        d.mkdir(exist_ok=True)
        test = d / ".t2d"
        test.write_text("")
        test.unlink()
        return d
    except OSError:
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
        d = Path(base) / "T2D-CAD" / "pdf_resimleri" / p.stem
        d.mkdir(parents=True, exist_ok=True)
        return d


def _pt(x, y):
    import pymupdf
    return pymupdf.Point(x, y)
