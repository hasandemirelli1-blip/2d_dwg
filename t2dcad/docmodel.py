"""Drawing document: ezdxf document, file I/O (DXF/DWG) and undo/redo."""
from __future__ import annotations

import glob
import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Optional

import ezdxf
from ezdxf.entities import factory
from ezdxf.document import Drawing

from PySide6.QtCore import QObject, Signal

from t2dcad import settings

DWG_VERSIONS = {
    "R2018": "AutoCAD 2018/2019/2020/2021/2022/2023/2024",
    "R2013": "AutoCAD 2013/2014/2015/2016/2017",
    "R2010": "AutoCAD 2010/2011/2012",
    "R2007": "AutoCAD 2007/2008/2009",
    "R2004": "AutoCAD 2004/2005/2006",
    "R2000": "AutoCAD 2000/2000i/2002",
}


class FileError(Exception):
    pass


class OdaMissing(FileError):
    pass


# ---------------------------------------------------------------- ODA converter
def find_oda_converter() -> str:
    """Return path of ODAFileConverter.exe (settings or auto detected) or ''."""
    p = settings.get("oda_path", "")
    if p and os.path.isfile(p):
        return p
    from t2dcad.odainstall import find_bundled
    p = find_bundled()
    if p:
        return p
    patterns = [
        r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe",
        r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe",
    ]
    found = []
    for pat in patterns:
        found.extend(glob.glob(pat))
    if found:
        return sorted(found)[-1]
    w = shutil.which("ODAFileConverter")
    return w or ""


def _configure_odafc() -> None:
    path = find_oda_converter()
    if not path:
        raise OdaMissing(
            "DWG dosyaları için ücretsiz 'ODA File Converter' programı gerekli.\n\n"
            "1) https://www.opendesign.com/guestfiles/oda_file_converter adresinden "
            "Windows sürümünü indirip kurun.\n"
            "2) T2D-CAD'i yeniden başlatın (otomatik bulunur) veya\n"
            "   Araçlar > Seçenekler menüsünden ODAFileConverter.exe yolunu gösterin."
        )
    if os.name == "nt":
        ezdxf.options.set("odafc-addon", "win_exec_path", f'"{path}"')
    else:
        ezdxf.options.set("odafc-addon", "unix_exec_path", path)


# ---------------------------------------------------------------- undo/redo
class Transaction:
    def __init__(self, name: str):
        self.name = name
        self.ops: list[tuple] = []
        self.regen = False

    def __bool__(self):
        return bool(self.ops)


