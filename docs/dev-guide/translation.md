# Translation (i18n)

REvoDesign supports multiple languages via **Qt Linguist** (`.ts`/`.qm` files).
The translation system is managed by `LanguageSwitch` in the
`REvoDesign.application.i18n` package.

## How It Works

### Translation sources

REvoDesign has two sources of translatable strings:

1. **`.ui` widget strings** — Labels, tooltips, and menu section titles defined in
   `REvoDesign.ui`.  These are extracted by `pylupdate5` and stored in the `.ts`
   files with `<location>` tags pointing back to the `.ui` file.

2. **Python-source strings** — Dynamic menu items (config-edit links, font settings,
   runtime tools) and dialog messages that use `_translate()` in builder functions.
   These are **hand-maintained** in the `.ts` files — `pylupdate5` cannot reliably
   extract them from Python source (it does not follow aliases or resolve variables).

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
  {"code": "eng-chs", "name": "中文",                  "action": "actionChinese"},
  {"code": "eng-cht", "name": "繁體中文",              "action": "actionChineseTraditional"},
  {"code": "eng-fr",  "name": "français",             "action": "actionFrench"}
]
```

Not all entries require `.qm` files — `eng-eng` (English) has no translation
binary, and some registered languages may lack completed translations.

### LanguageSwitch

`LanguageSwitch` (in `application/i18n/language_settings.py`) manages the
translator lifecycle:

1. **`_ensure_translator()`** — Checks for an existing `QTranslator` on the
   application. If none exists, creates one from the `.qm` file for the
   configured language code.
2. **`switch_language(language, *, show_restart_warning=True)`** — Removes the
   previous translator from the application, loads the new `.qm` file, installs
   it, and calls `ui.retranslateUi()` to refresh all static widget text.  On
   user-triggered switches, shows a QMessageBox warning that dynamic menu items
   require a restart.  During startup (`restore_from_config()`), the warning is
   suppressed via `show_restart_warning=False`.
3. **`_retranslate_language_actions()`** — Updates the dynamic language-switch
   menu items to show the correct language name.

### Known limitation

Dynamic menu items (config-edit links, font settings, runtime tools) are created
once at startup by builder functions in `application/menu.py`.  They use
`_translate()` at creation time to set the display text, so they capture the
language that was active when the app started.  Switching language mid-session
retranslates static `.ui` actions via `retranslateUi()`, but dynamic items
stay in the original language until the next restart.

## Adding a New Language

1. **Create the `.ts` file** — Use Qt Linguist or `pylupdate5`:
   ```bash
   pylupdate5 src/REvoDesign/UI/REvoDesign.ui -ts src/REvoDesign/UI/language/eng-xxx.ts
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

- The active language is stored in the config (`main.yaml`) under
  `language`.
- On plugin startup, `LanguageSwitch` reads this config and loads the
  corresponding `.qm` file.
- The language can be switched at runtime via **Menu > Language > ...**.
- `retranslateUi()` refreshes all static UI text. Dynamic text (e.g., mutant
  scores) is language-agnostic.
- Package Manager currently has no translations.

## Updating Translations After UI Changes

When `.ui` files are modified:

1. Regenerate the UI typing contract:
   ```bash
   python dev/tools/generate_ui_typing.py
   ```

2. Run `make translate` — this runs `pylupdate5` on `REvoDesign.ui` to
   update the `.ts` files with new/changed widget strings, strips
   `type="obsolete"` from hand-maintained Python-source entries so they
   are not dropped, then compiles `.ts` → `.qm` via `lrelease`.

   ```bash
   make translate
   ```

   The script (`tools/translate.sh`) scans only `REvoDesign.ui` for
   widget strings.  Dynamic-menu and dialog strings in Python source are
   hand-maintained — add or update their `<message>` entries directly in
   the `.ts` files.

### Adding a new Python-source string

When you add a `_translate()` call in Python source (e.g., a new menu
item in `application/menu.py` or a dialog in `language_settings.py`):

1. Add a `<message>` entry by hand to both `eng-chs.ts` and `eng-cht.ts`
   inside the `REvoDesignPyMOL_UI` context:
   ```xml
   <message>
       <source>Your English string</source>
       <translation>你的中文翻译</translation>
   </message>
   ```

2. Rebuild:
   ```bash
   make translate
   ```

   The `sed` step in `translate.sh` strips `type="obsolete"` so
   hand-maintained entries without `<location>` tags are included in the
   compiled `.qm`.

## API Reference

For the `LanguageSwitch`, `LanguageNameRegistry`, and `LanguageItem` API,
see [Application API](../api/application.md).
