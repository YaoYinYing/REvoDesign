# Translation (i18n)

REvoDesign supports multiple languages via **Qt Linguist** (`.ts`/`.qm` files).
The translation system is managed by `LanguageSwitch` in the
`REvoDesign.application.i18n` package.

## How It Works

### Translation sources

REvoDesign has three sources of translatable strings:

1. **`.ui` widget strings** — Labels, tooltips, and menu section titles defined in
   `REvoDesign.ui`, `value_dialog.ui`, and `launching.ui`.  These are extracted
   by `pylupdate5` and stored in `.ts` files with `<location>` tags.

2. **Python-source strings** — Dynamic menu items (config-edit links, font settings,
   runtime tools) and dialog messages that use `_translate()` in builder functions.
   These are **hand-maintained** in the `.ts` files — `pylupdate5` cannot reliably
   extract them from Python source (it does not follow aliases or resolve variables).

3. **YAML dialog strings** — `title`, `banner`, and `reason` fields in
   `shortcuts/registry/*.yaml` are translated at display time by `ValueDialog`
   via `_translate("ValueDialog", ...)`.  `reason` strings are kept as English
   source on the `AskedValue` dataclass so that open dialogs can retranslate
   after a language switch.

### Translator lifecycle

`install_translator_early()` (in `language_settings.py`) reads the saved
language from `main.yaml` directly and installs the translator on the
`QApplication` **before** the launching/splash page is shown, so the splash
appears in the correct language from the first paint.

When `LanguageSwitch` is later created during `make_window()`, its
`_ensure_translator()` finds and reuses the early-installed translator,
preventing duplicate translator instances.

### Language Files

Translation files live in `src/REvoDesign/UI/language/`:

```
UI/language/
├── language.json    # Registry: maps language codes to display names and actions
├── eng-chs.ts       # English → Chinese (Simplified) — Qt Linguist source
├── eng-chs.qm       # English → Chinese (Simplified) — compiled binary
├── eng-cht.ts       # English → Chinese (Traditional)
└── eng-cht.qm       # English → Chinese (Traditional)
```

- **`.ts` files** are XML-based Qt Linguist source files. Edit these in
  Qt Linguist or by hand to add or update translations.
- **`.qm` files** are compiled binary translations loaded at runtime.
- **`language.json`** is the registry that maps language codes to human-readable
  names and PyMOL menu action IDs.

### language.json format

Each entry maps a language code to a display name and menu action:

```json
[
  {"code": "eng-eng", "name": "English",              "action": "actionEnglish"},
  {"code": "eng-chs", "name": "简体中文",              "action": "actionChinese"},
  {"code": "eng-cht", "name": "繁體中文",              "action": "actionChineseTraditional"},
  {"code": "eng-fr",  "name": "français",             "action": "actionFrench"}
]
```

Not all entries require `.qm` files — `eng-eng` (English) has no translation
binary, and some registered languages may lack completed translations.

### LanguageSwitch

`LanguageSwitch` (in `application/i18n/language_settings.py`) manages the
translator lifecycle:

1. **`_ensure_translator()`** — Checks the `QApplication` for an early-installed
   translator from `install_translator_early()`, then falls back to
   `bus.ui.trans` (legacy path), and creates a fresh translator only as a last
   resort.
2. **`switch_language(language)`** — Removes the previous translator from the
   application, loads the new `.qm` file, installs it, calls `ui.retranslateUi()`
   to refresh all static widget text, then iterates `open_windows` and calls
   `retranslateUi()` on each window that supports it (e.g. `ValueDialog`).
   Dynamic menu items created at startup are not re-created, but their
   `action_text` strings are translated at binding time via lazy builder
   functions (see `application/menu.py`).
3. **`_retranslate_language_actions()`** — Updates the dynamic language-switch
   menu items to show the correct language name.

### Translation contexts

| `.ts` context | Source | Strings |
|---|---|---|
| `REvoDesignPyMOL_UI` | `REvoDesign.ui` + hand-maintained | Main window, menu items |
| `ValueDialog` | `value_dialog.ui` + hand-maintained | Dialog column headers, buttons, YAML `title`/`banner`/`reason` |
| `LaunchingPage` | `launching.ui` + hand-maintained | Splash page + 10 bootstrap status messages |

