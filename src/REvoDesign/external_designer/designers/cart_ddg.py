import logging
import os
import shutil
import warnings
from typing import Dict, Optional, Union

import docker
import docker.errors
from Bio.Data import IUPACData
from RosettaPy.analyser.ddg import RosettaCartesianddGAnalyser
from RosettaPy.app.cart_ddg import CartesianDDG
from RosettaPy.common.mutation import RosettaPyProteinSequence, mutants2mutfile
from RosettaPy.node import Native, NodeHintT, node_picker
from RosettaPy.node.wsl import which_wsl

from REvoDesign import ConfigBus, issues
from REvoDesign.common.Mutant import Mutant
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

from .. import ExternalDesignerAbstract


def is_run_node_available() -> bool:
    bus: ConfigBus = ConfigBus()
    node_hint: Optional[NodeHintT] = bus.get_value("rosetta.node_hint")  # type: ignore

    if node_hint is None or node_hint == "native":
        return not os.environ.get("ROSETTA_BIN", "") == ""

    if node_hint.startswith("wsl"):

        try:
            wsl_bin = which_wsl()
            return wsl_bin is not None
        except RuntimeError:
            warnings.warn(
                issues.PlatformNotSupportedWarning(
                    f"Invalid Node configuration: {node_hint}"
                )
            )
            return False

    if node_hint == "docker":
        return is_docker_available()

    if node_hint == "mpi":
        return shutil.which("mpirun") is not None

    return False


def is_docker_available() -> bool:
    """Returns True if Docker is available."""

    try:
        client = docker.from_env()
        del client
        return True
    except docker.errors.DockerException as e:
        warnings.warn(
            issues.PlatformNotSupportedWarning(f"Docker is not available: {e}")
        )

        return False


class ddg(ExternalDesignerAbstract):

    name = "Cartesian-ddG"
    installed = True

    scorer_only = True
    no_need_to_score_wt = True
    prefer_lower = True

    def __init__(self, molecule: str, **kwargs):
        self.installed = is_run_node_available()
        self.pdb_filename = None
        self.initialized = False
        self.molecule = molecule
        self.reload = False

        self.unrelaxed_pdb: Optional[str] = None
        self.relaxed_pdb: Optional[str] = None

        self.bus: ConfigBus = ConfigBus()

        self.node_hint: Optional[NodeHintT] = self.bus.get_value("rosetta.node_hint")  # type: ignore
        self.use_legacy: bool = bool(
            self.bus.get_value(
                "rosetta.cart_ddg.use_legacy", default_value=False
            )
        )
        self.ddg_iterations: int = int(
            self.bus.get_value(
                "rosetta.cart_ddg.iterations", converter=int, default_value=3
            )
        )
        self.node_config: Optional[Dict[str, str]] = dict(
            self.bus.get_value("rosetta.node_config")
        )

    def initialize(self, **kwargs):

        if self.node_config is None:
            self.node_config = {}

        if self.unrelaxed_pdb is None or not os.path.isfile(
            self.unrelaxed_pdb
        ):
            self.unrelaxed_pdb = make_temperal_input_pdb(
                molecule=self.molecule, reload=False
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
        self.relaxed_pdb = self.ddg_runner.relax()

        self.initialized = True
        self.cite()

    def scorer(
        self, mutant: Union[Mutant, RosettaPyProteinSequence], **kwargs
    ) -> float:
        if isinstance(mutant, Mutant):
            mutfile = mutants2mutfile(
                [mutant],
                file_path=os.path.join(
                    "cart_ddg_results",
                    "mutfiles",
                    f"{mutant.raw_mutant_id}.mutfile",
                ),
            )
        else:
            raise NotImplementedError

        ddg_value_df = self.ddg_runner.cartesian_ddg(
            input_pdb=self.relaxed_pdb,
            mutfiles=[mutfile],
            mutants=[mutant],
            use_legacy=self.use_legacy,
            ddg_iteration=self.ddg_iterations,
        )

        # TODO: jump positions for rosetta
        ddg_mut_id = "MUT_" + "_".join(
            f"{m.position}{IUPACData.protein_letters_1to3[m.mut_res]}"
            for m in mutant.mutations
        )
        score = ddg_value_df[ddg_value_df["Baseline"] == ddg_mut_id][
            "ddG_cart"
        ].values[0]
        return float(score)

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

URL = {
        https://doi.org/10.1021/acs.jctc.6b00819
},
eprint = {

        https://doi.org/10.1021/acs.jctc.6b00819
}

}
"""
    }
