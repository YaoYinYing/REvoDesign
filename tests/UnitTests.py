import os
import random
from pymol import cmd, util, CmdException
from absl.testing import absltest
from unittest.mock import Mock
from unittest.mock import MagicMock
from unittest.mock import patch

from typing import List, Dict, Union
from hashlib import sha256
from REvoDesign.clients.PSSM_GREMLIN_client import PSSMGremlinCalculator

from REvoDesign.common.Mutant import Mutant
from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.tools.mutant_tools import expand_range, extract_mutant_from_sequences, extract_mutant_score_from_string, extract_mutants_from_mutant_id, shorter_range
from REvoDesign.tools.pymol_utils import (
    any_posision_has_been_selected,
    find_all_protein_chain_ids_in_protein,
    find_design_molecules,
    find_small_molecules_in_protein,
    get_molecule_sequence,
    is_a_REvoDesign_session,
    is_distal_residue_pair,
    is_empty_session,
    is_hidden_object,
    is_polymer_protein,
    make_temperal_input_pdb,
    mutate,
    refresh_all_selections,
)

TEST_DATA = os.path.dirname(__file__)
TEST_DATA_DIR = os.path.join(TEST_DATA, 'testdata')
TEST_DATA_RES = os.path.join(TEST_DATA, 'testres')


molecule = '1nww'
chain_id = 'A'
sequence = 'XXXXIEQPRWASKDSAAGAASTPDEKIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'
hetatm = 'HPN'


class TestMutant(absltest.TestCase):
    def setUp(self):
        self.mutant_info = [
            {'chain_id': 'A', 'position': 10, 'wt_res': 'P', 'mut_res': 'L'},
            {'chain_id': 'A', 'position': 20, 'wt_res': 'S', 'mut_res': 'T'},
        ]
        self.mutant_score = 0.95
        self.mutant_obj = Mutant(self.mutant_info, self.mutant_score)

    def test_mutant_info(self):
        self.assertEqual(self.mutant_obj.get_mutant_info(), self.mutant_info)

    def test_mutant_score(self):
        self.assertEqual(self.mutant_obj.get_mutant_score(), self.mutant_score)

    def test_set_mutant_score(self):
        new_score = 0.85
        self.mutant_obj.set_mutant_score(new_score)
        self.assertEqual(self.mutant_obj.get_mutant_score(), new_score)

    def test_set_mutant_description(self):
        new_description = "New mutant description"
        self.mutant_obj.set_mutant_description(new_description)
        self.assertEqual(
            self.mutant_obj.get_mutant_description(), new_description
        )

    def test_mutant_id(self):
        expected_id = 'AP10L_AS20T_0.95'
        self.assertEqual(self.mutant_obj.get_mutant_id(), expected_id)

    def test_short_mutant_id(self):
        self.mutant_obj.mutant_info = [
            {'chain_id': 'A', 'position': 1, 'wt_res': 'P', 'mut_res': 'L'}
        ]
        expected_id = 'AP1L_0.95'
        self.assertEqual(self.mutant_obj.get_short_mutant_id(), expected_id)

    def test_mutant_sequence(self):
        self.mutant_obj.wt_sequence = 'MABCDEFGHPJKLMNOHHHSHHHQCEV'
        expected_sequence = 'MABCDEFGHLJKLMNOHHHTHHHQCEV'
        self.assertEqual(
            self.mutant_obj.get_mutant_sequence(), expected_sequence
        )

    def test_wt_score(self):
        self.mutant_obj.set_wt_score(5.0)
        self.assertEqual(self.mutant_obj.get_wt_score(), 5.0)

    def test_invalid_mutant_sequence(self):
        self.mutant_obj.wt_sequence = 'ABC'
        with self.assertRaises(ValueError):
            self.mutant_obj.get_mutant_sequence()

    def test_mutant_sequence_mismatch(self):
        self.mutant_obj.wt_sequence = 'MABCDEFGHIJKLMNO'
        self.mutant_obj.mutant_info = [
            {'chain_id': 'A', 'position': 10, 'wt_res': 'Q', 'mut_res': 'L'}
        ]
        with self.assertRaises(ValueError):
            self.mutant_obj.get_mutant_sequence()

    def test_mutant_sequence_short(self):
        self.mutant_obj.wt_sequence = 'MABCDEFGHIJKLMNO'
        self.mutant_obj.mutant_info = [
            {'chain_id': 'A', 'position': 30, 'wt_res': 'Q', 'mut_res': 'L'}
        ]
        with self.assertRaises(ValueError):
            self.mutant_obj.get_mutant_sequence()


