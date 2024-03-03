from dataclasses import dataclass
import importlib
import os
import hydra
from omegaconf import DictConfig, OmegaConf
from typing import Any, Union
import glob
import shutil


def set_REvoDesign_config_file():
    template_config_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..',
        'config',
    )

    default_storage_path = os.path.expanduser('~/.REvoDesign/')
    config_dir = os.path.join(default_storage_path, 'config')

    if not glob.glob(os.path.join(config_dir, '*.yaml')):
        print(
            f'Copied configuratiosn from {template_config_dir} to {config_dir}'
        )
        shutil.copytree(
            src=template_config_dir, dst=config_dir, dirs_exist_ok=True
        )
    else:
        print(f'Config file is already located at `{config_dir}`, do nothing.')

    main_config_file = os.path.join(config_dir, 'global_config.yaml')
    print(f'Main config: {main_config_file}')
    return main_config_file


def reload_config_file(config_name: str = 'global_config') -> DictConfig:
    return hydra.compose(
        config_name=config_name,
        return_hydra_config=False,
    )


def save_configuration(
    new_cfg: DictConfig, config_name: Union[str, None] = None
):
    from REvoDesign import REVODESIGN_CONFIG_FILE

    if not config_name:
        config_name = 'global_config'
    cfg_save_dir = os.path.dirname(REVODESIGN_CONFIG_FILE)
    cfg_save_fp = os.path.join(cfg_save_dir, f'{config_name}.yaml')
    OmegaConf.save(new_cfg, cfg_save_fp)
    print('Saved configuration.')
    return


def experiment_config():
    from REvoDesign import REVODESIGN_CONFIG_FILE

    experiments_dir = os.path.join(
        os.path.dirname(REVODESIGN_CONFIG_FILE), 'experiments'
    )
    os.makedirs(experiments_dir, exist_ok=True)
    return experiments_dir


def set_cache_dir() -> str:
    cfg: DictConfig = reload_config_file()
    if not cfg.cache_dir.under_home_dir and not cfg.cache_dir.customized:
        raise ValueError('You must specify a custom cache directory!')

    if cfg.cache_dir.under_home_dir:
        cache_dir = os.path.expanduser('~/.REvoDesign/')
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
        if not isinstance(config, DictConfig):
            raise ValueError(
                "Input must be an instance of omegaconf.DictConfig"
            )

        return ConfigConverter._recursive_convert(config)

    @staticmethod
    def _recursive_convert(config: Any) -> Any:
        """
        Recursively converts an omegaconf.DictConfig object or its nested structures
        to a standard Python dictionary. This method handles the recursion.

        :param config: The DictConfig object or its nested structure.
        :return: A standard Python dictionary or the original type if not DictConfig.
        """
        if isinstance(config, DictConfig):
            return {
                key: ConfigConverter._recursive_convert(value)
                for key, value in config.items()
            }
        elif isinstance(config, list):
            return [
                ConfigConverter._recursive_convert(item) for item in config
            ]
        else:
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


@dataclass(frozen=True)
class WITH_DEPENDENCIES:
    COLABDESIGN = is_package_installed('colabdesign')
    DLPACKER = is_package_installed('DLPacker')
    PIPPACK = is_package_installed('pippack')
