'''
Shortcut wrappers of results exporting
'''

from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.shortcuts.shortcuts import shortcut_dump_fasta_from_struct, shortcut_dump_sidechains
from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper

from Bio import SeqIO

from REvoDesign.tools.package_manager import run_worker_thread_with_progress
from REvoDesign.tools.utils import timing

from ...logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)


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
        logging.info(kwargs)
        run_worker_thread_with_progress(
            shortcut_dump_sidechains,
            **kwargs,
            progress_bar=ConfigBus().ui.progressBar
        )


@dialog_wrapper(
    title="Dump Sequenece from Structure",
    banner="Dump the sequence of the selected molecule/chain to a sequence file.",
    options=(
        AskedValue(
            "format",
            "fasta",
            typing=str,
            reason="Output format. Default is fasta.",
            required=True,
            choices=filter(lambda x: x.startswith('fas'), SeqIO._FormatToWriter.keys())
        ),
        AskedValue(
            "chain_ids",
            "",
            typing=list,
            reason="Chain IDs to operated on. Default is empty for the chain picked on UI.",
            choices=lambda: list(ConfigBus().get_value("designable_sequences", dict, reject_none=True).keys())
        ),
        AskedValue(
            "output_dir",
            'dumped_sequences',
            typing=str,
            required=True,
            reason="Output directory. Default is 'dumped_sequences'.",
        ),
        AskedValue(
            "drop_missing_residue",
            False,
            typing=bool,
            reason="Drop missing residues(`X`) in the sequence if True. Default is False.",
        ),
        AskedValue(
            "suffix",
            '',
            typing=str,
            reason="Suffix for the output file. Default is empty.",
        ),
    )
)
def wrapped_dump_fasta_from_struct(**kwargs):
    """
    Runs the dump_fasta_from_struct function with parameters collected from the dialog.
    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)

    shortcut_dump_fasta_from_struct(**kwargs)
