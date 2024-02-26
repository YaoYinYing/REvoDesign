import os
import shutil
import glob
import random
from pymol import cmd, util, CmdException
from absl.testing import absltest
from unittest.mock import Mock
from unittest.mock import MagicMock
from unittest.mock import patch

from omegaconf import DictConfig, OmegaConf

import logging as python_logging
import json
import datetime as dt

from typing import List, Dict, Union, Any
from dataclasses import dataclass
from collections.abc import MutableMapping
from hashlib import sha256
from REvoDesign.application.ui_driver import Widget2ConfigMapper, Widget2Widget
from REvoDesign.clients.PSSM_GREMLIN_client import PSSMGremlinCalculator

from REvoDesign.structure.PocketSearcher import PocketSearcher
from REvoDesign.structure.SurfaceFinder import SurfaceFinder

from REvoDesign.common.Mutant import Mutant
from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.tools.logger import (
    REvoDesignLogFormatter,
    setup_logger_level,
    logger_level,
)
from REvoDesign.tools.mutant_tools import (
    expand_range,
    extract_mutant_from_sequences,
    extract_mutant_score_from_string,
    extract_mutants_from_mutant_id,
    shorter_range,
)

from REvoDesign.tools.post_installed import (
    REVODESIGN_CONFIG_FILE,
    ConfigConverter,
    reload_config_file,
    save_configuration,
    set_REvoDesign_config_file,
    set_cache_dir,
    WITH_DEPENDENCIES
)
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
gremlin_mrf_pkl_url = 'https://raw.githubusercontent.com/YaoYinYing/REvoDesign-test-data/main/1nww_A.i90c75_aln.GREMLIN.mrf.pkl'
gremlin_mrf_pkl_md5sum = '201517130bbae68428e855c97dabe98a'


class TestREvoDesignLogFormatter(absltest.TestCase):
    """
    Tests for the REvoDesignLogFormatter to ensure it formats log records as expected.
    """

    def setUp(self):
        # Set up a minimal logging record
        self.record = python_logging.LogRecord(
            name='test',
            level=python_logging.INFO,
            pathname=__file__,
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None,
        )
        self.record.created = (
            1609459200.0  # Equivalent to 2021-01-01 00:00:00 UTC
        )
        self.formatter = REvoDesignLogFormatter()
        super().setUp()

    def test_format(self):
        """
        Test if the log formatter correctly formats a log record into JSON.
        """
        expected_timestamp = dt.datetime.fromtimestamp(
            self.record.created, tz=dt.timezone.utc
        ).isoformat()
        formatted_message = self.formatter.format(self.record)
        message_dict = json.loads(formatted_message)

        # Ensure the message contains at least the basic expected keys
        self.assertIn('message', message_dict)
        self.assertIn('timestamp', message_dict)
        self.assertEqual(message_dict['message'], 'Test message')
        self.assertEqual(message_dict['timestamp'], expected_timestamp)


class TestLoggingSetup(absltest.TestCase):
    """
    Tests for logging setup functions to ensure they configure the logging system as expected.
    """

    def test_setup_logger_level(self):
        """
        Test if the setup_logger_level function correctly maps string levels to logging constants.
        """
        for level_str, expected_level in logger_level.items():
            actual_level = setup_logger_level(level_str)
            self.assertEqual(
                actual_level,
                expected_level,
                f"Logger level mapping failed for {level_str}",
            )

    def test_setup_logging_from_dictconfig(self):
        """
        Test if setup_logging_from_dictconfig properly sets up logging handlers and formatters based on a DictConfig.
        """
        # Setup a minimal DictConfig for testing
        log_config = OmegaConf.create(
            {
                "handlers": {
                    "stdout": {"level": "INFO"},
                    "stderr": {"level": "ERROR"},
                    "file": {
                        "filename": "test.log",
                        "maxBytes": 1024 * 1024,
                        "backupCount": 3,
                        "level": "DEBUG",
                    },
                    "notebook": {
                        "filename": "notebook.log",
                        "maxBytes": 1024 * 1024,
                        "backupCount": 3,
                        "level": "DEBUG",
                    },
                },
                "formatters": {
                    "simple": {
                        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    },
                    "json": {
                        "fmt_keys": {"message": "msg", "timestamp": "asctime"}
                    },
                },
                "loggers": {
                    "root": {"level": "DEBUG"},
                },
            }
        )


