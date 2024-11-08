# -=-=-=-=-=-=-=-= the importing stack begins -=-=-=-=-=-=-=-=

# 0. build-in plugin: garbage collector

import gc


# 1. import basic
from REvoDesign.basic import SingletonAbstract


# 2. import post install module and methods
from REvoDesign.boot import (WITH_DEPENDENCIES, experiment_config,
                             reload_config_file, save_configuration,
                             set_cache_dir, set_REvoDesign_config_file,REVODESIGN_CONFIG_FILE)
# 3. import FileExtentions
from REvoDesign.common.FileExtentions import \
    REvoDesignFileExtentions as FileExtentions

# 4. import UI bus, depending on SingletonAbstract, logger, configuration
from REvoDesign.driver.ui_driver import ConfigBus, Widget2Widget
from REvoDesign.logger import setup_logging,root_logger

# 5. import the major plugin class
from REvoDesign.REvoDesign import REvoDesignPlugin
from REvoDesign.shortcuts import *

# 6. Set version info

__version__ = '1.5.11.post-2'



# 8. enable garbage collection
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
    'root_logger','setup_logging',
    'REVODESIGN_CONFIG_FILE','set_REvoDesign_config_file','experiment_config'
]
