'''
Shortcut wrappers of structure representation
'''

from pymol import cmd

from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.shortcuts import (shortcut_color_by_plddt,
                                            shortcut_real_sc,shortcut_color_by_mutation)
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


@dialog_wrapper(
    title="Color by pLDDT",
    banner="Color Predicted Protein structures by pLDDT values recorded in the B-factor column of the PDB file. "
           "Optionally, align to a target model and chain for comparison.",
    options=(
        AskedValue(
            "selection",
            "all",
            typing=str,
            reason="The PyMOL selection of objects or residues to color."
        ),
        AskedValue(
            "align_target",
            0,
            typing=int,
            reason="The rank order of the target in the selections (1-based). Set 0 to skip alignment."
        ),
        AskedValue(
            "chain_to_align",
            "A",
            typing=str,
            reason="The chain ID to align the selection to."
        ),
    )
)
def wrapped_color_by_plddt(**kwargs):
    """
    Runs the color_by_plddt function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("Coloring by pLDDT"):
        print(kwargs)
        run_worker_thread_with_progress(
            shortcut_color_by_plddt,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )


@dialog_wrapper(
    title="Set Sidechain Representation",
    banner="Set the molecular representation focusing on the sidechain or alpha carbon.",
    options=(
        AskedValue(
            "selection",
            "(all)",
            typing=str,
            reason="Atom selection to apply the representation to. Default is '(all)'."
        ),
        AskedValue(
            "representation",
            "lines",
            typing=str,
            reason="Representation style ('lines', 'sticks', 'spheres', 'dots').",
            choices=("lines", "sticks", "spheres", "dots"),
        ),
        AskedValue(
            "hydrogen",
            False,
            typing=bool,
            reason="Include hydrogens in the representation if True. Default is False."
        ),
    )
)
def wrapped_real_sc(**kwargs):
    """
    Runs the real_sc function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("Set Sidechain Representation"):
        logging.info(kwargs)
        run_worker_thread_with_progress(
            shortcut_real_sc,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )



@dialog_wrapper(
    title="Color by mutation",
    banner="""Creates an alignment of two proteins and superimposes them.
Aligned residues that are different in the two (i.e. mutations) are highlighted and
colored according to their difference in the BLOSUM90 matrix.
Is meant to be used for similar proteins, e.g. close homologs or point mutants,
to visualize their differences.""",
    options=(
        AskedValue(
            "obj1",
            typing=str,
            reason="The PyMOL selection of the first object to color.",
            choices=lambda: cmd.get_names("objects"),
            required=True
        ),
        AskedValue(
            "obj2",
            typing=str,
            reason="The PyMOL selection of the second object to color.",
            choices=lambda: cmd.get_names("objects"),
            required=True
        ),
        AskedValue(
            "waters",
            False,
            typing=bool,
            reason="Whether water should be included in the comparison. Default is False."
        ),
        AskedValue(
            "labels",
            False,
            typing=bool,
            reason="Whether to show mutation labels. Default is False."
        ),
    )
)
def wrapped_color_by_mutation(**kwargs):
    """
    Runs the color_by_mutation function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    with timing("Coloring by mutation"):
        print(kwargs)
        run_worker_thread_with_progress(
            shortcut_color_by_mutation,
            **kwargs,
        )
