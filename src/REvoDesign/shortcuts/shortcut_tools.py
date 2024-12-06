from ..driver.ui_driver import ConfigBus
from ..tools.customized_widgets import (AskedValue, AskedValueCollection,
                                        ask_for_values)
from ..tools.pymol_utils import get_all_groups
from ..tools.utils import run_worker_thread_with_progress
from .shortcuts import dump_sidechains


def menu_dump_sidechains(dump_all=False) -> None:
    """
    Launches a menu for dumping sidechains with configurable parameters.

    This function presents a user-friendly dialog (using `ask_for_values`) to collect
    user preferences for dumping sidechain conformers. Users can specify model selections,
    rendering options, and image properties. If `dump_all` is True, all models are preselected
    in the dialog.

    Parameters:
        dump_all (bool, optional):
            If True, automatically preselects all available models. Defaults to False.

    Collected Parameters:
        sele (list):
            A list of selected models for dumping sidechains. Defaults to all groups if `dump_all` is True.
        enabled_only (bool):
            Whether to dump sidechains only for enabled models. Defaults to False.
        save_dir (str):
            Directory path where the sidechains will be saved. Defaults to "png/sidechains".
        height (int):
            Height of the output image in pixels. Defaults to 1280.
        width (int):
            Width of the output image in pixels. Defaults to 1280.
        dpi (int):
            Dots per inch (DPI) for the output image. Choices are (150, 300, 600, 1200). Defaults to 150.
        ray (bool):
            Whether to use ray tracing for rendering. Defaults to True.
        hide_mesh (bool):
            Whether to hide mesh visualization. Defaults to True.
        neighborhood (int):
            Neighborhood size for selecting areas around the sidechains. Range: 1-24. Defaults to 3.
        reorient (bool):
            Whether to reorient the sidechains. Defaults to True.
        recenter (bool):
            Whether to recenter the sidechains. Disabling it keeps the background unmoved. Defaults to False.

    Returns:
        None:
            The function exits without further processing if the dialog is canceled.

    Side Effects:
        - Opens a user dialog to collect input parameters.
        - Runs the `dump_sidechains` process with the collected parameters using a worker thread.
        - Prints the collected parameters for debugging or logging purposes.

    Example:
        >>> menu_dump_sidechains(dump_all=True)
        Dump all sidechain conformers of selected groups.
        [AskedValue(key='sele', val=['group1', 'group2'], ...)]
        {'sele': ['group1', 'group2'], 'enabled_only': True, ...}

    Notes:
        - This function integrates with a worker thread (`run_worker_thread_with_progress`) to
          perform the actual sidechain dumping process asynchronously.
        - The dialog is dynamically constructed based on the `AskedValueCollection` definition,
          making it flexible for future extensions.
    """
    values = ask_for_values(
        "Dump sidechains",
        AskedValueCollection(
            [
                AskedValue(
                    "sele",
                    val=None if not dump_all else get_all_groups(),
                    typing=list,
                    reason="Select the models to dump sidechains.",
                    choices=get_all_groups()),
                AskedValue(
                    "enabled_only",
                    False,
                    typing=bool,
                    reason="Dump only enabled models."),
                AskedValue(
                    "save_dir",
                    "png/sidechains",
                    reason="Directory to save the sidechains."),
                AskedValue(
                    "height",
                    1280,
                    typing=int,
                    reason="Height of the image."),
                AskedValue(
                    "width",
                    1280,
                    typing=int,
                    reason="Width of the image."),
                AskedValue(
                    "dpi",
                    150,
                    typing=int,
                    reason="DPI of the image.",
                    choices=(150, 300, 600, 1200,),
                ),
                AskedValue(
                    "ray",
                    True,
                    typing=bool,
                    reason="Use ray tracing."),
                AskedValue(
                    "hide_mesh",
                    True,
                    typing=bool,
                    reason="Hide mesh."),
                AskedValue(
                    "neighborhood",
                    3,
                    typing=int,
                    reason="Select with neighborhood area. Enabled with `reorient=True`",
                    choices=range(1, 25),),
                AskedValue(
                    "reorient",
                    True,
                    typing=bool,
                    reason="Re-orients the residue. "
                    "Disable to prevent automatic orientatio, useful when user wants to dump the residue they just focused on."),
                AskedValue(
                    "recenter",
                    False,
                    typing=bool,
                    reason="Recenter sidechains. Disable to make the background unmoved."),
            ],
            banner='Dump all sidechain conformers of selected groups. '))

    if not values:
        return

    params = values.asdict
    print(values)
    print(params)

    run_worker_thread_with_progress(
        dump_sidechains,
        **params,
        progress_bar=ConfigBus().ui.progressBar
    )
