'''
This module contains the menu shortcuts for REvoDesign.
'''


from REvoDesign.shortcuts.shortcut_wrappers import (
    wrapped_color_by_plddt, wrapped_dump_fasta_from_struct,
    wrapped_menu_dump_sidechains, wrapped_profile_pick_design,
    wrapped_pssm2csv, wrapped_real_sc, wrapped_resi_renumber,
    wrapped_smiles_conformer_batch, wrapped_smiles_conformer_single)
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
