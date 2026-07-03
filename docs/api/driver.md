# Driver Layer

The driver layer is the central nervous system of REvoDesign — a bidirectional bridge between Qt UI widgets and OmegaConf/Hydra YAML configuration files. It manages singleton lifecycle, widget-to-config mapping, file dialogs, group registries, environment variables, and parameter toggle connections.

---

## Core Classes

### Config

```python
@dataclass
class Config:
    name: str
    path: str
    cfg: DictConfig
```

::: REvoDesign.driver.ui_driver.Config

### ConfigBus (detailed methods)

`ConfigBus` is the main singleton that orchestrates the UI-config bridge. It extends `SingletonAbstract` and `CitableModuleAbstract`. See the [Core API overview](core.md) for a higher-level introduction.

::: REvoDesign.driver.ui_driver.ConfigBus
    options:
        members:
            - singleton_init
            - initialize_widget_with_group
            - register_widget_changes_to_cfg
            - update_cfg_item_from_widget
            - get_widget_from_id
            - get_widget_from_cfg_item
            - get_widget_value
            - set_widget_value
            - restore_widget_value
            - get_cfg_item
            - get_value
            - set_value
            - toggle_buttons
            - fp_lock
            - button
            - buttons

### Widget2ConfigMapper

Maps UI widgets to configuration items and provides lookup methods across both directions.

::: REvoDesign.driver.ui_driver.Widget2ConfigMapper
    options:
        members:
            - __init__
            - find_child
            - get_button_from_id
            - all_widget_ids
            - all_cfg_items
            - widget_id2config_dict
            - find_config_item
            - get_widget_from_id

### StoresWidget

A singleton that holds server-switch references (`MenuActionServerMonitor` instances) used across the application. Provides a `reset_instance` classmethod.

::: REvoDesign.driver.ui_driver.StoresWidget

### HeadlessProtocol

A `typing.Protocol` that defines objects capable of running in headless mode, requiring a `headless: bool` attribute.

::: REvoDesign.driver.ui_driver.HeadlessProtocol

### require_non_headless decorator

::: REvoDesign.driver.ui_driver.require_non_headless

---

## Widget Link

### PushButtons

A frozen dataclass holding the canonical list of all push button IDs used across REvoDesign tabs.

::: REvoDesign.driver.widget_link.PushButtons

### Config2WidgetIds

A frozen dataclass that maps configuration item keys to widget IDs and classifies widget types (e.g. `pushButton` → `QPushButton`, `comboBox` → `QComboBox`).

::: REvoDesign.driver.widget_link.Config2WidgetIds
    options:
        members:
            - wi_types
            - c2wi
            - get_widget_typing

---

## Group Registry

### GroupRegistryItem

A frozen dataclass representing a single group registry entry — pairs a configuration item name with callables that dynamically generate its available values.

::: REvoDesign.basic.group_registries.GroupRegistryItem

### CallableGroupValues

Static-method namespace providing all the callables used as group generators for dropdown menus across the UI.

::: REvoDesign.driver.group_register.CallableGroupValues
    options:
        members:
            - list_some_blanks
            - list_score_matrix
            - list_color_map
            - list_installed_mutate_runners
            - list_all_profile_parsers
            - list_all_designers
            - list_all_scorers
            - list_all_rosetta_node_hints
            - list_cluster_methods

### GroupRegistryCollection

Module-level tuple that collects all `GroupRegistryItem` instances used to populate combo boxes (color maps, score matrices, cluster methods, profile types, scorers, sidechain solvers, Rosetta node hints).

::: REvoDesign.driver.group_register.GroupRegistryCollection

---

## File Dialog

### IO_MODE

Type alias for file I/O operations: `Literal["r", "w"]`.

::: REvoDesign.driver.file_dialog.IO_MODE

### FileDialog

Singleton providing centralized file browsing, opening, and saving across all tabs. Connects browse buttons to config items automatically.

::: REvoDesign.driver.file_dialog.FileDialog
    options:
        members:
            - singleton_init
            - browse_multiple_files
            - browse_filename
            - open_file
            - open_mutant_table
            - register_file_dialog_buttons

### flatten_compressed_files

Utility function that extracts a compressed archive into an `expanded_compressed_files/` subdirectory and returns the extraction path.

::: REvoDesign.driver.file_dialog.flatten_compressed_files

---

## Environment Registration

### register_environment_variables

Reads environment variable bindings from the `environ.yaml` configuration file and exports them to `os.environ`. Must be called after `ConfigBus` initialization.

::: REvoDesign.driver.environ_register.register_environment_variables

---

## Parameter Toggle Registration

### ParamChangeRegistryItem

A frozen dataclass that defines how a change in one widget should propagate to another configuration item via a widget signal.

::: REvoDesign.basic.param_toggle.ParamChangeRegistryItem
    options:
        members:
            - widget_signal
            - register

### ParamChangeRegister

A dataclass that collects multiple `ParamChangeRegistryItem` instances and registers them all with a shared callback function.

::: REvoDesign.basic.param_toggle.ParamChangeRegister
    options:
        members:
            - register_all

### ParamChangeCollections

The concrete `ParamChangeRegister` instance used by the driver, connecting sidechain-solver weight changes and profile-type `prefer_lower` toggles.

::: REvoDesign.driver.param_toggle_register.ParamChangeCollections
