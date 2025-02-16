'''
Shortcut wrappers of sequence designs
'''

from REvoDesign.driver.group_register import CallableGroupValues
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.shortcuts import shortcut_pssm2csv
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.mutant_tools import pick_design_from_profile
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


@dialog_wrapper(
    title="PSSM to CSV",
    banner="Convert a PSSM raw file to a CSV format for downstream processing.",
    options=(
        AskedValue(
            "pssm",
            "",
            typing=str,
            reason="Path to the PSSM raw file to be converted.",
            source='File',  # Mark this as a file input
            required=True,
        ),
    )
)
def wrapped_pssm2csv(**kwargs):
    """
    Runs the PSSM to CSV conversion process with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("PSSM to CSV Conversion"):
        logging.info(kwargs)
        run_worker_thread_with_progress(
            shortcut_pssm2csv,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )


@dialog_wrapper(
    title="Design with Profile",
    banner="Run mutant design with profile",
    options=(
        AskedValue(
            "profile",
            '',
            str,
            'Profile path for design',
            required=True,
            source='File'
        ),
        AskedValue(
            'profile_type',
            'PSSM',
            str,
            'Profile type',
            required=True,
            choices=CallableGroupValues.list_all_profile_parsers
        ),
        AskedValue(
            'prefer_lower_score',
            False,
            bool,
            'Whether to prefer lower score. Usefule when design with ddg data. Default is False.',
        ),
        AskedValue(
            'keep_missing',
            True,
            bool,
            'Keep X in the sequence',
        ),
        AskedValue(
            'residue_range',
            '',
            str,
            'Residue range to be shown, plotted and designed. Can be comma-separated digits, or textfile path. Default is empty for the full length sequence.'
            'Note that IndexOutOfRangeError will be raised if the range is not valid (on residue index where aa is `X`).',
            required=False,
            source='File'
        ),
        AskedValue(
            'view_highlight',
            'orient',
            str,
            'Whether to reorient the view to highlight the selected residues.',
            choices=('None', 'center', 'zoom', 'orient',)),
        AskedValue(
            'view_highlight_nbr',
            6,
            int,
            'Area to rezoom around',
            choices=range(0, 20),
            required=False
        )
    )
)
def wrapped_profile_pick_design(**kwargs):
    logging.info(kwargs)
    pick_design_from_profile(**kwargs)
