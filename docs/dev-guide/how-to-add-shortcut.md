# How to Add a Shortcut / PyMOL Command

This guide explains how to register a new function as a PyMOL `cmd.extend`
command, wrap it with a dialog popup, and add it to the REvoDesign
**Tools** menu.

## 1. Write the function

Place your core logic in an existing or new file under
`REvoDesign.shortcuts.wrappers/` or `REvoDesign.tools/`. Keep it as a plain
Python function that accepts keyword arguments:

```python
# src/REvoDesign/shortcuts/wrappers/my_tool.py
def my_function(threshold: float = 0.5, pdb_path: str = "") -> None:
    """Do something useful."""
    # implementation...
```

## 2. Wrap with a dialog (optional)

If the function needs user input, create a YAML config in
`src/REvoDesign/shortcuts/registry/` that describes the input fields:

```yaml
# src/REvoDesign/shortcuts/registry/my_tool.yaml
my_function:
  title: "My Tool"
  banner: "Describe what this tool does"
  options:
    - name: "threshold"
      type: float
      default: 0.5
      reason: "Score threshold for filtering"
    - name: "pdb_path"
      type: str
      default: ""
      reason: "Path to the PDB file"
      required: true
      source: File
```

Then create a wrapper module that registers the function with the dialog:

```python
# src/REvoDesign/shortcuts/wrappers/my_tool.py
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

registry = DialogWrapperRegistry("my_tool")  # matches registry/my_tool.yaml
wrapped_my_function = registry.register("my_function", my_function, use_thread=True)
```

The YAML `name` entries map to `AskedValue` fields:

| YAML key         | `AskedValue` attr   | Description                          |
|------------------|---------------------|--------------------------------------|
| `name`           | `key`               | Keyword argument name                |
| `type`           | `typing`            | `str`, `int`, `float`, `bool`        |
| `default`        | `val`               | Default value                        |
| `reason`         | `reason`            | Tooltip / help text                  |
| `required`       | `required`          | Whether the field is mandatory       |
| `choices`        | `choices`           | Static list of options               |
| `choices_from`   | (dynamic)           | See below                            |
| `source`         | `source`            | `"None"`, `"File"`, `"Directory"`    |
| `multiple_choices` | `multiple_choices` | Allow multiple selections           |

### Dynamic choices

For dropdowns populated at runtime, use `choices_from`:

```yaml
- name: "model"
  type: str
  required: true
  choices_from: "REvoDesign.my.module:function_name"
```

This resolves the dotted string `"REvoDesign.my.module:function_name"` to a
callable, invokes it, and uses the returned iterable as choices. Other supported
prefixes:

| Prefix       | Example                          | Effect                           |
|--------------|----------------------------------|----------------------------------|
| `range:`     | `range:1,10` or `range:0,20,2`   | Integer range                    |
| `FloatRange:`| `FloatRange:0.1,1.0,0.1`         | Float range                      |
| `CFG:`       | `CFG:ui.mutate.max_score`        | Look up a config value           |
| `LAMBDA:`    | `LAMBDA:[1,2,3]`                 | Evaluate a Python expression     |

### Options for `registry.register()`

| Argument             | Default | Description                         |
|----------------------|---------|-------------------------------------|
| `use_thread`         | `False` | Run in background thread            |
| `has_dynamic_values` | `False` | Accept dynamic input at call time   |
| `use_progressbar`    | `True`  | Show progress bar in threaded mode  |

### Manual dialog (without YAML)

For simple cases you can build the dialog directly with `AskedValue` and
`dialog_wrapper`:

```python
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper

@dialog_wrapper(
    title="My Tool",
    banner="Describe what this tool does",
    allow_real_time_update=False,
    options=(
        AskedValue("threshold", val=0.5, typing=float, reason="Score threshold"),
        AskedValue("pdb_path", val="", typing=str, reason="PDB file", required=True),
    ),
)
def my_function(threshold: float = 0.5, pdb_path: str = "") -> None:
    """Do something useful."""
```

## 3. Register as a PyMOL command

Open `src/REvoDesign/shortcuts/__init__.py` and add a `cmd.extend` call:

```python
from pymol import cmd
from .wrappers.my_tool import wrapped_my_function

cmd.extend("my_command", wrapped_my_function)
```

Optionally add autocompletion hints:

```python
cmd.auto_arg[0]["my_command"] = [
    cmd.auto_arg[0]["enable"][0],  # reuse existing shortcut
    "Target object",
    "",
]
```

## 4. Add to the Tools menu

Open `src/REvoDesign/application/menu.py` and add a `MenuItem` to
`TOOLS_MENU_LINKS`:

```python
from REvoDesign.basic.menu_item import MenuItem

TOOLS_MENU_LINKS = (
    # ... existing items ...
    MenuItem(
        "actionMyFunction",
        "REvoDesign.shortcuts.wrappers.my_tool:wrapped_my_function",
    ),
)
```

The first argument is a unique action name. The second is a dotted path to the
wrapped function, using the `module:attr` format.

## 5. Test

Run `cmd.extend` registered commands from PyMOL's command line:

```pymol
my_command threshold=0.8
```

For dialog-wrapped functions, the menu item or calling the wrapper directly
opens the popup window. Verify with:

```bash
conda run -n REvoDesignTestFlight make kw-test PYTEST_KW="shortcut or dialog"
```
