# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""OpenKinetics scorer classes — one base class and three concrete scorers."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.basic.designer import ExternalDesignerAbstract
from REvoDesign.common.mutant import Mutant

from ._client import (
    OpenKineticsClient,
    _normalize_result_rows,
    build_openkinetics_data_rows,
    load_openkinetics_config,
    write_json,
    write_normalized_scores_csv,
)
from ._models import (
    DEFAULT_OPENKINETICS_METHOD,
    DEFAULT_OPENKINETICS_PREDICTION_TYPE,
    OpenKineticsConfigurationError,
)

_VARIANT_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS variant_cache (
    cache_key        TEXT PRIMARY KEY,
    protein_sequence TEXT NOT NULL,
    substrate_smiles TEXT NOT NULL,
    method           TEXT NOT NULL,
    prediction_type  TEXT NOT NULL,
    predicted_value  REAL NOT NULL,
    score_direction  TEXT NOT NULL,
    variant_id       TEXT NOT NULL,
    mutation         TEXT NOT NULL,
    job_id           TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'completed',
    source           TEXT NOT NULL DEFAULT 'openkinetics_api',
    cached_at_utc    TEXT NOT NULL
)
"""


class OpenKineticsScorerAbstract(ExternalDesignerAbstract, ABC):
    """Base class for OpenKinetics API-based kinetic scorers.

    Concrete subclasses fix the method and prediction type via
    :meth:`built_in_defaults`.
    """

    installed = True
    scorer_only = True

    @classmethod
    @abstractmethod
    def built_in_defaults(cls) -> dict[str, str]:
        """Return ``{"method": ..., "prediction_type": ...}``."""

    def __init__(
        self,
        *,
        molecule: str | None = None,
        client: OpenKineticsClient | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_env: str | None = None,
        default_method: str | None = None,
        default_prediction_type: str | None = None,
        poll_interval_seconds: int | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        cache_enabled: bool | None = None,
        cache_dir: str | None = None,
        substrate_smiles: str | None = None,
    ) -> None:
        super().__init__(molecule or "")
        config = load_openkinetics_config()
        class_defaults = self.built_in_defaults()
        self.client = client or OpenKineticsClient(
            base_url=base_url,
            api_key=api_key,
            api_key_env=api_key_env,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.default_method = default_method or class_defaults["method"] or config["default_method"]
        self.default_prediction_type = (
            default_prediction_type or class_defaults["prediction_type"] or config["default_prediction_type"]
        )
        self.prefer_lower = self.default_prediction_type.lower() == "km"
        self.poll_interval_seconds = int(poll_interval_seconds or config["poll_interval_seconds"])
        self.timeout_seconds = int(timeout_seconds or config["timeout_seconds"])
        self.cache_enabled = config["cache_enabled"] if cache_enabled is None else cache_enabled
        self.cache_dir = os.path.expanduser(cache_dir or config["cache_dir"])
        self.substrate_smiles = substrate_smiles
        self.initialized = False

    # -- ExternalDesignerAbstract interface --------------------------------

    def initialize(self, *args, **kwargs):
        self.initialized = True

    @staticmethod
    def _sequence_from_mutant(mutant: Mutant | RosettaPyProteinSequence) -> tuple[str, str]:
        if isinstance(mutant, Mutant):
            chain_id = mutant.wt_protein_sequence.all_chain_ids[0]
            sequence = mutant.get_mutant_sequence_single_chain(chain_id=chain_id, ignore_missing=True).sequence
            return mutant.raw_mutant_id or "variant", sequence

        chain_id = mutant.all_chain_ids[0]
        return "variant", mutant.get_sequence_by_chain(chain_id=chain_id).replace("X", "")

    def scorer(self, mutant: Mutant | RosettaPyProteinSequence, **kwargs) -> float:
        substrate_smiles = kwargs.get("substrate_smiles") or self.substrate_smiles
        if not substrate_smiles:
            raise OpenKineticsConfigurationError("OpenKinetics scoring requires a substrate SMILES string.")
        variant_id, sequence = self._sequence_from_mutant(mutant)
        result = self.score_variants(
            [{"variant_id": variant_id, "mutation": variant_id, "protein_sequence": sequence}],
            substrate_smiles=substrate_smiles,
            method=kwargs.get("method"),
            prediction_type=kwargs.get("prediction_type"),
            wait=kwargs.get("wait", True),
            use_cache=kwargs.get("use_cache"),
        )
        return float(result["normalized_scores"][0]["predicted_value"])

    # -- helpers -----------------------------------------------------------

    def _prepare_rows(
        self,
        variants: list[dict[str, Any]],
        substrate_smiles: str,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        local_rows = OpenKineticsClient._normalize_score_variants_input(variants)
        api_rows = build_openkinetics_data_rows(local_rows, substrate_smiles)
        return local_rows, api_rows

    # -- per-variant cache (SQLite) ----------------------------------------

    @staticmethod
    def _variant_cache_key(
        protein_sequence: str,
        substrate_smiles: str,
        method: str,
        prediction_type: str,
    ) -> str:
        """Deterministic cache key for a single (sequence, substrate, method, pred) tuple."""
        return hashlib.sha256(
            json.dumps(
                {
                    "protein_sequence": protein_sequence,
                    "substrate_smiles": substrate_smiles,
                    "method": method,
                    "prediction_type": prediction_type,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

    def _cache_db_path(self) -> Path:
        return Path(self.cache_dir) / "variant_cache.db"

    def _ensure_cache_db(self) -> None:
        db_path = self._cache_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(_VARIANT_CACHE_DDL)
            conn.commit()

    def _load_variant_cache(self, cache_key: str) -> dict[str, Any] | None:
        if not self.cache_enabled:
            return None
        db_path = self._cache_db_path()
        if not db_path.is_file():
            return None
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(_VARIANT_CACHE_DDL)
            row = conn.execute(
                "SELECT cache_key, protein_sequence, substrate_smiles, method, prediction_type, "
                "predicted_value, score_direction, variant_id, mutation, job_id, status, source, "
                "cached_at_utc FROM variant_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return {
            "cache_key": row[0],
            "protein_sequence": row[1],
            "substrate_smiles": row[2],
            "method": row[3],
            "prediction_type": row[4],
            "predicted_value": row[5],
            "score_direction": row[6],
            "variant_id": row[7],
            "mutation": row[8],
            "job_id": row[9],
            "status": row[10],
            "source": row[11],
            "cached_at_utc": row[12],
        }

    def _write_variant_cache(self, cache_key: str, row: dict[str, Any]) -> None:
        if not self.cache_enabled:
            return
        self._ensure_cache_db()
        db_path = self._cache_db_path()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(_VARIANT_CACHE_DDL)
            conn.execute(
                "INSERT OR REPLACE INTO variant_cache "
                "(cache_key, protein_sequence, substrate_smiles, method, prediction_type, "
                "predicted_value, score_direction, variant_id, mutation, job_id, status, source, "
                "cached_at_utc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cache_key,
                    row["protein_sequence"],
                    row["substrate_smiles"],
                    row["method"],
                    row["prediction_type"],
                    row["predicted_value"],
                    row["score_direction"],
                    row["variant_id"],
                    row["mutation"],
                    row.get("job_id", ""),
                    row.get("status", "completed"),
                    row.get("source", "openkinetics_api"),
                    row.get("cached_at_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                ),
            )
            conn.commit()

    # -- main scoring entry point ------------------------------------------

    def score_variants(
        self,
        variants,
        substrate_smiles: str,
        method: str | None = None,
        prediction_type: str | None = None,
        wait: bool = True,
        use_cache: bool | None = None,
        output_csv_path: str | Path | None = None,
        raw_result_path: str | Path | None = None,
    ) -> dict[str, Any]:
        selected_method = method or self.default_method
        selected_prediction_type = prediction_type or self.default_prediction_type
        local_rows, api_rows = self._prepare_rows(variants, substrate_smiles)
        cache_enabled = self.cache_enabled if use_cache is None else use_cache

        # ---- per-variant cache lookup ------------------------------------
        cached_scores: list[dict[str, Any] | None] = [None] * len(local_rows)
        uncached_indices: list[int] = []

        for i, row in enumerate(local_rows):
            if cache_enabled:
                ck = self._variant_cache_key(
                    row["protein_sequence"], substrate_smiles, selected_method, selected_prediction_type
                )
                entry = self._load_variant_cache(ck)
                if entry is not None:
                    cached_scores[i] = entry
                    continue
            uncached_indices.append(i)

        # ---- all cached → no API call ------------------------------------
        if not uncached_indices:
            normalized_scores = [cached_scores[i] for i in range(len(local_rows))]  # type: ignore[arg-type]
            result: dict[str, Any] = {
                "job_id": "",
                "status": "completed",
                "normalized_scores": normalized_scores,
                "raw_result": None,
                "status_responses": [],
            }
            if output_csv_path:
                write_normalized_scores_csv(output_csv_path, normalized_scores)
            return result

        # ---- submit only uncached variants -------------------------------
        uncached_api_rows = [api_rows[i] for i in uncached_indices]
        submit_response = self.client.submit(
            uncached_api_rows, method=selected_method, prediction_type=selected_prediction_type
        )
        job_id = submit_response["jobId"]
        if not wait:
            return {"job_id": job_id, "status": "submitted"}

        status_responses = self.client.poll_until_complete(
            job_id,
            poll_interval_seconds=self.poll_interval_seconds,
            timeout_seconds=self.timeout_seconds,
        )
        result_payload = self.client.get_result(job_id, result_format="json")
        if not isinstance(result_payload, dict):
            raise OpenKineticsConfigurationError("Expected JSON result payload")

        uncached_local_rows = [local_rows[i] for i in uncached_indices]
        fresh_scores = _normalize_result_rows(
            result_payload,
            method=selected_method,
            prediction_type=selected_prediction_type,
            substrate_smiles=substrate_smiles,
            variant_rows=uncached_local_rows,
            job_id=job_id,
        )

        # Write fresh scores to per-variant cache.
        for fresh_row in fresh_scores:
            ck = self._variant_cache_key(
                fresh_row["protein_sequence"], substrate_smiles, selected_method, selected_prediction_type
            )
            fresh_row["cached_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._write_variant_cache(ck, fresh_row)

        # Merge cached + fresh, preserving original order.
        fresh_iter = iter(fresh_scores)
        merged_scores: list[dict[str, Any]] = []
        for i in range(len(local_rows)):
            if cached_scores[i] is not None:
                merged_scores.append(cached_scores[i])
            else:
                merged_scores.append(next(fresh_iter))

        if output_csv_path:
            write_normalized_scores_csv(output_csv_path, merged_scores)
        if raw_result_path:
            write_json(Path(raw_result_path), result_payload)

        return {
            "job_id": job_id,
            "status": "completed",
            "normalized_scores": merged_scores,
            "raw_result": result_payload,
            "status_responses": status_responses,
        }


# ---------------------------------------------------------------------------
# Concrete scorers — one class per (method, prediction_type) pair.
#
# All single-substrate predictors (Protein Sequence + Substrate input).
# Km-type predictions are "lower is better"; kcat and kcat/Km are
# "higher is better".
# ---------------------------------------------------------------------------


# -- kcat scorers ---------------------------------------------------------


class CataProKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-CataPro-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "CataPro", "prediction_type": "kcat"}


class CatPredKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-CatPred-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "CatPred", "prediction_type": "kcat"}


class DLKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-DLKcat-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "DLKcat", "prediction_type": "kcat"}


class EITLEMKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-EITLEM-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "EITLEM", "prediction_type": "kcat"}


class KinFormHKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-KinForm-H-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "KinForm-H", "prediction_type": "kcat"}


class KinFormLKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-KinForm-L-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "KinForm-L", "prediction_type": "kcat"}


class OmniESIKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-OmniESI-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "OmniESI", "prediction_type": "kcat"}


class RealKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-RealKcat-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "RealKcat", "prediction_type": "kcat"}


class UniKPKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-UniKP-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "UniKP", "prediction_type": "kcat"}


# -- Km scorers -----------------------------------------------------------


class CataProKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-CataPro-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "CataPro", "prediction_type": "Km"}


class CatPredKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-CatPred-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "CatPred", "prediction_type": "Km"}


class EITLEMKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-EITLEM-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "EITLEM", "prediction_type": "Km"}


class KinFormHKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-KinForm-H-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "KinForm-H", "prediction_type": "Km"}


class MMISAKMKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-MMISA-KM-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "MMISA-KM", "prediction_type": "Km"}


class OmniESIKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-OmniESI-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "OmniESI", "prediction_type": "Km"}


class RealKcatKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-RealKcat-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "RealKcat", "prediction_type": "Km"}


class UniKPKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-UniKP-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "UniKP", "prediction_type": "Km"}


# -- kcat/Km scorers ------------------------------------------------------


class CataProKcatKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-CataPro-kcat/Km"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "CataPro", "prediction_type": "kcat/Km"}


class IECataKcatKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-IECata-kcat/Km"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "IECata", "prediction_type": "kcat/Km"}
