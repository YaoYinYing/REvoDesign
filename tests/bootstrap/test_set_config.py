import os
from unittest.mock import MagicMock, patch

import pytest
from omegaconf import DictConfig, OmegaConf

from REvoDesign.bootstrap.set_config import (
    ConfigConverter,
    _iter_yaml_rel_paths,
    experiment_config,
    is_package_installed,
    list_all_config_files,
    reload_config_file,
    save_configuration,
    set_cache_dir,
    set_REvoDesign_config_file,
    verify_config_tree_structure,
)
from tests.conftest import DATA_DIRNAME

# from tests.conftest import check_real_config_dir

# check_real_config_dir() # failed


def test_set_REvoDesign_config_file():
    # check_real_config_dir() # failed
    with (
        patch("REvoDesign.bootstrap.set_config.os.path.isfile", return_value=False),
        patch("REvoDesign.bootstrap.set_config.os.path.isdir", return_value=False),
        patch("REvoDesign.bootstrap.set_config.os.listdir", return_value=[]),
        patch("REvoDesign.bootstrap.set_config.shutil.copytree") as mock_copytree,
    ):

        main_config = set_REvoDesign_config_file()
        mock_copytree.assert_called_once()
        assert "main.yaml" in main_config


def test_reload_config_file():
    with patch(
        "REvoDesign.bootstrap.set_config.hydra.compose", return_value=DictConfig({"key": "value"})
    ) as mock_compose:
        config = reload_config_file()
        mock_compose.assert_called_once_with(config_name="main", overrides=None, return_hydra_config=False)
        assert config["key"] == "value"


def test_save_configuration():
    with (
        patch("REvoDesign.bootstrap.set_config.OmegaConf.save") as mock_save,
        patch("REvoDesign.bootstrap.os.path.dirname", return_value="/mock/path"),
    ):
        from REvoDesign.bootstrap import REVODESIGN_CONFIG_DIR

        config = OmegaConf.create({"key": "value"})
        save_configuration(config)
        mock_save.assert_called_once_with(config, f"{REVODESIGN_CONFIG_DIR}/main.yaml")


def test_experiment_config():
    with (patch("REvoDesign.bootstrap.set_config.os.makedirs") as mock_makedirs,):
        from REvoDesign.bootstrap import REVODESIGN_CONFIG_DIR

        exp_dir = experiment_config()
        mock_makedirs.assert_called_once_with(f"{REVODESIGN_CONFIG_DIR}/experiments", exist_ok=True)
        assert "experiments" in exp_dir


def test_set_cache_dir():
    mock_bus = MagicMock()
    mock_bus.cfg_group["main"].cache_dir.under_home_dir = True
    mock_bus.cfg_group["main"].cache_dir.customized = ""

    with (
        patch("REvoDesign.ConfigBus", return_value=mock_bus),
        patch("REvoDesign.bootstrap.set_config.user_cache_dir", return_value="/mock/cache/dir") as mock_user_cache_dir,
    ):

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


@pytest.mark.parametrize("user_decide", [True, False])
def test_main_config_upgrade(user_decide, patch_config_user_data):
    with (
        patch("REvoDesign.bootstrap.set_config.decide", return_value=user_decide) as mock_decide,
        # main.yaml not exists
        patch("REvoDesign.bootstrap.set_config.os.path.isfile", return_value=False),
        # configure dir exists
        patch("REvoDesign.bootstrap.set_config.os.path.isdir", return_value=True),
        # configure dir exists
        patch("REvoDesign.bootstrap.set_config.os.listdir", return_value=["master.yaml", "a_dir"]),
        # if user has decide, the tree will be removed
        patch("REvoDesign.bootstrap.set_config.shutil.rmtree") as mock_rmtree,
        # whatever, the new tree will be copied
        patch("REvoDesign.bootstrap.set_config.shutil.copytree") as mock_copytree,
    ):

        set_REvoDesign_config_file()
        mock_decide.assert_called_once()
        mock_copytree.assert_called_once()
        if user_decide:
            mock_rmtree.assert_called_once()
        else:
            mock_rmtree.assert_not_called()


def test_iter_yaml_rel_paths(tmp_path):
    base_dir = tmp_path / "configs"
    base_dir.mkdir()
    (base_dir / "root.yaml").write_text("root: 1\n")
    (base_dir / "readme.txt").write_text("ignore\n")
    nested = base_dir / "nested"
    nested.mkdir()
    (nested / "child.yaml").write_text("child: 2\n")
    (nested / "another.txt").write_text("nope\n")
    deeper = nested / "deeper"
    deeper.mkdir()
    (deeper / "deep.yaml").write_text("deep: 3\n")

    results = _iter_yaml_rel_paths(str(base_dir))
    expected = [
        "root.yaml",
        os.path.join("nested", "child.yaml"),
        os.path.join("nested", "deeper", "deep.yaml"),
    ]
    assert results == sorted(expected)


def test_verify_config_tree_structure_copies_missing_files(tmp_path):
    template_dir = tmp_path / "template"
    user_dir = tmp_path / "user"
    template_dir.mkdir()
    user_dir.mkdir()

    (template_dir / "main.yaml").write_text("template: true\n")
    nested_template = template_dir / "subdir"
    nested_template.mkdir()
    (nested_template / "missing.yaml").write_text("copied: true\n")

    (user_dir / "main.yaml").write_text("template: false\n")

    copied = verify_config_tree_structure(str(user_dir), str(template_dir))
    assert copied == [os.path.join("subdir", "missing.yaml")]
    copied_file = user_dir / "subdir" / "missing.yaml"
    assert copied_file.exists()
    assert copied_file.read_text() == "copied: true\n"
    assert (user_dir / "main.yaml").read_text() == "template: false\n"


def test_verify_config_tree_structure_no_missing_files(tmp_path):
    template_dir = tmp_path / "template"
    user_dir = tmp_path / "user"
    template_dir.mkdir()
    user_dir.mkdir()

    files = [
        template_dir / "base.yaml",
        template_dir / "nested" / "inner.yaml",
    ]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"content for {path.name}\n")
        user_path = user_dir / path.relative_to(template_dir)
        user_path.parent.mkdir(parents=True, exist_ok=True)
        user_path.write_text(f"user {path.name}\n")

    with patch("REvoDesign.bootstrap.set_config.shutil.copy2") as mock_copy:
        copied = verify_config_tree_structure(str(user_dir), str(template_dir))

    assert copied == []
    mock_copy.assert_not_called()
