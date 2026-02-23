# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Module to initialize REvoDesign Configurating system with Hydra and OmegaConf.
"""

import os

import hydra

from .. import Qt
from .set_config import (
    enforce_config_key_structure,
    experiment_config,
    reload_config_file,
    save_configuration,
    set_cache_dir,
    set_REvoDesign_config_file,
    verify_config_tree_structure,
)

# 1. initialize config file at user space
REVODESIGN_CONFIG_FILE = set_REvoDesign_config_file()
REVODESIGN_CONFIG_DIR = os.path.dirname(REVODESIGN_CONFIG_FILE)


try:
    # 2. initialize hydra with config dir
    hydra.initialize_config_dir(version_base=None, config_dir=REVODESIGN_CONFIG_DIR, job_name="REvoDesign")
except ValueError as e:
    print(
        "An instance of Global Hydra is already initialized before REvoDesign itself."
        "This usually happens when REvoDesign is imported from another module or mocking "
        " the configuration under test suite. "
        "Ingore this error message and continue if you know what you are doing.\n",
        "-=" * 16,
        " Original Error: ",
        "-=" * 16,
        f"\n{e}\n",
        "-=" * 49,
    )

_TEMPLATE_CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
_copied = verify_config_tree_structure(REVODESIGN_CONFIG_DIR, _TEMPLATE_CONFIG_DIR)
_replaced = enforce_config_key_structure(REVODESIGN_CONFIG_DIR, _TEMPLATE_CONFIG_DIR)
if _copied or _replaced:
    print(
        "Configuration synchronized.",
        f"copied={_copied}",
        f"replaced={_replaced}",
    )

# 3. initialize experiments directory, depending on config
EXPERIMENTS_CONFIG_DIR = experiment_config()

# 4. initialize cache directory for intermediate yaml files
CACHE_CONFIG_DIR = experiment_config("cache")


__all__ = [
    "Qt",
    "experiment_config",
    "set_REvoDesign_config_file",
    "reload_config_file",
    "set_cache_dir",
    "save_configuration",
    "REVODESIGN_CONFIG_FILE",
    "REVODESIGN_CONFIG_DIR",
    "EXPERIMENTS_CONFIG_DIR",
]
