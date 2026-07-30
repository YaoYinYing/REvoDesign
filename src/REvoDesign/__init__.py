# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Importing stack for REvoDesign
"""

# -=-=-=-=-=-=-=-= the importing stack begins -=-=-=-=-=-=-=-=

# 0. build-in plugin: garbage collector
import gc
from typing import Any

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

# 4. import logger, which is based on the configuration
# import it here so that the logger can be seen everywhere
from REvoDesign.logger import ROOT_LOGGER, setup_logging

# 5. Set version info
# version number checker: https://regex101.com/r/6AoOI9/1
__version__ = "1.9.1"
# To bump a new version tag, change __version__, use the checker to ensure no syntax error.
# then use `make tag` at repository root to complete the committing.


# 6. enable garbage collection
gc.enable()

# Type declarations keep the lazy public exports visible to static analyzers
# without binding them at runtime; missing attributes still flow through
# ``__getattr__`` below.
REvoDesignPlugin: Any
all_shortcuts: list[str]
ConfigBus: Any


def __getattr__(name: str):
    if name == "REvoDesignPlugin":
        from REvoDesign.REvoDesign import REvoDesignPlugin as _REvoDesignPlugin

        return _REvoDesignPlugin
    if name == "all_shortcuts":
        from REvoDesign.shortcuts import __all__ as _all_shortcuts

        return _all_shortcuts
    if name == "ConfigBus":
        from REvoDesign.driver.ui_driver import ConfigBus as _ConfigBus

        return _ConfigBus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