class TestMutantTree(absltest.TestCase):
    def setUp(self):
        # Creating mock Mutant objects with necessary kwargs
        mutant1 = Mutant(mutant_info=[], mutant_score=0.5)
        mutant2 = Mutant(mutant_info=[], mutant_score=0.8)
        mutant3 = Mutant(mutant_info=[], mutant_score=0.3)

        self.mutant_tree = {
            'branch1': {'mutant1': mutant1, 'mutant2': mutant2},
            'branch2': {'mutant3': mutant3},
        }
        self.mutant_tree_obj = MutantTree(self.mutant_tree)

    def test_init_mutant_tree(self):
        self.assertEqual(self.mutant_tree_obj.mutant_tree, self.mutant_tree)

    def test_refresh_mutants(self):
        self.mutant_tree_obj.refresh_mutants()
        self.assertEqual(
            self.mutant_tree_obj.all_mutant_branch_ids, ['branch1', 'branch2']
        )
        self.assertFalse(self.mutant_tree_obj.empty)

    def test_get_branch_index(self):
        index = self.mutant_tree_obj.get_branch_index('branch1')
        self.assertEqual(index, 0)

    def test_get_a_branch(self):
        branch = self.mutant_tree_obj.get_a_branch('branch2')
        self.assertEqual(len(branch), 1)
        self.assertIn('mutant3', branch)

    def test_search_a_branch(self):
        matching_branches = self.mutant_tree_obj.search_a_branch('branch')
        self.assertEqual(len(matching_branches), 2)

    def test_get_mutant_index_in_branch(self):
        index = self.mutant_tree_obj.get_mutant_index_in_branch(
            'branch1', 'mutant2'
        )
        self.assertEqual(index, 1)

    def test_get_mutant_index_in_all_mutants(self):
        index = self.mutant_tree_obj.get_mutant_index_in_all_mutants('mutant3')
        self.assertEqual(index, 2)

    def test_is_the_mutant_the_last_in_branch(self):
        result = self.mutant_tree_obj.is_the_mutant_the_last_in_branch(
            'branch1', 'mutant2'
        )
        self.assertTrue(result)

    def test_is_this_branch_empty(self):
        result = self.mutant_tree_obj.is_this_branch_empty('branch2')
        self.assertFalse(result)

    def test_initialize_current_branch(self):
        self.mutant_tree_obj.current_branch_id = ''
        self.mutant_tree_obj.initialize_current_branch()
        self.assertNotEqual(self.mutant_tree_obj.current_branch_id, '')

    def test_extend_tree_with_new_branches(self):
        new_branches = {
            'branch3': {'mutant4': Mutant(mutant_info=[], mutant_score=0.6)}
        }
        self.mutant_tree_obj.extend_tree_with_new_branches(new_branches)
        self.assertIn('branch3', self.mutant_tree_obj.all_mutant_branch_ids)

    def test_add_mutant_to_branch(self):
        self.mutant_tree_obj.add_mutant_to_branch(
            'branch1', 'mutant3', Mutant(mutant_info=[], mutant_score=0.4)
        )
        self.assertIn('mutant3', self.mutant_tree_obj.mutant_tree['branch1'])

    def test_remove_mutant_from_branch(self):
        self.mutant_tree_obj.remove_mutant_from_branch('branch1', 'mutant1')
        self.assertNotIn(
            'mutant1', self.mutant_tree_obj.mutant_tree['branch1']
        )

    def test_create_mutant_tree_from_list(self):
        new_mutant_ids = ['mutant1', 'mutant3']
        new_tree = self.mutant_tree_obj.create_mutant_tree_from_list(
            new_mutant_ids
        )
        self.assertIsInstance(new_tree, MutantTree)
        self.assertEqual(len(new_tree.all_mutant_branch_ids), 2)

    def test_jump_to_the_best_mutant_in_branch(self):
        self.mutant_tree_obj.jump_to_the_best_mutant_in_branch('branch1')
        self.assertIsNotNone(self.mutant_tree_obj.current_mutant_id)

    def test_walk_the_mutants(self):
        self.mutant_tree_obj.walk_the_mutants()
        self.assertNotEqual(self.mutant_tree_obj.current_branch_id, '')

    def test_jump_to_branch(self):
        self.mutant_tree_obj.jump_to_branch('branch2')
        self.assertEqual(self.mutant_tree_obj.current_branch_id, 'branch2')

    def test_list_mutants(self):
        mutants_list = self.mutant_tree_obj.list_mutants()
        self.assertIsNotNone(mutants_list)
        self.assertIsInstance(mutants_list, list)

    def test_diff_tree_from(self):
        other_tree = MutantTree(
            {'branch2': {'mutant3': Mutant(mutant_info=[], mutant_score=0.3)}}
        )
        diff_tree = self.mutant_tree_obj.diff_tree_from(other_tree)
        self.assertIsInstance(diff_tree, MutantTree)
        self.assertEqual(len(diff_tree.all_mutant_branch_ids), 1)