class CadDocument(QObject):
    # added entities, removed entities, full regen required
    changed = Signal(list, list, bool)
    modified_changed = Signal(bool)
    layers_changed = Signal()

    def __init__(self, doc: Drawing, path: str = "", file_format: str = "dxf"):
        super().__init__()
        self.doc = doc
        self.path = path
        self.file_format = file_format  # "dxf" or "dwg"
        self.save_version = doc.acad_release  # e.g. "R2018"
        self._modified = False
        self.undo_stack: list[Transaction] = []
        self.redo_stack: list[Transaction] = []
        self._tx: Optional[Transaction] = None
        self._tx_depth = 0
        prepare_document(doc)

    # ------------------------------------------------------------ factory
    @classmethod
    def new(cls) -> "CadDocument":
        doc = ezdxf.new("R2018", setup=True, units=4)
        doc.header["$MEASUREMENT"] = 1
        doc.header["$LTSCALE"] = 1.0
        d = cls(doc)
        doc.header["$DIMSTYLE"] = "T2D"
        doc.header["$TEXTSTYLE"] = "Standard"
        return d

    @classmethod
    def open(cls, path: str) -> "CadDocument":
        ext = Path(path).suffix.lower()
        if ext == ".dwg":
            _configure_odafc()
            from ezdxf.addons import odafc
            try:
                doc = odafc.readfile(path)
            except Exception as ex:  # noqa
                raise FileError(f"DWG dosyası açılamadı:\n{ex}") from ex
            d = cls(doc, path, "dwg")
            return d
        if ext == ".dxf":
            try:
                doc = ezdxf.readfile(path)
            except ezdxf.DXFStructureError:
                from ezdxf import recover
                doc, auditor = recover.readfile(path)
            except Exception as ex:
                raise FileError(f"DXF dosyası açılamadı:\n{ex}") from ex
            return cls(doc, path, "dxf")
        raise FileError(f"Desteklenmeyen dosya türü: {ext}")

    # ------------------------------------------------------------ properties
    @property
    def msp(self):
        return self.doc.modelspace()

    @property
    def title(self) -> str:
        return Path(self.path).name if self.path else "Çizim1.dwg"

    @property
    def modified(self) -> bool:
        return self._modified

    def set_modified(self, flag: bool = True):
        if flag != self._modified:
            self._modified = flag
            self.modified_changed.emit(flag)

    # ------------------------------------------------------------ saving
    def save(self, path: Optional[str] = None, version: Optional[str] = None) -> None:
        path = path or self.path
        if not path:
            raise FileError("Dosya adı belirtilmedi.")
        ext = Path(path).suffix.lower()
        version = version or self.save_version or "R2018"
        if version not in DWG_VERSIONS and not (ext == ".dxf" and version == "R12"):
            version = "R2018"
        if os.path.exists(path) and settings.get_bool("create_bak", True):
            try:
                shutil.copy2(path, str(Path(path).with_suffix(".bak")))
            except OSError:
                pass
        if ext == ".dwg":
            _configure_odafc()
            from ezdxf.addons import odafc
            with tempfile.TemporaryDirectory(prefix="t2d_") as tmp:
                tmp_dwg = os.path.join(tmp, Path(path).name)
                try:
                    # the ODA converter writes the requested DWG version
                    odafc.export_dwg(self.doc, tmp_dwg, version=version, replace=True)
                except Exception as ex:
                    raise FileError(f"DWG kaydedilemedi:\n{ex}") from ex
                if not os.path.exists(tmp_dwg):
                    raise FileError("DWG kaydedilemedi (ODA File Converter çıktı üretmedi).")
                shutil.copyfile(tmp_dwg, path)
            self.file_format = "dwg"
        else:
            try:
                if self.doc.acad_release != "R12":
                    # R2000+ share the same structure, R12 can not be upgraded
                    self.doc.dxfversion = version
                else:
                    version = "R12"
                tmp = path + ".t2dtmp"
                self.doc.saveas(tmp)
                os.replace(tmp, path)
            except Exception as ex:
                raise FileError(f"DXF kaydedilemedi:\n{ex}") from ex
            self.file_format = "dxf"
        self.path = path
        self.save_version = version
        self.set_modified(False)

    # ------------------------------------------------------------ transactions
    def begin(self, name: str):
        if self._tx_depth == 0:
            self._tx = Transaction(name)
        self._tx_depth += 1

    def commit(self):
        if self._tx_depth == 0:
            return
        self._tx_depth -= 1
        if self._tx_depth == 0:
            tx = self._tx
            self._tx = None
            if tx:
                self.undo_stack.append(tx)
                if len(self.undo_stack) > 500:
                    self.undo_stack.pop(0)
                self.redo_stack.clear()
                self.set_modified(True)

    def rollback(self):
        """Undo all changes of the active transaction."""
        if self._tx_depth == 0:
            return
        self._tx_depth = 0
        tx = self._tx
        self._tx = None
        if tx:
            self._apply(tx, undo=True)

    def _record(self, op: tuple):
        if self._tx is None:
            # implicit single-step transaction
            self.begin("edit")
            self._tx.ops.append(op)
            self.commit()
        else:
            self._tx.ops.append(op)

    # ------------------------------------------------------------ entity ops
    def added(self, entity) -> None:
        """Register an entity which was created in the modelspace."""
        self._record(("add", entity))
        self.changed.emit([entity], [], False)

    def added_many(self, entities) -> None:
        """Register many new modelspace entities at once (one redraw)."""
        entities = list(entities)
        if not entities:
            return
        self.begin("import")
        for e in entities:
            self._record(("add", e))
        self.commit()
        self.changed.emit(entities, [], False)

    def add_entity(self, entity) -> None:
        """Bind (if necessary) and add a virtual entity to the modelspace."""
        if not factory.is_bound(entity, self.doc):
            factory.bind(entity, self.doc)
        self.msp.add_entity(entity)
        self.added(entity)

    def restore(self, entity) -> None:
        """Put an entity, which was erased before, back into the modelspace."""
        self.msp.add_entity(entity)
        self._record(("add", entity))
        self.changed.emit([entity], [], False)

    def erase(self, entities) -> None:
        entities = [e for e in entities if e.is_alive and e.dxf.owner == self.msp.layout_key]
        for e in entities:
            self.msp.unlink_entity(e)
            self._record(("remove", e))
        if entities:
            self.changed.emit([], entities, False)

    def clone(self, entity):
        """Return a copy of `entity`, bound to the document but not in a layout."""
        c = entity.copy()
        factory.bind(c, self.doc)
        return c

    def replace(self, old, new) -> None:
        """Replace `old` by `new` (new must be bound, not yet in a layout)."""
        self.begin("replace")
        self.msp.add_entity(new)
        self._record(("add", new))
        self.msp.unlink_entity(old)
        self._record(("remove", old))
        self.commit()
        self.changed.emit([new], [old], False)

    def modify(self, entity, fn: Callable) -> object:
        """Modify a copy of entity by `fn(copy)` and replace the original.
        Returns the new entity."""
        new = self.clone(entity)
        fn(new)
        self.replace(entity, new)
        return new

    def custom(self, undo_fn: Callable, redo_fn: Callable, regen=True):
        """Register a custom change which was already applied (redo_fn)."""
        self._record(("call", undo_fn, redo_fn, regen))
        if regen:
            self.changed.emit([], [], True)

    # ------------------------------------------------------------ undo/redo
    def _apply(self, tx: Transaction, undo: bool) -> None:
        added, removed, regen = [], [], False
        ops = reversed(tx.ops) if undo else tx.ops
        msp = self.msp
        for op in ops:
            kind = op[0]
            if kind == "add":
                e = op[1]
                if undo:
                    if e.dxf.owner == msp.layout_key:
                        msp.unlink_entity(e)
                    removed.append(e)
                else:
                    msp.add_entity(e)
                    added.append(e)
            elif kind == "remove":
                e = op[1]
                if undo:
                    msp.add_entity(e)
                    added.append(e)
                else:
                    if e.dxf.owner == msp.layout_key:
                        msp.unlink_entity(e)
                    removed.append(e)
            elif kind == "call":
                (op[1] if undo else op[2])()
                regen = regen or op[3]
        # entities added and removed again in the same step:
        add_ids = {id(e) for e in added}
        rem_ids = {id(e) for e in removed}
        both = add_ids & rem_ids
        added = [e for e in added if id(e) not in both and e.dxf.owner == msp.layout_key]
        removed = [e for e in removed if id(e) not in both]
        self.changed.emit(added, removed, regen)

    def undo(self) -> Optional[str]:
        if not self.undo_stack:
            return None
        tx = self.undo_stack.pop()
        self._apply(tx, undo=True)
        self.redo_stack.append(tx)
        self.set_modified(True)
        return tx.name

    def redo(self) -> Optional[str]:
        if not self.redo_stack:
            return None
        tx = self.redo_stack.pop()
        self._apply(tx, undo=False)
        self.undo_stack.append(tx)
        self.set_modified(True)
        return tx.name

    # ------------------------------------------------------------ helpers
    def entity_by_handle(self, handle: str):
        e = self.doc.entitydb.get(handle)
        if e is not None and e.is_alive:
            return e
        return None

    @property
    def current_layer(self) -> str:
        name = self.doc.header.get("$CLAYER", "0")
        if name not in self.doc.layers:
            name = "0"
        return name

    @current_layer.setter
    def current_layer(self, name: str):
        self.doc.header["$CLAYER"] = name
        self.layers_changed.emit()

    def default_attribs(self) -> dict:
        """DXF attributes for new entities (current layer, color, ...)."""
        h = self.doc.header
        attribs = {"layer": self.current_layer}
        color = h.get("$CECOLOR", 256)
        if color != 256:
            attribs["color"] = color
        lt = h.get("$CELTYPE", "BYLAYER")
        if lt.upper() != "BYLAYER" and lt in self.doc.linetypes:
            attribs["linetype"] = lt
        lw = h.get("$CELWEIGHT", -1)
        if lw != -1:
            attribs["lineweight"] = lw
        return attribs


def prepare_document(doc: Drawing) -> None:
    """Make sure resources used by T2D-CAD exist."""
    if "T2D" not in doc.dimstyles:
        try:
            ds = doc.dimstyles.new("T2D")
            ds.dxf.dimtxt = 2.5
            ds.dxf.dimasz = 2.5
            ds.dxf.dimexe = 1.25
            ds.dxf.dimexo = 0.625
            ds.dxf.dimgap = 0.625
            ds.dxf.dimdec = 2
            ds.dxf.dimadec = 0
            ds.dxf.dimtad = 1
            ds.dxf.dimtih = 0
            ds.dxf.dimtoh = 0
            ds.dxf.dimzin = 8
            ds.dxf.dimdsep = 46
            ds.dxf.dimblk = ""
            ds.dxf.dimlunit = 2
            ds.dxf.dimtxsty = "Standard"
        except Exception:
            pass
    if "Standard" not in doc.styles:
        doc.styles.new("Standard", dxfattribs={"font": "arial.ttf"})
    # load standard linetypes if they are missing
    try:
        from ezdxf.tools.standards import linetypes
        for name, desc, pattern in linetypes():
            if name not in doc.linetypes:
                doc.linetypes.add(name, pattern, description=desc)
    except Exception:
        pass
