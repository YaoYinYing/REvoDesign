### REvoDesign

- __version__: 1.8.1
- Exports: REvoDesignPlugin, SingletonAbstract, ConfigBus, file_extensions,
  reload_config_file, set_cache_dir, save_configuration, ROOT_LOGGER,
  setup_logging, REVODESIGN_CONFIG_FILE, set_REvoDesign_config_file,
  experiment_config, all_shortcuts

Usage example:

```python
from REvoDesign import REvoDesignPlugin, ConfigBus

# Initialize plugin (inside PyMOL context)
plugin = REvoDesignPlugin()
plugin.run_plugin_gui()

# Access configuration bus
bus = ConfigBus()
workdir = bus.get_value("work_dir", str)
```

#### REvoDesignPlugin
PyMOL Qt widget plugin hosting the REvoDesign UI.

Key methods:
- run_plugin_gui(): Open the main window.
- reinitialize(delete: bool = False): Reset state and optionally delete user config.
- set_working_directory(new_dir: Optional[str] = None): Set session working directory.

Example:
```python
plugin = REvoDesignPlugin()
plugin.run_plugin_gui()
```