class TestPSSMGremlinCalculator(absltest.TestCase):
    def setUp(self):
        self.calculator = PSSMGremlinCalculator()
        # Mock QLineEdit objects
        lineEdit_url = MagicMock(text=lambda: 'https://revodesign.yaoyy.moe/')
        lineEdit_user = MagicMock(text=lambda: os.environ['REVODESIGN_USERS'])
        print(f'user: { os.environ["REVODESIGN_USERS"]}')
        
        lineEdit_password = MagicMock(text=lambda:  os.environ['REVODESIGN_SERVER_PASS'])

        self.calculator.setup_url(
            lineEdit_url, lineEdit_user, lineEdit_password
        )

        # Mock working_directory to a temporary directory
        tmp_dir = TEST_DATA_RES
        random.seed(42)
        self.calculator.setup_calculator(tmp_dir, molecule, chain_id, random.sample(sequence,len(sequence)))

    def tearDown(self):
        if os.path.exists(self.calculator.temp_file_path):
            os.remove(self.calculator.temp_file_path)

    def test_setup_url(self):
        self.assertEqual(self.calculator.url, 'https://revodesign.yaoyy.moe/')
        self.assertIsNotNone(self.calculator.auth)

    def test_setup_calculator(self):
        self.assertTrue(os.path.exists(self.calculator.temp_file_path))

    def test_submit_fasta_file(self):
        fasta_file_path = os.path.join(
            TEST_DATA_RES, f'{molecule}_{chain_id}.fasta'
        )
        result = self.calculator.submit_fasta_file(fasta_file_path)

        self.assertEqual(result.status_code, 202)

        md5sum = self.calculator.md5sum
        result = self.calculator.cancel_job(md5sum)

        self.assertIn(result.status_code, [202, 404, 200])


class TestPymolUtils(absltest.TestCase):
    def setUp(self):
        try:
            cmd.fetch(molecule)
            cmd.remove('c. B')
            cmd.remove('r. hoh or r. MES')
        except CmdException:
            pass

    def test_is_empty_session(self):
        self.assertFalse(is_empty_session())

    def test_is_hidden_object(self):
        self.assertFalse(is_hidden_object(selection=molecule))

    def test_is_polymer_protein(self):
        self.assertTrue(is_polymer_protein(sele=molecule))

    def test_find_small_molecules_in_protein(self):
        self.assertIn(hetatm, find_small_molecules_in_protein(sele=molecule))

    def test_find_design_molecules(self):
        self.assertIn(molecule, find_design_molecules())

    def test_find_all_protein_chain_ids_in_protein(self):
        self.assertIn(
            chain_id, find_all_protein_chain_ids_in_protein(sele=molecule)
        )

    def test_is_distal_residue_pair(self):
        self.assertTrue(
            is_distal_residue_pair(
                molecule=molecule,
                chain_id=chain_id,
                resi_1=137,
                resi_2=45,
                minimal_distance=10,
                use_sidechain_angle=1,
            )
        )
        self.assertFalse(
            is_distal_residue_pair(
                molecule=molecule,
                chain_id=chain_id,
                resi_1=137,
                resi_2=138,
                minimal_distance=10,
                use_sidechain_angle=1,
            )
        )
        self.assertTrue(
            is_distal_residue_pair(
                molecule=molecule,
                chain_id=chain_id,
                resi_1=8,
                resi_2=141,
                minimal_distance=20,
                use_sidechain_angle=1,
            )
        )
        self.assertFalse(
            is_distal_residue_pair(
                molecule=molecule,
                chain_id=chain_id,
                resi_1=8,
                resi_2=141,
                minimal_distance=60,
                use_sidechain_angle=1,
            )
        )

        self.assertTrue(
            is_distal_residue_pair(
                molecule=molecule,
                chain_id=chain_id,
                resi_1=104,
                resi_2=98,
                minimal_distance=20,
                use_sidechain_angle=1,
            )
        )
        self.assertFalse(
            is_distal_residue_pair(
                molecule=molecule,
                chain_id=chain_id,
                resi_1=104,
                resi_2=98,
                minimal_distance=20,
                use_sidechain_angle=0,
            )
        )

    def test_get_molecule_sequence(self):
        self.assertEqual(
            get_molecule_sequence(
                molecule=molecule, chain_id=chain_id, keep_missing=True
            ),
            sequence,
        )

    def test_refresh_all_selections(self):
        cmd.select('test', 'byres hetatm around 4')
        self.assertIn('test', refresh_all_selections())

    def test_is_a_REvoDesign_session(self):
        self.assertFalse(is_a_REvoDesign_session())
        cmd.fetch('5i9f')
        cmd.group('test_group', '5i9f')
        self.assertTrue(is_a_REvoDesign_session())

    def test_make_temperal_input_pdb(self):
        self.assertTrue(
            os.path.exists(
                make_temperal_input_pdb(
                    molecule=molecule, wd=TEST_DATA_RES, reload=False
                )
            )
        )

    def test_mutate(self):
        cmd.create(f'copy_{molecule}', molecule)
        mutate(
            molecule=f'copy_{molecule}', chain=chain_id, resi=45, target='ALA'
        )
        mutant_seq = get_molecule_sequence(
            molecule=f'copy_{molecule}', chain_id=chain_id, keep_missing=True
        )
        expected_sequence = 'XXXXIEQPRWASKDSAAGAASTPDEKIVLEFMDALTSNDAAKLIAYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'
        self.assertNotEqual(mutant_seq, sequence)
        self.assertEqual(mutant_seq, expected_sequence)

        cmd.delete(f'copy_{molecule}')

    def test_any_posision_has_been_selected(self):
        cmd.select('sele', 'i. 45')
        self.assertTrue(any_posision_has_been_selected())
        cmd.disable('sele')
        self.assertFalse(any_posision_has_been_selected())
    
    def tearDown(self):
        cmd.reinitialize()


