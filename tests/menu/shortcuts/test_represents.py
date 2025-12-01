import os
import random

import pandas as pd
import pytest
from pymol import cmd

from REvoDesign.shortcuts.tools.represents import (_load_b_factors,
                                                   shortcut_color_by_mutation)
from REvoDesign.tools.pymol_utils import get_molecule_sequence
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


@pytest.mark.parametrize("test_name,table_file_name,pos_slice,offset,label_x,label_y,index_x,index_y,palette_code,do_rescale", [
    
    # test formats
    ['CSV','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', None, 0, None, None, None, None, None, False],
    ['Excel Modern','csv/3fap_hf3_A_short.Backbone.rmsf_res.xlsx', None, 0, None, None, None, None, None, False],
    ['Excel Legacy','csv/3fap_hf3_A_short.Backbone.rmsf_res.xls', None, 0, None, None, None, None, None, False],
    ['TSV','tsv/3fap_hf3_A_short.Backbone.rmsf_res.tsv', None, 0, None, None, None, None, None, False],
    ['TXT','txt/3fap_hf3_A_short.Backbone.rmsf_res.txt', None, 0, None, None, None, None, None, False],
    ['PDB','pdb/3fap_hf3_A_short_lig.rmsf.pdb', None, 0, None, None, None, None, None, False],


    # test slices and offsets
    ['CSV-explict-full-length','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', '1-11', 0, None, None, None, None, None, False],
    ['CSV-custom-range-1','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', '2-9', 0, None, None, None, None, None, False],
    ['CSV-four-signel','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', '1+3+5+7', 0, None, None, None, None, None, False],
    ['CSV-single-seg','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', '1+3+5-7', 0, None, None, None, None, None, False],
    ['CSV-single-seg-offset','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', '1+3+5-7', 1, None, None, None, None, None, False],

    # test labels
    ['CSV_text_label','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', None, 0, 'position', 'rmsf', None, None, None, False],
    ['CSV_numeric_col_idx','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', None, 0, None, None, 0, 1, None, False],

    # test palette
    ['CSV-magenta_white_blue','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', None, 0, None, None, None, None, 'magenta_white_blue', False],
    ['CSV-cyan_magenta','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', None, 0, None, None, None, None, 'cyan_magenta', False],

    # test rescaling
    ['CSV-rescale','csv/3fap_hf3_A_short.Backbone.rmsf_res.csv', None, 0, None, None, None, None, None, True],



])
def test_load_b_factors(test_name,table_file_name, pos_slice, offset,label_x,label_y,index_x,index_y,palette_code,do_rescale, test_worker: TestWorker):

    pdb_path = '../tests/data/3fap_hf3_A_short.pdb'
    test_data_path='../tests/data/'
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


    test_worker.save_pymol_png(f'{test_name}.before_load_b_{pos_slice}_{offset}_{test_worker.method_name()}')

    # load b-factors
    _load_b_factors(
        mol=obj_name,
        chain_ids='A',
        keep_missing=True,
        source=os.path.join(test_data_path, table_file_name),
        label_x=label_x or None,
        label_y=label_y or None,
        index_x=index_x or 0,
        index_y=index_y or 1,
        palette_code=palette_code or 'rainbow',
        do_rescale=do_rescale,
        pos_slice=pos_slice,
        offset=offset
    )

    test_worker.save_pymol_png(f'{test_name}.after_load_b_factors_{pos_slice}_{offset}_{test_worker.method_name()}')

    # after loading b-factors, check that they are updated
    model = cmd.get_model(obj_name)
    b_factors = [atom.b for atom in model.atom]
    assert any(b != 0.0 for b in b_factors), "B-factors were not updated, all are still 0.0"
