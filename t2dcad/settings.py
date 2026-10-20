"""Persistent user settings (stored by QSettings in the Windows registry)."""
from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QSettings

_qs: QSettings | None = None


def _s() -> QSettings:
    global _qs
    if _qs is None:
        if os.environ.get("T2D_TEST"):
            # tests must never touch the user's real settings
            _qs = QSettings(os.path.join(tempfile.gettempdir(), "t2dcad_test.ini"), QSettings.IniFormat)
        else:
            _qs = QSettings("T2D", "T2D-CAD")
    return _qs


def get(key: str, default=None):
    v = _s().value(key, default)
    return default if v is None else v


def get_bool(key: str, default: bool = False) -> bool:
    v = _s().value(key, default)
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes")
    return bool(v)


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(_s().value(key, default))
    except (TypeError, ValueError):
        return default


def get_float(key: str, default: float = 0.0) -> float:
    try:
        return float(_s().value(key, default))
    except (TypeError, ValueError):
        return default


def set(key: str, value) -> None:  # noqa: A001
    _s().setValue(key, value)


def get_list(key: str) -> list[str]:
    v = _s().value(key, [])
    if isinstance(v, str):
        return [v] if v else []
    return list(v or [])