class TestWidget2ConfigMapper(absltest.TestCase):
    """
    Tests for the Widget2ConfigMapper class to ensure that UI elements are correctly mapped to configuration settings.
    """

    def setUp(self):
        # Mock the UI elements to simulate the real UI components
        self.mock_ui = self._create_mock_ui()
        self.mapper = Widget2ConfigMapper(self.mock_ui)
        super().setUp()

    def _create_mock_ui(self) -> Dict[str, Any]:
        """
        Creates a mock UI with simulated UI components.

        Returns:
            A dictionary representing mock UI components.
        """
        # This mock should mirror the structure expected by Widget2ConfigMapper
        # For simplicity, we use dummy objects or simple placeholders
        return {
            "comboBox_cmap": object(),
            "lineEdit_pssm_gremlin_url": object(),
            # Add other UI elements as needed
        }


class TestPocketSearcher(absltest.TestCase):
    """
    Tests for the PocketSearcher class to ensure it processes surface residues as expected.
    """

    def setUp(self):
        self.p450_pdb_code = '1SUO'
        try:
            cmd.fetch(self.p450_pdb_code)
            cmd.remove('r. hoh or r. MES')
        except CmdException:
            pass
        self.input_pdb_file = make_temperal_input_pdb(
            molecule=self.p450_pdb_code, reload=False
        )
        self.chain_id = 'A'
        self.cofactor = 'HEM'
        self.cofactor_radius = 7
        self.ligand = 'CPZ'
        self.ligand_radius = 8

        self.expected_moelecule = self.p450_pdb_code

        self.expected_pocket_pse = os.path.join(
            'pocket_searcher', f'{self.p450_pdb_code}_pocket.pze'
        )
        self.expected_pocket_txts = f"{self.expected_moelecule}_*_residues.txt"

        os.makedirs(os.path.dirname(self.expected_pocket_pse), exist_ok=True)

    def test_search_pockets(self):
        """
        Test if the search_pockets method correctly identifies pockets and saves the records.
        """
        pocket_seacher = PocketSearcher(
            input_pse=self.input_pdb_file,
            output_pse=self.expected_pocket_pse,
            molecule=self.expected_moelecule,
            chain_id=self.chain_id,
            ligand=self.ligand,
            cofactor=self.cofactor,
            cofactor_radius = self.cofactor_radius,
            ligand_radius = self.ligand_radius,
            save_dir = os.path.dirname(self.expected_pocket_pse)

        )


        pocket_seacher.search_pockets()
        self.assertTrue(os.path.isfile(self.expected_pocket_pse))
        pocket_files = glob.glob(
            os.path.join(
                os.path.dirname(self.expected_pocket_pse),
                self.expected_pocket_txts,
            )
        )
        self.assertEqual(len(pocket_files), 4)


class TestSurfaceFinder(absltest.TestCase):
    """
    Tests for the SurfaceFinder class to ensure it processes surface residues as expected.
    """

    def setUp(self):
        self.p450_pdb_code = '1SUO'
        try:
            cmd.fetch(self.p450_pdb_code)
            cmd.remove('r. hoh or r. MES')
        except CmdException:
            pass
        self.input_pdb_file = make_temperal_input_pdb(
            molecule=self.p450_pdb_code, reload=False
        )
        self.chain_id = 'A'
        self.expected_surface_pse = os.path.join(
            'surface_finder', f'{self.p450_pdb_code}_surface.pze'
        )

        os.makedirs(os.path.dirname(self.expected_surface_pse), exist_ok=True)
        self.expected_moelecule = self.p450_pdb_code
        self.cutoff = 15

        self.expected_residue_filename = os.path.join(
            'surface_residue_records',
            f'{self.expected_moelecule}_residues_cutoff_{self.cutoff:.1f}.txt',
        )

    def test_process_surface_residues(self):
        surface_finder = SurfaceFinder(
            input_pse=self.input_pdb_file,
            output_pse=self.expected_surface_pse,
            molecule=self.expected_moelecule,
            chain_id=self.chain_id,
            cutoff = self.cutoff,
            do_show_surf_CA=True
        )
        surface_finder.process_surface_residues()
        self.assertTrue(os.path.isfile(self.expected_surface_pse))
        self.assertTrue(os.path.isfile(self.expected_residue_filename))


