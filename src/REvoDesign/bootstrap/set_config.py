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

    print('-'*79)
    print('Ensuring the configuration directory...')

    # if main config file does not exist, 
    # a new release may have been upgrated to. 
    # copy the config tree from template
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

    # othwerwise, check the structure of the config tree. If there are missing files or keys, 
    # a new minor release may have been upgrated to.
    # fix the config tree from template
    else:
        print(f"Config file is already located at `{config_dir}`, do nothing.")
    
        print(f'Verifying the structure of the configuration directory...')
        verify_config_tree_structure(config_dir, template_config_dir)
        print('Enforcing the key structure of the configuration directory...')
        
        enforce_config_key_structure(config_dir, template_config_dir)
        
    print(f"Main config: {main_config_file}")
    print('All set.')
    print('-'*79)
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
    """
    Save configuration to specified directory
    
    Args:
        new_cfg (DictConfig): The configuration object to be saved
        config_name (str, optional): Configuration file name, defaults to "main"
    
    Returns:
        None
    """
    from . import REVODESIGN_CONFIG_DIR

    # Build the path for saving the configuration file
    cfg_save_fp = os.path.join(REVODESIGN_CONFIG_DIR, f"{config_name}.yaml")
    OmegaConf.save(new_cfg, cfg_save_fp)
    print(f"Saved configuration: {cfg_save_fp}")
    return


def experiment_config(name: str = "experiments") -> str:
    """
    Create and return the path to the experiment configuration directory.
    
    This function creates an experiment directory based on the global configuration directory 
    and the specified name. If the directory doesn't exist, it automatically creates it, 
    ensuring the directory exists before returning its full path.
    
    Args:
        name (str): The name of the experiment directory, defaults to "experiments"
        
    Returns:
        str: The full path to the experiment directory
    """
    from . import REVODESIGN_CONFIG_DIR

    # Build the experiment directory path and create the directory
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
        # Check if the input is a DictConfig instance and perform conversion
        if isinstance(config, DictConfig):
            return ConfigConverter._recursive_convert(config)
        # Raise error if input is not a DictConfig instance
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
        config_dir (str): Path to the configuration directory
        tree (bool): If True, returns a recursive list of paths to all YAML files in the directory tree. 
            Defaults to False.

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


def _iter_yaml_rel_paths(base_dir: str) -> list[str]:
    """
    Iterates through the specified directory and its subdirectories to collect relative paths of all .yaml files
    
    Args:
        base_dir (str): The base directory path to traverse
    
    Returns:
        list[str]: A list containing relative paths of all found .yaml files with respect to base_dir, sorted in lexicographical order
    """
    base_dir = os.path.abspath(base_dir)
    rel_paths: list[str] = []
    # Traverse the directory tree to find all .yaml files
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".yaml"):
                abs_path = os.path.join(root, file)
                rel_paths.append(os.path.relpath(abs_path, base_dir))
    return sorted(rel_paths)


def verify_config_tree_structure(user_config_dir: str, template_config_dir: str) -> list[str]:
    """
    Ensures every YAML file in the template tree exists in the user's config directory.
    Missing files are copied over, preserving the relative directory structure.

    Args:
        user_config_dir (str): Path to the user's configuration directory where files should be present
        template_config_dir (str): Path to the template configuration directory containing reference files

    Returns:
        list[str]: List of relative paths of files that were copied from template to user config directory
    """
    # Initialize list to track copied files
    copied: list[str] = []
    
    # Get all YAML file paths from template directory
    template_files = _iter_yaml_rel_paths(template_config_dir)
    user_config_dir = os.path.abspath(user_config_dir)
    template_config_dir = os.path.abspath(template_config_dir)

    # Process each template file to ensure it exists in user config
    for rel_path in template_files:
        src = os.path.join(template_config_dir, rel_path)
        dst = os.path.join(user_config_dir, rel_path)
        if os.path.exists(dst):
            continue
        
        # Create parent directories if they don't exist
        dst_parent = os.path.dirname(dst)
        if dst_parent:
            os.makedirs(dst_parent, exist_ok=True)
        
        # Copy file and record the operation
        shutil.copy2(src, dst)
        copied.append(rel_path)
        print(f'Copied {src} to {dst}')
    return copied


def _collect_key_paths(node, prefix: tuple[str, ...], bag: set[tuple[str, ...]]):
    """
    Recursively collects all key paths in a nested data structure
    
    Args:
        node: The data node to traverse (can be dictionary, list, or other type)
        prefix: Current path prefix stored as a tuple of keys in the path
        bag: A set used to store all found key paths
    
    Returns:
        None, results are stored directly in the bag parameter
    """
    if isinstance(node, dict):
        # Traverse each key-value pair in the dictionary, build path and recursively process values
        for key, value in node.items():
            key_path = prefix + (str(key),)
            bag.add(key_path)
            _collect_key_paths(value, key_path, bag)
    elif isinstance(node, list):
        # Traverse each element in the list, keeping the current path prefix for recursive calls
        for item in node:
            _collect_key_paths(item, prefix, bag)


def _yaml_key_signature(path: str) -> frozenset[tuple[str, ...]]:
    cfg = OmegaConf.load(path)
    container = OmegaConf.to_container(cfg, resolve=False)
    bag: set[tuple[str, ...]] = set()
    _collect_key_paths(container, tuple(), bag)
    return frozenset(bag)


def enforce_config_key_structure(user_config_dir: str, template_config_dir: str) -> list[str]:
    """
    Compares YAML files between template and user directories and replaces files
    whose key structure differs from the template.

    Args:
        user_config_dir (str): Path to the user configuration directory
        template_config_dir (str): Path to the template configuration directory

    Returns:
        list[str]: Returns a list of relative paths of files that were replaced
    """
    from REvoDesign.issues import InternalError

    # Define list of files to be ignored
    ignored= (
        "environ.yaml",
    )

    replaced: list[str] = []
    template_files = _iter_yaml_rel_paths(template_config_dir)
    user_config_dir = os.path.abspath(user_config_dir)
    template_config_dir = os.path.abspath(template_config_dir)

    for rel_path in template_files:
        template_file = os.path.join(template_config_dir, rel_path)
        user_file = os.path.join(user_config_dir, rel_path)

        # Check if user file exists, raise internal error if it doesn't
        if not os.path.exists(user_file):
            raise InternalError(f"Missing file: {user_file}, which should have already been copied from {template_file}")
        
        # Skip ignored files
        if os.path.basename(rel_path) in ignored:
            print(f'Skipped {rel_path} due to being ignored')
            continue

        # Compare YAML file key signatures, if they don't match, replace user file with template file
        if _yaml_key_signature(template_file) != _yaml_key_signature(user_file):
            shutil.copy2(template_file, user_file)
            replaced.append(rel_path)
            print(f'Replaced {user_file} -> {template_file}')
    return replaced
