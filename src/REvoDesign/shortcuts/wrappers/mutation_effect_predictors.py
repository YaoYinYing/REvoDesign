'''
Shortcut wrappers of mutation effect predictors
'''
from REvoDesign.shortcuts.tools.mutation_effect_predictors import \
    shortcut_thermompnn
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
registry = DialogWrapperRegistry("mutation")
wrapped_thermompnn = registry.register(
    "thermompnn",
    shortcut_thermompnn,
    use_thread=True
)