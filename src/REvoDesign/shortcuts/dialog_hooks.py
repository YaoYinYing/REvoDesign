# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Utility functions for dialogs hook functions
"""

import pymol
import pymol.plugins
from Bio import SeqIO
from pymol import cmd

from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.tools.pymol_utils import find_small_molecules_in_protein

from ..logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


def get_fasta_writer_choices() -> list[str]:
    return [fmt for fmt in SeqIO._FormatToWriter.keys() if fmt.startswith("fas")]


def get_designable_chain_ids() -> list[str]:
    designable = ConfigBus().get_value("designable_sequences", dict, reject_none=True, cfg="runtime")
    return list(designable.keys())


def get_selections() -> list[str]:
    return [""] + list(cmd.get_names("selections"))


def find_all_small_molecules_in_protein():
    return find_small_molecules_in_protein("(all)")


def get_all_chain_ids() -> list[str]:
    designable = ConfigBus().get_value("designable_sequences", dict, reject_none=True, cfg="runtime")
    return list(designable.keys())


def get_all_object_names():
    return cmd.get_names("objects")


def get_all_selections():
    return cmd.get_names("selections")


def get_all_objects():
    return cmd.get_names("objects")


def get_pymol_plugin_paths():
    """
    Retrieve the list of PyMOL plugin startup paths

    Returns:
        list: A list of PyMOL plugin startup paths, or an empty list if PyMOL is running in headless mode

    Raises:
        AttributeError: Caught when PyMOL is running in headless mode
    """
    try:
        # Attempt to get PyMOL plugin startup paths
        return [p for p in pymol.plugins.get_startup_path()]
    except AttributeError as e:
        # Handle headless mode case by logging error and returning empty list
        logging.error(f"PyMOL is running in headless mode. {e}")
        return []
