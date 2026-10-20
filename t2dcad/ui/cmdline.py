"""AutoCAD style command line (history + prompt + input)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QDialog, QListWidget, QListWidgetItem, QAbstractItemView)

from t2dcad import engine
from t2dcad.cmdnames import DESCRIPTIONS, POPULAR
from t2dcad.engine import GetString


def suggestions(prefix: str, limit: int = 14) -> list[tuple[str, str]]:
    """(typed word, command name) pairs for an AutoCAD style auto-complete."""
    p = prefix.strip().upper()
    if not p:
        return []
    rank = {n: i for i, n in enumerate(POPULAR)}
    out: dict[str, tuple] = {}
    for alias, cmd in engine.ALIASES.items():
        if alias.startswith(p) and not alias.startswith("__"):
            key = (0 if alias == p else 1, rank.get(cmd, 999), 1, len(alias), alias)
            if cmd not in out or key < out[cmd][0]:
                out[cmd] = (key, alias)
    for name in engine.COMMANDS:
        if name.startswith(p) and not name.startswith("__"):
            key = (0 if name == p else 1, rank.get(name, 999), 0, len(name), name)
            if name not in out or key < out[name][0]:
                out[name] = (key, name)
    items = sorted(out.items(), key=lambda kv: kv[1][0])
    return [(word, cmd) for cmd, (key, word) in items[:limit]]


class CompletionPopup(QListWidget):
    """Suggestion list shown above the command line while typing."""

    def __init__(self, cmdline):
        super().__init__(cmdline.main)
        self.cmdline = cmdline
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setStyleSheet("QListWidget{background:#2b3038;color:#e6e6e6;border:1px solid #DC6E2D;"
                           "font-family:Consolas,monospace;font-size:10pt;}"
                           "QListWidget::item{padding:2px 6px;}"
                           "QListWidget::item:selected{background:#2F6299;}")
        self.itemClicked.connect(self._clicked)

    def update_for(self, text: str):
        items = suggestions(text)
        self.clear()
        if not items:
            self.hide()
            return
        for word, cmd in items:
            desc = DESCRIPTIONS.get(cmd, "")
            label = f"{word:<10} {cmd if word != cmd else '':<14} {desc}"
            it = QListWidgetItem(label.rstrip())
            it.setData(Qt.UserRole, word)
            self.addItem(it)
        self.setCurrentRow(0)
        edit = self.cmdline.edit
        h = min(len(items), 14) * (self.sizeHintForRow(0) + 1) + 6
        w = max(360, self.sizeHintForColumn(0) + 30)
        pos = edit.mapToGlobal(QPoint(0, 0))
        self.setGeometry(pos.x(), pos.y() - h - 2, w, h)
        self.show()
        self.raise_()

    def move_selection(self, d: int):
        if self.count():
            self.setCurrentRow((self.currentRow() + d) % self.count())

    def current_word(self):
        it = self.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _clicked(self, it):
        self.cmdline.edit.setText(it.data(Qt.UserRole))
        self.hide()
        self.cmdline.submit()


class CommandLine(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.history_cmds: list[str] = []
        self.hist_pos = 0
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(1)
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setFont(font)
        self.history.setMaximumBlockCount(2000)
        self.history.setFocusPolicy(Qt.NoFocus)
        self.history.setFixedHeight(64)
        lay.addWidget(self.history)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.prompt = QLabel("Komut:")
        self.prompt.setFont(font)
        self.prompt.setStyleSheet("color:#e8e8e8;")
        self.edit = _Edit(self)
        self.edit.setFont(font)
        self.edit.setPlaceholderText("Komut yazın (ör. L, C, TR, M)...")
        row.addWidget(self.prompt)
        row.addWidget(self.edit, 1)
        lay.addLayout(row)
        self.popup = CompletionPopup(self)
        self.edit.textChanged.connect(self._text_changed)

    def _text_changed(self, text):
        mgr = self.main.manager()
        if mgr is not None and mgr.active:
            self.popup.hide()
            return
        t = text.strip()
        if not t or any(c in t for c in ",@<"):
            self.popup.hide()
            return
        self.popup.update_for(t)

    # ------------------------------------------------------------ output
    def add_history(self, text: str):
        self.history.appendPlainText(text)
        self.history.moveCursor(QTextCursor.End)

    def set_prompt(self, text: str):
        self.prompt.setText(text)

    def show_history_window(self):
        dlg = QDialog(self.main)
        dlg.setWindowTitle("T2D-CAD Metin Penceresi")
        dlg.resize(700, 450)
        v = QVBoxLayout(dlg)
        t = QPlainTextEdit()
        t.setReadOnly(True)
        t.setFont(self.history.font())
        t.setPlainText(self.history.toPlainText())
        t.moveCursor(QTextCursor.End)
        v.addWidget(t)
        dlg.exec()

    # ------------------------------------------------------------ input
    def submit(self, use_popup=True):
        text = self.edit.text()
        if use_popup and self.popup.isVisible():
            # AutoCAD runs the highlighted suggestion unless the text is a command itself
            word = self.popup.current_word()
            if word and engine.resolve(text) is None:
                text = word
        self.popup.hide()
        self.edit.clear()
        mgr = self.main.manager()
        if mgr is None:
            if text.strip():
                self.add_history("Önce bir çizim açın veya yeni çizim oluşturun.")
            return
        if text.strip():
            if not mgr.active:
                self.history_cmds.append(text.strip())
                self.hist_pos = len(self.history_cmds)
            self.add_history(f"{self.prompt.text()} {text}")
        mgr.text_input(text)

    def handle_key(self, ev: QKeyEvent) -> bool:
        """Keyboard handling for both the canvas and the edit field."""
        key = ev.key()
        mgr = self.main.manager()
        tab = self.main.current_tab()
        if key == Qt.Key_Escape:
            self.popup.hide()
            self.edit.clear()
            if mgr and mgr.active:
                mgr.cancel()
            elif tab:
                tab.canvas.window_start = None
                tab.canvas.osnap_override = None
                tab.canvas.clear_selection()
                tab.canvas.update()
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.submit()
            return True
        if key == Qt.Key_Space:
            if mgr and mgr.active and isinstance(mgr.req, GetString) and mgr.req.spaces:
                self.edit.insert(" ")
            else:
                self.submit()
            return True
        if key == Qt.Key_Backspace:
            self.edit.backspace()
            return True
        if key == Qt.Key_Delete and not self.edit.text():
            if tab and not (mgr and mgr.active) and tab.canvas.selection:
                mgr.start("ERASE")
            return True
        if key in (Qt.Key_Up, Qt.Key_Down) and self.popup.isVisible():
            self.popup.move_selection(-1 if key == Qt.Key_Up else 1)
            return True
        if key == Qt.Key_Tab and self.popup.isVisible():
            w = self.popup.current_word()
            if w:
                self.edit.setText(w)
            return True
        if key == Qt.Key_Up and not (mgr and mgr.active and mgr.req):
            if self.history_cmds:
                self.hist_pos = max(0, self.hist_pos - 1)
                self.edit.setText(self.history_cmds[self.hist_pos])
            return True
        if key == Qt.Key_Down and not (mgr and mgr.active and mgr.req):
            if self.history_cmds:
                self.hist_pos = min(len(self.history_cmds), self.hist_pos + 1)
                self.edit.setText(self.history_cmds[self.hist_pos] if self.hist_pos < len(self.history_cmds) else "")
            return True
        text = ev.text()
        if text and text.isprintable() and not (ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            self.edit.insert(text)
            return True
        return False


class _Edit(QLineEdit):
    def __init__(self, cmdline: CommandLine):
        super().__init__()
        self.cmdline = cmdline

    def keyPressEvent(self, ev: QKeyEvent):
        key = ev.key()
        if key in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Up, Qt.Key_Down,
                   Qt.Key_Tab):
            if self.cmdline.handle_key(ev):
                tab = self.cmdline.main.current_tab()
                if tab and key != Qt.Key_Space:
                    tab.canvas.setFocus()
                return
        super().keyPressEvent(ev)