class TestMutantTools(absltest.TestCase):
    def setUp(self):
        try:
            cmd.fetch(molecule)
            cmd.remove('c. B')
            cmd.remove('r. hoh or r. MES')
        except CmdException:
            pass
    def test_extract_mutants_from_mutant_id_full(self):
        mutant_string='AI5R_AK26T_0.4567'
        expected_sequence='XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'

        _, _o=extract_mutants_from_mutant_id(mutant_string=mutant_string)
        self.assertIsInstance(_o,Mutant)
        self.assertEqual(_o.get_mutant_score(), 0.4567)
        _o.wt_sequence=sequence
        
        self.assertEqual(_o.get_mutant_sequence(), expected_sequence)
        
    def test_extract_mutants_from_mutant_id_reduced(self):
        mutant_string='I5R_K26T_0.4567'
        expected_sequence='XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'

        _, _o=extract_mutants_from_mutant_id(mutant_string=mutant_string,chain_id=chain_id)
        self.assertIsInstance(_o,Mutant)
        self.assertEqual(_o.get_mutant_score(), 0.4567)
        _o.wt_sequence=sequence
        
        self.assertEqual(_o.get_mutant_sequence(), expected_sequence)
        
    def test_extract_mutants_from_mutant_id_fuzzy(self):
        mutant_string='5R_26T_0.4567'
        expected_sequence='XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'

        _, _o=extract_mutants_from_mutant_id(mutant_string=mutant_string,chain_id=chain_id,sequence=sequence)
        self.assertIsInstance(_o,Mutant)
        self.assertEqual(_o.get_mutant_score(), 0.4567)
        _o.wt_sequence=sequence
        
        self.assertEqual(_o.get_mutant_sequence(), expected_sequence)
        
    def test_extract_mutants_from_mutant_id_invalid(self):
        mutant_string='5R_26T_0.4567'

        _, _o=extract_mutants_from_mutant_id(mutant_string=mutant_string)
        self.assertIsNone(_o,)

    def test_extract_mutant_score_from_string(self):
        mutant_string='I5R_K26T_0.4567'
        self.assertEqual(extract_mutant_score_from_string(mutant_string=mutant_string), 0.4567)

    def test_extract_mutant_from_sequences(self):
        mutant_sequence='XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'
        _o1=extract_mutant_from_sequences(wt_sequence=sequence,mutant_sequence=mutant_sequence,chain_id=chain_id,fix_missing=False)
        _o2=extract_mutant_from_sequences(wt_sequence=sequence,mutant_sequence=mutant_sequence.replace('X', ''),chain_id=chain_id,fix_missing=True)

        self.assertEqual(_o1.get_mutant_info(), _o2.get_mutant_info())

    def test_shorter_range_continuous_sequence(self):
        input_list = [395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409]
        expected_expression='395-409'
        result = shorter_range(input_list)
        self.assertEqual(result,expected_expression)

    def test_shorter_range_discontinuous_sequence(self):
        input_list = [395, 396, 397, 398, 399, 401, 402, 403, 404, 405, 406, 407, 408, 409]
        expected_expression='395-399+401-409'
        result = shorter_range(input_list)
        self.assertEqual(result,expected_expression)

    def test_expand_range_continuous_sequence(self):
        shortened_str = "395-409"
        expected_list=[395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409]
        result = expand_range(shortened_str)
        self.assertEqual(result, expected_list)

    def test_expand_range_discontinuous_sequence(self):
        shortened_str = "395-401+403-409"
        expected_list=[395, 396, 397, 398, 399, 400, 401, 403, 404, 405, 406, 407, 408, 409]
        result = expand_range(shortened_str)
        self.assertEqual(result, expected_list)

    def tearDown(self):
        cmd.reinitialize()



if __name__ == '__main__':
    absltest.main()
