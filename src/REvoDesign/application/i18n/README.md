# Translate REvoDesign into Your Language

REvoDesign uses Qt Translation files to translate the user interface into different languages.

# DO THIS

1. Setup Qt Linguist.
2. Load the UI and translate each string one after another.
3. Save the translation file (`*.ts`) in the `UI/languages` directory.`
4. Add the language to the `UI/languages/languages.json` file so that it can be loaded by the program.
5. Add the language as a new line of the linguist project file `src/REvoDesign/UI/liguist.pro`: `TRANSLATIONS += language/<language-code>.ts`
6. Compile the translation file by running `make translate`
7. After the compile, run `make black` to format the Py-code of UI file.
8. Add the translation files(`*.ts`, `*.qm`) to the commit and push to a new branch.
9. Create a pull request to merge the translation.

## Language Registry

REvoDesign uses a JSON file to record the languages that are available for translation.
The JSON file is located at `UI/languages/languages.json`.

Basically the record contains the following fields:

```json
[
    {"code":"eng-fr","name": "français", "action": "actionFrench"}
]
```

- `code`: The language code. This is used to identify the language in the program and the translation file prefix.
- `name`: The name of the language. This is used to display the language in the menu.
- `action`: The action to trigger name when the language is selected.

## DON'T DO THIS

DO NOT hardcode any new language action to the menu manually.
