import pytest
from unittest.mock import MagicMock, patch, call
from REvoDesign.bootstrap.set_config import (
    set_REvoDesign_config_file,
    reload_config_file,
    save_configuration,
    experiment_config,
    set_cache_dir,
    ConfigConverter,
    is_package_installed
)
from omegaconf import OmegaConf, DictConfig


def test_set_REvoDesign_config_file():
    with patch("REvoDesign.bootstrap.set_config.os.path.exists", return_value=False), \
         patch("REvoDesign.bootstrap.set_config.glob.glob", return_value=[]), \
         patch("REvoDesign.bootstrap.set_config.shutil.copytree") as mock_copytree:

        main_config = set_REvoDesign_config_file()
        mock_copytree.assert_called_once()
        assert "global_config.yaml" in main_config

def test_reload_config_file():
    with patch("REvoDesign.bootstrap.set_config.hydra.compose", return_value=DictConfig({"key": "value"})) as mock_compose:
        config = reload_config_file()
        mock_compose.assert_called_once_with(config_name="global_config", return_hydra_config=False)
        assert config["key"] == "value"

def test_save_configuration():
    with patch("REvoDesign.bootstrap.set_config.OmegaConf.save") as mock_save, \
         patch("REvoDesign.bootstrap.set_config.os.path.dirname", return_value="/mock/path"):

        config = OmegaConf.create({"key": "value"})
        save_configuration(config)
        mock_save.assert_called_once_with(config, "/mock/path/global_config.yaml")

def test_experiment_config():
    with patch("REvoDesign.bootstrap.set_config.os.makedirs") as mock_makedirs, \
         patch("REvoDesign.bootstrap.set_config.os.path.dirname", return_value="/mock/path"):

        exp_dir = experiment_config()
        mock_makedirs.assert_called_once_with("/mock/path/experiments", exist_ok=True)
        assert "experiments" in exp_dir

def test_set_cache_dir():
    mock_bus = MagicMock()
    mock_bus.cfg.cache_dir.under_home_dir = True
    mock_bus.cfg.cache_dir.customized = ""

    with patch("REvoDesign.ConfigBus", return_value=mock_bus), \
         patch("REvoDesign.bootstrap.set_config.user_cache_dir", return_value="/mock/cache/dir") as mock_user_cache_dir:

        cache_dir = set_cache_dir()
        mock_user_cache_dir.assert_called_once_with(appname="REvoDesign", ensure_exists=True)
        assert cache_dir == "/mock/cache/dir"

def test_config_converter():
    config = DictConfig({"key": {"nested_key": "value"}})
    result = ConfigConverter.convert(config)
    assert isinstance(result, dict)
    assert result["key"]["nested_key"] == "value"

def test_is_package_installed():
    with patch("REvoDesign.bootstrap.set_config.importlib.util.find_spec", return_value=True):
        assert is_package_installed("omegaconf") is True

    with patch("REvoDesign.bootstrap.set_config.importlib.util.find_spec", return_value=None):
        assert is_package_installed("nonexistent") is False
