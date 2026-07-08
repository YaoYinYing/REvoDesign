# UI Design

REvoDesign uses **Qt Designer** for visual UI layout. The main UI definition is
`src/REvoDesign/UI/REvoDesign.ui` — an XML file created and edited in Qt
Designer. There is also `REvoDesign-PyMOL-entry.ui` for the standalone Package
Manager installer window.

## Workflow

### Editing the UI

1. **Open `REvoDesign.ui` in Qt Designer** — Use Qt 5 Designer (matching the
   PyQt5 runtime). The VS Code "PYQT Integration" extension can also be used.

2. **Modify the layout** — Add/remove widgets, adjust layouts, set object names.
   Object names are critical: they become Python attribute names on the
   `RuntimeUiProxy` and are referenced throughout the codebase.

3. **Save** — The `.ui` file is the source of truth. Do not manually edit the
   generated typing contract.

### After UI Changes

1. **Regenerate the typing contract**:
   ```bash
   python dev/tools/generate_ui_typing.py
   ```
   This updates `src/REvoDesign/UI/types.py` with typed attributes for IDE
   autocompletion. The pre-commit hook `generate-ui-typing` runs this
   automatically.

2. **Update translations** — See [Translation](translation.md) for updating
   `.ts`/`.qm` files.

3. **Verify** — The pre-commit hook `validate-ui-i18n` smoke-tests runtime
   loading and the i18n pipeline:
   ```bash
   python dev/tools/generate_ui_typing.py --check
   ```

## Key Files

| File | Purpose |
|------|---------|
| `UI/REvoDesign.ui` | Main plugin window layout (tabs, buttons, tables, menus) |
| `UI/REvoDesign-PyMOL-entry.ui` | Package Manager installer window |
| `UI/types.py` | Auto-generated `REvoDesignUiProtocol` typing contract |
| `UI/language/` | Translation `.ts`/`.qm` files and `language.json` registry |
| `UI/liguist.pro` | Qt Linguist project file for translation pipeline |

## Runtime Loading

The `.ui` file is loaded at runtime (no code generation step) by
`RuntimeUiProxy` in `REvoDesign.Qt.ui_runtime_loader`:

```python
from REvoDesign.Qt.ui_runtime_loader import load_runtime_ui

main_window, ui = load_runtime_ui(ui_path)
```

This avoids the deprecated `Ui_REvoDesign.py` pattern. The
`reject-generated-main-ui` pre-commit hook prevents that file from being
re-introduced.

## Object Naming Conventions

Widget object names in Qt Designer follow these patterns:

- **Descriptive prefixes**: `pushButton_`, `comboBox_`, `checkBox_`,
  `radioButton_`, `spinBox_`, `doubleSpinBox_`, `tabWidget_`, `label_`,
  `groupBox_`, `tableWidget_`, `textEdit_`.
- **Config-mapped widgets**: Names match config item keys for automatic
  binding via `Widget2ConfigMapper` (see [Architecture](architecture.md)).
- **Menu actions**: Named `actionSomething_Descriptive` — these become
  `QAction` attributes on the proxy.
- **Duplicate names**: If the `.ui` file has duplicate object names,
  `RuntimeUiProxy` records them in `_duplicate_object_names` and only the
  first-seen object becomes an attribute on the proxy. Avoid duplicates.

## Adding a New Widget

1. Add the widget in Qt Designer with a unique, descriptive `objectName`.
2. If the widget maps to a config value, add an entry in
   `driver/widget_link.py` (`Config2WidgetIds` or `PushButtons`).
3. If the widget needs signal wiring, add the connection in
   `REvoDesignPlugin.__init__()` or a deferred `QTimer` callback.
4. Regenerate `types.py` and update translations.
5. If it's a new menu action, add a `MenuItem` to the appropriate tuple
   in `application/menu.py` (e.g. `TOOLS_MENU_LINKS`, `OTHER_MENU_LINKS`)
   or to `core_menu_links()` for core application actions.

## Package Manager UI

The Package Manager uses a separate `.ui` file
(`REvoDesign-PyMOL-entry.ui`) and has its own bootstrap path:

```
REvoDesignPackageManager.__init__()
  → load_runtime_ui("REvoDesign-PyMOL-entry.ui")
  → populate extras table from Gist JSON
  → wire Git solver, pip installer, and thread dashboard
```

The Package Manager `.ui` is uploaded to GitHub Gist via `make upload-gists`
for distribution. It currently has no translations.
