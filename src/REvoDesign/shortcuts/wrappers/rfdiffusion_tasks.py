'''
Shortcut wrappers of rfdiffusion tasks
'''
import os
import shutil
from REvoDesign.common import file_extensions as Fext
from REvoDesign.shortcuts.tools.rfdiffusion_tasks import (
    RFDIFFUSION_CONFIG_DIR, run_general_rfdiffusion_task,
    visualize_substrate_potentials)
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from ...logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
def _visualize_substrate_potentials(**kwargs):
    """
    Runs the visualize_substrate_potentials function with parameters collected from the dialog.
    Args:
        **kwargs: Parameters collected from the dialog.
    """
    pdb_path = kwargs.pop('pdb_path')
    kwargs['pdb_path'] = os.path.abspath(pdb_path)
    grid_size = kwargs.pop('grid_size')
    margin = kwargs.pop('margin')
    save_to = kwargs.pop('save_to')
    sp_visualizer = visualize_substrate_potentials(**kwargs)
    sp_visualizer.plot_potential_field(
        grid_size=grid_size, margin=margin, save_to=save_to
    )
def _run_general_rfdiffusion_task(**kwargs):
    config_preset: str = kwargs.pop('config_preset')
    config_file: str = kwargs.pop('config_file')
    
    if config_file != '' and os.path.isfile(config_file):
        target_config_file = os.path.join(RFDIFFUSION_CONFIG_DIR, os.path.basename(config_file))
        if os.path.exists(target_config_file):
            logging.warning(
                f"The config file {config_file} already exists at {target_config_file}. It will be overwritten.")
        shutil.copy(config_file, target_config_file)
        logging.info(f"A copy of the config file {config_file} is created at {target_config_file}")
        config_preset = Fext.YAML.basename_stem(os.path.basename(target_config_file))
        logging.info(f'Config preset is set to {config_preset}')
    else:
        config_preset = config_preset or 'base'
    kwargs['config_preset'] = config_preset
    overrides: str = kwargs.pop('overrides')
    if overrides != '':
        kwargs['overrides'] = overrides.split(' ')
    else:
        kwargs['overrides'] = None
    run_general_rfdiffusion_task(**kwargs)
registry = DialogWrapperRegistry("rfdiffusion")
wrapped_visualize_substrate_potentials = registry.register(
    "visualize_substrate_potentials",
    _visualize_substrate_potentials
)
wrapped_general_rfdiffusion_task = registry.register(
    "general_rfdiffusion_task",
    _run_general_rfdiffusion_task,
    use_thread=True,
    use_progressbar=True
)