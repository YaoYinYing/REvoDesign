'''
Importing stack for REvoDesign
'''
# -=-=-=-=-=-=-=-= the importing stack begins -=-=-=-=-=-=-=-=

# 0. build-in plugin: garbage collector

import gc

# 1. import basic
from REvoDesign.basic import SingletonAbstract
# 2. import post install module and methods
from REvoDesign.bootstrap import (REVODESIGN_CONFIG_FILE, experiment_config,
                                  reload_config_file, save_configuration,
                                  set_cache_dir, set_REvoDesign_config_file)
# 3. import FileExtentions
from REvoDesign.common import FileExtentions
# 4. import UI bus, depending on SingletonAbstract, logger, configuration
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.logger import root_logger, setup_logging
# 5. import the major plugin class
from REvoDesign.REvoDesign import REvoDesignPlugin
# 6. add shortcuts to PyMOL commandline prompt
# follow alphabeitical order of imports and prevent cyclic import
from REvoDesign.shortcuts import __all__ as all_shortcuts

# 7. Set version info
__version__ = "1.7.13"

# 8. enable garbage collection
gc.enable()

__all__ = [
    "REvoDesignPlugin",
    "SingletonAbstract",
    "ConfigBus",
    "FileExtentions",
    "reload_config_file",
    "set_cache_dir",
    "save_configuration",
    "root_logger",
    "setup_logging",
    "REVODESIGN_CONFIG_FILE",
    "set_REvoDesign_config_file",
    "experiment_config",
    "all_shortcuts",
]
