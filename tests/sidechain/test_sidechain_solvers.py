# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import pytest
from pymol import cmd

from REvoDesign.common.mutant import Mutant
from REvoDesign.sidechain.mutate_runner import DLPackerPytorch_worker, MutateRelax_worker, PIPPack_worker, PyMOL_mutate

WT_PDB = "../tests/data/3fap_hf3_A_short.pdb"
MUT_PDB = "../tests/data/3fap_hf3_A_RFD.pdb"
MOLECULE = "3fap_hf3_A_short"
MUTANTS: list[Mutant] = [Mutant(**m.__dict__) for m in Mutant.from_pdb(WT_PDB, [MUT_PDB])]
mutant_string = MUTANTS[0].full_mutant_id


class TestSidechainSolver:

    @pytest.fixture(autouse=True)
    def setup_pymol(self):
        """Auto-used fixture to load PDB file before each test"""
        cmd.load(WT_PDB)

    def _run_mutate_test(self, runner, init_kwargs, mutant=MUTANTS[0]):
        """
        Common test logic for all mutate runners

        Parameters:
            runner: The mutate runner class to test
            init_kwargs: Initialization arguments for the runner
            mutant: The mutant to test (defaults to first mutant)
        """
        if not runner.installed:
            pytest.skip(f"{runner.__name__} is not installed")

        mutate_runner = runner(**init_kwargs)
        mutate_pdb_path = mutate_runner.run_mutate(mutant=mutant)

        from Bio.PDB.PDBParser import PDBParser
        from Bio.PDB.Structure import Structure

        parser = PDBParser(PERMISSIVE=1)
        structure: Structure = parser.get_structure(mutant.short_mutant_id, mutate_pdb_path)
        mut_residue_1 = structure[0]["A"][1]
        mut_residue_2 = structure[0]["A"][2]
        assert mut_residue_1.get_resname() == "GLY"
        assert mut_residue_2.get_resname() == "GLY"

    @pytest.mark.parametrize(
        "id, runner,init_kwargs",
        [
            # ['DLpacker', DLPacker_worker, {'pdb_file': WT_PDB}, ],  # disabled dure to segfault on CI
            # ['DLpacker-range', DLPacker_worker, {'pdb_file': WT_PDB, 'radius': 3.5}, ],  # disabled dure to segfault on CI
            ["DLpacker-pytorch", DLPackerPytorch_worker, {"pdb_file": WT_PDB}],
            ["PIPPack-model_1", PIPPack_worker, {"pdb_file": WT_PDB, "use_model": "pippack_model_1"}],
            [
                "PIPPack-ensumble",
                PIPPack_worker,
                {
                    "pdb_file": WT_PDB,
                },
            ],
            ["PyMOL-mutate", PyMOL_mutate, {"molecule": MOLECULE, "pdb_file": WT_PDB}],
        ],
    )
    def test_runner_mutate(self, id, runner, init_kwargs):
        self._run_mutate_test(runner, init_kwargs)

    @pytest.mark.parametrize(
        "id, runner,init_kwargs", [["MutateRelax_worker", MutateRelax_worker, {"pdb_file": WT_PDB}]]
    )
    def test_runner_mutate_rosetta(self, id, runner, init_kwargs, mock_rosetta_node_config):
        self._run_mutate_test(runner, init_kwargs)
