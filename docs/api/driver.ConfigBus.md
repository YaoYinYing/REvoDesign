### driver.ConfigBus

Central UI-configuration bus (singleton) providing typed access to configuration and UI widgets.

Constructor: use `ConfigBus()`; it’s a singleton.

Key attributes:

- headless: bool
- cfg: omegaconf.DictConfig

Selected methods:

- initialize_widget_with_group() # non-headless
- update_cfg_item_from_widget(widget_id: str)
- register_widget_changes_to_cfg()
- get_widget_from_id(widget_id: str) -> QWidget
- get_widget_from_cfg_item(cfg_item: str) -> QWidget
- get_widget_value(cfg_item: str, typing) -> Any
- set_widget_value(cfg_item: str, value) -> None
- restore_widget_value(cfg_item: str) -> None
- get_cfg_item(widget_id: str) -> str
- button(id: str) -> QPushButton
- toggle_buttons(buttons: Iterable, set_enabled: bool = False)
- get_value(cfg_item: str, typing=None, reject_none: bool=False, default_value: Any=None)
- set_value(cfg_item: str, value) -> None

Example (headless value access):

```python
from REvoDesign.driver.ui_driver import ConfigBus

bus = ConfigBus()
molecule = bus.get_value("ui.header_panel.input.molecule", str, reject_none=True)
```
