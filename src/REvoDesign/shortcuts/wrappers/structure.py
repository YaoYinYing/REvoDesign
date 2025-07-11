'''
Shortcut wrappers of structure manipulation
'''


from REvoDesign.tools.pymol_utils import renumber_protein_chain

from REvoDesign.shortcuts.utils import DialogWrapperRegistry

# Create registry for 'structure' category
registry = DialogWrapperRegistry("structure")

wrapped_resi_renumber = registry.register(
    "resi_renumber",
    renumber_protein_chain,
    use_thread=True
)