class TestWidget2Widget(absltest.TestCase):
    """
    Tests for the Widget2Widget class to ensure that related widget mappings are correctly handled.
    """

    def setUp(self):
        self.widget2widget = Widget2Widget()
        super().setUp()

    def test_sidechain_solver2model_mapping(self):
        """
        Test if the mapping from sidechain solver to its models is correctly established.
        """
        # Example test for PIPPack solver
        expected_models = [
            'ui.config.sidechain_solver.pippack.model_names.group',
            'ui.config.sidechain_solver.pippack.model_names.default',
        ]
        actual_models = self.widget2widget.sidechain_solver2model['PIPPack']
        self.assertEqual(
            expected_models,
            actual_models,
            "The mapping for PIPPack models is incorrect.",
        )


class TestREvoDesignConfigFile(absltest.TestCase):
    """
    Tests for the REvoDesign configuration file setting and related functionalities.
    """

    def setUp(self):
        # Setup necessary variables for the test
        self.expected_default_storage_path = os.path.expanduser(
            '~/.REvoDesign/'
        )
        self.expected_config_dir = os.path.join(
            self.expected_default_storage_path, 'config'
        )
        self.expected_main_config_file = os.path.join(
            self.expected_config_dir, 'global_config.yaml'
        )
        self.expected_global_cfg = reload_config_file()
        self.expected_pippack_cfg = reload_config_file(
            'sidechain-solver/pippack'
        )['sidechain-solver']
        super().setUp()

    def test_set_REvoDesign_config_file(self):
        """
        Test if the set_REvoDesign_config_file function creates the config directory and copies the configuration templates correctly.
        """
        # Mock the os.path and shutil functionalities to not actually perform file system operations

        # Test the function's output
        main_config_file = set_REvoDesign_config_file()
        self.assertEqual(main_config_file, self.expected_main_config_file)

        # Further tests can mock file system effects and check for the expected behavior

    def test_reload_config_file(self):
        """
        Test if the reload_config_file function correctly reloads the configuration.
        """
        # This test depends on the actual implementation details of hydra.compose
        # Mocking or setting up a test environment for hydra might be necessary

        self.assertTrue(isinstance(self.expected_global_cfg, DictConfig))
        self.assertEqual(
            self.expected_global_cfg.ui.header_panel.cmap.default, 'bwr_r'
        )

    def test_save_configuration(self):
        """
        Test if the save_configuration function saves the configuration correctly.
        """
        # Setup a temporary configuration for testing
        test_cfg = OmegaConf.create({"test_key": "test_value"})

        # Save the configuration
        save_configuration(test_cfg, "test_config")

        # Check if the file was saved correctly
        cfg_save_dir = os.path.dirname(REVODESIGN_CONFIG_FILE)
        cfg_save_fp = os.path.join(cfg_save_dir, 'test_config.yaml')

        # Assert the file exists and contains the expected content
        self.assertTrue(os.path.exists(cfg_save_fp))
        with open(cfg_save_fp, 'r') as f:
            loaded_cfg = OmegaConf.load(f)
            self.assertEqual(loaded_cfg.test_key, "test_value")

    def test_set_cache_dir(self):
        """
        Test the behavior of set_cache_dir function under various configuration conditions.
        """
        # This test will require to mock or manipulate the DictConfig returned by reload_config_file to simulate different scenarios
        new_customized_cache_dir = os.path.abspath(
            os.path.join('.', 'customized_revodesign_cache_dir')
        )
        self.expected_global_cfg.cache_dir.under_home_dir = False
        self.expected_global_cfg.cache_dir.customized = (
            new_customized_cache_dir
        )
        save_configuration(self.expected_global_cfg)
        new_cfg = reload_config_file()
        expected_new_cache_dir = set_cache_dir()
        self.assertEqual(
            new_customized_cache_dir, new_cfg.cache_dir.customized
        )
        self.assertEqual(new_customized_cache_dir, expected_new_cache_dir)

        self.expected_global_cfg.cache_dir.under_home_dir = True
        self.expected_global_cfg.cache_dir.customized = ''
        save_configuration(self.expected_global_cfg)
        expected_old_cache_dir = set_cache_dir()
        self.assertEqual(
            expected_old_cache_dir, self.expected_default_storage_path
        )


