import gc
import os

import hydra

from REvoDesign.application.ui_driver import ConfigBus, Widget2Widget
# -2. import basic
from REvoDesign.basic import SingletonAbstract
from REvoDesign.boot import (WITH_DEPENDENCIES, experiment_config,
                             reload_config_file, save_configuration,
                             set_cache_dir, set_REvoDesign_config_file)
# -1. import FileExtentions
from REvoDesign.common.FileExtentions import \
    REvoDesignFileExtentions as FileExtentions
from REvoDesign.logger import setup_logging
from REvoDesign.REvoDesign import REvoDesignPlugin
from REvoDesign.shortcuts import *

# 0. import version info

__version__ = '1.5.11.post-2'

# version alias
VERSION = __version__

# -=-=-=-=-=-=-=-= the importing stack begins -=-=-=-=-=-=-=-=

# 1. import post install module and methods

# 2. initialize config file
REVODESIGN_CONFIG_FILE = set_REvoDesign_config_file()
hydra.initialize_config_dir(
    version_base=None, config_dir=os.path.dirname(REVODESIGN_CONFIG_FILE)
)

# 2.5. initialize experiments directory, depending on config
EXPERIMENTS_CONFIG_DIR = experiment_config()

# 3. initialize logging config and root logger, depending on config

root_logger = setup_logging()

# 4. import UI bus, depending on SingletonAbstract, logger, configuration
# 5. import the major plugin class

# 6. enable garbage collection
gc.enable()

# 7. add shortcuts to PyMOL commandline prompt

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
