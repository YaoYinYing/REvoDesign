'''
Shortcut wrappers of results exporting
'''

from typing import Any, List, Optional

from REvoDesign.shortcuts.tools.exports import (
    shortcut_dump_fasta_from_struct, shortcut_dump_sidechains)
from REvoDesign.shortcuts.utils import DialogWrapperRegistry


from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)

# Init registry for sequence-related dialogs
registry = DialogWrapperRegistry("exports")

# Register function manually
registry.register("wrapped_dump_fasta_from_struct", shortcut_dump_fasta_from_struct)

registry.register("wrapped_menu_dump_sidechains", shortcut_dump_sidechains, use_thread=True)


def wrapped_dump_fasta_from_struct():
    """
    Runs the dump_fasta_from_struct function with parameters collected from the dialog.
    Args:
        **kwargs: Parameters collected from the dialog.
    """

    registry.call("wrapped_dump_fasta_from_struct")


def wrapped_menu_dump_sidechains(dynamic_values: Optional[List[Any]] = None):
    '''
    Runs the dump_sidechains function with parameters collected from the dialog.
    '''
    registry.call("wrapped_menu_dump_sidechains", dynamic_values=dynamic_values)