class TestConfigConverter(absltest.TestCase):
    """
    Tests for the ConfigConverter utility class.
    """

    def test_convert_valid_input(self):
        """
        Test converting a valid DictConfig to a Python dictionary.
        """
        dict_config = OmegaConf.create(
            {"key": "value", "nested": {"nkey": "nvalue"}}
        )
        expected_output = {"key": "value", "nested": {"nkey": "nvalue"}}
        output = ConfigConverter.convert(dict_config)
        self.assertEqual(output, expected_output)

    def test_convert_raises_with_invalid_input(self):
        """
        Test that converting a non-DictConfig object raises a ValueError.
        """
        with self.assertRaises(ValueError):
            ConfigConverter.convert("not a DictConfig")

    def test_recursive_conversion(self):
        """
        Test the recursive conversion of nested DictConfig objects.
        """
        nested_dict_config = OmegaConf.create(
            {
                "key": "value",
                "nested": {"nkey": "nvalue", "nnested": {"nnkey": "nnvalue"}},
            }
        )
        expected_output = {
            "key": "value",
            "nested": {"nkey": "nvalue", "nnested": {"nnkey": "nnvalue"}},
        }
        output = ConfigConverter.convert(nested_dict_config)
        self.assertEqual(output, expected_output)


class TestMutant(absltest.TestCase):
    def setUp(self):
        super().setUp()  # Call the superclass setup method
        self.mutant_info = [
            {'chain_id': 'A', 'position': 10, 'wt_res': 'P', 'mut_res': 'L'},
            {'chain_id': 'A', 'position': 20, 'wt_res': 'S', 'mut_res': 'T'},
        ]
        self.mutant_score = 0.95
        self.mutant_obj = Mutant(self.mutant_info, self.mutant_score)
        self.mutant_obj.wt_sequences = {'A': 'MABCDEFGHPJKLMNOHHHSHHHQCEV'}

    def test_mutant_info(self):
        self.assertEqual(self.mutant_obj.mutant_info, self.mutant_info)

    def test_mutant_score(self):
        self.assertEqual(self.mutant_obj.mutant_score, self.mutant_score)

    def test_set_mutant_score(self):
        new_score = 0.85
        self.mutant_obj.mutant_score = new_score
        self.assertEqual(self.mutant_obj.mutant_score, new_score)

    def test_set_mutant_description(self):
        new_description = "New mutant description"
        self.mutant_obj._mutant_description = new_description
        self.assertEqual(self.mutant_obj._mutant_description, new_description)

    def test_mutant_id(self):
        expected_raw_id = 'AP10L_AS20T'
        expected_id = 'AP10L_AS20T_0.95'
        self.assertEqual(self.mutant_obj.full_mutant_id, expected_raw_id)
        self.assertEqual(self.mutant_obj.short_mutant_id, expected_id)

    def test_short_mutant_id(self):
        self.mutant_obj.mutant_info = [
            {'chain_id': 'A', 'position': 1, 'wt_res': 'P', 'mut_res': 'L'}
        ]
        expected_id = 'AP1L_0.95'  # This might change based on hashing
        self.assertTrue(
            self.mutant_obj.short_mutant_id.startswith(
                expected_id.split('_')[0]
            )
        )

    def test_mutant_sequence(self):
        expected_sequence = 'MABCDEFGHLJKLMNOHHHTHHHQCEV'
        self.assertEqual(
            self.mutant_obj.get_mutant_sequence_single_chain(chain_id='A'),
            expected_sequence,
        )

    def test_wt_score(self):
        self.mutant_obj.wt_score = 5.0
        self.assertEqual(self.mutant_obj.wt_score, 5.0)

    def test_invalid_mutant_sequence(self):
        self.mutant_obj.wt_sequences = {'A': 'ABC'}
        with self.assertRaises(ValueError):
            self.mutant_obj.get_mutant_sequence_single_chain(chain_id='A')

    def test_mutant_sequence_mismatch(self):
        self.mutant_obj.wt_sequences = {'A': 'MABCDEFGHIJKLMNO'}
        self.mutant_obj.mutant_info = [
            {'chain_id': 'A', 'position': 10, 'wt_res': 'Q', 'mut_res': 'L'}
        ]
        with self.assertRaises(ValueError):
            self.mutant_obj.get_mutant_sequence_single_chain(chain_id='A')

    def test_mutant_sequence_short(self):
        self.mutant_obj.wt_sequences = {'A': 'MABCDEFGHIJKLMNO'}
        self.mutant_obj.mutant_info = [
            {'chain_id': 'A', 'position': 30, 'wt_res': 'Q', 'mut_res': 'L'}
        ]
        with self.assertRaises(ValueError):
            self.mutant_obj.get_mutant_sequence_single_chain(chain_id='A')


