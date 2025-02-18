'''
Shortcut wrappers of Rosetta-related tasks
'''

from pymol import cmd

from REvoDesign import ConfigBus
from REvoDesign.common import file_extensions as FExt
from REvoDesign.shortcuts.utils import read_rosetta_node_config
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.rosetta_utils import (extra_res_to_opts,
                                            list_fastrelax_scripts)
from REvoDesign.tools.utils import timing

from ...logger import ROOT_LOGGER
from ..tools.rosetta_tasks import (shortcut_fast_relax, shortcut_pross,
                                   shortcut_relax_w_ca_constraints,
                                   shortcut_rosettaligand)

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
            choices=range(10, 90)
        ),

        AskedValue(
            "start_from_xyz_sele",
            '',
            typing=str,
            reason="Startpoint selection from XYZ coordinates. Will use center of mass coordinates if provided.",
            choices=lambda: [''] + list(cmd.get_names("selections")),
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
    ligand_params: str = kwargs.pop('ligand_params')
    ligands = ligand_params.split('|')
    kwargs['ligands'] = ligands

    # parse start_from_xyz_sele to start_from_xyz coordinates
    start_from_xyz_sele = kwargs.pop('start_from_xyz_sele')
    if not start_from_xyz_sele:
        kwargs['start_from_xyz'] = None
    else:
        kwargs['start_from_xyz'] = tuple(cmd.centerofmass(start_from_xyz_sele))

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

    with timing('running PROSS design'):

        run_worker_thread_with_progress(
            shortcut_pross,
            **kwargs,
        )


@dialog_wrapper(
    title="FastRelax",
    banner="Perform Rosetta FastRelax",
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
            "relax_script",
            "MonomerRelax2019",
            typing=str,
            reason="Name of the fastrelax script.",
            choices=list_fastrelax_scripts,
            required=True,
        ),
        AskedValue(
            "dualspace",
            False,
            typing=bool,
            reason="Whether to use dual space. Default is False.",
        ),
        AskedValue(
            "default_repeats",
            3,
            typing=int,
            choices=range(3, 100),
            reason="Default number of repeats.",
        ),
        AskedValue(
            "nstruct",
            4,
            typing=int,
            reason="Number of structures to be generated in relax.",
            required=True,
        ),
        AskedValue(
            "save_dir",
            "relaxed/fastrelax",
            typing=str,
            reason="Path to the directory to save the results.",
            source='Directory',  # Mark this as a folder input
            required=True,
        ),
        AskedValue(
            "job_id",
            "relaxed",
            typing=str,
            reason="Job ID for the FastRelax design.",
            required=True,
        ),
        AskedValue(
            "ligand_params",
            "",
            typing=str,
            reason="Path to the ligands (*.params) to be docked.",
            source='Files',  # Mark this as a multi-file input
            ext=FExt.RosettaParams
        ),
        AskedValue(
            "opts",
            "",
            typing=str,
            reason="Other options for the FastRelax.",

        ),
    )
)
def wrapped_fast_relax(**kwargs):
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

    with timing('running Rosetta FastRelax'):

        run_worker_thread_with_progress(
            shortcut_fast_relax,
            **kwargs,
        )


@dialog_wrapper(
    title="RelaxWithCaConstraints",
    banner="Perform Rosetta Relax With Ca Constraints",
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
            "nstruct_per_round",
            1,
            typing=int,
            reason="Number of structures to generate per round. Default is 1.",
            choices=range(1, 100),
            required=True,
        ),
        AskedValue(
            "ncycles",
            3,
            typing=int,
            reason="Number of cycles to run. Default is 3.",
            choices=range(3, 100)
        ),

        AskedValue(
            "save_dir",
            "relaxed",
            typing=str,
            reason="Path to the directory to save the results.",
            source='Directory',  # Mark this as a folder input
            required=True,
        ),
        AskedValue(
            "job_id",
            "relax_w_ca_constraints",
            typing=str,
            reason="Job ID for the FastRelax design.",
            required=True,
        ),
        AskedValue(
            "opts",
            "",
            typing=str,
            reason="Other options for the FastRelax.",

        ),
    )
)
def wrapped_relax_w_ca_constraints(**kwargs):
    """
    Runs the FastRelax.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)
    bus = ConfigBus()

    node_hint = bus.get_value('rosetta.node_hint')
    node_config = read_rosetta_node_config()

    kwargs['node_hint'] = node_hint
    kwargs['node_config'] = node_config

    ligand_params: str = kwargs.pop('ligand_params')
    opts: str = kwargs.pop('opts')

    relax_opts = [x.strip() for x in opts.split(' ')]
    if ligand_params:
        relax_opts.extend(extra_res_to_opts(ligand_params))

    kwargs['relax_opts'] = [op for op in relax_opts if op]

    with timing('running Rosetta FastRelax'):

        run_worker_thread_with_progress(
            shortcut_relax_w_ca_constraints,
            **kwargs,
        )
