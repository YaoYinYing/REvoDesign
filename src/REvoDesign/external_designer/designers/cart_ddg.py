'''
Cartesian-ddG, driven by RosettaPy Package
'''

import logging
import os
import platform
import shutil
import warnings
from typing import Any, Dict, List, Optional, Union

import docker
import docker.errors
from Bio.Data import IUPACData
from RosettaPy.app.cart_ddg import CartesianDDG
from RosettaPy.common.mutation import (Mutation, RosettaPyProteinSequence,
                                       mutants2mutfile)
from RosettaPy.node import NodeHintT, node_picker
from RosettaPy.node.wsl import which_wsl

from REvoDesign import ConfigBus, issues
from REvoDesign.basic import ExternalDesignerAbstract
from REvoDesign.common.Mutant import Mutant
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb


def is_run_node_available(node_hint: Optional[NodeHintT]) -> bool:

    if node_hint is None or node_hint == "native":
        return not os.environ.get("ROSETTA_BIN", "") == ""

    if node_hint.startswith("wsl"):
        if platform.system() != "Windows":
            return False
        return is_wsl_available()

    if node_hint.startswith("docker"):
        return is_docker_available()

    if node_hint == "mpi":
        return shutil.which("mpirun") is not None

    return False


def is_wsl_available():
    """Returns True if WSL is available."""
    try:
        wsl_bin = which_wsl()
        return wsl_bin is not None
    except RuntimeError:
        warnings.warn(
            issues.PlatformNotSupportedWarning(
                "WSL is not available on this machine."
            )
        )
        return False


def is_docker_available() -> bool:
    """Returns True if Docker is available."""

    try:
        client = docker.from_env()
        del client
        return True
    except docker.errors.DockerException as e:
        warnings.warn(
            issues.PlatformNotSupportedWarning(f"Docker is not available on this machine: {e}")
        )
        return False


def get_ddg_mut_id(mutations: List[Mutation]) -> str:
    return "MUT_" + "_".join(
        f"{_m.position}{IUPACData.protein_letters_1to3[_m.mut_res].upper()}"
        for _m in mutations
    )


def preprocess_ddg_values(ddg_value_df) -> Dict[str, float]:
    # Create a dictionary for quick lookup
    ddg_dict = {
        row["Baseline"]: row["ddG_cart"] for _, row in ddg_value_df.iterrows()
    }
    return ddg_dict


class ddg(ExternalDesignerAbstract):

    name = "Cartesian-ddG"
    installed = True

    scorer_only = True
    no_need_to_score_wt = True
    prefer_lower = True

    def __init__(self, molecule: str, **kwargs):

        self.molecule = molecule
        self.reload = False

        # Qt is unpickable
        bus: ConfigBus = ConfigBus()
        self.node_hint: Optional[NodeHintT] = bus.get_value("rosetta.node_hint", default_value="native")  # type: ignore

        self.installed = is_run_node_available(self.node_hint)
        self.pdb_filename = None
        self.initialized = False

        self.unrelaxed_pdb: Optional[str] = None
        self.relaxed_pdb: Optional[str] = None

        self.nproc: int = int(bus.get_value("ui.header_panel.nproc"))

        self.relax_nstruct: int = bus.get_value("rosetta.cart_ddg.relax.nstruct")  # type: ignore
        self.use_legacy: bool = bool(
            bus.get_value("rosetta.cart_ddg.use_legacy", default_value=False)
        )
        self.ddg_iterations: int = int(
            bus.get_value("rosetta.cart_ddg.iterations", default_value=3)
        )
        self.node_config: Optional[Dict[str, Any]] = bus.get_value(
            "rosetta.node_config"
        )
        if self.node_config is None:
            self.node_config = {}

    def initialize(self, **kwargs):

        if self.node_config is None:
            self.node_config = {}

        self.node_config.update({"nproc": self.nproc})

        if self.unrelaxed_pdb is None or not os.path.isfile(
            self.unrelaxed_pdb
        ):
            self.unrelaxed_pdb = make_temperal_input_pdb(
                molecule=self.molecule, reload=False  # , selection="not hetatm"
            )

        self.ddg_runner = CartesianDDG(
            pdb=self.unrelaxed_pdb,
            save_dir="cart_ddg_results",
            job_id=self.molecule,
            node=node_picker(self.node_hint, **self.node_config),
        )

        # skip relax if it has been done
        if (
            isinstance(self.relaxed_pdb, str)
            and os.path.isfile(self.relaxed_pdb)
            and not self.reload
        ):
            return
        logging.info(f"Relaxing {self.molecule} ...")
        self.relaxed_pdb = self.ddg_runner.relax(
            nstruct_relax=self.relax_nstruct
        )

        self.initialized = True

    def parallel_scorer(
        self, mutants: List[Mutant], nproc=2, **kwargs
    ) -> List[Mutant]:

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

    def scorer(
        self, mutant: Union[Mutant, RosettaPyProteinSequence], **kwargs
    ) -> float:
        if isinstance(mutant, RosettaPyProteinSequence):
            raise NotImplementedError

        updated_mutant = self.parallel_scorer(mutants=[mutant], nproc=1)

        return float(updated_mutant[0].mutant_score)

    __bibtex__ = {
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
