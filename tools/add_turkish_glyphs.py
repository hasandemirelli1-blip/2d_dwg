"""Add missing Turkish characters (Ç Ş Ğ İ Ö Ü ç ş ğ ı ö ü) to LibreCAD .lff
stroke fonts by combining the base letter with accents.

    python tools/add_turkish_glyphs.py t2dcad/resources/fonts
"""
import re
import sys
from pathlib import Path

# char code: (base code, accent, uppercase)
TARGETS = {
    0x00C7: (0x43, "cedilla", True), 0x00E7: (0x63, "cedilla", False),
    0x015E: (0x53, "cedilla", True), 0x015F: (0x73, "cedilla", False),
    0x011E: (0x47, "breve", True), 0x011F: (0x67, "breve", False),
    0x0130: (0x49, "dot", True), 0x0131: (0x69, "dotless", False),
    0x00D6: (0x4F, "diaeresis", True), 0x00F6: (0x6F, "diaeresis", False),
    0x00DC: (0x55, "diaeresis", True), 0x00FC: (0x75, "diaeresis", False),
}


def parse(text):
    glyphs = {}
    order = []
    cur = None
    for line in text.splitlines():
        m = re.match(r"^\[([0-9A-Fa-f]{4,6})\]", line)
        if m:
            cur = int(m.group(1), 16)
            glyphs[cur] = [line]
            order.append(cur)
        elif cur is not None and line.strip():
            glyphs[cur].append(line)
    return glyphs


def points(glyphs, code, depth=0):
    """All vertices of a glyph (resolving references)."""
    pts, lines = [], glyphs.get(code, [])[1:]
    for ln in lines:
        ln = ln.strip()
        if ln.startswith("C") and depth < 3:
            try:
                pts += points(glyphs, int(ln[1:], 16), depth + 1)
            except ValueError:
                pass
            continue
        for v in ln.split(";"):
            parts = v.split(",")
            try:
                pts.append((float(parts[0]), float(parts[1])))
            except (ValueError, IndexError):
                pass
    return pts


def fmt(v):
    return f"{v:.4g}"


def make(glyphs, code, base, accent, upper):
    if base not in glyphs:
        return None
    pts = points(glyphs, base)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx = (min(xs) + max(xs)) / 2
    top = max(ys)
    char = chr(code)
    out = [f"[{code:04X}] {char}"]
    if accent == "dotless":
        # copy 'i' without the dot (polylines lying completely above x-height)
        for ln in glyphs[base][1:]:
            if ln.strip().startswith("C"):
                out.append(ln)
                continue
            vs = [v.split(",") for v in ln.split(";")]
            try:
                if min(float(v[1]) for v in vs) > 6.5:
                    continue
            except (ValueError, IndexError):
                pass
            out.append(ln)
        return out
    out.append(f"C{base:04X}")
    if accent == "cedilla":
        bottom = min(y for x, y in pts if y >= -0.01) if any(y >= -0.01 for x, y in pts) else 0
        out.append(f"{fmt(cx)},{fmt(bottom)};{fmt(cx - 0.5)},-2")
    elif accent == "breve":
        y = top + (1.25 if upper else 2.75)
        out.append(f"{fmt(cx - 1.25)},{fmt(y + 1)};{fmt(cx + 1.25)},{fmt(y + 1)},A1")
    elif accent == "dot":
        out.append(f"{fmt(cx)},{fmt(top + 1.25)};{fmt(cx)},{fmt(top + 1.75)}")
    elif accent == "diaeresis":
        y = top + (1.25 if upper else 2.5)
        for dx in (-1.0, 1.0):
            out.append(f"{fmt(cx + dx)},{fmt(y)};{fmt(cx + dx)},{fmt(y + 0.5)}")
    return out


def _broken(glyphs, code) -> bool:
    """Some fonts contain only the accent of a letter (e.g. romand Ü)."""
    if any(ln.strip().startswith("C") for ln in glyphs[code][1:]):
        return False
    ys = [y for x, y in points(glyphs, code)]
    return not ys or max(ys) - min(ys) < 4


def fix(path: Path) -> int:
    text = path.read_text(encoding="utf8", errors="replace")
    header = text.split("\n[", 1)[0] if not text.startswith("[") else ""
    glyphs = parse(text)
    count = 0
    for code, (base, accent, upper) in TARGETS.items():
        if code in glyphs and not _broken(glyphs, code):
            continue
        g = make(glyphs, code, base, accent, upper)
        if g:
            glyphs[code] = g
            count += 1
    if count:
        body = "\n\n".join("\n".join(g) for g in glyphs.values())
        path.write_text(header.rstrip("\n") + "\n\n" + body + "\n", encoding="utf8")
    return count


if __name__ == "__main__":
    for f in sorted(Path(sys.argv[1]).glob("*.lff")):
        n = fix(f)
        print(f"{f.name}: {n} karakter eklendi")
