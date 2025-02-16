'''
Shortcut wrappers of structure manipulation
'''

from pymol import cmd


from REvoDesign.tools.customized_widgets import AskedValue, dialog_wrapper
from REvoDesign.tools.pymol_utils import renumber_protein_chain

from ...logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)




@dialog_wrapper(
    title="Renumber Residue index",
    banner="Renumber Residue index by giving an offset.",
    options=(
        AskedValue(
            "molecule",
            "",
            typing=list,
            reason="Molecule to operated on.",
            required=True,
            choices=cmd.get_object_list
        ),
        AskedValue(
            "chain",
            'A',
            typing=str,
            reason="Chain ID to operate on. Accept PyMOL chain syntax (A+B+C for chain A and B and C). Default is A.",
        ),
        AskedValue(
            "offset",
            0,
            typing=int,
            reason="Renumber offset. Default is 0.",
        ),
    )
)
def wrapped_resi_renumber(**kwargs):
    """
    Runs the renumber_protein_chain function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    logging.info(kwargs)
    renumber_protein_chain(**kwargs)