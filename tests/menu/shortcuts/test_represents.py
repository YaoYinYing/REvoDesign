import os

import pytest
from pymol import cmd
import random
import pandas as pd
from REvoDesign.shortcuts.tools.represents import shortcut_color_by_mutation, _load_b_factors
from tests.conftest import TestWorker
from REvoDesign.tools.pymol_utils import get_molecule_sequence


@pytest.mark.serial
def test_shortcut_color_by_mutation(test_worker: TestWorker):
    pdb_1 = '../tests/data/pdb/3fap_hf3_A_short_00001.pdb'
    pdb_2 = '../tests/data/pdb/3fap_hf3_A_short_00001_0.5.pdb'

    cmd.load(pdb_1)
    cmd.load(pdb_2)

    obj_1 = os.path.basename(pdb_1)[:-4]
    obj_2 = os.path.basename(pdb_2)[:-4]

    shortcut_color_by_mutation(
        obj1=obj_1,
        obj2=obj_2
    )

    selections = cmd.get_names('selections')

    for sel_id in ['mutations', 'non_mutations', 'not_aligned']:
        assert sel_id in selections, f"{sel_id} not in selections"

    mutation_atoms_set_1 = cmd.get_model(f'mutations and {obj_1} ').atom

    mutation_ca_atoms_set_1 = [atom for atom in mutation_atoms_set_1 if atom.name == 'CA']

    mutation_atoms_set_2 = cmd.get_model(f'mutations and {obj_2}').atom

    mutation_ca_atoms_set_2 = [atom for atom in mutation_atoms_set_2 if atom.name == 'CA']

    for ca_1, ca_2 in zip(mutation_ca_atoms_set_1, mutation_ca_atoms_set_2):
        assert ca_1.resi == ca_2.resi, f'{ca_1.resi} != {ca_2.resi}'
        assert ca_1.resn != ca_2.resn, f'{ca_1.resn} == {ca_2.resn}'

@pytest.mark.parametrize("table_file_name,pos_slice,offset", [
    ['b_factors.bfactors.csv', None, 0],
    ['b_factors.bfactors.csv', '1-11', 0],
    ['b_factors.bfactors.csv', '2-9', 0],
    ['b_factors.bfactors.csv', '1+3+5+7', 0],
    ['b_factors.bfactors.csv', '1+3+5-7', 0],
    ['b_factors.bfactors.csv', '1+3+5-7', 1],


])
def test_load_b_factors(table_file_name,pos_slice,offset, test_worker: TestWorker, test_tmp_dir):

    pdb_path = '../tests/data/3fap_hf3_A_short.pdb'
    test_worker.test_id = test_worker.method_name()
    test_worker.load_session_and_check(customized_session=pdb_path)

    obj_name = os.path.basename(pdb_path)[:-4]

    # clear b-factors before get model for testing
    cmd.alter('(all)', "b=0.0")
    cmd.orient(obj_name)

    # before loading b-factors, all b-factors should be zero
    model = cmd.get_model(obj_name)

    
    for atom in model.atom:
        assert atom.b == 0.0, f"Expected b-factor 0.0, got {atom.b} for atom {atom.name} in residue {atom.resi}"

    seq=get_molecule_sequence(obj_name,'A')
    randb=random.sample(range(1,20),len(seq))

    table_file_path=os.path.join(test_tmp_dir, table_file_name)
    with open(table_file_path, 'w') as bf:
        df=pd.DataFrame({'b_factor':randb})
        df.to_csv(bf,index=False)

    test_worker.save_pymol_png(f'before_load_b_{pos_slice}_{offset}_{test_worker.method_name()}')

    # load b-factors
    _load_b_factors(
        mol=obj_name,
        chain_ids='A',
        keep_missing=True,
        source=table_file_path,
        label='b_factor',
        pos_slice=pos_slice,
        offset=offset
    )
    
    test_worker.save_pymol_png(f'after_load_b_factors_{pos_slice}_{offset}_{test_worker.method_name()}')


    # after loading b-factors, check that they are updated
    model = cmd.get_model(obj_name)
    b_factors = [atom.b for atom in model.atom]
    assert any(b != 0.0 for b in b_factors), "B-factors were not updated, all are still 0.0"