# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Wrapper for DiffPack sidechain packing.
"""

import os
import uuid

from joblib import Parallel, delayed

from REvoDesign import reload_config_file
from REvoDesign.basic.mutate_runner import MutateRunnerAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.common.mutant import Mutant
from REvoDesign.logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


class DiffPack_worker(MutateRunnerAbstract):
    name: str = "DiffPack"
    installed: bool = is_package_installed("diffpack")

    weights_preset: tuple[str, ...] = ("native", "torchdrug", "pyg")
    default_weight_preset: str = "native"

    def __init__(self, pdb_file: str, radius: float = 0.0, use_model: str | None = None, **kwargs):
        super().__init__(pdb_file)

        sc_cfg = reload_config_file("sidechain-solver/diffpack")["sidechain-solver"]
        inference_cfg = sc_cfg.inference

        self.pdb_file = pdb_file
        self.reconstruct_area_radius = radius

        self.backend = use_model or inference_cfg.backend or self.default_weight_preset
        if self.backend not in self.weights_preset:
            logging.warning(f"Unknown DiffPack backend {self.backend=}, fallback to {self.default_weight_preset}.")
            self.backend = self.default_weight_preset

        self.device: str = inference_cfg.device
        self.hetero_policy: str = inference_cfg.hetero_policy
        self.fast: bool = bool(inference_cfg.fast)
        self.memory_mode: str = inference_cfg.memory_mode
        self.cache_root: str | None = str(inference_cfg.cache_root).strip() if inference_cfg.cache_root else None
        self.config_path: str = self._resolve_config_path(str(inference_cfg.config))

        self.temp_dir = self.new_cache_dir

        self._cache_bootstrapped = False
        self._ensure_cache_ready()

    def _resolve_config_path(self, config_setting: str) -> str:
        from diffpack.util import get_default_config_path

        cfg = (config_setting or "").strip()
        if cfg:
            explicit = os.path.realpath(os.path.expanduser(cfg))
            if os.path.exists(explicit):
                return explicit

        try:
            default_path = get_default_config_path(cfg or "inference_confidence.yaml")
            default_path = os.path.realpath(os.path.expanduser(default_path))
        except Exception as exc:
            raise RuntimeError(f"Unable to resolve DiffPack config path from `{config_setting}`: {exc}") from exc

        if not os.path.exists(default_path):
            raise FileNotFoundError(f"DiffPack config file not found: {default_path}")
        return default_path

    def _ensure_cache_ready(self):
        if self._cache_bootstrapped:
            return

        from diffpack.schedule_cache import (
            prepare_schedule_cache,
            required_schedule_pis,
            resolve_cache_root,
            validate_required_schedule_caches,
        )

        resolved_root = resolve_cache_root(self.cache_root)
        validation = validate_required_schedule_caches(resolved_root)

        if validation.get("errors"):
            logging.warning("DiffPack schedule cache missing/invalid. Auto-preparing cache once...")
            try:
                for pi in required_schedule_pis():
                    prepare_schedule_cache(resolved_root, pi, force=False)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to prepare DiffPack cache at `{resolved_root}`. "
                    "Please run `diffpack-prepare-cache` manually."
                ) from exc

            post_validation = validate_required_schedule_caches(resolved_root)
            if post_validation.get("errors"):
                raise RuntimeError(
                    f"DiffPack cache remains invalid after auto-prepare at `{resolved_root}`: "
                    f"{post_validation['errors']}"
                )

        self.cache_root = resolved_root
        self._cache_bootstrapped = True

    @staticmethod
    def _to_mutation_tokens(mutant: Mutant) -> str:
        return ",".join(
            f"{mut_info.chain_id}{mut_info.wt_res}{mut_info.position}{mut_info.mut_res}" for mut_info in mutant.mutations
        )

    def _run_diffpack(
        self,
        *,
        output_dir: str,
        mutations: str | None,
        repack_radius: float | None,
    ) -> str:
        from diffpack.backends import InferenceRequest, get_backend_adapter

        self._ensure_cache_ready()

        os.makedirs(output_dir, exist_ok=True)
        request = InferenceRequest(
            config=self.config_path,
            seed=0,
            output_dir=output_dir,
            pdb_files=[self.pdb_file],
            center_residues=[],
            repack_radius=repack_radius,
            hetero_policy=self.hetero_policy,
            device=self.device,
            fast=self.fast,
            profile=False,
            memory_mode=self.memory_mode,
            cache_root=self.cache_root,
            cache_read_only=True,
            mutations=mutations,
        )
        adapter = get_backend_adapter(self.backend)
        metadata = adapter.run_inference(request)

        output_files = metadata.get("output_files", [])
        if not output_files:
            raise RuntimeError(f"DiffPack output_files is empty: {metadata}")

        output_pdb = output_files[0]
        if not os.path.exists(output_pdb):
            raise FileNotFoundError(f"DiffPack reported output does not exist: {output_pdb}")
        return output_pdb

    @staticmethod
    def _rename_output(source_pdb: str, target_pdb: str) -> str:
        os.makedirs(os.path.dirname(target_pdb), exist_ok=True)
        if os.path.realpath(source_pdb) != os.path.realpath(target_pdb):
            os.replace(source_pdb, target_pdb)
        return target_pdb

    def reconstruct(self):
        run_dir = os.path.join(
            self.temp_dir,
            "_diffpack_reconstruct",
            f"{os.path.basename(self.pdb_file).removesuffix('.pdb')}_{uuid.uuid4().hex[:8]}",
        )
        output_pdb = self._run_diffpack(
            output_dir=run_dir,
            mutations=None,
            repack_radius=None,
        )
        target_pdb = os.path.join(
            self.temp_dir,
            f"{os.path.basename(self.pdb_file).removesuffix('.pdb')}_reconstructed.pdb",
        )
        return self._rename_output(output_pdb, target_pdb)

    def run_mutate(self, mutant: Mutant):
        new_obj_name = mutant.short_mutant_id
        temp_pdb_path = os.path.join(self.temp_dir, f"{new_obj_name}.pdb")

        run_dir = os.path.join(
            self.temp_dir,
            "_diffpack_mutate",
            f"{new_obj_name}_{uuid.uuid4().hex[:8]}",
        )
        mutation_tokens = self._to_mutation_tokens(mutant)

        repack_radius = self.reconstruct_area_radius if self.reconstruct_area_radius > 0 else -1.0
        output_pdb = self._run_diffpack(
            output_dir=run_dir,
            mutations=mutation_tokens,
            repack_radius=repack_radius,
        )
        return self._rename_output(output_pdb, temp_pdb_path)

    def run_mutate_parallel(
        self,
        mutants: list[Mutant],
        nproc: int = 2,
    ) -> list[str]:
        if not mutants:
            return []

        max_cores = os.cpu_count() or 1
        requested_nproc = max_cores if nproc is None or nproc < 1 else nproc
        effective_nproc = min(requested_nproc, len(mutants), max_cores)
        logging.info(
            f"DiffPack parallel mutate: {effective_nproc=} with one-mutant-one-core policy "
            f"(requested={nproc}, mutants={len(mutants)}, cpu={max_cores})."
        )

        results = Parallel(n_jobs=effective_nproc, return_as="list")(delayed(self.run_mutate)(mutant) for mutant in mutants)
        return list(results)  # type: ignore

    __bibtex__ = {
        "DiffPack": """@article{zhang2023diffpack,
title={DiffPack: A Torsional Diffusion Model for Autoregressive Protein Side-Chain Packing},
author={Zhang, Yangtian and Zhang, Zuobai and Zhong, Bozitao and Misra, Sanchit and Tang, Jian},
journal={arXiv preprint arXiv:2306.01794},
year={2023}
}"""
    }