class TestMutantTree(absltest.TestCase):
    def setUp(self):
        # Creating mock Mutant objects with necessary kwargs
        mutant1 = Mutant(mutant_info=[])
        mutant1.mutant_score = 0.5
        mutant2 = Mutant(mutant_info=[])
        mutant2.mutant_score = 0.8
        mutant3 = Mutant(mutant_info=[])
        mutant3.mutant_score = 0.3

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
            'branch3': {'mutant4': Mutant(mutant_info=[], _mutant_score=0.6)}
        }
        self.mutant_tree_obj.update_tree_with_new_branches(new_branches)
        self.assertIn('branch3', self.mutant_tree_obj.all_mutant_branch_ids)

    def test_add_mutant_to_branch(self):
        self.mutant_tree_obj.add_mutant_to_branch(
            'branch1', 'mutant3', Mutant(mutant_info=[], _mutant_score=0.4)
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
            {'branch2': {'mutant3': Mutant(mutant_info=[], _mutant_score=0.3)}}
        )
        diff_tree = self.mutant_tree_obj.diff_tree_from(other_tree)
        self.assertIsInstance(diff_tree, MutantTree)
        self.assertEqual(len(diff_tree.all_mutant_branch_ids), 1)


class TestPSSMGremlinCalculator(absltest.TestCase):
    def setUp(self):
        from requests.auth import HTTPBasicAuth
        self.calculator = PSSMGremlinCalculator()
        user = os.environ['REVODESIGN_USERS']
        password = os.environ['REVODESIGN_SERVER_PASS']

        self.calculator.url='https://revodesign.yaoyy.moe/'
        self.calculator.user=user
        self.calculator.password=password
        self.calculator.auth = HTTPBasicAuth(
                self.calculator.user,
                self.calculator.password
            )

        # Mock working_directory to a temporary directory
        tmp_dir = TEST_DATA_RES
        random.seed(42)
        self.calculator.setup_calculator(
            tmp_dir,
            molecule,
            chain_id,
            ''.join(random.sample(sequence, len(sequence))),
        )

    def tearDown(self):
        if os.path.exists(self.calculator.temp_file_path):
            os.remove(self.calculator.temp_file_path)

    def test_setup_url(self):
        self.assertEqual(self.calculator.url, 'https://revodesign.yaoyy.moe/')
        self.assertIsNotNone(self.calculator.auth)
        self.assertEqual(self.calculator.user, os.environ['REVODESIGN_USERS'])
        self.assertEqual(
            self.calculator.password, os.environ['REVODESIGN_SERVER_PASS']
        )

    def test_setup_calculator(self):
        self.assertTrue(os.path.exists(self.calculator.temp_file_path))

    def test_submit_fasta_file(self):
        fasta_file_path = os.path.join(
            TEST_DATA_RES, f'{molecule}_{chain_id}.fasta'
        )
        result = self.calculator.submit_fasta_file(fasta_file_path)
        print(result.content)

        self.assertIn(result.status_code, [202, 404, 200, 403, 400,502])

        md5sum = self.calculator.md5sum
        result = self.calculator.cancel_job(md5sum)
        print(result.content)

        self.assertIn(result.status_code, [202, 404, 200, 403, 400, 502])


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
        cmd.enable('sele')
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
        mutant_string = 'AI5R_AK26T_0.4567'
        expected_sequence = 'XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'

        _o = extract_mutants_from_mutant_id(
            mutant_string=mutant_string, sequences={'A': sequence}
        )
        self.assertIsInstance(_o, Mutant)
        self.assertEqual(_o.mutant_score, 0.4567)

        self.assertEqual(
            _o.get_mutant_sequence_single_chain(chain_id='A'),
            expected_sequence,
        )

    def test_extract_mutants_from_mutant_id_reduced(self):
        mutant_string = 'I5R_K26T_0.4567'
        expected_sequence = 'XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'

        _o = extract_mutants_from_mutant_id(
            mutant_string=mutant_string, sequences={'A': sequence}
        )
        self.assertIsInstance(_o, Mutant)
        self.assertEqual(_o.mutant_score, 0.4567)

        self.assertEqual(
            _o.get_mutant_sequence_single_chain(chain_id='A'),
            expected_sequence,
        )

    def test_extract_mutants_from_mutant_id_fuzzy(self):
        mutant_string = '5R_26T_0.4567'
        expected_sequence = 'XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'

        _o = extract_mutants_from_mutant_id(
            mutant_string=mutant_string, sequences={'A': sequence}
        )
        self.assertIsInstance(_o, Mutant)
        self.assertEqual(_o.mutant_score, 0.4567)

        self.assertEqual(
            _o.get_mutant_sequence_single_chain(chain_id='A'),
            expected_sequence,
        )

    def test_extract_mutants_from_mutant_id_invalid(self):
        mutant_string = '5R_26T_0.4567'

        _o = extract_mutants_from_mutant_id(mutant_string=mutant_string)
        self.assertIs(_o.empty, True)

    def test_extract_mutant_score_from_string(self):
        mutant_string = 'I5R_K26T_0.4567'
        self.assertEqual(
            extract_mutant_score_from_string(mutant_string=mutant_string),
            0.4567,
        )

    def test_extract_mutant_from_sequences(self):
        mutant_sequence = 'XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'
        _o1 = extract_mutant_from_sequences(
            wt_sequence=sequence,
            mutant_sequence=mutant_sequence,
            chain_id=chain_id,
            fix_missing=False,
        )
        _o2 = extract_mutant_from_sequences(
            wt_sequence=sequence,
            mutant_sequence=mutant_sequence.replace('X', ''),
            chain_id=chain_id,
            fix_missing=True,
        )

        self.assertEqual(_o1.mutant_info, _o2.mutant_info)

    def test_shorter_range_continuous_sequence(self):
        input_list = [
            395,
            396,
            397,
            398,
            399,
            400,
            401,
            402,
            403,
            404,
            405,
            406,
            407,
            408,
            409,
        ]
        expected_expression = '395-409'
        result = shorter_range(input_list)
        self.assertEqual(result, expected_expression)

    def test_shorter_range_discontinuous_sequence(self):
        input_list = [
            395,
            396,
            397,
            398,
            399,
            401,
            402,
            403,
            404,
            405,
            406,
            407,
            408,
            409,
        ]
        expected_expression = '395-399+401-409'
        result = shorter_range(input_list)
        self.assertEqual(result, expected_expression)

    def test_expand_range_continuous_sequence(self):
        shortened_str = "395-409"
        expected_list = [
            395,
            396,
            397,
            398,
            399,
            400,
            401,
            402,
            403,
            404,
            405,
            406,
            407,
            408,
            409,
        ]
        result = expand_range(shortened_str)
        self.assertEqual(result, expected_list)

    def test_expand_range_discontinuous_sequence(self):
        shortened_str = "395-401+403-409"
        expected_list = [
            395,
            396,
            397,
            398,
            399,
            400,
            401,
            403,
            404,
            405,
            406,
            407,
            408,
            409,
        ]
        result = expand_range(shortened_str)
        self.assertEqual(result, expected_list)

    def tearDown(self):
        cmd.reinitialize()


