import gc
from REvoDesign.basic import SingletonAbstract
from REvoDesign.bootstrap import (REVODESIGN_CONFIG_FILE, experiment_config,
                                  reload_config_file, save_configuration,
                                  set_cache_dir, set_REvoDesign_config_file)
from REvoDesign.common import file_extensions
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.logger import ROOT_LOGGER, setup_logging
from REvoDesign.REvoDesign import REvoDesignPlugin
from REvoDesign.shortcuts import __all__ as all_shortcuts
__version__ = "1.8.3"
gc.enable()
__all__ = [
    "REvoDesignPlugin",
    "SingletonAbstract",
    "ConfigBus",
    "file_extensions",
    "reload_config_file",
    "set_cache_dir",
    "save_configuration",
    "ROOT_LOGGER",
    "setup_logging",
    "REVODESIGN_CONFIG_FILE",
    "set_REvoDesign_config_file",
    "experiment_config",
    "all_shortcuts",
]