---
name: qt-pymol-guardrails
description: Enforce REvoDesign Qt/PyMOL conventions. Use when touching Qt imports, threading, UI loading, PyMOL API calls, or i18n strings. Catch the mistakes that cause SIGABRT or silent breakage across Qt5/Qt6.
when_to_use: Qt widget code, PyMOL cmd usage, thread spawning, .ui file changes, translation strings, RuntimeUiProxy usage
---

# Qt + PyMOL Guardrails

## Qt imports — the cardinal rule

**NEVER import PyQt5, PyQt6, or PySide directly in runtime code.** Every Qt import goes through `REvoDesign.Qt`:

```python
from REvoDesign.Qt import QtCore, QtWidgets, QtGui
```

The pre-commit hook `check_qt_binding_imports.py` enforces this. At TYPE_CHECKING time the wrapper imports from PyQt5 for static analysis; at runtime it resolves through `pymol.Qt`.

## Qt5/Qt6 compatibility

- **Dialogs**: `qexec(dialog)` not `dialog.exec()` or `dialog.exec_()`. From `REvoDesign.Qt.qt_wrapper`.
- **Enums**: Use `QtCompat.AlignCenter` (from qt_wrapper) rather than `QtCore.Qt.AlignCenter`.
- **Scoped enum lookup**: `_qt_enum(owner, enum_name, member_name)` when writing compatibility-sensitive code.
- `QT_BACKEND` and `QT_MAJOR` are set at import time. Don't branch on them unless you have to.

## Threading — the load-bearing rule

**Long-lived event-loop servers (uvicorn, asyncio) MUST use `threading.Thread`, never `QThread`.**

This is not pedantry — QThread creates a SIP-managed C++ object whose Python wrapper can outlive the C++ object during GC. When cross-thread Qt signals touch the stale wrapper → `sipWrapper_dealloc` → `forgetObject` → `QMessageLogger::fatal` → SIGABRT. Heisenbug: moves every time you change code.

- **`threading.Thread`**: uvicorn servers, asyncio event loops, long-lived background work not coupled to Qt widgets. Pattern: `_run_server_and_mark_stopped` wraps `server.run()` in `try/finally` clearing `is_running`.
- **`WorkerThread` (QThread)**: short-lived Qt-adjacent jobs where signals/slots are needed. Created via `run_worker_thread_in_pool(fn, trigger_buttons=..., notify_slot=...)`.
- **Joining `threading.Thread` from main thread**: pump Qt events with `QApplication.processEvents()` so UI doesn't freeze.
- **Testing**: Mock `threading.Thread` with `MagicMock(is_alive.return_value=False)`, no `spec=WorkerThread`.

## UI loading — runtime only

- **Load .ui files**: `load_runtime_ui(ui_path)` returns `(window, RuntimeUiProxy)`. Never compile .ui to Python modules.
- **Apply .ui to existing widget**: `apply_ui_to_widget(ui_path, widget)`.
- **Access named widgets**: `RuntimeUiProxy` exposes them as attributes via `refresh_bindings()` (walks `findChildren`, uses `objectName()`). Never `findChild()` directly.
- **Duplicate names**: collected in `_duplicate_object_names`, only first-seen becomes attribute.
- **Regenerate types after .ui changes**: `python dev/tools/generate_ui_typing.py`. Pre-commit hook enforces freshness. `REvoDesignUiProtocol` in `types.py` is for static analysis only — it never constructs the UI.
- `Ui_REvoDesign.py` is **deprecated** and blocked by `reject_generated_main_ui.py` pre-commit hook.

## PyMOL API patterns

Import convention: `from pymol import cmd` (never `import pymol; pymol.cmd.xxx`).

Common operations: `cmd.get("session_file")`, `cmd.save(filename)`, `cmd.load(filepath)`, `cmd.reinitialize()`, `cmd.remove(selection)`, `cmd.alter(selection, expr)`, `cmd.select(name, expr)`, `cmd.get_names(type=..., enabled_only=...)`, `cmd.get_model(selection)`, `cmd.get_chains(selection)`, `cmd.get_coords(selection)`, `cmd.centerofmass(selection)`.

Session reset pattern: save to temp → `cmd.reinitialize()` → `cmd.load(temp)` → `cmd.remove('not alt ""+A')` → `cmd.alter("all", 'alt=""')`.

Other imports: `from pymol import cgo`, `from pymol.vfont import plain`, `from pymol.parsing import QuietException`, `from pymol.plugins import addmenuitemqt`, `import pymol2` (for sub-interpreters).

## i18n / Translation

- User-visible strings: `_translate = QtCore.QCoreApplication.translate` then `_translate("Context", "string")`.
- Language registry: `src/REvoDesign/UI/language/language.json` — entries with `code`, `name`, `action`. `.qm` files alongside.
- Two-phase translator install: `install_translator_early()` before splash (reads from YAML directly), then `LanguageSwitch` after window creation.
- `RuntimeUiProxy.retranslateUi()` dispatches to generated retranslateUi or sends `LanguageChange` event.
- `LanguageSwitch._retranslate_language_actions()` handles menu action texts (not covered by .ui retranslation).
- New language: add `.qm` file + JSON entry. English (`eng-eng`) has no `.qm` — source strings are the fallback.

## Exceptions and logging

- Base exception: `REvoDesignException` in `src/REvoDesign/issues/exceptions.py`.
- Base warning: `REvoDesignWarning` in `src/REvoDesign/issues/warnings.py`.
- Warnings issued as `warnings.warn(issues.SomeWarning("message"))`.
- `notify_box(message, error_type, details)` shows QMessageBox from any thread (marshals to GUI thread).
- Logger: `ROOT_LOGGER.getChild(__name__)` for module-level, `ROOT_LOGGER.getChild(self.__class__.__name__)` for class-level. JSON-structured via `REvoDesignLogFormatter`.
