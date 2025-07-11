'''
Shortcut wrappers of sequence designs
'''

from REvoDesign.shortcuts.tools.designs import shortcut_pssm2csv

from REvoDesign.tools.mutant_tools import pick_design_from_profile


from REvoDesign.shortcuts.tools.designs import shortcut_pssm2csv
from REvoDesign.tools.mutant_tools import pick_design_from_profile
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

registry = DialogWrapperRegistry("designs")

wrapped_pssm2csv = registry.register(
    "pssm2csv",
    shortcut_pssm2csv,
    use_thread=True
)

wrapped_profile_pick_design = registry.register(
    "profile_pick_design",
    pick_design_from_profile,
    use_thread=True
)
