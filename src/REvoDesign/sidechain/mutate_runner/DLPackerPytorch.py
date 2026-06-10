# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Wrapper for DLPacker PyTorch implementation.
"""

import gc
import os

from joblib import Parallel, delayed

from REvoDesign import reload_config_file, set_cache_dir
from REvoDesign.basic.mutate_runner import MutateRunnerAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.common.mutant import Mutant
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.tools.utils import timing

logging = ROOT_LOGGER.getChild(__name__)


class DLPackerPytorch_worker(MutateRunnerAbstract):
    name: str = "DLPackerPytorch"
    installed: bool = is_package_installed("dlpacker_pytorch")

    weights_preset: tuple[str, ...] = ("hybrid", "tf", "steric")
    default_weight_preset: str = "hybrid"

    def __init__(self, pdb_file: str, radius: float = 0.0, use_model: str | None = None, **kwargs):
        super().__init__(pdb_file)

        sc_cfg = reload_config_file("sidechain-solver/dlpacker_pytorch")["sidechain-solver"]
        inference_cfg = sc_cfg.inference

        cache_dir = set_cache_dir()
        expected_dlpacker_weight_cache_dir = os.path.join(os.path.abspath(cache_dir), "weights", "DLPacker")
        default_weights_prefix = os.path.join(expected_dlpacker_weight_cache_dir, "DLPacker_weights")
        configured_weights_prefix = (str(inference_cfg.weights_prefix).strip() if inference_cfg.weights_prefix else "")
        self.weights_prefix = configured_weights_prefix or default_weights_prefix
        os.environ["DLPACKER_PRETRAINED_WEIGHT"] = os.path.dirname(self.weights_prefix)

        self.pdb_file = pdb_file
        self.reconstruct_area_radius = radius
        self.device: str | None = inference_cfg.device

        # Reuse existing UI model dropdown for DLPackerPyTorch rotamer policy.
        self.rotamer_policy = use_model or inference_cfg.rotamer_policy or self.default_weight_preset
        if self.rotamer_policy not in self.weights_preset:
            logging.warning(
                f"Unknown DLPackerPyTorch policy {self.rotamer_policy=}, fallback to {self.default_weight_preset}."
            )
            self.rotamer_policy = self.default_weight_preset

        self.temp_dir = self.new_cache_dir

    def _build_worker(self):
        from dlpacker_pytorch import DLPacker
        from dlpacker_pytorch.utils import DLPModel

        model = DLPModel(device=self.device)
        return DLPacker(
            str_pdb=self.pdb_file,
            model=model,
            weights_filename=self.weights_prefix,
            rotamer_policy=self.rotamer_policy,
        )

    def reconstruct(self):
        dlpacker_worker = self._build_worker()

        temperal_relaxed_pdb = os.path.join(
            self.temp_dir,
            f'{os.path.basename(self.pdb_file).removesuffix(".pdb")}_reconstructed.pdb',
        )
        dlpacker_worker.reconstruct_protein(order="sequence", output_filename=temperal_relaxed_pdb)
        del dlpacker_worker
        return temperal_relaxed_pdb

    def run_mutate(self, mutant: Mutant):
        from Bio.Data import IUPACData

        dlpacker_worker = self._build_worker()

        logging.debug(f"Mutating {mutant=}")
        new_obj_name = mutant.short_mutant_id

        temp_pdb_path = os.path.join(self.temp_dir, f"{new_obj_name}.pdb")

        for mut_info in mutant.mutations:
            new_residue_3 = IUPACData.protein_letters_1to3[mut_info.mut_res].upper()
            wt_residue_3 = IUPACData.protein_letters_1to3[mut_info.wt_res].upper()
            dlpacker_worker.mutate_sequence(
                target=(mut_info.position, mut_info.chain_id, wt_residue_3),
                new_label=new_residue_3,
            )

        reconstruct_area = self._get_reconstruct_area(
            mutant_obj=mutant,
            reconstruct_area_radius=self.reconstruct_area_radius,
        )
        logging.debug(f"Reconstruct within {self.reconstruct_area_radius=}: {reconstruct_area=}")
        dlpacker_worker.reconstruct_region(
            targets=reconstruct_area,
            order="natoms" if self.reconstruct_area_radius > 0 else "sequence",
            output_filename=temp_pdb_path,
        )

        del dlpacker_worker
        return temp_pdb_path

    def _get_reconstruct_area(self, mutant_obj: Mutant, reconstruct_area_radius: float = -1):
        from Bio.Data import IUPACData

        dlpacker_worker = self._build_worker()

        reconstruct_area = []
        for mut_info in mutant_obj.mutations:
            new_residue_3 = IUPACData.protein_letters_1to3[mut_info.mut_res].upper()
            wt_residue_3 = IUPACData.protein_letters_1to3[mut_info.wt_res].upper()
            if reconstruct_area_radius <= 0:
                reconstruct_area.append((mut_info.position, mut_info.chain_id, new_residue_3))
            else:
                nearby_targets = dlpacker_worker.get_targets(
                    target=(
                        mut_info.position,
                        mut_info.chain_id,
                        wt_residue_3,
                    ),
                    radius=reconstruct_area_radius,
                )
                center_target = (mut_info.position, mut_info.chain_id, new_residue_3)
                reconstruct_area.extend(nearby_targets)
                reconstruct_area.append(center_target)

        if reconstruct_area:
            reconstruct_area = list(set(reconstruct_area))

        del dlpacker_worker
        return reconstruct_area

    def run_mutate_parallel(
        self,
        mutants: list[Mutant],
        nproc: int = 2,
    ) -> list[str]:
        with timing("setting up DLPackerPytorch"):
            from dlpacker_pytorch import DLPacker

        if nproc is None:
            nproc = os.cpu_count()

        if nproc > (num_task := len(mutants)):
            logging.warning(f"Fixed {nproc=} to {num_task=}")
            nproc = num_task

        results = Parallel(n_jobs=nproc, return_as="list")(delayed(self.run_mutate)(mutant) for mutant in mutants)

        gc.collect()
        return list(results)  # type: ignore

    __bibtex__ = {
        "DLPacker": r"""@article{https://doi.org/10.1002/prot.26311,
author = {Misiura, Mikita and Shroff, Raghav and Thyer, Ross and Kolomeisky, Anatoly B.},
title = {DLPacker: Deep learning for prediction of amino acid side chain conformations in proteins},
journal = {Proteins: Structure, Function, and Bioinformatics},
volume = {90},
number = {6},
pages = {1278-1290},
keywords = {3DCNN, DNN, protein structure prediction, side chain restoration, U-net},
doi = {https://doi.org/10.1002/prot.26311},
url = {https://onlinelibrary.wiley.com/doi/abs/10.1002/prot.26311},
eprint = {https://onlinelibrary.wiley.com/doi/pdf/10.1002/prot.26311},
year = {2022}
}"""
    }
