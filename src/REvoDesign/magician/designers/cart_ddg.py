# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Cartesian-ddG, driven by RosettaPy Package
"""

import logging
import os
from typing import Any

from Bio.Data import IUPACData
from RosettaPy.app.cart_ddg import CartesianDDG
from RosettaPy.common.mutation import Mutation, RosettaPyProteinSequence, mutants2mutfile
from RosettaPy.node import NodeHintT

from REvoDesign import ConfigBus
from REvoDesign.basic.designer import ExternalDesignerAbstract
from REvoDesign.common.mutant import Mutant
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb
from REvoDesign.tools.rosetta_utils import IS_ROSETTA_RUNNABLE, copy_rosetta_citation, read_rosetta_node_config


def get_ddg_mut_id(mutations: list[Mutation]) -> str:
    return "MUT_" + "_".join(f"{_m.position}{IUPACData.protein_letters_1to3[_m.mut_res].upper()}" for _m in mutations)


def preprocess_ddg_values(ddg_value_df) -> dict[str, float]:
    # Create a dictionary for quick lookup
    ddg_dict = {row["Baseline"]: row["ddG_cart"] for _, row in ddg_value_df.iterrows()}
    return ddg_dict


class ddg(ExternalDesignerAbstract):

    name = "Cartesian-ddG"
    # the class variable installed is set to True if rosetta is installed as any node
    installed = IS_ROSETTA_RUNNABLE

    scorer_only = True
    no_need_to_score_wt = True
    prefer_lower = True

    def __init__(self, molecule: str, **kwargs):

        self.molecule = molecule
        self.reload = False

        # Qt is unpickable
        bus: ConfigBus = ConfigBus()
        self.node_hint: NodeHintT = bus.get_value("rosetta.node_hint", default_value="native")  # type: ignore

        self.pdb_filename = None
        self.initialized = False

        self.unrelaxed_pdb: str | None = None
        self.relaxed_pdb: str | None = None

        self.relax_nstruct: int = bus.get_value("rosetta.cart_ddg.relax.nstruct")  # type: ignore
        self.use_legacy = bus.get_value("rosetta.cart_ddg.use_legacy", bool, default_value=False, reject_none=True)

        self.ddg_iterations = bus.get_value("rosetta.cart_ddg.iterations", int, default_value=3, reject_none=True)

        self.node_config: dict[str, Any] | None = read_rosetta_node_config()
        if self.node_config is None:
            self.node_config = {}

    def initialize(self, **kwargs):

        if self.node_config is None:
            self.node_config = {}

        if self.unrelaxed_pdb is None or not os.path.isfile(self.unrelaxed_pdb):
            self.unrelaxed_pdb = make_temperal_input_pdb(
                molecule=self.molecule, reload=False  # , selection="not hetatm"
            )

        self.ddg_runner = CartesianDDG(
            pdb=self.unrelaxed_pdb,
            save_dir="cart_ddg_results",
            job_id=self.molecule,
            node_hint=self.node_hint,
            node_config=self.node_config,
        )

        # skip relax if it has been done
        if isinstance(self.relaxed_pdb, str) and os.path.isfile(self.relaxed_pdb) and not self.reload:
            return
        logging.info(f"Relaxing {self.molecule} ...")
        self.relaxed_pdb = self.ddg_runner.relax(nstruct_relax=self.relax_nstruct)

        self.initialized = True

    def parallel_scorer(self, mutants: list[Mutant], nproc=2, **kwargs) -> list[Mutant]:

        mutfile_paths = [
            os.path.abspath(
                os.path.join(
                    "cart_ddg_results",
                    "mutfiles",
                    f"{mutant.raw_mutant_id}.mutfile",
                )
            )
            for mutant in mutants
        ]

        non_xtal_mutants = [mutant.non_xtal for mutant in mutants]

        for nx_m, mfp in zip(non_xtal_mutants, mutfile_paths):
            mutants2mutfile(mutants=[nx_m], file_path=mfp)

        ddg_value_df = self.ddg_runner.cartesian_ddg(
            input_pdb=self.relaxed_pdb,
            mutfiles=mutfile_paths,
            mutants=non_xtal_mutants,
            use_legacy=self.use_legacy,
            ddg_iteration=self.ddg_iterations,
        )

        # Preprocess ddg values for quick lookup
        ddg_dict = preprocess_ddg_values(ddg_value_df)

        for nx_m, m in zip(non_xtal_mutants, mutants):
            ddg_mut_id = get_ddg_mut_id(nx_m.mutations)
            score = ddg_dict.get(ddg_mut_id)

            if score is not None:
                m.mutant_score = score
                m.wt_score = 0
            else:
                print(f"Warning: No ddG value found for {ddg_mut_id}")

        self.cite()

        return mutants

    def scorer(self, mutant: Mutant | RosettaPyProteinSequence, **kwargs) -> float:
        if isinstance(mutant, RosettaPyProteinSequence):
            raise NotImplementedError

        updated_mutant = self.parallel_scorer(mutants=[mutant], nproc=1)

        return float(updated_mutant[0].mutant_score)

    __bibtex__ = copy_rosetta_citation(
        {
            "Cartesian-ddG": """@article{doi:10.1021/acs.jctc.6b00819,
author = {Park, Hahnbeom and Bradley, Philip and Greisen, Per Jr. and Liu, Yuan and Mulligan, Vikram Khipple and Kim, David E. and Baker, David and DiMaio, Frank},
title = {Simultaneous Optimization of Biomolecular Energy Functions on Features from Small Molecules and Macromolecules},
journal = {Journal of Chemical Theory and Computation},
volume = {12},
number = {12},
pages = {6201-6212},
year = {2016},
doi = {10.1021/acs.jctc.6b00819},
    note ={PMID: 27766851},
URL = {https://doi.org/10.1021/acs.jctc.6b00819},
eprint = {https://doi.org/10.1021/acs.jctc.6b00819}
}
"""
        }
    )
