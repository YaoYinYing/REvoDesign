### editor

- menu_edit_file: Open Monaco-based editor window via menu.
- MonacoEditorManager: Ensure and manage Monaco editor assets.

Example:

```python
from REvoDesign.editor.monaco.monaco import MonacoEditorManager
m = MonacoEditorManager(app_name="REvoDesign", app_author="REvoDesign")
m.ensure_editor_downloaded()
```
