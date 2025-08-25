from REvoDesign.shortcuts.tools.exports import (
    shortcut_dump_fasta_from_struct, shortcut_dump_sidechains)
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from ...logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
registry = DialogWrapperRegistry("exports")
wrapped_dump_fasta_from_struct = registry.register("dump_fasta_from_struct", shortcut_dump_fasta_from_struct)
wrapped_menu_dump_sidechains = registry.register(
    "menu_dump_sidechains",
    shortcut_dump_sidechains,
    use_thread=True,
    has_dynamic_values=True)