### ValueDialog retranslation pattern

`ValueDialog` defers translation to display time so that open dialogs
retranslate correctly after a language switch:

1. **Title and banner** — YAML strings are passed as raw English source
   from `shortcuts/utils.py`.  `ValueDialog.__init__` stores the source
   (`_title_source_text`, `_banner_source_text`) and translates via
   `_tr("ValueDialog", source)` only for display.  `retranslateUi`
   re-translates from the stored source.

2. **Action buttons** — Each button stores its English source strings as
   Qt dynamic properties (`source_text`, `source_tooltip`) in
   `_add_field_to_table`.  `_retranslate_row` reads these properties
   instead of maintaining a separate objectName→source mapping,
   and handles both direct-`QPushButton` cell widgets (Browse,
   Pick Color) and container-embedded buttons (JsonInput, multi-choice).

## Adding a New Language

1. **Create the `.ts` file** — Use Qt Linguist or `pylupdate5`:
   ```bash
   pylupdate5 src/REvoDesign/UI/REvoDesign.ui src/REvoDesign/UI/value_dialog.ui src/REvoDesign/UI/launching.ui -ts src/REvoDesign/UI/language/eng-xxx.ts
   ```

2. **Add the new language to `language.json`** — Register it with a unique
   `code`, `name`, and matching `action` ID:
   ```json
   {
     "code": "eng-xxx",
     "name": "English → New Language",
     "action": "actionSwitch_to_New_Language"
   }
   ```

3. **Translate** — Open the `.ts` file in Qt Linguist, fill in translations for
   each UI string.

4. **Build** — Compile `.ts` → `.qm`:
   ```bash
   make translate
   ```

5. **Test** — Restart PyMOL and switch to the new language via the menu.

## Runtime Behavior

- The active language is stored in the config (`main.yaml`) under `language`.
- On plugin startup, `install_translator_early()` reads this config and loads
  the corresponding `.qm` file **before** the splash dialog is shown.
- When `LanguageSwitch` is later initialized, it reuses the early-installed
  translator.
- The language can be switched at runtime via **Menu > Language > ...**.
- `retranslateUi()` refreshes all static UI text and any open `ValueDialog`
  instances. There is no restart warning — all visible strings update immediately.
- Dynamic text (e.g., mutant scores) is language-agnostic.
- Package Manager currently has no translations.

## Updating Translations After UI Changes

When `.ui` files are modified:

1. Regenerate the UI typing contract:
   ```bash
   python dev/tools/generate_ui_typing.py
   ```

2. Run `make translate` — this runs `pylupdate5` on all three `.ui` files to
   update the `.ts` files with new/changed widget strings, strips
   `type="obsolete"` and `type="unfinished"` from hand-maintained entries so
   they are not dropped, then compiles `.ts` → `.qm` via `lrelease`.

   ```bash
   make translate
   ```

   The script (`tools/translate.sh`) scans `REvoDesign.ui`, `value_dialog.ui`,
   and `launching.ui` for widget strings.  Dynamic-menu and dialog strings in
   Python source are hand-maintained — add or update their `<message>` entries
   directly in the `.ts` files.

   The script uses portable `sed -i.bak` + `rm -f` (compatible with both
   BSD/macOS and GNU/Linux) and iterates over `.ts` files via glob rather
   than `ls` output.

### Adding a new Python-source string

When you add a `_translate()` call in Python source (e.g., a new menu item
in `menu.py`, a dialog in `language_settings.py`, or a YAML `reason` field):

1. Add a `<message>` entry by hand to both `eng-chs.ts` and `eng-cht.ts`
   inside the appropriate context (`REvoDesignPyMOL_UI`, `ValueDialog`, or
   `LaunchingPage`):
   ```xml
   <message>
       <source>Your English string</source>
       <translation>你的中文翻译</translation>
   </message>
   ```

2. Omit the `<location>` tag — `pylupdate5` will mark the entry `type="obsolete"`,
   but the `sed` step in `translate.sh` strips that attribute so the translation
   survives into the compiled `.qm`.

3. Rebuild:
   ```bash
   make translate
   ```

## API Reference

For the `LanguageSwitch`, `LanguageNameRegistry`, and `LanguageItem` API,
see [Application API](../api/application.md).
