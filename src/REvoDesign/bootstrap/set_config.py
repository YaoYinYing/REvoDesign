"""
Module for bootstrapping REvoDesign with Hydra and OmegaConf.
"""

import glob
import importlib.util
import os
import shutil
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf
from platformdirs import user_cache_dir, user_data_dir

from REvoDesign.Qt import QtCore, QtWidgets


def decide(title="", description="", rich: bool = False, details: str | None = None):
    """
    A copy of decide function from package_manager.py
    """

    # A confirmation message.
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(description)
    if details is not None:
        msg.setDetailedText(details)
    if rich:
        msg.setTextFormat(QtCore.Qt.RichText)
    msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    result = msg.exec_()

    return result == QtWidgets.QMessageBox.Yes


def set_REvoDesign_config_file(delete_user_config_tree: bool = False):
    """
    Sets the REvoDesign configuration directory. If the main configuration file does not exist,
    it will be copied from the template directory. If the configuration directory exists,
    it will also be checked for potential issues.

    Arguments:
        delete_user_config_tree (bool): Whether to delete the user's configuration tree. Defaults to False.

    Returns:
        str: The path to the REvoDesign configuration directory.

    """
    template_config_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "config",
    )

    default_storage_path = user_data_dir(appname="REvoDesign")
    config_dir = os.path.join(default_storage_path, "config")

    main_config_file = os.path.join(config_dir, "main.yaml")

    if delete_user_config_tree and os.path.exists(config_dir):
        print("WARNING: The configuration directory will be deleted as required")
        shutil.rmtree(config_dir)

    # if main config file does not exist, copy the config tree from template
    if not os.path.isfile(main_config_file):
        if os.path.isdir(config_dir) and [x for x in os.listdir(config_dir) if not x.endswith(".yaml")]:
            reset_warning = (
                "Warning: The configuration directory is not empty, which means you are upgrading REvoDesign. "
                "A proper reset is recommended to avoid any potential issues. "
            )
            print(reset_warning)

            if decide(
                title="Reset REvoDesign Configuration?",
                description=reset_warning + "Do you want to continue? \n"
                "You can still choose to cancel the reset to proceed it manually.",
            ):

                shutil.rmtree(config_dir)
            else:
                print("Please manually delete the configuration directory and restart REvoDesign.")

        print(f"Copied configurations from {template_config_dir} to {config_dir}")
        shutil.copytree(src=template_config_dir, dst=config_dir, dirs_exist_ok=True)
    else:
        print(f"Config file is already located at `{config_dir}`, do nothing.")

    print(f"Main config: {main_config_file}")
    return main_config_file


def reload_config_file(
    config_name: str = "main", overrides: list[str] | None = None, return_hydra_config: bool = False
) -> DictConfig:
    """
    Reload a configuration yaml file in a Hydra manner. As we initialize hydra w/ initialize_config_dir,
    which is the REVODESIGN_CONFIG_DIR at user's data directory, the config_name is supposed as a relative path of the yaml file.
    e.g. config_name="experiments/my_experiment" refers to experiments/my_experiment.yaml
    the DictConfig object can be accessed like `reload_config_file(config_name="experiments/my_experiment")["experiments"]`

    Arguments:
        config_name (str): The name of the configuration file. Defaults to "main".
        overrides (list[str]): A list of overrides to apply to the configuration. Defaults to None.
        return_hydra_config (bool): Whether to return the Hydra configuration. Defaults to False.
    """
    return hydra.compose(
        config_name=config_name,
        overrides=overrides,
        return_hydra_config=return_hydra_config,
    )


def save_configuration(new_cfg: DictConfig, config_name: str = "main"):
    from . import REVODESIGN_CONFIG_DIR

    cfg_save_fp = os.path.join(REVODESIGN_CONFIG_DIR, f"{config_name}.yaml")
    OmegaConf.save(new_cfg, cfg_save_fp)
    print(f"Saved configuration: {cfg_save_fp}")
    return


def experiment_config(name: str = "experiments") -> str:
    from . import REVODESIGN_CONFIG_DIR

    experiments_dir = os.path.join(REVODESIGN_CONFIG_DIR, name)
    os.makedirs(experiments_dir, exist_ok=True)
    return experiments_dir


def set_cache_dir() -> str:
    from REvoDesign.driver.ui_driver import ConfigBus

    bus: ConfigBus = ConfigBus()
    cfg: DictConfig = bus.cfg_group["main"].cfg
    if not cfg.cache_dir.under_home_dir and not cfg.cache_dir.customized:
        raise ValueError("You must specify a custom cache directory!")

    if cfg.cache_dir.under_home_dir:
        cache_dir = user_cache_dir(appname="REvoDesign", ensure_exists=True)
    else:
        cache_dir = os.path.expanduser(cfg.cache_dir.customized)
    return cache_dir


class ConfigConverter:
    """
    A utility class to convert omegaconf.DictConfig objects to standard Python dictionaries.
    This conversion is done recursively to handle nested DictConfig objects.
    """

    @staticmethod
    def convert(config: DictConfig) -> dict:
        """
        Converts an omegaconf.DictConfig object to a standard Python dictionary.

        Usage:
            converted_dict = ConfigConverter.convert(dict_config)

        :param config: The DictConfig object to convert.
        :return: A standard Python dictionary representation of the input DictConfig.
        """
        if isinstance(config, DictConfig):
            return ConfigConverter._recursive_convert(config)
        raise ValueError("Input must be an instance of omegaconf.DictConfig")

    @staticmethod
    def _recursive_convert(config: Any) -> Any:
        """
        Recursively converts an omegaconf.DictConfig object or its nested structures
        to a standard Python dictionary. This method handles the recursion.

        :param config: The DictConfig object or its nested structure.
        :return: A standard Python dictionary or the original type if not DictConfig.
        """
        if isinstance(config, DictConfig):
            return {key: ConfigConverter._recursive_convert(value) for key, value in config.items()}
        if isinstance(config, list):
            return [ConfigConverter._recursive_convert(item) for item in config]
        return config


def is_package_installed(package):
    """
    Function: is_package_installed
    Usage: is_installed = is_package_installed(package)

    This function checks if a specified package is installed in the current Python environment.

    Args:
    - package (str): Name of the package to check

    Returns:
    - bool: True if the package is installed, False otherwise
    """
    package_loader = importlib.util.find_spec(package)
    return package_loader is not None

def list_all_config_files(config_dir: str, tree: bool = False) -> list[str]:
    """
    Function: list_all_config_files
    Usage: config_files = list_all_config_files(config_dir)

    This function lists all YAML configuration files in the specified directory.

    Args:
    - config_dir (str): Path to the configuration directory

    Returns:
    - list[str]: List of paths to YAML configuration files
    """
    if not tree:
        return sorted(glob.glob(os.path.join(config_dir, "*.yaml")))

    config_dir = os.path.abspath(config_dir)
    yaml_files: list[str] = []
    for root, _, files in os.walk(config_dir):
        if root == config_dir:
            continue
        yaml_files.extend(os.path.join(root, f) for f in files if f.endswith(".yaml"))
    return sorted(yaml_files)
