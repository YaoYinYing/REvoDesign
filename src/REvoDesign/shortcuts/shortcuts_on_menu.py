'''
This module contains the menu shortcuts for REvoDesign.
'''
# To create a dialog form, one must implement a wrapper function that
# decorated by `dialog_wrapper` and import it here
from REvoDesign.shortcuts.wrappers.designs import (wrapped_profile_pick_design,
                                                   wrapped_pssm2csv)
from REvoDesign.shortcuts.wrappers.exports import (
    wrapped_dump_fasta_from_struct, wrapped_menu_dump_sidechains)
from REvoDesign.shortcuts.wrappers.ligand_converters import (
    wrapped_smiles_conformer_batch, wrapped_smiles_conformer_single,
    wrapper_sdf2rosetta_params)
from REvoDesign.shortcuts.wrappers.represents import (
    wrapped_color_by_mutation, wrapped_color_by_plddt, wrapped_real_sc)
from REvoDesign.shortcuts.wrappers.rosetta_tasks import (wrapped_pross,
                                                         wrapped_rosettaligand)
from REvoDesign.shortcuts.wrappers.structure import wrapped_resi_renumber
from REvoDesign.tools.customized_widgets import AskedValue
from REvoDesign.tools.pymol_utils import get_all_groups


def menu_dump_sidechains(dump_all=False):
    """
    Prepares and launches the sidechain dumping menu.

    Args:
        dump_all (bool): If True, preselects all groups for sidechain dumping.
    """
    dynamic_value = {
        "value": AskedValue(
            "sele",
            val=get_all_groups() if dump_all else None,
            typing=list,
            reason="Select the models to dump sidechains.",
            choices=get_all_groups(),
        ),
        "index": 0,  # Specify the position in the options list
    }

    wrapped_menu_dump_sidechains(dynamic_values=[dynamic_value])


def menu_color_by_plddt():
    """
    Launches the wrapped dialog for coloring by pLDDT values.

    Dynamic values, if any, can be appended here before invoking the wrapped function.
    """
    wrapped_color_by_plddt()


def menu_pssm2csv():
    """
    Launches the dialog for PSSM to CSV conversion.
    """
    wrapped_pssm2csv()


def menu_real_sc():
    """
    Launches the dialog for setting sidechain representation.
    """
    wrapped_real_sc()


def menu_color_by_mutation():
    '''
    Launches the dialog for coloring by mutation.
    '''

    wrapped_color_by_mutation()


def menu_smiles_conformer_single():
    """
    Launches the dialog for generating 3D conformers for a SMILES string.
    """
    wrapped_smiles_conformer_single()


def menu_smiles_conformer_batch():
    """
    Launches the dialog for generating 3D conformers for multiple SMILES strings.
    """
    wrapped_smiles_conformer_batch()


def menu_profile_pick_design():
    """
    Launches the dialog for profile pick design.
    """
    return wrapped_profile_pick_design()


def menu_resi_renumber():
    """
    Launches the dialog for residue renumbering.
    """
    wrapped_resi_renumber()


def menu_dump_fasta_from_struct():
    """
    Launches the dialog for dumping sequences from a structure.
    """
    wrapped_dump_fasta_from_struct()


def menu_sdf2rosetta_params():
    """
    Launches the dialog for converting SDF to Rosetta parameters.
    """
    wrapper_sdf2rosetta_params()


def menu_rosettaligand():
    """
    Launches the dialog for docking a ligand to a protein.
    """
    wrapped_rosettaligand()


def menu_pross():
    """
    Launches the dialog for PROSS design dialog
    """
    wrapped_pross()
