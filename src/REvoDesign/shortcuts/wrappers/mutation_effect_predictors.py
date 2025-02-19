'''
Shortcut wrappers of third-party mutant effect predictors
'''

from REvoDesign.common import file_extensions as FExt
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.tools.mutation_effect_predictors import \
    shortcut_thermompnn
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import device_picker, timing

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


@dialog_wrapper(
    title="ThermoMPNN",
    banner="Perform ThermoMPNN prediction",
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
            "save_dir",
            '',
            typing=str,
            reason="Path to the output directory. If not provided, the output will not be saved.",
            source='Directory',
        ),
        AskedValue(
            "chains",
            typing=list,
            reason="Chain ID for the docking. Default is None for all chains.",
            choices=lambda: list(ConfigBus().get_value("designable_sequences", dict, reject_none=True).keys()),
        ),
        AskedValue(
            "mode",
            "single",
            typing=str,
            reason="Run mode of ThermoMPNN prediction. Default is 'single'.",
            choices=["single", "additive", "epistatic"],
            required=True,
        ),
        AskedValue(
            "batch_size",
            256,
            typing=int,
            reason="Batch size for the run.",
            choices=[64, 128, 256, 512, 1024, 2048],
            required=True,
        ),
        AskedValue(
            "threshold",
            -0.5,
            typing=float,
            reason="Job ID for the ddG cutoff.",
            required=True,
        ),
        AskedValue(
            "distance",
            5.0,
            typing=float,
            reason="Spatial Distance constraints of 2-residues",
            choices=range(1, 1000),
        ),
        AskedValue(
            "ss_penalty",
            False,
            typing=bool,
            reason="Enable SS penalty. Default is False.",
        ),

        AskedValue(
            "device",
            'cpu',
            typing=str,
            choices=device_picker,
            reason="Device for the run. Default is 'cpu'. MPS may not work with better performance.",
        ),
        AskedValue(
            "load_to_preview",
            False,
            typing=bool,
            reason="Whether to load the result to preview. Default is False."
        ),
        AskedValue(
            "top_ranked",
            -1,
            typing=int,
            reason="Number of top ranked predictions should be loaded. Default is -1 for all predictions."
        )
    )
)
def wrapped_thermompnn(**kwargs):
    """
    Runs the RosettaLigand docking.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    with timing('running ThermoMPNN prediction'):

        run_worker_thread_with_progress(
            shortcut_thermompnn,
            **kwargs,
        )
