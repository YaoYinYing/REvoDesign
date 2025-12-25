"""
Shortcut wrappers of structure representation
"""

from REvoDesign import issues
from REvoDesign.shortcuts.tools.represents import (load_b_factors,
                                                   shortcut_color_by_mutation,
                                                   shortcut_color_by_plddt,
                                                   shortcut_real_sc)
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.tools.package_manager import notify_box

# Category registry: represents
registry = DialogWrapperRegistry("represents")


def _color_by_mutation(**kwargs):
    """
    Runs the color_by_mutation function with parameters collected from the dialog.

    Args:
        **kwargs: Parameters collected from the dialog.
    """
    if kwargs["obj1"] == kwargs["obj2"]:
        raise issues.InvalidInputError(
            "The two objects cannot be the same. " f'obj1={kwargs["obj1"]}, obj2={kwargs["obj2"]}'
        )

    shortcut_color_by_mutation(**kwargs)


wrapped_color_by_plddt = registry.register("color_by_plddt", shortcut_color_by_plddt, use_thread=True)
wrapped_real_sc = registry.register("real_sc", shortcut_real_sc, use_thread=True)
wrapped_color_by_mutation = registry.register("color_by_mutation", _color_by_mutation, use_thread=True)
wrapped_load_b_factors = registry.register("load_b_factors", load_b_factors)
