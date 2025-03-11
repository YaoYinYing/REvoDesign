import os
import shutil
from REvoDesign import ROOT_LOGGER
from REvoDesign.common import file_extensions as Fext
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing
from REvoDesign.tools.pymol_utils import find_small_molecules_in_protein
from ..tools.rfdiffusion_tasks import RFDIFFUSION_CONFIG_DIR, list_all_config_preset, list_all_rfd_models, run_general_rfdiffusion_task, visualize_substrate_potentials
from REvoDesign.tools.rfdiffusion_tools import SubstratePotentialVisualizer

logging = ROOT_LOGGER.getChild(__name__)
@dialog_wrapper(
    title="Substrate Potential Visualizer",
    banner="Visualize substrate potential energy maps for ligand pocket generation with RFdiffusion. "
           f"Also, this function helps to reproduce the Extended Data Fig. 6E of the RFdiffusion paper.\n {SubstratePotentialVisualizer.__init__.__doc__}",
    options=(
        AskedValue(
            "pdb_path",
            "all",
            typing=str,
            required=True,
            reason="Path to the input PDB file containing the protein-ligand complex.",
            source='File',
            ext=Fext.PDB_STRICT
        ),
        AskedValue(
            "lig_key",
            '',
            typing=str,
            reason='Residue name of the ligand (e.g., "ATP", "HEM")',
            required=True,
            choices=lambda : find_small_molecules_in_protein('(all)') or None
        ),
        AskedValue(
            "blur",
            False,
            typing=bool,
            reason="If True, applies a Gaussian blur to the potential map. "
        ),
        AskedValue(
            "weight",
            1,
            typing=float,
            reason="Scaling factor for the total potential energy. Higher values increase the influence of the external potential on the diffusion process."
        ),
        AskedValue(
            "r_0",
            8,
            typing=float,
            reason="Defines the maximum range of attractive interactions. Beyond this distance, the attraction potential smoothly decays."
        ),
        AskedValue(
            "d_0",
            2,
            typing=float,
            reason="Defines the preferred contact distance for attractive interactions. At distances **d < d_0**, the attractive potential plateaus."
        ),
        AskedValue(
            "s",
            1,
            typing=float,
            reason="Scaling factor for the attractive contact potential. Larger values make attractive interactions stronger relative to repulsion."
        ),
        AskedValue(
            "eps",
            1e-6,
            typing=float,
            reason="Small constant added to prevent division by zero in energy calculations."
        ),
        AskedValue(
            "rep_r_0",
            5,
            typing=float,
            reason="Defines the onset of repulsive interactions. If the distance between a ligand atom and a protein atom is **d < rep_r_0**, a repulsive force is applied."
        ),
        AskedValue(
            "rep_s",
            2,
            typing=float,
            reason="Scaling factor for the repulsive potential. Larger values make steric repulsions stronger."
        ),
        AskedValue(
            "rep_r_min",
            1,
            typing=float,
            reason="Defines the minimum repulsion distance. When **d < rep_r_min**, repulsion is maximized."
        ),
        AskedValue(
            "grid_size",
            200,
            typing=int,
            reason="Number of grid points in each direction."
        ),
        AskedValue(
            "margin",
            10,
            typing=int,
            reason="Margin around the ligand atoms."
        ),
        AskedValue(
            "save_to",
            'default.png',
            typing=str,
            reason="Path to save the plot. If 'default.png', the plot will be saved in the current working directory.",
            source='FileO',
            ext=Fext.Pictures
        ),
    )
)
def wrapped_visualize_substrate_potentials(**kwargs):
    """
    Runs the visualize_substrate_potentials function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing('ploting substrate potential'):
        print(kwargs)
        run_worker_thread_with_progress(
            visualize_substrate_potentials,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )


@dialog_wrapper(
    title="Run RFdiffusion",
    banner="Run General RFdiffusion task.",
    options=(
        AskedValue(
            "config_preset",
            '',
            typing=str,
            reason="The config preset to use. Defaults to 'base'.",
            choices=lambda: ['']+ list_all_config_preset(),
        ),
        AskedValue(
            "config_file",
            '',
            typing=str,
            reason="The config preset to use. Defaults to 'base'.",
            source='File',
            ext=Fext.YAML
        ),
        AskedValue(
            "model_name",
            '',
            typing=int,
            reason="The model name to use. Defaults to empty string to let config preset and config contents decide.",
            choices=list_all_rfd_models
        ),
        AskedValue(
            "overrides",
            "",
            typing=str,
            reason="The override configure term to use.", 
            required=True,
        ),
    )
)
def wrapped_general_rfdiffusion_task(**kwargs):

    config_preset: str=kwargs.pop('config_preset')
    config_file: str=kwargs.pop('config_file')

    # override config preset with user defined config file
    if config_file != '' and os.path.isfile(config_file):
        target_config_file = os.path.join(RFDIFFUSION_CONFIG_DIR, os.path.basename(config_file))
        shutil.copy(config_file, target_config_file)

        logging.info(f"A copy of the config file {config_file} is created at {target_config_file}")
        
        config_preset= Fext.YAML.basename_stem(target_config_file)
        logging.info(f'Config preset is set to {config_preset}')
        
    else:
        config_preset = config_preset or 'base'
    
    kwargs['config_preset'] = config_preset


    overrides: str=kwargs.pop('overrides')
    if overrides != '':
        kwargs['overrides'] = overrides.split(' ')
    else:
        kwargs['overrides'] = None

    with timing('running rfdiffusion task'):
        print(kwargs)
        run_worker_thread_with_progress(
            run_general_rfdiffusion_task,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )