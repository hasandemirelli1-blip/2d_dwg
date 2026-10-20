"""CommandContext: the API which commands use to talk to the document and UI."""
from __future__ import annotations

from typing import Optional

from ezdxf.math import Vec2

from t2dcad.engine import GetSelection, match_keyword
from t2dcad.snap import OVERRIDE_WORDS


class CommandContext:
    def __init__(self, tab):
        self.tab = tab
        self.last_point: Optional[Vec2] = None
        self.vars: dict = {}
        self.last_created: list = []
        self._sel_req: Optional[GetSelection] = None

    # ------------------------------------------------------------ shortcuts
    @property
    def doc(self):
        return self.tab.doc

    @property
    def dxf(self):
        return self.tab.doc.doc

    @property
    def msp(self):
        return self.tab.doc.msp

    @property
    def canvas(self):
        return self.tab.canvas

    @property
    def main(self):
        return self.tab.main

    def attribs(self, **extra) -> dict:
        a = self.doc.default_attribs()
        a.update(extra)
        return a

    def print(self, msg: str, echo=False):
        self.tab.main.cmdline.add_history(msg)

    def prompt_changed(self):
        self.tab.main.cmdline.set_prompt(self.tab.manager.prompt_text())
        self.canvas.update_cursor(self.canvas.cursor_screen)

    def command_finished(self):
        self.canvas.window_start = None
        self.canvas.osnap_override = None
        self.canvas.realtime_pan = False
        self.canvas.prune_selection()
        self.tab.main.update_ui_state()

    def created(self, entity):
        """Register a new modelspace entity created by msp.add_xxx()."""
        self.doc.added(entity)
        self.last_created = [entity]
        return entity

    def entities(self, handles) -> list:
        out = []
        for h in handles:
            e = self.doc.entity_by_handle(h)
            if e is not None and e.dxf.owner == self.msp.layout_key:
                out.append(e)
        return out

    # ------------------------------------------------------------ selection
    def take_pickfirst(self) -> list:
        sel = self.entities(self.canvas.selection)
        sel = [e for e in sel if not self.tab.is_locked(e.dxf.handle)]
        if sel:
            self.canvas.prev_selection = [e.dxf.handle for e in sel]
        self.canvas.clear_selection()
        return sel

    def begin_selection(self, req: GetSelection):
        self._sel_req = req
        self.canvas.sel_remove_mode = False
        self.canvas.clear_selection()

    def end_selection(self) -> list:
        sel = self.entities(self.canvas.selection)
        if sel:
            self.canvas.prev_selection = [e.dxf.handle for e in sel]
        self.canvas.clear_selection()
        self.canvas.sel_remove_mode = False
        self._sel_req = None
        return sel

    def selection_keyword(self, text: str):
        kw = match_keyword(text, ["ALL", "Tümü", "Last", "Previous", "Remove", "Add", "Window", "Crossing"])
        t = text.strip().upper()
        c = self.canvas
        if t in ("ALL", "TÜMÜ", "TUMU") or kw in ("ALL", "Tümü"):
            hs = [e.dxf.handle for e in self.msp if not self.tab.is_locked(e.dxf.handle)
                  and self.tab.is_visible(e)]
            c.set_selection(hs, add=True)
            self.print(f"{len(hs)} bulundu")
        elif kw == "Last":
            hs = [e.dxf.handle for e in self.last_created if e.is_alive]
            if not hs:
                ents = list(self.msp)
                hs = [ents[-1].dxf.handle] if ents else []
            c.set_selection(hs, add=True)
            self.print(f"{len(hs)} bulundu")
        elif kw == "Previous":
            hs = [h for h in c.prev_selection if self.doc.entity_by_handle(h) is not None]
            c.set_selection(hs, add=True)
            self.print(f"{len(hs)} bulundu")
        elif kw == "Remove":
            c.sel_remove_mode = True
            self.print("Nesneleri kaldırın:")
        elif kw == "Add":
            c.sel_remove_mode = False
            self.print("Nesneleri ekleyin:")
        elif kw in ("Window", "Crossing"):
            self.print("Pencere için boş bir alana tıklayın (soldan sağa: Window, sağdan sola: Crossing).")
        else:
            self.print("Seçenekler: ALL, Last, Previous, Remove, Add")
        if self._sel_req is not None and self._sel_req.single and c.selection:
            self.tab.manager.send(self.end_selection())

    # ------------------------------------------------------------ points
    def osnap_override_from_text(self, text: str) -> bool:
        w = text.strip().upper()
        if w in OVERRIDE_WORDS:
            kind = OVERRIDE_WORDS[w]
            self.canvas.osnap_override = set() if kind == "none" else {kind}
            self.print(f"Tek seferlik nesne yakalama: {w}")
            return True
        return False

    def direct_distance_point(self, base: Vec2, d: float) -> Optional[Vec2]:
        u = self.canvas.constrained_direction(base)
        if u is None:
            return None
        return base + u * d

    # ------------------------------------------------------------ misc
    def get(self, key, default=None):
        return self.vars.get(key, default)

    def set(self, key, value):
        self.vars[key] = value

    def header(self, name, default=None):
        try:
            return self.dxf.header.get(name, default)
        except Exception:
            return default

    def set_header(self, name, value):
        try:
            self.dxf.header[name] = value
        except Exception:
            pass

    def regen(self):
        self.tab.regen()
