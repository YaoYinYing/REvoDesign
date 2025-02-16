from REvoDesign.shortcuts.shortcut_tools import wrapped_smiles_conformer_single
from tests.conftest import TestWorker

# def test_smiles_conformer_single(tmpdir, test_worker: TestWorker):
#     """
#     Tests the smiles_conformer_single function.
#     """
#     wrapped_smiles_conformer_single(
#         ligand_name='LIG',
#         smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
#         show_conformer="None",
#         num_conformers=10,
#         save_dir=tmpdir,
#     )
#     assert os.path.exists(os.path.join(tmpdir, "LIG.sdf"))
