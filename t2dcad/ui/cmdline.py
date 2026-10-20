"""AutoCAD style command line (history + prompt + input)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QDialog)

from t2dcad.engine import GetString


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
    def submit(self):
        text = self.edit.text()
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
        if key in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Up, Qt.Key_Down):
            if self.cmdline.handle_key(ev):
                tab = self.cmdline.main.current_tab()
                if tab and key != Qt.Key_Space:
                    tab.canvas.setFocus()
                return
        super().keyPressEvent(ev)
