
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

from REvoDesign.shortcuts.tools.mutation_effect_predictors import shortcut_thermompnn

# Register the ThermoMPNN task in the 'mutation' category
registry = DialogWrapperRegistry("mutation")

wrapped_thermompnn = registry.register(
    "thermompnn",
    shortcut_thermompnn,
    use_thread=True
)
