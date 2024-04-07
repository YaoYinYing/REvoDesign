import gc
import os

import hydra

from REvoDesign.basic import SingletonAbstract

# 0. import version info
from REvoDesign.__version__ import __version__ as VERSION

# 1. import post install module and methods
from REvoDesign.tools.post_installed import (
    experiment_config,
    set_REvoDesign_config_file,
    WITH_DEPENDENCIES,
    reload_config_file,
    set_cache_dir,
    save_configuration,
)

# 2. initialize config file
REVODESIGN_CONFIG_FILE = set_REvoDesign_config_file()
hydra.initialize_config_dir(
    version_base=None, config_dir=os.path.dirname(REVODESIGN_CONFIG_FILE)
)

# 2.5. initialize experiments directory
EXPERIMENTS_CONFIG_DIR = experiment_config()

# 3. initialize logging config and root logger
from REvoDesign.tools.logger import setup_logging

root_logger = setup_logging()

# 4. import UI bus
from REvoDesign.application.ui_driver import (
    Widget2Widget,
    ConfigBus,
)

# 5. import FileExtentions
from REvoDesign.common.FileExtentions import (
    REvoDesignFileExtentions as FileExtentions,
)

# 6. import the plugin class
from REvoDesign.REvoDesign import REvoDesignPlugin


# 7. enable garbage collection
gc.enable()

# 8. add shortcuts
from REvoDesign.shortcuts import *


__all__ = [
    'REvoDesignPlugin',
    'SingletonAbstract',
    'Widget2Widget',
    'ConfigBus',
    'WITH_DEPENDENCIES',
    'FileExtentions',
    'reload_config_file',
    'set_cache_dir',
    'save_configuration',
    'tests',
    'VERSION',
]
