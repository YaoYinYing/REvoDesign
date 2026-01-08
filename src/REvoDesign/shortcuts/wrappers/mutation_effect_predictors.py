"""
Shortcut wrappers of mutation effect predictors
"""

from REvoDesign.shortcuts.tools.mutation_effect_predictors import shortcut_thermompnn
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

# Register the ThermoMPNN task in the 'mutation' category
registry = DialogWrapperRegistry("mutation")

wrapped_thermompnn = registry.register("thermompnn", shortcut_thermompnn, use_thread=True)
