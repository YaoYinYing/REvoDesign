"""
Shortcut wrappers of Rosetta-related tasks
"""

from pymol import cmd

from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.tools.rosetta_utils import extra_res_to_opts

from ...logger import ROOT_LOGGER
from ..tools.rosetta_tasks import (shortcut_fast_relax, shortcut_pross,
                                   shortcut_relax_w_ca_constraints,
                                   shortcut_rosettaligand)

logging = ROOT_LOGGER.getChild(__name__)

# 1. Prepare functions that has kwargs input and pre-/post-processing
# no need to use threading


def rosettaligand(**kwargs):
    """
    Runs the RosettaLigand docking.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    # Parse ligand params
    ligand_params: str = kwargs.pop("ligand_params")
    ligands = ligand_params.split("|")
    kwargs["ligands"] = ligands

    # parse start_from_xyz_sele to start_from_xyz coordinates
    start_from_xyz_sele = kwargs.pop("start_from_xyz_sele")
    if not start_from_xyz_sele:
        kwargs["start_from_xyz"] = None
    else:
        kwargs["start_from_xyz"] = tuple(cmd.centerofmass(start_from_xyz_sele))

    shortcut_rosettaligand(**kwargs)


def fast_relax(**kwargs):
    """
    Runs the FastRelax.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)
    ligand_params: str = kwargs.pop("ligand_params")
    opts: str = kwargs.pop("opts")

    relax_opts = [x.strip() for x in opts.split(" ")]
    if ligand_params:
        relax_opts.extend(extra_res_to_opts(ligand_params))

    kwargs["relax_opts"] = [op for op in relax_opts if op]

    shortcut_fast_relax(**kwargs)


def relax_w_ca_constraints(**kwargs):
    """
    Runs the FastRelax.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    ligand_params: str = kwargs.pop("ligand_params")
    opts: str = kwargs.pop("opts")

    relax_opts = [x.strip() for x in opts.split(" ")]
    if ligand_params:
        relax_opts.extend(extra_res_to_opts(ligand_params))

    kwargs["relax_opts"] = [op for op in relax_opts if op]

    shortcut_relax_w_ca_constraints(**kwargs)


# 2. Init registry for Rosetta-related dialogs
registry = DialogWrapperRegistry("rosetta_tasks")


# 3. Register functions into the registry by id-function pairs with threading enabled or not
# wrapped window pop trigger will be returned after this registration
wrapped_rosettaligand = registry.register("rosettaligand", rosettaligand, use_thread=True)
wrapped_pross = registry.register("pross", shortcut_pross, use_thread=True)
wrapped_fast_relax = registry.register("fast_relax", fast_relax, use_thread=True)
wrapped_relax_w_ca_constraints = registry.register("relax_w_ca_constraints", relax_w_ca_constraints, use_thread=True)
