import pytest

from REvoDesign.driver.ui_driver import ConfigBus


# Pytest tests
def test_require_non_headless_in_headless_mode():
    config_bus = ConfigBus()
    with pytest.raises(RuntimeError, match="cannot be called when the application is running in headless mode"):
        config_bus.initialize_widget_with_group()

    language = config_bus.get_value("language")
    assert language is not None
