'''
Shortcut wrappers of vina-related structure manipulation
'''


from REvoDesign.shortcuts.tools.vina_tools import (box_helper, get_pca_box,
                                                   getbox, rmhet)
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

# Create registry for vina
registry = DialogWrapperRegistry("vina")

wrapped_getbox = registry.register("get_box", getbox, use_thread=True)
wrapped_alter_box = registry.register("alter_box", box_helper)
wrapped_get_pca_box = registry.register("get_pca_box", get_pca_box, use_thread=True)


def wrapped_rmhet():
    """
    Remove all HETATM records (ligands, waters, ions).
    """
    return rmhet()
