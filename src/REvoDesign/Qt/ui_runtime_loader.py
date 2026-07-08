# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Runtime Qt Designer UI loading for the REvoDesign main window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from REvoDesign.Qt import QT_BACKEND, QtCore, QtUiTools, QtWidgets


def _load_pyqt_uic_module() -> Any:
    """Import the PyQt uic module matching the active PyMOL Qt backend."""

    if QT_BACKEND == "PyQt6":
        from PyQt6 import uic

        return uic
    if QT_BACKEND == "PyQt5":
        from PyQt5 import uic

        return uic
    raise ImportError(f"The active backend {QT_BACKEND!r} does not provide PyQt uic.")


def _language_change_event_type():
    event_type_owner = getattr(QtCore.QEvent, "Type", QtCore.QEvent)
    return getattr(event_type_owner, "LanguageChange")


def is_language_change_event(event: QtCore.QEvent) -> bool:
    """Return whether an event is a Qt language-change event across Qt5 and Qt6."""

    return event.type() == _language_change_event_type()


class RuntimeUiProxy:
    """Expose a runtime-loaded Designer UI through Ui_* style attributes."""

    def __init__(
        self,
        window: QtCore.QObject,
        retranslator: Callable[[QtCore.QObject], None] | None = None,
        source_ui: object | None = None,
    ) -> None:
        self._window = window
        self._retranslator = retranslator
        self._source_ui = source_ui
        self._duplicate_object_names: dict[str, list[QtCore.QObject]] = {}
        self.refresh_bindings()

        # Kept for backward compatibility with the legacy generated-UI i18n path.
        # The original generated Ui_REvoDesign held a QTranslator as `trans` so
        # that language-switching code could install / remove it.  RuntimeUiProxy
        # preserves this attribute so that existing callers (LanguageSwitch and
        # the main plugin) continue to work without modification.
        self.trans = QtCore.QTranslator(window)

    def refresh_bindings(self) -> None:
        """Bind named Qt descendants as attributes on this proxy."""

        for attr_name in list(vars(self)):
            if attr_name.startswith("_") or attr_name == "trans":
                continue
            delattr(self, attr_name)

        self._duplicate_object_names = {}
        seen_names: set[str] = set()
        for obj in [self._window, *self._window.findChildren(QtCore.QObject)]:
            object_name = obj.objectName() if hasattr(obj, "objectName") else ""
            if not object_name or not object_name.isidentifier() or object_name.startswith("_"):
                continue
            if object_name in seen_names:
                self._duplicate_object_names.setdefault(object_name, []).append(obj)
                continue
            setattr(self, object_name, obj)
            seen_names.add(object_name)

    def retranslateUi(self, window: QtCore.QObject | None = None) -> None:
        """Retranslate the loaded UI after a language change."""

        target_window = window or self._window
        if self._retranslator is not None:
            self._retranslator(target_window)
        else:
            event = QtCore.QEvent(_language_change_event_type())
            QtCore.QCoreApplication.sendEvent(target_window, event)
        self.refresh_bindings()


def _load_with_pyuic(
    ui_path: Path, parent: QtWidgets.QWidget | None = None
) -> tuple[QtWidgets.QWidget, RuntimeUiProxy]:
    uic = _load_pyqt_uic_module()
    form_class, base_class = uic.loadUiType(str(ui_path))
    window = base_class(parent)
    ui_form = form_class()
    ui_form.setupUi(window)
    if not isinstance(window, QtWidgets.QWidget):
        raise TypeError(f"Expected runtime UI root to be a QWidget, got {type(window)!r}")
    return window, RuntimeUiProxy(window, retranslator=ui_form.retranslateUi, source_ui=ui_form)


def _load_with_qtuitools(
    ui_path: Path,
    parent: QtWidgets.QWidget | None = None,
) -> tuple[QtWidgets.QWidget, RuntimeUiProxy]:
    if QtUiTools is None or not hasattr(QtUiTools, "QUiLoader"):
        raise ImportError(f"The active backend {QT_BACKEND!r} does not provide QtUiTools.QUiLoader.")

    ui_file = QtCore.QFile(str(ui_path))
    if not ui_file.open(QtCore.QIODevice.OpenModeFlag.ReadOnly):
        raise OSError(f"Unable to open UI file: {ui_path}")

    try:
        loader = QtUiTools.QUiLoader()
        if hasattr(loader, "setWorkingDirectory"):
            loader.setWorkingDirectory(QtCore.QDir(str(ui_path.parent)))
        if hasattr(loader, "setLanguageChangeEnabled"):
            loader.setLanguageChangeEnabled(True)
        window = loader.load(ui_file, parent)
    finally:
        ui_file.close()

    if not isinstance(window, QtWidgets.QWidget):
        raise TypeError(f"Expected runtime UI root to be a QWidget, got {type(window)!r}")
    return window, RuntimeUiProxy(window)


def load_runtime_ui(
    ui_path: str | Path,
    parent: QtWidgets.QWidget | None = None,
) -> tuple[QtWidgets.QWidget, RuntimeUiProxy]:
    """Load a Qt Designer UI file at runtime and expose named objects through a proxy."""

    resolved_ui_path = Path(ui_path).resolve()
    attempted_loaders: list[str] = []

    try:
        attempted_loaders.append("PyQt uic.loadUiType")
        return _load_with_pyuic(resolved_ui_path, parent=parent)
    except ImportError:
        pass

    try:
        attempted_loaders.append("QtUiTools.QUiLoader")
        return _load_with_qtuitools(resolved_ui_path, parent=parent)
    except ImportError:
        pass

    attempted = ", ".join(attempted_loaders) or "no runtime UI loader"
    raise ImportError(
        f"Unable to load {resolved_ui_path} with the active backend {QT_BACKEND!r}; attempted: {attempted}."
    )


__all__ = ["RuntimeUiProxy", "is_language_change_event", "load_runtime_ui"]
