'''
Shortcut wrappers of results exporting
'''

from typing import List
from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.tools.exports import (
    shortcut_dump_fasta_from_struct, shortcut_dump_sidechains)
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)

# Init registry for sequence-related dialogs
registry = DialogWrapperRegistry("exports")

# Register function manually
registry.register("wrapped_dump_fasta_from_struct", shortcut_dump_fasta_from_struct)

def _wrapped_menu_dump_sidechains(**kwargs):
    """
    Runs the sidechain dumping process with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("Dumping sidechains"):
        logging.info(kwargs)
        run_worker_thread_with_progress(
            shortcut_dump_sidechains,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )

registry.register("wrapped_menu_dump_sidechains", _wrapped_menu_dump_sidechains)

def wrapped_dump_fasta_from_struct():
    """
    Runs the dump_fasta_from_struct function with parameters collected from the dialog.
    Args:
        **kwargs: Parameters collected from the dialog.
    """

    registry.call("wrapped_dump_fasta_from_struct")

def wrapped_menu_dump_sidechains(dynamic_values: List):
    '''
    Runs the dump_sidechains function with parameters collected from the dialog.
    '''
    registry.call("wrapped_menu_dump_sidechains", dynamic_values=dynamic_values)