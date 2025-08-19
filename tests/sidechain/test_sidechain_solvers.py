import warnings
from unittest.mock import patch

import pytest
from pymol import cmd

from REvoDesign.bootstrap.set_config import ConfigConverter, reload_config_file
from REvoDesign.common.mutant import Mutant
from REvoDesign.sidechain.mutate_runner import (DLPacker_worker,
                                                MutateRelax_worker,
                                                PIPPack_worker, PyMOL_mutate)

WT_PDB = '../tests/data/3fap_hf3_A_short.pdb'
MUT_PDB = '../tests/data/3fap_hf3_A_RFD.pdb'
MOLECULE = '3fap_hf3_A_short'
MUTANTS: list[Mutant] = [Mutant(**m.__dict__) for m in Mutant.from_pdb(WT_PDB, [MUT_PDB])]
mutant_string = MUTANTS[0].full_mutant_id


class TestSidechainSolver:

    @pytest.mark.parametrize(
        'id, runner,init_kwargs', [
            # ['DLpacker', DLPacker_worker, {'pdb_file': WT_PDB}, ],
            # ['DLpacker-range', DLPacker_worker, {'pdb_file': WT_PDB, 'radius': 3.5}, ],
            ['PIPPack-model_1', PIPPack_worker, {'pdb_file': WT_PDB, 'use_model': "pippack_model_1"}],
            ['PIPPack-ensumble', PIPPack_worker, {'pdb_file': WT_PDB, }],
            ['PyMOL-mutate', PyMOL_mutate, {'molecule': MOLECULE, 'pdb_file': WT_PDB}],
        ]
    )
    def test_runner_mutate(self, id, runner, init_kwargs):
        if not runner.installed:
            pytest.skip(f"{runner.__name__} is not installed")

        cmd.load(WT_PDB)

        mutate_runner = runner(**init_kwargs)
        mutate_pdb_path = mutate_runner.run_mutate(mutant=MUTANTS[0])

        from Bio.PDB.PDBParser import PDBParser
        from Bio.PDB.Structure import Structure

        parser = PDBParser(PERMISSIVE=1)
        structure: Structure = parser.get_structure(
            MUTANTS[0].short_mutant_id, mutate_pdb_path
        )
        mut_residue_1 = structure[0]["A"][1]
        mut_residue_2 = structure[0]["A"][2]
        assert mut_residue_1.get_resname() == "GLY"
        assert mut_residue_2.get_resname() == "GLY"

    @pytest.mark.parametrize(
        'id, runner,init_kwargs', [
            ['MutateRelax_worker', MutateRelax_worker, {'pdb_file': WT_PDB}]
        ]
    )
    def test_runner_mutate_rosetta(self, id, runner, init_kwargs, test_node_hint):
        if not runner.installed:
            pytest.skip(f"{runner.__name__} is not installed")

        cmd.load(WT_PDB)
        from RosettaPy.node import node_picker
        
        # patch the app
        with patch('REvoDesign.sidechain.mutate_runner.RosettaMutateRelax.MutateRelax') as patched_app:

            # fetch node config according to node_hint
            node_config = ConfigConverter.convert(reload_config_file(
                f'rosetta-node/{test_node_hint}')['rosetta-node']['node_config'])
            
            # inject test node
            patched_app._node = node_picker(
                test_node_hint, **node_config)

            warnings.warn(RuntimeWarning(
                f"Using rosetta-node/{test_node_hint} as node config: {node_config}"
            ))
            mutate_runner = runner(**init_kwargs)
            mutate_pdb_path = mutate_runner.run_mutate(mutant=MUTANTS[0])

        from Bio.PDB.PDBParser import PDBParser
        from Bio.PDB.Structure import Structure

        parser = PDBParser(PERMISSIVE=1)
        structure: Structure = parser.get_structure(
            MUTANTS[0].short_mutant_id, mutate_pdb_path
        )
        mut_residue_1 = structure[0]["A"][1]
        mut_residue_2 = structure[0]["A"][2]
        assert mut_residue_1.get_resname() == "GLY"
        assert mut_residue_2.get_resname() == "GLY"
