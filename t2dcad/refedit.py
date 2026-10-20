"""In-place block editing (AutoCAD REFEDIT / BEDIT in place).

The content of the block is copied into the modelspace at the position of
the selected block reference (the reference itself is hidden). All normal
commands can be used on these objects. Objects can be moved out of the block
(REFREMOVE) or other drawing objects can be put into it (REFADD). REFCLOSE
writes the objects back into the block definition (all references update) or
discards the changes."""
from __future__ import annotations

from typing import Optional

from ezdxf.math import Matrix44


class RefEditSession:
    def __init__(self, tab, insert):
        self.tab = tab
        self.doc = tab.doc
        self.insert = insert
        self.name = insert.dxf.name
        self.matrix: Matrix44 = insert.matrix44()
        self.outside: set[str] = set()  # handles which are NOT in the working set
        self.undo_mark = 0
        self.adding = False  # REFADD selection may pick outside objects

    # ------------------------------------------------------------ start
    def start(self) -> list[str]:
        doc = self.doc
        msp = doc.msp
        blk = doc.doc.blocks.get(self.name)
        self.undo_mark = len(doc.undo_stack)
        self.outside = {e.dxf.handle for e in msp}
        problems = []
        doc.begin("REFEDIT")
        for e in list(blk):
            try:
                c = doc.clone(e)
                c.transform(self.matrix)
            except Exception as ex:  # e.g. non uniform scaled circles
                problems.append(f"{e.dxftype()}: {ex}")
                continue
            doc.add_entity(c)
        doc.erase([self.insert])
        doc.commit()
        return problems

    # ------------------------------------------------------------ working set
    def is_working(self, handle: str) -> bool:
        return handle not in self.outside

    def working_entities(self) -> list:
        return [e for e in self.doc.msp if e.dxf.handle not in self.outside]

    def add(self, entities) -> int:
        n = 0
        for e in entities:
            if e.dxf.handle in self.outside:
                self.outside.discard(e.dxf.handle)
                n += 1
        return n

    def remove(self, entities) -> int:
        n = 0
        for e in entities:
            if e.dxf.handle not in self.outside:
                self.outside.add(e.dxf.handle)
                n += 1
        return n

    # ------------------------------------------------------------ close
    def save(self) -> list[str]:
        doc = self.doc
        dxf = doc.doc
        blk = dxf.blocks.get(self.name)
        inv = self.matrix.copy()
        inv.inverse()
        working = self.working_entities()
        new_content = []
        problems = []
        for e in working:
            try:
                c = doc.clone(e)
                c.transform(inv)
                new_content.append(c)
            except Exception as ex:
                problems.append(f"{e.dxftype()}: {ex}")
        old_content = list(blk)

        def put(content_out, content_in):
            for x in content_out:
                if x.dxf.owner == blk.block_record_handle:
                    blk.unlink_entity(x)
            for x in content_in:
                blk.add_entity(x)

        doc.begin("REFCLOSE")
        put(old_content, new_content)
        doc.custom(lambda: put(new_content, old_content), lambda: put(old_content, new_content), regen=False)
        doc.erase(working)
        doc.restore(self.insert)
        doc.commit()
        doc.changed.emit([], [], True)
        return problems

    def discard(self) -> None:
        doc = self.doc
        while len(doc.undo_stack) > self.undo_mark:
            if doc.undo() is None:
                break
        doc.redo_stack.clear()
        doc.changed.emit([], [], True)


def block_reference_at(tab, handle: str) -> Optional[object]:
    e = tab.doc.entity_by_handle(handle)
    if e is None or e.dxftype() != "INSERT":
        return None
    name = e.dxf.name
    if name.startswith("*"):
        return None
    blk = tab.doc.doc.blocks.get(name)
    if blk is None or blk.block.is_xref:
        return None
    return e
