"""Command engine.

Commands are generator functions which yield input requests (GetPoint,
GetSelection, ...) and receive the user's answer::

    @command("LINE", "L")
    def line(ctx):
        p1 = yield GetPoint("İlk noktayı belirtin:")
        ...
"""
from __future__ import annotations

import math
import re
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional, Any

from ezdxf.math import Vec2


class Cancel(Exception):
    pass


class Pt(Vec2):
    """Point answer of a request; compares unequal to keyword strings so
    commands can write `if p == "Undo":`."""

    def __eq__(self, other):
        if isinstance(other, str) or other is None:
            return False
        return Vec2.__eq__(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = Vec2.__hash__


# ---------------------------------------------------------------- requests
@dataclass
class Request:
    prompt: str = ""
    keywords: tuple = ()
    default: Any = None

    def keyword_prompt(self) -> str:
        if not self.keywords:
            return ""
        return " [" + "/".join(self.keywords) + "]"

    def match_keyword(self, text: str) -> Optional[str]:
        return match_keyword(text, self.keywords)


@dataclass
class GetPoint(Request):
    base: Optional[Vec2] = None
    preview: Optional[Callable] = None  # fn(point) -> list of shapes
    allow_none: bool = False  # Enter allowed -> None
    rubber: bool = True  # rubber band line from base
    no_snap: bool = False


@dataclass
class GetDistance(Request):
    base: Optional[Vec2] = None
    preview: Optional[Callable] = None
    allow_none: bool = False


@dataclass
class GetAngle(Request):
    base: Optional[Vec2] = None
    preview: Optional[Callable] = None
    allow_none: bool = False


@dataclass
class GetNumber(Request):
    integer: bool = False
    allow_none: bool = False


@dataclass
class GetString(Request):
    spaces: bool = False


@dataclass
class GetKeyword(Request):
    allow_none: bool = True


@dataclass
class GetSelection(Request):
    single: bool = False
    pickfirst: bool = True


@dataclass
class GetEntity(Request):
    types: tuple = ()  # allowed dxf types, empty = all
    allow_none: bool = False
    preview: Optional[Callable] = None


def match_keyword(text: str, keywords) -> Optional[str]:
    """Keywords are written like 'Close' or 'eXit', the capital letters are the
    shortcut. Returns the keyword or None."""
    t = text.strip().lower()
    if not t:
        return None
    for kw in keywords:
        if kw.lower() == t:
            return kw
    for kw in keywords:
        short = "".join(c for c in kw if c.isupper()).lower()
        if short and short == t:
            return kw
    for kw in keywords:
        if kw.lower().startswith(t):
            return kw
    return None


# ---------------------------------------------------------------- registry
@dataclass
class CommandDef:
    name: str
    func: Callable
    aliases: tuple = ()
    pickfirst: bool = False
    repeatable: bool = True
    transparent: bool = False
    undoable: bool = True
    description: str = ""


COMMANDS: dict[str, CommandDef] = {}
ALIASES: dict[str, str] = {}


def command(name: str, *aliases: str, pickfirst=False, repeatable=True,
            transparent=False, undoable=True, description=""):
    def deco(func):
        cd = CommandDef(name.upper(), func, tuple(a.upper() for a in aliases),
                        pickfirst, repeatable, transparent, undoable, description)
        COMMANDS[cd.name] = cd
        for a in cd.aliases:
            ALIASES[a] = cd.name
        return func
    return deco


def resolve(name: str) -> Optional[CommandDef]:
    n = name.strip().upper().lstrip("_.-'")
    if n in COMMANDS:
        return COMMANDS[n]
    if n in ALIASES:
        return COMMANDS[ALIASES[n]]
    return None


# ---------------------------------------------------------------- parsing
_num = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def parse_number(text: str) -> Optional[float]:
    t = text.strip().replace(",", ".")
    try:
        return float(t)
    except ValueError:
        pass
    # simple expressions like 100/2 or 3*25
    if re.fullmatch(r"[0-9+\-*/(). ]+", t):
        try:
            return float(eval(t, {"__builtins__": {}}, {}))  # noqa: S307
        except Exception:
            return None
    return None


def parse_point(text: str, last: Optional[Vec2]) -> Optional[Vec2]:
    """Parse AutoCAD style coordinates:
    x,y   @dx,dy   @dist<angle   dist<angle   #x,y
    (Turkish keyboards: ';' is accepted as separator too.)
    """
    t = text.strip().replace(" ", "")
    if not t:
        return None
    rel = False
    if t.startswith("@"):
        rel = True
        t = t[1:]
        if not t:
            return last
    elif t.startswith("#"):
        t = t[1:]
    m = re.fullmatch(rf"({_num})<({_num})", t)
    if m:
        d = float(m.group(1).replace(",", "."))
        a = math.radians(float(m.group(2).replace(",", ".")))
        v = Vec2.from_angle(a, d)
    else:
        m = re.fullmatch(rf"({_num})[,;]({_num})(?:[,;]{_num})?", t)
        if not m:
            # "10,5" with comma decimal is ambiguous, accept "10.5;3,2"
            return None
        v = Vec2(float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", ".")))
    if rel:
        return (last or Vec2()) + v
    return v


# ---------------------------------------------------------------- manager
class CommandManager:
    """Drives the active command generator.

    The canvas/UI calls `start`, `text_input`, `point_input`, `enter`,
    `cancel` and `selection_done`."""

    def __init__(self, ctx):
        self.ctx = ctx  # CommandContext
        self.gen = None
        self.cmd: Optional[CommandDef] = None
        self.req: Optional[Request] = None
        self.last_command: Optional[str] = None
        self._first_selection = True
        self._dist_first: Optional[Vec2] = None  # 2-point distance input
        # point modifiers: FROM (reference point + offset), M2P (mid between 2 points)
        self._special: Optional[str] = None
        self._special_pt: Optional[Vec2] = None

    # ------------------------------------------------------------ state
    @property
    def active(self) -> bool:
        return self.gen is not None

    def prompt_text(self) -> str:
        if not self.req:
            return "Komut:"
        from t2dcad.i18n import tr
        r = self.req
        txt = tr(r.prompt) + r.keyword_prompt()
        if r.default is not None and not isinstance(r, GetSelection):
            d = r.default
            if isinstance(d, float):
                d = fmt(d)
            txt += f" <{d}>"
        if self._dist_first is not None:
            txt = "İkinci noktayı belirtin:"
        if self._special == "from_base":
            txt = "Referans (temel) noktası:"
        elif self._special == "from_off":
            txt = "<Ofset> (ör. @10,5 veya mesafe):"
        elif self._special == "m2p1":
            txt = "Orta noktanın ilk noktası:"
        elif self._special == "m2p2":
            txt = "Orta noktanın ikinci noktası:"
        txt = tr(txt) if self._special or self._dist_first is not None else txt
        return txt + ":" if not txt.endswith(":") else txt

    # ------------------------------------------------------------ control
    def start(self, name: str, echo=True) -> bool:
        cd = resolve(name)
        if cd is None:
            self.ctx.print(f'Bilinmeyen komut "{name.upper()}". Yardım için F1.')
            return False
        return self.start_def(cd, echo)

    def start_def(self, cd: CommandDef, echo=True) -> bool:
        if self.gen is not None:
            if cd.transparent:
                # run transparent commands (zoom, pan, settings) inline
                try:
                    g = cd.func(self.ctx)
                    if g is not None and hasattr(g, "send"):
                        g.close()
                except Exception:
                    pass
                return True
            self.cancel(quiet=True)
        if echo:
            self.ctx.print(f"Komut: {cd.name}", echo=True)
        self.cmd = cd
        if cd.repeatable:
            self.last_command = cd.name
        self._first_selection = True
        self._dist_first = None
        if cd.undoable:
            self.ctx.doc.begin(cd.name)
        try:
            g = cd.func(self.ctx)
        except Exception as ex:
            self._error(ex)
            return False
        if g is None or not hasattr(g, "send"):
            self._finish()
            return True
        self.gen = g
        self._advance(None, first=True)
        return True

    def repeat(self):
        if self.last_command:
            self.start(self.last_command)

    def _advance(self, value, first=False):
        try:
            if first:
                req = next(self.gen)
            else:
                req = self.gen.send(value)
        except StopIteration:
            self._finish()
            return
        except Cancel:
            self.ctx.print("*İptal*")
            self._finish()
            return
        except Exception as ex:
            self._error(ex)
            return
        self.req = req
        self._dist_first = None
        self._special = None
        self._special_pt = None
        # pickfirst selection
        if isinstance(req, GetSelection) and self._first_selection:
            self._first_selection = False
            if req.pickfirst and self.cmd and self.cmd.pickfirst:
                sel = self.ctx.take_pickfirst()
                if sel:
                    self.ctx.print(f"{len(sel)} nesne bulundu")
                    self._advance(sel)
                    return
            self.ctx.begin_selection(req)
        elif isinstance(req, GetSelection):
            self.ctx.begin_selection(req)
        self.ctx.prompt_changed()

    def _finish(self):
        self.gen = None
        self.req = None
        self._dist_first = None
        if self.cmd and self.cmd.undoable:
            self.ctx.doc.commit()
        self.cmd = None
        self.ctx.command_finished()
        self.ctx.prompt_changed()

    def _error(self, ex: Exception):
        traceback.print_exc()
        self.ctx.print(f"Hata: {ex}")
        gen = self.gen
        self.gen = None
        self.req = None
        if gen is not None:
            try:
                gen.close()
            except Exception:
                pass
        if self.cmd and self.cmd.undoable:
            self.ctx.doc.commit()
        self.cmd = None
        self.ctx.command_finished()
        self.ctx.prompt_changed()

    def cancel(self, quiet=False):
        if self.gen is None:
            return
        gen = self.gen
        self.gen = None
        self.req = None
        try:
            gen.close()
        except Exception:
            pass
        if not quiet:
            self.ctx.print("*İptal*")
        if self.cmd and self.cmd.undoable:
            self.ctx.doc.commit()
        self.cmd = None
        self.ctx.command_finished()
        self.ctx.prompt_changed()

    # ------------------------------------------------------------ point modifiers
    def start_special(self, kind: str) -> bool:
        """kind: 'from' or 'm2p' (only while a point is requested)."""
        if not isinstance(self.req, GetPoint):
            self.ctx.print("Bu seçenek sadece nokta istenirken kullanılabilir.")
            return False
        self._special = "from_base" if kind == "from" else "m2p1"
        self._special_pt = None
        self.ctx.prompt_changed()
        return True

    def _special_point(self, p: Vec2) -> Optional[Vec2]:
        """Returns the final point or None if the point was consumed."""
        st = self._special
        if st is None:
            return p
        if st == "from_base":
            self._special_pt = p
            self._special = "from_off"
            self.ctx.last_point = p
            self.ctx.prompt_changed()
            return None
        if st == "m2p1":
            self._special_pt = p
            self._special = "m2p2"
            self.ctx.prompt_changed()
            return None
        if st == "m2p2":
            p = self._special_pt.lerp(p)
        self._special = None
        self._special_pt = None
        return p

    # ------------------------------------------------------------ input
    def send(self, value):
        if self.gen is None:
            return
        if isinstance(value, Vec2) and not isinstance(value, Pt):
            value = Pt(value)
        self._advance(value)

    def enter(self):
        """Empty Enter / Space / right click."""
        if self.gen is None:
            self.repeat()
            return
        r = self.req
        if isinstance(r, GetSelection):
            self.send(self.ctx.end_selection())
            return
        if self._dist_first is not None or self._special is not None:
            self._dist_first = None
            self._special = None
            self.ctx.prompt_changed()
            return
        if r.default is not None:
            self.send(r.default)
        elif isinstance(r, GetString):
            self.send("")
        elif getattr(r, "allow_none", False):
            self.send(None)
        else:
            # AutoCAD finishes most commands with Enter
            self.cancel(quiet=True)

    def text_input(self, text: str):
        text = text.strip()
        if self.gen is None:
            if not text:
                self.repeat()
            else:
                cd = resolve(text)
                if cd is not None and cd.name != text.upper():
                    self.ctx.print(cd.name)
                self.start(text, echo=False)
            return
        r = self.req
        if text == "":
            self.enter()
            return
        # transparent commands typed with apostrophe
        if text.startswith("'"):
            self.start(text[1:])
            return
        kw = r.match_keyword(text) if r.keywords else None
        if isinstance(r, GetString):
            self.send(text)
            return
        if kw and not isinstance(r, GetSelection):
            self.send(kw)
            return
        if isinstance(r, GetPoint):
            up = text.strip().upper()
            if up in ("FROM", "FRO", "FR", "_FROM"):
                self.start_special("from")
                return
            if up in ("M2P", "MTP", "_M2P"):
                self.start_special("m2p")
                return
            ov = self.ctx.osnap_override_from_text(text)
            if ov:
                return
            p = parse_point(text, self.ctx.last_point)
            if p is None:
                d = parse_number(text)
                base = self.rubber_base
                if d is not None and (base is not None or self.ctx.canvas.track_align is not None):
                    p = self.ctx.direct_distance_point(base, d)
            if p is None:
                self.ctx.print("Geçersiz nokta.")
                return
            p = self._special_point(p)
            if p is None:
                return
            self.ctx.last_point = p
            self.send(p)
        elif isinstance(r, GetDistance):
            d = parse_number(text)
            if d is None:
                p = parse_point(text, self.ctx.last_point)
                if p is not None and r.base is not None:
                    d = r.base.distance(p)
            if d is None:
                self.ctx.print("Sayı veya mesafe gerekli.")
                return
            self.send(d)
        elif isinstance(r, GetAngle):
            d = parse_number(text)
            if d is None:
                p = parse_point(text, self.ctx.last_point)
                if p is not None and r.base is not None:
                    d = math.degrees((p - r.base).angle)
            if d is None:
                self.ctx.print("Açı gerekli.")
                return
            self.send(d)
        elif isinstance(r, GetNumber):
            d = parse_number(text)
            if d is None:
                self.ctx.print("Sayı gerekli.")
                return
            self.send(int(round(d)) if r.integer else d)
        elif isinstance(r, GetKeyword):
            if kw:
                self.send(kw)
            else:
                self.ctx.print("Geçersiz seçenek.")
        elif isinstance(r, GetSelection):
            self.ctx.selection_keyword(text)
        elif isinstance(r, GetEntity):
            self.ctx.print("Bir nesne seçin.")

    def point_input(self, p: Vec2, picked_handle: Optional[str] = None):
        """Mouse click in the drawing (already snapped)."""
        r = self.req
        if r is None:
            return
        if isinstance(r, GetPoint):
            p = self._special_point(p)
            if p is None:
                return
            self.ctx.last_point = p
            self.send(p)
        elif isinstance(r, (GetDistance, GetAngle)):
            base = r.base or self._dist_first
            if base is None:
                self._dist_first = p
                self.ctx.prompt_changed()
                return
            self._dist_first = None
            if isinstance(r, GetDistance):
                self.send(base.distance(p))
            else:
                self.send(math.degrees((p - base).angle))

    @property
    def rubber_base(self) -> Optional[Vec2]:
        r = self.req
        if self._dist_first is not None:
            return self._dist_first
        if self._special in ("from_off", "m2p2"):
            return self._special_pt
        if self._special in ("from_base", "m2p1"):
            return None
        if isinstance(r, (GetPoint, GetDistance, GetAngle)):
            return r.base
        return None


def fmt(v: float, dec: int = 4) -> str:
    s = f"{v:.{dec}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def fmt_pt(p: Vec2) -> str:
    return f"{fmt(p.x)},{fmt(p.y)}"
