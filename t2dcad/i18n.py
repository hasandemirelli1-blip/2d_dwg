"""Interface language (Türkçe / English).

The source texts are Turkish. With English selected, `tr()` translates
texts (and f-string results via templates) and `install()` translates every
widget when it is shown, plus the standard Qt dialogs, so the code does not
need a translation call at every place."""
from __future__ import annotations

import re
from typing import Optional

from t2dcad import settings

_lang: Optional[str] = None
_exact: dict[str, str] = {}
_templates: list[tuple[re.Pattern, str, str]] = []
_cache: dict[str, str] = {}

LANGUAGES = [("tr", "Türkçe"), ("en", "English")]


def lang() -> str:
    global _lang
    if _lang is None:
        _lang = str(settings.get("language", "tr") or "tr")
    return _lang


def set_language(code: str) -> None:
    """Stored for the next start of the program."""
    settings.set("language", code)


def _template_regex(key: str) -> tuple[re.Pattern, str]:
    parts = []
    i = 0
    first_literal = None
    lit = ""
    while i < len(key):
        if key.startswith("{{", i):
            lit += "{"
            i += 2
        elif key.startswith("}}", i):
            lit += "}"
            i += 2
        elif key.startswith("{}", i):
            parts.append(re.escape(lit))
            if first_literal is None and lit.strip():
                first_literal = lit
            lit = ""
            parts.append("(.*?)")
            i += 2
        else:
            lit += key[i]
            i += 1
    parts.append(re.escape(lit))
    if first_literal is None:
        first_literal = lit
    return re.compile("^" + "".join(parts) + "$", re.S), first_literal


def _load():
    if _exact or _templates:
        return
    from t2dcad.i18n_en import EN
    for k, v in EN.items():
        if "{}" in k:
            rx, probe = _template_regex(k)
            _templates.append((rx, v, probe))
        else:
            _exact[k] = v


def tr(text):
    """Translate a Turkish UI text (no-op in Turkish mode)."""
    if not text or lang() != "en" or not isinstance(text, str):
        return text
    r = _cache.get(text)
    if r is not None:
        return r
    _load()
    r = _exact.get(text)
    if r is None:
        stripped = text.strip()
        if stripped != text and stripped in _exact:
            lead = text[:len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            r = lead + _exact[stripped] + trail
    if r is None and text.endswith(":") and text[:-1].strip() in _exact:
        r = _exact[text[:-1].strip()] + ":"
    if r is None:
        for rx, en, probe in _templates:
            if probe and probe not in text:
                continue
            m = rx.match(text)
            if m:
                try:
                    r = en.format(*[tr(g) for g in m.groups()])
                except (IndexError, KeyError, ValueError):
                    r = None
                if r is not None:
                    break
    if r is None:
        r = text
    if len(_cache) < 20000:
        _cache[text] = r
    return r


# ---------------------------------------------------------------- Qt integration
def translate_widget(w) -> None:
    from PySide6.QtWidgets import (QAbstractButton, QLabel, QGroupBox, QLineEdit, QComboBox, QTabWidget,
                                   QTabBar, QMenu, QTableWidget, QToolButton, QDockWidget)
    try:
        t = w.windowTitle()
        if t:
            w.setWindowTitle(tr(t))
        tip = w.toolTip()
        if tip:
            w.setToolTip(tr(tip))
        if isinstance(w, QToolButton) and w.defaultAction() is not None:
            _translate_action(w.defaultAction())
        elif isinstance(w, QAbstractButton):
            if w.text():
                w.setText(tr(w.text()))
        elif isinstance(w, QLabel):
            if w.text():
                w.setText(tr(w.text()))
        elif isinstance(w, QGroupBox):
            w.setTitle(tr(w.title()))
        elif isinstance(w, QLineEdit):
            if w.placeholderText():
                w.setPlaceholderText(tr(w.placeholderText()))
        elif isinstance(w, QComboBox):
            for i in range(w.count()):
                txt = w.itemText(i)
                if txt:
                    n = tr(txt)
                    if n != txt:
                        w.setItemText(i, n)
        elif isinstance(w, QTabWidget):
            for i in range(w.count()):
                w.setTabText(i, tr(w.tabText(i)))
        elif isinstance(w, QTabBar):
            for i in range(w.count()):
                w.setTabText(i, tr(w.tabText(i)))
        elif isinstance(w, QMenu):
            w.setTitle(tr(w.title()))
            for a in w.actions():
                _translate_action(a)
        elif isinstance(w, QTableWidget):
            for c in range(w.columnCount()):
                it = w.horizontalHeaderItem(c)
                if it is not None:
                    it.setText(tr(it.text()))
        elif isinstance(w, QDockWidget):
            w.setWindowTitle(tr(w.windowTitle()))
    except RuntimeError:
        pass  # widget already deleted


def _translate_action(a) -> None:
    if a.text():
        a.setText(tr(a.text()))
    if a.toolTip():
        a.setToolTip(tr(a.toolTip()))
    if a.statusTip():
        a.setStatusTip(tr(a.statusTip()))
    m = a.menu()
    if m is not None:
        m.setTitle(tr(m.title()))


def translate_tree(root) -> None:
    from PySide6.QtWidgets import QWidget
    from PySide6.QtGui import QAction
    translate_widget(root)
    for w in root.findChildren(QWidget):
        translate_widget(w)
    for a in root.findChildren(QAction):
        _translate_action(a)


def install(app) -> None:
    """English mode: translate widgets when they are shown and the texts of
    the standard dialogs."""
    if lang() != "en":
        return
    _load()
    from PySide6.QtCore import QObject, QEvent
    from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog, QWidget

    class _ShowFilter(QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.Show and isinstance(obj, QWidget):
                translate_widget(obj)
            return False

    app._t2d_show_filter = _ShowFilter(app)
    app.installEventFilter(app._t2d_show_filter)

    def wrap(cls, name, idx):
        orig = getattr(cls, name)

        def f(*args, **kw):
            args = list(args)
            for i in idx:
                if i < len(args) and isinstance(args[i], str):
                    args[i] = tr(args[i])
            return orig(*args, **kw)
        setattr(cls, name, staticmethod(f))

    wrap(QFileDialog, "getOpenFileName", (1, 3))
    wrap(QFileDialog, "getOpenFileNames", (1, 3))
    wrap(QFileDialog, "getSaveFileName", (1, 3, 4))
    wrap(QFileDialog, "getExistingDirectory", (1,))
    for n in ("question", "information", "warning", "critical", "about"):
        wrap(QMessageBox, n, (1, 2))
    for n in ("getText", "getInt", "getDouble", "getItem"):
        wrap(QInputDialog, n, (1, 2))
