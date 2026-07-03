# Qt Layer

The Qt compatibility layer abstracts PyQt5/PyQt6 differences behind a unified import surface. All REvoDesign modules **must** import Qt bindings exclusively through `REvoDesign.Qt` — never directly from `PyQt5` or `PyQt6`. A pre-commit hook (`check-qt-binding-imports`) enforces this.

---

## Module-Level Imports

These objects are re-exported from `REvoDesign.Qt` for convenient access:

| Export | Description |
|---|---|
| `QtCore` | QtCore module from the active backend (PyQt5 or PyQt6) |
| `QtGui` | QtGui module from the active backend |
| `QtWidgets` | QtWidgets module from the active backend |
| `QtNetwork` | QtNetwork module, or `None` if unavailable |
| `QtWebSockets` | QtWebSockets module, or `None` if unavailable |
| `QtSvg` | QtSvg module, or `None` if unavailable |
| `QtUiTools` | QtUiTools module, or `None` if unavailable |

---

## Backend Detection

### QT_BACKEND

A string identifying the active Qt backend (`"PyQt5"`, `"PyQt6"`, or `"pymol.Qt"`). Detected at import time from `pymol.Qt.PYQT_NAME`.

### QT_MAJOR

An integer representing the Qt major version (5 or 6). Extracted from `QT_BACKEND` by regex.

### QtSource

Alias for `QT_BACKEND`. Preserved for backward compatibility.

### QtCompat

Namespace of compatibility constants that work across both Qt5 and Qt6 backends: message-box icons, standard buttons, widget attributes, alignment flags, check states, scroll-bar policies, and more.

::: REvoDesign.Qt.qt_wrapper.QtCompat

---

## Runtime UI Loading

### RuntimeUiProxy

Exposes named Qt objects from a runtime-loaded Designer `.ui` file as attributes on the proxy. Mimics the old generated-UI (`Ui_REvoDesign`) pattern without requiring code generation.

::: REvoDesign.Qt.ui_runtime_loader.RuntimeUiProxy
    options:
        members:
            - __init__
            - refresh_bindings
            - retranslateUi

### load_runtime_ui

Loads a Qt Designer `.ui` file at runtime. First attempts PyQt `uic.loadUiType`, then falls back to `QtUiTools.QUiLoader`. Returns a `(QMainWindow, RuntimeUiProxy)` tuple.

::: REvoDesign.Qt.ui_runtime_loader.load_runtime_ui

### is_language_change_event

Checks whether a `QEvent` is a language-change event across Qt5 and Qt6.

::: REvoDesign.Qt.ui_runtime_loader.is_language_change_event

---

## Compatibility Helpers

### has_qt_module

Returns `True` when the named Qt module is available from the active backend.

::: REvoDesign.Qt.has_qt_module

### install_qt6_aliases

Installs Qt6-style scoped enum aliases on the active backend's Qt namespace, plus flat backward-compatible aliases for Qt5-style code. Covers `QtCore`, `QtWidgets`, `QtGui`, `QtNetwork`, and `QtWebSockets` enums.

::: REvoDesign.Qt.qt_wrapper.install_qt6_aliases

### install_qt5_aliases

Backward-compatible alias that delegates to `install_qt6_aliases`.

::: REvoDesign.Qt.qt_wrapper.install_qt5_aliases

### qexec

Cross-version `exec` call (Qt5 uses `exec_()`, Qt6 uses `exec()`).

::: REvoDesign.Qt.qexec

---

## UI Protocol

### REvoDesignUiProtocol

A static typing contract (typing.Protocol) auto-generated from `REvoDesign.ui` by `dev/tools/generate_ui_typing.py`. Provides typed attribute declarations for IDE completion and static analysis — it never constructs the UI at runtime. The pre-commit hook `generate-ui-typing` keeps it in sync with the `.ui` file.

::: REvoDesign.UI.types.REvoDesignUiProtocol
