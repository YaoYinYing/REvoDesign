# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""
Evo cluster method entry.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

import numpy as np
import pandas as pd
from Bio.PDB import PDBParser

from REvoDesign.clusters.cluster_sequence import ClusterMethodAbstract, ClusterMethodSpec, logging
from REvoDesign.common.profile_parsers import ProfileManager
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id


class EvoCluster(ClusterMethodAbstract):
    name = "EvoCluster"
    spec = ClusterMethodSpec(
        name=name,
        display_name="EvoCluster",
        description=(
            "Average-linkage clustering on a renormalized weighted distance model combining sequence, "
            "physicochemical, spatial, PSSM, and ESM components when available."
        ),
        representative_policy="Nearest centroid among clustered variants; not a medoid selection.",
    )

    aa_physchem_group = {
        "A": 0,
        "V": 0,
        "I": 0,
        "L": 0,
        "M": 0,
        "F": 1,
        "W": 1,
        "Y": 1,
        "S": 2,
        "T": 2,
        "N": 2,
        "Q": 2,
        "C": 2,
        "G": 3,
        "P": 3,
        "H": 4,
        "K": 4,
        "R": 4,
        "D": 5,
        "E": 5,
    }

    def __init__(self, fastafile: str):
        super().__init__(fastafile)
        self.last_component_report: dict[str, object] = {}

    def _normalize_mutation_token(self, token: str) -> str:
        token = str(token).strip().replace(":", "")
        token = token.split("_")[0]
        return token

    def _get_mutations_per_record(self) -> list[list]:
        if not self.records:
            return []
        wt_sequence = self.wt_sequence or str(self.records[0].seq)
        chain_id = self.chain_id or "A"
        mutations_per_record = []
        for record in self.records:
            try:
                mut_obj = extract_mutants_from_mutant_id(
                    mutant_string=str(record.name),
                    sequences={chain_id: wt_sequence},
                )
                mutations_per_record.append(list(mut_obj.mutations))
            except Exception:
                mutations_per_record.append([])
        return mutations_per_record

    def _build_physchem_distance_matrix(self, mutations_per_record: list[list]) -> np.ndarray | None:
        if not mutations_per_record:
            return None
        features = np.zeros((len(mutations_per_record), 6), dtype=float)
        for idx, mutations in enumerate(mutations_per_record):
            for mutation in mutations:
                group = self.aa_physchem_group.get(mutation.mut_res)
                if group is not None:
                    features[idx, group] += 1.0
            total = np.sum(features[idx])
            if total > 0:
                features[idx] /= total
        if not np.any(features):
            return None
        diff = features[:, None, :] - features[None, :, :]
        return np.linalg.norm(diff, axis=2)

    def _resolve_structure_pdb(self) -> str:
        if self.structure_pdb and os.path.exists(self.structure_pdb):
            return self.structure_pdb
        return ""

    def _build_spatial_distance_matrix(self, mutations_per_record: list[list]) -> np.ndarray | None:
        structure_pdb = self._resolve_structure_pdb()
        if not structure_pdb:
            return None

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("cluster_structure", structure_pdb)
        coords = {}
        for model in structure:
            for chain in model:
                for residue in chain:
                    if "CA" in residue:
                        coords[(chain.id, int(residue.id[1]))] = residue["CA"].coord
            break

        if not coords:
            return None

        centroids = np.full((len(mutations_per_record), 3), np.nan, dtype=float)
        for idx, mutations in enumerate(mutations_per_record):
            pts = []
            for mutation in mutations:
                key = (mutation.chain_id, mutation.position)
                if key in coords:
                    pts.append(coords[key])
            if pts:
                centroids[idx] = np.mean(np.asarray(pts, dtype=float), axis=0)

        valid = ~np.isnan(centroids).any(axis=1)
        if np.sum(valid) < 2:
            return None

        for idx in range(len(centroids)):
            if not valid[idx]:
                centroids[idx] = np.nanmean(centroids[valid], axis=0)

        diff = centroids[:, None, :] - centroids[None, :, :]
        return np.linalg.norm(diff, axis=2)

    def _load_pssm_df(self) -> pd.DataFrame | None:
        profile_path = str(self.evo_pssm_profile or "").strip()
        if not profile_path or not os.path.exists(profile_path):
            return None

        profile_type = "CSV" if profile_path.lower().endswith(".csv") else "PSSM"
        manager = ProfileManager(profile_type=profile_type)
        manager.parse(
            {
                "profile_input": profile_path,
                "molecule": "",
                "chain_id": self.chain_id,
                "sequence": self.wt_sequence,
            }
        )
        return manager.parser.df

    @staticmethod
    def _resolve_profile_column(df: pd.DataFrame, position: int):
        candidates: Iterable[object] = (
            str(position - 1),
            str(position),
            position - 1,
            position,
        )
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None

    def _build_pssm_distance_matrix(self, mutations_per_record: list[list]) -> np.ndarray | None:
        df = self._load_pssm_df()
        if df is None:
            return None

        scalar_scores = np.zeros(len(mutations_per_record), dtype=float)
        for idx, mutations in enumerate(mutations_per_record):
            values = []
            for mutation in mutations:
                col = self._resolve_profile_column(df, mutation.position)
                if col is None or mutation.mut_res not in df.index:
                    continue
                try:
                    values.append(float(df.loc[mutation.mut_res, col]))
                except Exception:
                    continue
            if values:
                scalar_scores[idx] = float(np.mean(values))

        if np.allclose(scalar_scores, scalar_scores[0]):
            return None

        return np.abs(scalar_scores[:, None] - scalar_scores[None, :])

    def _build_esm_distance_matrix(self, mutations_per_record: list[list]) -> np.ndarray | None:
        esm_path = str(self.evo_esm1v_table or "").strip()
        if not esm_path or not os.path.exists(esm_path):
            return None

        df = pd.read_csv(esm_path)
        if self.evo_esm_mutation_col not in df.columns:
            return None

        numeric_cols = [
            col for col in df.columns if col != self.evo_esm_mutation_col and pd.api.types.is_numeric_dtype(df[col])
        ]
        if not numeric_cols:
            return None

        df = df.copy()
        df["mutation_token"] = df[self.evo_esm_mutation_col].map(self._normalize_mutation_token)
        df["esm_group_score"] = df[numeric_cols].mean(axis=1)
        mut_score_map = df.groupby("mutation_token")["esm_group_score"].mean().to_dict()

        scalar_scores = np.zeros(len(mutations_per_record), dtype=float)
        for idx, mutations in enumerate(mutations_per_record):
            values = []
            for mutation in mutations:
                token = f"{mutation.wt_res}{mutation.position}{mutation.mut_res}"
                if token in mut_score_map:
                    values.append(float(mut_score_map[token]))
            if values:
                scalar_scores[idx] = float(np.mean(values))

        if np.allclose(scalar_scores, scalar_scores[0]):
            return None

        return np.abs(scalar_scores[:, None] - scalar_scores[None, :])

    def _renormalize_weights(self, components: list[tuple[str, np.ndarray]]) -> list[tuple[str, float, np.ndarray]]:
        weighted_components = []
        for name, matrix in components:
            weight = float(self.evo_weights.get(name, 0.0))
            if weight > 0:
                weighted_components.append((name, weight, matrix))

        if not weighted_components:
            return []

        total = sum(weight for _, weight, _ in weighted_components)
        return [(name, weight / total, matrix) for name, weight, matrix in weighted_components]

    def _build_evo_distance(self, score_matrix: np.ndarray) -> np.ndarray:
        mutations_per_record = self._get_mutations_per_record()

        components = []
        component_status: dict[str, dict[str, object]] = {}
        seq_matrix = self.normalize_distance_matrix(self.build_distance_matrix_from_scores(score_matrix))
        components.append(("seq", seq_matrix))
        component_status["seq"] = {
            "requested_weight": float(self.evo_weights.get("seq", 0.0)),
            "available": True,
            "reason": "sequence_distance",
        }

        physchem = self._build_physchem_distance_matrix(mutations_per_record)
        if physchem is not None:
            components.append(("physchem", self.normalize_distance_matrix(physchem)))
        component_status["physchem"] = {
            "requested_weight": float(self.evo_weights.get("physchem", 0.0)),
            "available": physchem is not None,
            "reason": "physicochemical_signal_available" if physchem is not None else "no_physicochemical_signal",
        }

        spatial = self._build_spatial_distance_matrix(mutations_per_record)
        if spatial is not None:
            components.append(("spatial", self.normalize_distance_matrix(spatial)))
        component_status["spatial"] = {
            "requested_weight": float(self.evo_weights.get("spatial", 0.0)),
            "available": spatial is not None,
            "reason": "structure_signal_available" if spatial is not None else "missing_or_unusable_structure",
        }

        pssm = self._build_pssm_distance_matrix(mutations_per_record)
        if pssm is not None:
            components.append(("pssm", self.normalize_distance_matrix(pssm)))
        component_status["pssm"] = {
            "requested_weight": float(self.evo_weights.get("pssm", 0.0)),
            "available": pssm is not None,
            "reason": "pssm_signal_available" if pssm is not None else "missing_or_unusable_pssm_profile",
        }

        esm = self._build_esm_distance_matrix(mutations_per_record)
        if esm is not None:
            components.append(("esm", self.normalize_distance_matrix(esm)))
        component_status["esm"] = {
            "requested_weight": float(self.evo_weights.get("esm", 0.0)),
            "available": esm is not None,
            "reason": "esm_signal_available" if esm is not None else "missing_or_unusable_esm_table",
        }

        weighted_components = self._renormalize_weights(components)
        if not weighted_components:
            raise ValueError(
                "EvoCluster has no active distance components after applying the configured weights. "
                "Provide at least one available component with a positive weight."
            )

        total_distance = np.zeros_like(seq_matrix, dtype=float)
        for _, norm_weight, matrix in weighted_components:
            total_distance += norm_weight * matrix

        normalized_weights = {name: norm_weight for name, norm_weight, _ in weighted_components}
        active_components = [name for name in normalized_weights]
        skipped_components = {
            name: details for name, details in component_status.items() if name not in active_components
        }
        self.last_component_report = {
            "component_status": component_status,
            "active_components": active_components,
            "skipped_components": skipped_components,
            "normalized_weights": normalized_weights,
            "inputs": {
                "pssm_profile": bool(str(self.evo_pssm_profile).strip()),
                "esm1v_table": bool(str(self.evo_esm1v_table).strip()),
                "structure_pdb": bool(str(self.structure_pdb).strip()),
                "esm_mutation_col": self.evo_esm_mutation_col,
            },
        }
        logging.info("EvoCluster active distance components: %s", active_components)
        logging.info("EvoCluster normalized weights: %s", normalized_weights)
        if skipped_components:
            logging.info("EvoCluster skipped distance components: %s", skipped_components)

        return self.normalize_distance_matrix(total_distance)

    def build_method_report(self) -> dict[str, object]:
        report = super().build_method_report()
        report["evo"] = self.last_component_report
        return report

    def predict_labels(self, score_matrix: np.ndarray) -> np.ndarray:
        from sklearn.cluster import AgglomerativeClustering

        evo_distance = self._build_evo_distance(score_matrix)
        return AgglomerativeClustering(
            n_clusters=self.num_clusters,
            linkage="average",
            metric="precomputed",
        ).fit_predict(evo_distance)


__all__ = ["EvoCluster"]
