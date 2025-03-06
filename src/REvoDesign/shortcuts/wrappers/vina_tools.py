'''
Shortcut wrappers of structure manipulation
'''

from pymol import cmd
from REvoDesign.shortcuts.tools.vina_tools import box_helper, rmhet,getbox, get_pca_box
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
    title="Alter Box",
    banner="Change Box coordinates or size",
    options=(
        AskedValue(
            "box_name",
            "",
            typing=str,
            reason="Box name to operated on.",
            required=True,
            choices=lambda: list(b for b in  cmd.get_object_list() if b.startswith('box_'))
        ),
        AskedValue(
            "action",
            '',
            typing=str,
            reason="Action to take on the box. move_coords or change_size",
            choices=['move_coords', 'change_size']
        )
    )
)
def wrapped_alterbox(**kwargs):
    """
    Runs the get_box function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)
    box_helper(**kwargs)


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
