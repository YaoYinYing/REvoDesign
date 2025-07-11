from REvoDesign.shortcuts.tools.ligand_converters import (
    shortcut_sdf2rosetta_params, shortcut_smiles_conformer_batch,
    shortcut_smiles_conformer_single)
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

# Initialize the registry for the 'ligand' category
registry = DialogWrapperRegistry("ligand")

# Register the SMILES Conformer (Single)
wrapped_smiles_conformer_single = registry.register(
    "smiles_conformer_single",
    shortcut_smiles_conformer_single
)

# Register the SMILES Conformer (Batch)
wrapped_smiles_conformer_batch = registry.register(
    "smiles_conformer_batch",
    shortcut_smiles_conformer_batch
)

# Register the SDF to Rosetta Parameter Conversion
wrapper_sdf2rosetta_params = registry.register(
    "sdf2rosetta_params",
    shortcut_sdf2rosetta_params
)
