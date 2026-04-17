# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Importing stack for REvoDesign
"""

# -=-=-=-=-=-=-=-= the importing stack begins -=-=-=-=-=-=-=-=

# 0. build-in plugin: garbage collector
import gc

# 1. import basic modules
from REvoDesign.basic import SingletonAbstract

# 2. import to bootstrap configurations
from REvoDesign.bootstrap import (
    REVODESIGN_CONFIG_FILE,
    experiment_config,
    reload_config_file,
    save_configuration,
    set_cache_dir,
    set_REvoDesign_config_file,
)

# 3. import File Extentions
from REvoDesign.common import file_extensions

# 4. import UI bus, depending on SingletonAbstract, logger, configuration
# root logger initialized at here
from REvoDesign.driver.ui_driver import ConfigBus

# 5. import logger, which is based on the configuration
# import it here so that the logger can be seen everywhere
from REvoDesign.logger import ROOT_LOGGER, setup_logging

# 6. import the major plugin for PyMOL
from REvoDesign.REvoDesign import REvoDesignPlugin

# 7. add shortcuts to PyMOL commandline prompt
# follow alphabeitical order of imports and prevent cyclic import
from REvoDesign.shortcuts import __all__ as all_shortcuts

# 8. Set version info
# version number checker: https://regex101.com/r/6AoOI9/1
__version__ = "1.8.6"
# To bump a new version tag, change __version__, use the checker to ensure no syntax error. 
# then use `make tag` at repository root to complete the committing.


# 9. enable garbage collection
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
