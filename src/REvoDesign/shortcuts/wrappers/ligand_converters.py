from REvoDesign.shortcuts.tools.ligand_converters import (
    shortcut_sdf2rosetta_params, shortcut_smiles_conformer_batch,
    shortcut_smiles_conformer_single)
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
registry = DialogWrapperRegistry("ligand")
wrapped_smiles_conformer_single = registry.register(
    "smiles_conformer_single",
    shortcut_smiles_conformer_single
)
wrapped_smiles_conformer_batch = registry.register(
    "smiles_conformer_batch",
    shortcut_smiles_conformer_batch
)
wrapper_sdf2rosetta_params = registry.register(
    "sdf2rosetta_params",
    shortcut_sdf2rosetta_params
)