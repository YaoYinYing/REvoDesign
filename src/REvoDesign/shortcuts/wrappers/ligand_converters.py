'''
Shortcut wrappers of ligand file converting
'''

from REvoDesign.shortcuts.shortcuts import (shortcut_sdf2rosetta_params,
                                            shortcut_smiles_conformer_batch,
                                            shortcut_smiles_conformer_single)
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


@dialog_wrapper(
    title="Get SMILES Conformer",
    banner="Generate 3D conformers for a SMILES string using RDKit.",
    options=(
        AskedValue(
            "ligand_name",
            "",
            typing=str,
            reason="Name for the ligand. This will be used as the filename prefix.",
            required=True,
        ),
        AskedValue(
            "smiles",
            "",
            typing=str,
            reason="SMILES string to generate conformers for.",
            required=True,
        ),
        AskedValue(
            "num_conformer",
            100,
            typing=int,
            choices=range(50, 300)
        ),
        AskedValue(
            "save_dir",
            "./ligands/",
            typing=str,
            reason="Directory to save the conformers.",
            source='Directory',  # Mark this as a directory input
        ),
        AskedValue(
            "show_conformer",
            'New Window',
            typing=str,
            reason="Show the conformer in PyMOL if True. Default is New Window to launch a new window.",
            choices=('None', 'Current Window', 'New Window')
        ),
    )
)
def wrapped_smiles_conformer_single(**kwargs):
    """
    Runs the smiles_conformer_single function with parameters collected from the dialog.
    """
    logging.info(kwargs)
    shortcut_smiles_conformer_single(**kwargs)


@dialog_wrapper(
    title="Get SMILES Conformers (Many)",
    banner="Generate 3D conformers for multiple SMILES strings using RDKit.",
    options=(
        AskedValue(
            "smiles",
            "",
            typing=str,
            reason="Path to SMILES json file to generate conformers for. Each line should be a separate SMILES string.",
            required=True,
            source='JsonInput'
        ),
        AskedValue(
            "num_conformer",
            100,
            typing=int,
        ),
        AskedValue(
            "save_dir",
            "./ligands/",
            typing=str,
            reason="Directory to save the conformers.",
            source='Directory',  # Mark this as a directory input
        ),
        AskedValue(
            "n_jobs",
            1,
            typing=int,
            choices=range(1, 16)
        ),
        AskedValue(
            "show_conformer",
            'None',
            typing=str,
            reason="Show the conformer in PyMOL if True. Default is New Window to launch a new window.",
            choices=('None', 'Current Window', 'New Window')
        ),
    )
)
def wrapped_smiles_conformer_batch(**kwargs):
    """
    Runs the smiles_conformer_batch function with parameters collected from the dialog.
    """
    logging.info(kwargs)

    shortcut_smiles_conformer_batch(**kwargs)


@dialog_wrapper(
    title="Convert SDF to Rosetta Parameter File",
    banner="Convert a given SDF to Rosetta Parameter File",
    options=(
        AskedValue(
            "ligand_name",
            "",
            typing=str,
            reason="A name for the ligand.",
            required=True
        ),
        AskedValue(
            "sdf_path",
            "",
            typing=str,
            reason="File path of the SDF.",
            required=True,
            source='File'

        ),
        AskedValue(
            "charge",
            0,
            typing=int,
            reason="Addtional charge to the ligand. Default is 0.",
            choices=range(-3, 3)
        ),
        AskedValue(
            "save_dir",
            '',
            typing=bool,
            reason="Save directory. Default is './ligands_sdf/'.",
            source='Directory'
        ),
    )
)
def wrapper_sdf2rosetta_params(**kwargs):
    logging.info(kwargs)
    shortcut_sdf2rosetta_params(**kwargs)
