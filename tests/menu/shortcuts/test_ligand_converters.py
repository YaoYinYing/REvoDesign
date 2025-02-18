import json
import os
from typing import Dict

import pytest

from REvoDesign.shortcuts.tools.ligand_converters import (shortcut_sdf2rosetta_params,
                                            shortcut_smiles_conformer_batch,
                                            shortcut_smiles_conformer_single)
from tests.conftest import TestWorker


@pytest.mark.serial
def test_shortcut_smiles_conformer_single(test_worker: TestWorker):
    ligand_name = 'MOR'
    smiles = "CN1CC[C@]23[C@@H]4[C@H]1CC5=C2C(=C(C=C5)O)O[C@H]3[C@H](C=C4)O"  # morphine
    shortcut_smiles_conformer_single(
        ligand_name=ligand_name,
        smiles=smiles,
        num_conformer=100,
        save_dir=os.path.abspath('./ligands_conformers/'),
        show_conformer='None'
    )
    res_dir = os.path.join(os.path.abspath('./ligands_conformers/'), ligand_name)
    assert os.path.isfile(os.path.join(os.path.abspath('./ligands_conformers/'),
                          f'{ligand_name}.sdf')), f'{ligand_name}.sdf not found in the directory {os.path.abspath("./ligands_conformers/")}'

    res_files = os.listdir(res_dir)
    assert len(res_files) == 6, f'Expected 6 files in the directory {res_dir}/{ligand_name}, but got: \n {res_files}'
    conformer_fa_pdb = os.path.join(res_dir, f'{ligand_name}.fa_conformers.pdb')
    assert os.path.isfile(conformer_fa_pdb)
    assert os.path.getsize(
        conformer_fa_pdb) > 0, f'{ligand_name}.fa_conformers.pdb should not be empty in the directory {res_dir}/{ligand_name}'
    conformer_pdb_contents = open(conformer_fa_pdb).readlines()
    assert len([x for x in conformer_pdb_contents if x.startswith(
        'TER')]) > 1, f'{ligand_name}.fa_conformers.pdb should have multiple TER record in the directory {res_dir}/{ligand_name}'
    assert os.path.isfile(os.path.join(res_dir, f'{ligand_name}.fa.params'))


@pytest.mark.serial
def test_shortcut_smiles_conformer_batch(test_worker: TestWorker):
    smiles = '../tests/data/json/sm_input/12968814160.json'
    res_dir = os.path.abspath('./ligands_conformers_batch/')

    smi: Dict[str, str] = json.load(open(smiles))
    shortcut_smiles_conformer_batch(
        smiles=smiles,
        num_conformer=20,
        save_dir=res_dir,
        n_jobs=1,
        show_conformer='None'
    )

    for k in smi:
        sdf_path = os.path.join(res_dir, f"{k}.sdf")
        assert os.path.isfile(sdf_path), f'{k}.sdf not found in the directory {res_dir}'
        assert os.path.getsize(sdf_path) > 0, f'{k}.sdf should not be empty in the directory {res_dir}'
        params_dir = os.path.join(res_dir, k)
        assert os.path.isfile(os.path.join(params_dir, f"{k}.fa.params")
                              ), f'{k}.fa.params not found in the directory {res_dir}'
        assert os.path.getsize(
            os.path.join(
                params_dir, f"{k}.fa.params")) > 0, f'{k}.fa.params should not be empty in the directory {res_dir}'

@pytest.mark.serial
def test_shortcut_sdf2rosetta_params(test_worker: TestWorker):
    sdf_path = os.path.abspath('../tests/data/sdf/HEM.sdf')
    save_dir = os.path.abspath('./ligands_sdf/')
    shortcut_sdf2rosetta_params(
        ligand_name='HEM',
        sdf_path=sdf_path,
        save_dir=save_dir
    )
    res_dir = os.path.join(save_dir, 'HEM')
    assert len(os.listdir(res_dir)
               ) == 6, f'Expected 6 files in the directory {res_dir}/HEM, but got: \n {os.listdir(res_dir)}'
    assert os.path.isfile(os.path.join(res_dir, 'HEM.fa.params')
                          ), f'HEM.fa.params not found in the directory {res_dir}/HEM'

    assert os.path.getsize(os.path.join(res_dir, 'HEM.fa.params')
                           ) > 0, f'HEM.fa.params is empty in the directory {res_dir}/HEM'
    assert os.path.getsize(os.path.join(res_dir, 'HEM.fa_conformers.pdb')
                           ) == 0, 'HEM.fa_conformers.pdb should be empty since there is only one conformer.'

