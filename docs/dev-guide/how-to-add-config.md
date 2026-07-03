# How to Add a New Configuration File

This guide covers adding a new YAML configuration file and wiring it into the
REvoDesign configuration system.

## 1. Create the YAML file

Place your file under `src/REvoDesign/config/` (top-level) or in a
subdirectory for logical grouping:

```text
src/REvoDesign/config/
  my_settings.yaml          # top-level config
  my_module/
    defaults.yaml           # nested config (grouped under a subdirectory)
```

The file uses standard YAML with no special schema. The bootstrap system will
copy it to the user config directory on next plugin launch.

## 2. Bootstrap copies it automatically

On startup, `REvoDesign.bootstrap.set_config.verify_config_tree_structure()`
scans the template directory (`src/REvoDesign/config/`) and copies any missing
`.yaml` files to the user config directory
(`~/.local/share/REvoDesign/config/` on Linux, equivalent on macOS/Windows).

If a file already exists but its key structure diverges from the template,
`enforce_config_key_structure()` replaces it. Files named `environ.yaml` are
ignored during structure enforcement (they are user-specific).

```python
# REvoDesign/bootstrap/__init__.py (simplified)
_TEMPLATE_CONFIG_DIR = "src/REvoDesign/config/"
verify_config_tree_structure(REVODESIGN_CONFIG_DIR, _TEMPLATE_CONFIG_DIR)
enforce_config_key_structure(REVODESIGN_CONFIG_DIR, _TEMPLATE_CONFIG_DIR)
```

## 3. Load the config in code

Use `reload_config_file()` to compose and load your config via Hydra:

```python
from REvoDesign.bootstrap import reload_config_file

cfg = reload_config_file("my_settings")
value = cfg.my_settings.some_key
```

The argument is the config name without the `.yaml` extension, relative to the
config directory. For nested files, include the subdirectory prefix:

```python
cfg = reload_config_file("my_module/defaults")
```

The loaded object is an `omegaconf.DictConfig`. You can access values by
attribute or by key, and use OmegaConf's merge/update utilities.

Alternatively, config files are pre-loaded into `ConfigBus().cfg_group`, keyed
by their name:

```python
from REvoDesign.driver.ui_driver import ConfigBus

bus = ConfigBus()
main_cfg = bus.cfg_group["main"].cfg
my_cfg = bus.cfg_group["my_settings"].cfg
```

This is populated at startup by `Config.from_files()` in
`REvoDesign.driver.ui_driver`.

## 4. Wire config to UI widgets

If your config drives a UI widget (text field, spinner, checkbox, combo box),
add a mapping to `Config2WidgetIds` in
`REvoDesign.driver.widget_link.py`:

```python
# Inside the c2wi frozen dict
"my_settings.some_key": "lineEdit_my_widget",
```

The key is the dotted config path (e.g. `my_settings.some_key`), and the value
is the Qt object name of the widget. Supported widget types are:

| Config prefix      | Qt widget type       |
|--------------------|----------------------|
| `pushButton_*`     | `QPushButton`        |
| `lineEdit_*`       | `QLineEdit`          |
| `comboBox_*`       | `QComboBox`          |
| `spinBox_*`        | `QSpinBox`           |
| `doubleSpinBox_*`  | `QDoubleSpinBox`     |
| `checkBox_*`       | `QCheckBox`          |

## 5. Populate combo box choices

If your config drives a combo box with dynamic choices, add a group generator
in `REvoDesign.driver.group_register.py`:

```python
GroupMyConfig = GR(
    "comboBox_my_choice",
    (CallableGroupValues.list_some_blanks,),
)
```

Then add it to `GroupRegistryCollection`:

```python
GroupRegistryCollection: tuple[GR, ...] = (
    ...
    GroupMyConfig,
)
```

The callable(s) passed to `GR` return the list of choices shown in the
dropdown. You can chain multiple callables to merge lists.

## 6. Menu edit links (automatic)

The Edit Configuration menu is populated automatically by
`REvoDesign.application.menu.py`. It scans the user config directory for all
`.yaml` files and generates a `MenuItem` for each. Non-hidden config files in
subdirectories (except `cache/` and `experiments/`) appear under section
headers. No action is needed on your part.
