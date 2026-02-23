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

get_fasta_writer_choices = lambda: list(filter(lambda x: x.startswith("fas"), SeqIO._FormatToWriter.keys()))


get_designable_chain_ids = lambda: list(
    ConfigBus().get_value("designable_sequences", dict, reject_none=True, cfg="runtime").keys()
)
get_selections = lambda: [""] + list(cmd.get_names("selections"))


find_all_small_molecules_in_protein = lambda: find_small_molecules_in_protein("(all)") or None


get_all_chain_ids = lambda: list(
    ConfigBus().get_value("designable_sequences", dict, reject_none=True, cfg="runtime").keys()
)

get_all_object_names = lambda: cmd.get_names("objects")


get_all_selections = lambda: cmd.get_names("selections")
get_all_objects = lambda: cmd.get_names("objects")


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
