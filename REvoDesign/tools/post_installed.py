import os
from absl import logging
import hydra
from omegaconf import DictConfig


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
        logging.info(f'Config file is created at {config_file}')
    else:
        logging.info(f'Config file is located at {config_file}')

    return config_file


REVODESIGN_CONFIG_FILE = set_REvoDesign_config_file()
hydra.initialize_config_dir(
    version_base=None, config_dir=os.path.dirname(REVODESIGN_CONFIG_FILE)
)


def reload_config_file() -> DictConfig:
    return hydra.compose(
        config_name=os.path.basename(REVODESIGN_CONFIG_FILE).replace(
            '.yaml', ''
        ),
        return_hydra_config=True,
    )


def set_cache_dir() -> str:
    cfg: DictConfig = reload_config_file()
    if not cfg.cache_dir.under_home_dir and not cfg.cache_dir.customized:
        raise ValueError('You must specify a custom cache directory!')

    if cfg.cache_dir.under_home_dir:
        cache_dir = os.path.expanduser('~/.REvoDesign/')
    else:
        cache_dir = os.path.expanduser(cfg.cache_dir.customized)
    return cache_dir
