
from ..driver.ui_driver import ConfigBus
from ..tools.utils import run_worker_thread_with_progress
from ..tools.customized_widgets import AskedValue, AskedValueCollection, ask_for_values
from ..tools.pymol_utils import get_all_groups

from .shortcuts import dump_sidechains


def menu_dump_sidechains() -> None:
    values = ask_for_values(
        "Dump sidechains",
        AskedValueCollection(
            [
                AskedValue("sele", typing=list, reason="Select the models to dump sidechains.", choices=get_all_groups()),
                AskedValue("enabled_only",False, typing=bool, reason= "Dump only enabled models."),
                AskedValue("save_dir","png/sidechains", reason="Directory to save the sidechains."),
                AskedValue("height",1280,typing=int, reason="Height of the image."),
                AskedValue("width",1280,typing=int, reason="Width of the image."),
                AskedValue("dpi",150,typing=int, reason="DPI of the image."),
                AskedValue("ray",True,typing=bool, reason="Use ray to dump sidechains."),
                AskedValue("hide_mesh",True,typing=bool, reason="Hide mesh."),
                AskedValue("neiborhood",3,typing=int, reason="Neiborhood size."),
            ]
        )
    )

    if not values:
        return
    

    params=values.asdict
    print(values)
    print(params)

    run_worker_thread_with_progress(
        dump_sidechains,
        **params,
        progress_bar=ConfigBus().ui.progressBar
    )