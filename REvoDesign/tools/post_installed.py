import os
import hydra
from omegaconf import DictConfig
from typing import Any


def set_REvoDesign_config_file():
    default_storage_path = os.path.expanduser('~/.REvoDesign/')
    config_dir = os.path.join(default_storage_path, 'config')

    os.makedirs(config_dir, exist_ok=True)

    config_file = os.path.join(config_dir, 'global_config.yaml')

    if not os.path.exists(config_file):
        import shutil

        template_config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..',
            'config/revodesign/global_config.yaml',
        )
        shutil.copyfile(template_config_file, config_file)
        print(f'Config file is created at {config_file}')
    else:
        print(f'Config file is located at {config_file}')

    return config_file


REVODESIGN_CONFIG_FILE = set_REvoDesign_config_file()
hydra.initialize_config_dir(
    version_base=None, config_dir=os.path.dirname(REVODESIGN_CONFIG_FILE)
)


def reload_config_file(config_name: str = 'global_config') -> DictConfig:
    return hydra.compose(
        config_name=config_name,
        return_hydra_config=True,
    )


# def save_to_config_file(cfg:DictConfig, drop_groups: bool = True) -> None:


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
