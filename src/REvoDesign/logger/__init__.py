# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
This module contains the logger setup.
"""

from .logger import LOGGER_CONFIG, ROOT_LOGGER, LoggerT, setup_logging

__all__ = ["setup_logging", "ROOT_LOGGER", "LoggerT", "LOGGER_CONFIG"]
