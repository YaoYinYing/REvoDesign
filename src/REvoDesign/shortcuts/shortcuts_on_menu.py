'''
This module contains the menu shortcuts for REvoDesign.
'''
from REvoDesign.shortcuts.wrappers.exports import wrapped_menu_dump_sidechains
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
            typing=str,
            reason="Select the models to dump sidechains.",
            choices=get_all_groups(),
            multiple_choices=True
        ),
        "index": 0,
    }
    wrapped_menu_dump_sidechains([dynamic_value])
