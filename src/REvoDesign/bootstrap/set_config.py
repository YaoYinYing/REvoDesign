import glob
import importlib.util
import os
import shutil
from typing import Any, List, Optional
import hydra
from omegaconf import DictConfig, OmegaConf
from platformdirs import user_cache_dir, user_data_dir
def set_REvoDesign_config_file(delete_user_config_tree: bool = False):
    template_config_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "config",
    )
    default_storage_path = user_data_dir(appname="REvoDesign")
    config_dir = os.path.join(default_storage_path, "config")
    if delete_user_config_tree and os.path.exists(config_dir):
        print(
            "WARNING: The configuration directory will be deleted as required"
        )
        shutil.rmtree(config_dir)
    if not glob.glob(os.path.join(config_dir, "*.yaml")):
        print(
            f"Copied configuratiosn from {template_config_dir} to {config_dir}"
        )
        shutil.copytree(
            src=template_config_dir, dst=config_dir, dirs_exist_ok=True
        )
    else:
        print(f"Config file is already located at `{config_dir}`, do nothing.")
    main_config_file = os.path.join(config_dir, "global_config.yaml")
    print(f"Main config: {main_config_file}")
    return main_config_file
def reload_config_file(config_name: str = "global_config",
                       overrides: Optional[List[str]] = None,
                       return_hydra_config: bool = False) -> DictConfig:
    return hydra.compose(
        config_name=config_name,
        overrides=overrides,
        return_hydra_config=return_hydra_config,
    )
def save_configuration(
    new_cfg: DictConfig, config_name: str = "global_config"
):
    from . import REVODESIGN_CONFIG_FILE
    cfg_save_dir = os.path.dirname(REVODESIGN_CONFIG_FILE)
    cfg_save_fp = os.path.join(cfg_save_dir, f"{config_name}.yaml")
    OmegaConf.save(new_cfg, cfg_save_fp)
    print(f"Saved configuration: {cfg_save_fp}")
    return
def experiment_config():
    from . import REVODESIGN_CONFIG_FILE
    experiments_dir = os.path.join(
        os.path.dirname(REVODESIGN_CONFIG_FILE), "experiments"
    )
    os.makedirs(experiments_dir, exist_ok=True)
    return experiments_dir
def set_cache_dir() -> str:
    from REvoDesign.driver.ui_driver import ConfigBus
    bus: ConfigBus = ConfigBus()
    cfg: DictConfig = bus.cfg
    if not cfg.cache_dir.under_home_dir and not cfg.cache_dir.customized:
        raise ValueError("You must specify a custom cache directory!")
    if cfg.cache_dir.under_home_dir:
        cache_dir = user_cache_dir(appname="REvoDesign", ensure_exists=True)
    else:
        cache_dir = os.path.expanduser(cfg.cache_dir.customized)
    return cache_dir
class ConfigConverter:
    @staticmethod
    def convert(config: DictConfig) -> dict:
        if isinstance(config, DictConfig):
            return ConfigConverter._recursive_convert(config)
        raise ValueError("Input must be an instance of omegaconf.DictConfig")
    @staticmethod
    def _recursive_convert(config: Any) -> Any:
        if isinstance(config, DictConfig):
            return {
                key: ConfigConverter._recursive_convert(value)
                for key, value in config.items()
            }
        if isinstance(config, list):
            return [
                ConfigConverter._recursive_convert(item) for item in config
            ]
        return config
def is_package_installed(package):
    package_loader = importlib.util.find_spec(package)
    return package_loader is not None