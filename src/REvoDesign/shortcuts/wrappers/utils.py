# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Shortcut wrappers of other utility functions
"""

from REvoDesign.logger.logger import logger_level_setter
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.tools.mutant_tools import shorter_range
from REvoDesign.tools.utils import convert_residue_ranges

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)

logger_registry = DialogWrapperRegistry("logger")

wrapped_logger_level_setter = logger_registry.register("logger_level_setter", logger_level_setter)


utils_registry = DialogWrapperRegistry("utils")
wrapped_convert_residue_ranges = utils_registry.register("convert_residue_ranges", convert_residue_ranges)


def _short_range(input_string: str, separator: str, connector: str):
    logging.debug(f"Shortening range {input_string}")
    input_list = [int(x) for x in input_string.split(",") if x.isdigit()]
    ret = shorter_range(input_list, separator, connector)
    logging.info(f"Shortened range: \n{ret}")
    return ret


wrapped_short_range = utils_registry.register("short_residue_ranges", _short_range)
