'''
Shortcut wrappers of Rosetta-related tasks
'''


from pymol import cmd

from REvoDesign.shortcuts.utils import DialogWrapperRegistry

from REvoDesign.tools.rosetta_utils import extra_res_to_opts

from ...logger import ROOT_LOGGER
from ..tools.rosetta_tasks import (shortcut_fast_relax, shortcut_pross,
                                   shortcut_relax_w_ca_constraints,
                                   shortcut_rosettaligand)

logging = ROOT_LOGGER.getChild(__name__)


# Init registry for Rosetta-related dialogs
registry = DialogWrapperRegistry("rosetta_tasks")


# Wrapping function calls
def wrapped_rosettaligand():
    registry.call("wrapped_rosettaligand")

def wrapped_pross():
    registry.call("wrapped_pross")

def wrapped_fast_relax():
    registry.call("wrapped_fast_relax")


def wrapped_relax_w_ca_constraints():
    registry.call("wrapped_relax_w_ca_constraints")


def _wrapped_rosettaligand(**kwargs):
    """
    Runs the RosettaLigand docking.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    # Parse ligand params
    ligand_params: str = kwargs.pop('ligand_params')
    ligands = ligand_params.split('|')
    kwargs['ligands'] = ligands

    # parse start_from_xyz_sele to start_from_xyz coordinates
    start_from_xyz_sele = kwargs.pop('start_from_xyz_sele')
    if not start_from_xyz_sele:
        kwargs['start_from_xyz'] = None
    else:
        kwargs['start_from_xyz'] = tuple(cmd.centerofmass(start_from_xyz_sele))

    shortcut_rosettaligand(**kwargs)


def _wrapped_fast_relax(**kwargs):
    """
    Runs the FastRelax.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)
    ligand_params: str = kwargs.pop('ligand_params')
    opts: str = kwargs.pop('opts')

    relax_opts = [x.strip() for x in opts.split(' ')]
    if ligand_params:
        relax_opts.extend(extra_res_to_opts(ligand_params))

    kwargs['relax_opts'] = [op for op in relax_opts if op]

    shortcut_fast_relax(**kwargs)


def _wrapped_relax_w_ca_constraints(**kwargs):
    """
    Runs the FastRelax.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    ligand_params: str = kwargs.pop('ligand_params')
    opts: str = kwargs.pop('opts')

    relax_opts = [x.strip() for x in opts.split(' ')]
    if ligand_params:
        relax_opts.extend(extra_res_to_opts(ligand_params))

    kwargs['relax_opts'] = [op for op in relax_opts if op]

    shortcut_relax_w_ca_constraints(**kwargs)


# Register functions manually
registry.register("wrapped_rosettaligand", _wrapped_rosettaligand, use_thread=True)
registry.register("wrapped_pross", shortcut_pross, use_thread=True)
registry.register("wrapped_fast_relax", _wrapped_fast_relax, use_thread=True)
registry.register("wrapped_relax_w_ca_constraints", _wrapped_relax_w_ca_constraints, use_thread=True)
