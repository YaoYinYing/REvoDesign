import os

import pytest
from pymol import cmd

from REvoDesign.shortcuts.tools.represents import shortcut_color_by_mutation
from tests.conftest import TestWorker

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
