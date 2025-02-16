'''
Shortcut wrappers of Rosetta-related tasks
'''

from pymol import cmd

from REvoDesign.common import file_extensions as FExt

from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper

from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing
from ..shortcuts import shortcut_pross, shortcut_rosettaligand

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)



@dialog_wrapper(
    title="RosettaLigand",
    banner="Perform RosettaLigand Docking",
    options=(
        AskedValue(
            "pdb",
            "",
            typing=str,
            reason="Path to the PDB file",
            source='File',  # Mark this as a file input
            required=True,
            ext=FExt.PDB_STRICT,
        ),
        AskedValue(
            "ligand_params",
            "",
            typing=str,
            reason="Path to the ligands (*.params) to be docked.",
            source='Files',  # Mark this as a multi-file input
            required=True,
            ext=FExt.RosettaParams
        ),
        AskedValue(
            "nstruct",
            "10",
            typing=int,
            reason="Number of structures to be generated.",
            required=True,
        ),
        AskedValue(
            "chain_id_for_dock",
            "B",
            typing=str,
            reason="Chain ID for the docking.",
            required=True,
        ),
        AskedValue(
            "save_dir",
            "",
            typing=str,
            reason="Path to the directory to save the results.",
            source='Directory',  # Mark this as a folder input
            required=True,
        ),
        AskedValue(
            "job_id",
            "rosettaligand",
            typing=str,
            reason="Job ID for the docking.",
            required=True,
        ),
        AskedValue(
            "cst",
            "",
            typing=str,
            reason="Path to the constraint file.",
            source='File',  # Mark this as a file input
            required=False,
        ),
        AskedValue(
            "box_size",
            30,
            typing=int,
            reason="Box size for the docking.",
            required=True,
        ),
        AskedValue(
            "move_distance",
            0.5,
            typing=float,
            reason="Move distance for the docking.",
        ),
        AskedValue(
            "gridwidth",
            45,
            typing=int,
            reason="Grid width for the docking.",
            choices=range(10,90)
        ),
        
        AskedValue(
            "start_from_xyz_sele",
            '',
            typing=str,
            reason="Startpoint selection from XYZ coordinates. Will use center of mass coordinates if provided.",
            choices=lambda: ['']+list(cmd.get_names("selections")),
        ),
    )
)
def wrapped_rosettaligand(**kwargs):
    """
    Runs the RosettaLigand docking.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    # Parse ligand params 
    ligand_params: str=kwargs.pop('ligand_params')
    ligands=ligand_params.split('|')
    kwargs['ligands']=ligands


    # parse start_from_xyz_sele to start_from_xyz coordinates
    start_from_xyz_sele=kwargs.pop('start_from_xyz_sele')
    if not start_from_xyz_sele:
        kwargs['start_from_xyz']=None
    else:
        kwargs['start_from_xyz']=cmd.centerofmass(start_from_xyz_sele)
    

    with timing('running RosettaLigand docking'):
        
        run_worker_thread_with_progress(
            shortcut_rosettaligand,
            **kwargs,
        )



@dialog_wrapper(
    title="PROSS design",
    banner="Perform PROSS design",
    options=(
        AskedValue(
            "pdb",
            "",
            typing=str,
            reason="Path to the PDB file",
            source='File',  # Mark this as a file input
            required=True,
            ext=FExt.PDB_STRICT,
        ),
        AskedValue(
            "pssm",
            "",
            typing=str,
            reason="Path to the PSSM file. ",
            source='File',  # Mark this as a file input
            required=True,
            ext=FExt.PSSM
        ),
        AskedValue(
            "res_to_fix",
            "1A",
            typing=str,
            reason="Residue to fix. Default is 1A.",
        ),
        AskedValue(
            "res_to_restrict",
            "1A",
            typing=str,
            reason="Residue to restrict. Default is 1A.",
        ),
        AskedValue(
            "nstruct_refine",
            4,
            typing=int,
            reason="Number of structures to be generated in refinement.",
            required=True,
        ),
        AskedValue(
            "save_dir",
            "design/pross",
            typing=str,
            reason="Path to the directory to save the results.",
            source='Directory',  # Mark this as a folder input
            required=True,
        ),
        AskedValue(
            "job_id",
            "pross_design",
            typing=str,
            reason="Job ID for the PROSS design.",
            required=True,
        ),
    )
)
def wrapped_pross(**kwargs):
    """
    Runs the PROSS design.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    with timing('running RosettaLigand docking'):
        
        run_worker_thread_with_progress(
            shortcut_pross,
            **kwargs,
        )


