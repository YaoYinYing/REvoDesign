'''
Shortcut wrappers of structure manipulation
'''

from pymol import cmd
from REvoDesign.shortcuts.tools.vina_tools import rmhet,getbox, movebox, enlargebox, get_pca_box
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)

def wrapped_rmhet():
    '''
    Get Auto Dock Box for a selection
    '''
    return rmhet()

@dialog_wrapper(
    title="Get Box",
    banner="Get Auto Dock Box for a selection",
    options=(
        AskedValue(
            "selection",
            "",
            typing=str,
            reason="Selections to operated on.",
            required=True,
            choices=lambda: list(cmd.get_names('selections'))
        ),
        AskedValue(
            "new_box_name",
            '',
            typing=str,
            reason="Box name. Leave blank for a random name.",
        ),
        AskedValue(
            "extending",
            5.0,
            typing=int,
            reason="Box padding distance. Default is 5.",
        ),
    )
)
def wrapped_getbox(**kwargs):
    """
    Runs the get_box function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)
    getbox(**kwargs)


@dialog_wrapper(
    title="Get PCA Box, non axes aligned",
    banner="Get PCA analysed Box for a selection",
    options=(
        AskedValue(
            "selection",
            "",
            typing=str,
            reason="Selections to operated on.",
            required=True,
            choices=lambda: list(cmd.get_names('selections'))
        ),
        AskedValue(
            "new_box_name",
            '',
            typing=str,
            reason="Box name. Leave blank for a random name.",
        ),
        AskedValue(
            "extending",
            5.0,
            typing=int,
            reason="Box padding distance. Default is 5.",
        ),
    )
)
def wrapped_get_pca_box(**kwargs):
    """
    Runs the get_pca_box function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)
    get_pca_box(**kwargs)