class TestSidechainSolver(absltest.TestCase):
    def setUp(self):
        self.mutant_string = 'AI5R_AK26T_0.4567'
        self.expected_sequence = 'XXXXREQPRWASKDSAAGAASTPDETIVLEFMDALTSNDAAKLIEYFAEDTMYQNMPLPPAYGRDAVEQTLAGLFTVMMSIDAVETFHIGSSNGLLVYTERVDVLLRALPTGKSYNLSILGVFQLTEGKITGWRDYFDLREFEEAVDLP'
        self.mutant_obj = extract_mutants_from_mutant_id(
            mutant_string=self.mutant_string, sequences={'A': sequence}
        )
        try:
            cmd.fetch(molecule)
            cmd.remove('c. B')
            cmd.remove('r. hoh or r. MES')

        except CmdException:
            pass

        self.wt_pdb = make_temperal_input_pdb(
            molecule=molecule, reload=False, chain_id='A'
        )
        self.new_pdb_code = '1nww'

    def test_pymol_mutate(self):
        from REvoDesign.sidechain_solver.DunbrackRotamerLib import PyMOL_mutate

        mutate_runner = PyMOL_mutate(
            molecule=self.new_pdb_code, input_session=self.wt_pdb
        )
        mutate_pdb_path = mutate_runner.run_mutate(
            mutant_obj=self.mutant_obj, in_place=False
        )

        from Bio.PDB.PDBParser import PDBParser

        parser = PDBParser(PERMISSIVE=1)
        structure = parser.get_structure(self.mutant_string, mutate_pdb_path)
        mut_residue_1 = structure[0]["A"][5]
        mut_residue_2 = structure[0]["A"][26]
        self.assertEqual(mut_residue_1.get_resname(), 'ARG')
        self.assertEqual(mut_residue_2.get_resname(), 'THR')

    def test_dlpacker_mutate(self):
        if not WITH_DEPENDENCIES.DLPACKER:
            print('Skiping dlpacker tests..')
        from REvoDesign.sidechain_solver.DLPacker import DLPacker_worker

        mutate_runner = DLPacker_worker(pdb_file=self.wt_pdb)
        mutate_pdb_path = mutate_runner.run_mutate(mutant_obj=self.mutant_obj)

        from Bio.PDB.PDBParser import PDBParser

        parser = PDBParser(PERMISSIVE=1)
        structure = parser.get_structure(self.mutant_string, mutate_pdb_path)
        mut_residue_1 = structure[0]["A"][5]
        mut_residue_2 = structure[0]["A"][26]
        self.assertEqual(mut_residue_1.get_resname(), 'ARG')
        self.assertEqual(mut_residue_2.get_resname(), 'THR')

    def test_dlpacker_mutate_reconstruct_range(self):
        if not WITH_DEPENDENCIES.DLPACKER:
            print('Skiping dlpacker tests..')
        from REvoDesign.sidechain_solver.DLPacker import DLPacker_worker

        mutate_runner = DLPacker_worker(pdb_file=self.wt_pdb)
        mutate_pdb_path = mutate_runner.run_mutate(
            mutant_obj=self.mutant_obj, reconstruct_area_radius=5
        )

        from Bio.PDB.PDBParser import PDBParser

        parser = PDBParser(PERMISSIVE=1)
        structure = parser.get_structure(self.mutant_string, mutate_pdb_path)
        mut_residue_1 = structure[0]["A"][5]
        mut_residue_2 = structure[0]["A"][26]
        self.assertEqual(mut_residue_1.get_resname(), 'ARG')
        self.assertEqual(mut_residue_2.get_resname(), 'THR')

    def test_pippack_mutate(self):
        if not WITH_DEPENDENCIES.PIPPACK:
            print('Skiping pippack tests..')
        from REvoDesign.sidechain_solver.PIPPack import PIPPack_worker

        mutate_runner = PIPPack_worker(pdb_file=self.wt_pdb)
        mutate_pdb_path = mutate_runner.run_mutate(mutant_obj=self.mutant_obj)

        from Bio.PDB.PDBParser import PDBParser

        parser = PDBParser(PERMISSIVE=1)
        structure = parser.get_structure(self.mutant_string, mutate_pdb_path)
        mut_residue_1 = structure[0]["A"][5]
        mut_residue_2 = structure[0]["A"][26]
        self.assertEqual(mut_residue_1.get_resname(), 'ARG')
        self.assertEqual(mut_residue_2.get_resname(), 'THR')


if __name__ == '__main__':
    absltest.main()
