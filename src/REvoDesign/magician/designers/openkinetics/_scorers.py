# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""OpenKinetics scorer classes — one base class and three concrete scorers."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.basic.designer import ExternalDesignerAbstract
from REvoDesign.common.mutant import Mutant

from ._client import (
    OpenKineticsClient,
    _normalize_result_rows,
    _stable_cache_key,
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

    def _cache_path(self, cache_key: str) -> Path:
        return Path(self.cache_dir) / f"{cache_key}.json"

    def _load_cache(self, cache_key: str) -> dict[str, Any] | None:
        cache_path = self._cache_path(cache_key)
        if not self.cache_enabled or not cache_path.is_file():
            return None
        return json.loads(cache_path.read_text(encoding="utf-8"))

    def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        if not self.cache_enabled:
            return
        cache_path = self._cache_path(cache_key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(cache_path, payload)

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

        cache_key = _stable_cache_key(
            {
                "base_url": self.client.base_url,
                "method": selected_method,
                "prediction_type": selected_prediction_type,
                "rows": api_rows,
            }
        )
        if cache_enabled:
            cached = self._load_cache(cache_key)
            if cached is not None:
                if output_csv_path:
                    write_normalized_scores_csv(output_csv_path, cached["normalized_scores"])
                if raw_result_path and "raw_result" in cached:
                    write_json(Path(raw_result_path), cached["raw_result"])
                return cached

        submit_response = self.client.submit(api_rows, method=selected_method, prediction_type=selected_prediction_type)
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

        normalized_scores = _normalize_result_rows(
            result_payload,
            method=selected_method,
            prediction_type=selected_prediction_type,
            substrate_smiles=substrate_smiles,
            variant_rows=local_rows,
            job_id=job_id,
        )

        payload = {
            "job_id": job_id,
            "status": "completed",
            "normalized_scores": normalized_scores,
            "raw_result": result_payload,
            "status_responses": status_responses,
        }
        self._write_cache(cache_key, payload)

        if output_csv_path:
            write_normalized_scores_csv(output_csv_path, normalized_scores)
        if raw_result_path:
            write_json(Path(raw_result_path), result_payload)

        return payload


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
