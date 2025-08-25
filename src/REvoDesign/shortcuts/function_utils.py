import os
import subprocess
from typing import Dict, Literal
from pymol import cmd
from RosettaPy.app.utils.smiles2param import SmallMoleculeParamsGenerator
from REvoDesign import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
def visualize_conformer_sdf(sdf_file_path: str, show_conformer: Literal['New Window', 'Current Window']):
    if show_conformer == 'Current Window':
        cmd.load(sdf_file_path)
        return
    tmpdir = os.path.abspath(os.path.dirname(sdf_file_path))
    sdf_bn = os.path.basename(sdf_file_path)
    sdf_bn_wo_ext, _ = os.path.splitext(sdf_bn)
    pml_file_path = os.path.join(tmpdir, f'{sdf_bn_wo_ext}_load_to_preview.pml')
    with open(pml_file_path, 'w') as pmlh:
        pmlh.write(f"load {os.path.abspath(sdf_file_path)}\n")
        pmlh.write("zoom\norient\n")
        pmlh.write("set internal_feedback, 0\n")
        pmlh.write("viewport 800, 600\n")
        pmlh.write("bg_color white\n")
    pymol_command = ["pymol", "-xi", pml_file_path]
    subprocess.Popen(pymol_command)
    print(f"PyMOL launched in the background with {sdf_file_path}.")
def smiles_conformer_batch(smi: Dict[str, str], num_conformer: int, save_dir: str, n_jobs: int = 1):
    print(f'Converting {len(smi)} molecules to 3D conformers({num_conformer})...')
    converter = SmallMoleculeParamsGenerator(save_dir=save_dir, num_conformer=num_conformer)
    converter.convert(ligands=smi, n_jobs=n_jobs)
def smiles_conformer_single(ligand_name: str, smiles: str, num_conformer: int, save_dir: str,):
    return smiles_conformer_batch(smi={ligand_name: smiles}, num_conformer=num_conformer, save_dir=save_dir)