from ..driver.ui_driver import ConfigBus
from ..tools.customized_widgets import (AskedValue, AskedValueCollection,
                                        ask_for_values, dialog_wrapper)
from ..tools.pymol_utils import get_all_groups
from ..tools.utils import run_worker_thread_with_progress,timing
from .shortcuts import dump_sidechains

@dialog_wrapper(
    title="Dump Sidechains",
    banner="Dump all sidechain conformers of selected groups.",
    options=(
        AskedValue(
            "enabled_only",
            False,
            typing=bool,
            reason="Dump only enabled models."
        ),
        AskedValue(
            "save_dir",
            "png/sidechains",
            reason="Directory to save the sidechains."
        ),
        AskedValue(
            "height",
            1280,
            typing=int,
            reason="Height of the image."
        ),
        AskedValue(
            "width",
            1280,
            typing=int,
            reason="Width of the image."
        ),
        AskedValue(
            "dpi",
            150,
            typing=int,
            reason="DPI of the image.",
            choices=(150, 300, 600, 1200),
        ),
        AskedValue(
            "ray",
            True,
            typing=bool,
            reason="Use ray tracing."
        ),
        AskedValue(
            "hide_mesh",
            True,
            typing=bool,
            reason="Hide mesh."
        ),
        AskedValue(
            "neighborhood",
            3,
            typing=int,
            reason="Select with neighborhood area.",
            choices=range(1, 25),
        ),
        AskedValue(
            "recenter",
            False,
            typing=bool,
            reason="Recenter sidechains. Disable to make the background unmoved.",
        ),
        AskedValue(
            "reorient",
            True,
            typing=bool,
            reason="Re-orients the residue. "
            "Disable to prevent automatic orientation, useful when user wants to dump the residue they just focused on.",
        ),
    )
)
def wrapped_menu_dump_sidechains(**kwargs):
    """
    Runs the sidechain dumping process with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("Dumping sidechains"):
        print(kwargs)
        run_worker_thread_with_progress(
            dump_sidechains,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )

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
            typing=list,
            reason="Select the models to dump sidechains.",
            choices=get_all_groups(),
        ),
        "index": 0,  # Specify the position in the options list
    }

    wrapped_menu_dump_sidechains(dynamic_values=[dynamic_value])

