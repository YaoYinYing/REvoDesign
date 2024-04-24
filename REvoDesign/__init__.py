import gc
import os

import hydra

# -2. import basic
from REvoDesign.basic import SingletonAbstract

# -1. import FileExtentions
from REvoDesign.common.FileExtentions import (
    REvoDesignFileExtentions as FileExtentions,
)

# 0. import version info
from REvoDesign.__version__ import __version__ as VERSION

# -=-=-=-=-=-=-=-= the importing stack begins -=-=-=-=-=-=-=-=

# 1. import post install module and methods
from REvoDesign.boot import (
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

# 2.5. initialize experiments directory, depending on config
EXPERIMENTS_CONFIG_DIR = experiment_config()

# 3. initialize logging config and root logger, depending on config
from REvoDesign.logger import setup_logging

root_logger = setup_logging()

# 4. import UI bus, depending on SingletonAbstract, logger, configuration
from REvoDesign.application.ui_driver import (
    Widget2Widget,
    ConfigBus,
)

# 5. import the major plugin class
from REvoDesign.REvoDesign import REvoDesignPlugin


# 6. enable garbage collection
gc.enable()

# 7. add shortcuts to PyMOL commandline prompt
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
