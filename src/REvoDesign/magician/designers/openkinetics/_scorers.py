# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""OpenKinetics scorer classes."""

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

from REvoDesign import ROOT_LOGGER, set_cache_dir
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
from ._models import OpenKineticsConfigurationError
from ._pdb import resolve_substrate_metadata

logging = ROOT_LOGGER.getChild(__name__)

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

_OPENKINETICS_PREDICTOR_BIBTEX = r"""@misc{OpenKineticsPredictorCitationPending,
  title = {OpenKineticsPredictor: open-source platform for kinetic parameter prediction},
  note = {Citation details to be added},
  url = {https://predictor.openkinetics.org}
}"""

_PREDICTOR_BIBTEX = {
    "CataPro": r"""@article{Wang2025CataPro,
  title = {Robust enzyme discovery and engineering with deep learning using CataPro},
  author = {Wang, Zechen and Xie, Dongqi and Wu, Dong and Luo, Xiaozhou and Wang, Sheng and Li, Yangyang and Yang, Yanmei and Li, Weifeng and Zheng, Liangzhen},
  journal = {Nature Communications},
  volume = {16},
  number = {1},
  year = {2025},
  doi = {10.1038/s41467-025-58038-4},
  url = {https://doi.org/10.1038/s41467-025-58038-4}
}""",
    "CatPred": r"""@article{Boorla2025CatPred,
  title = {CatPred: a comprehensive framework for deep learning in vitro enzyme kinetic parameters},
  author = {Boorla, Veda Sheersh and Maranas, Costas D.},
  journal = {Nature Communications},
  volume = {16},
  number = {1},
  year = {2025},
  doi = {10.1038/s41467-025-57215-9},
  url = {https://doi.org/10.1038/s41467-025-57215-9}
}""",
    "DLKcat": r"""@article{Li2022DLKcat,
  title = {Deep learning-based kcat prediction enables improved enzyme-constrained model reconstruction},
  author = {Li, Feiran and Yuan, Le and Lu, Hongzhong and Li, Gang and Chen, Yu and Engqvist, Martin K. M. and Kerkhoven, Eduard J. and Nielsen, Jens},
  journal = {Nature Catalysis},
  volume = {5},
  number = {8},
  pages = {662--672},
  year = {2022},
  doi = {10.1038/s41929-022-00798-z},
  url = {https://doi.org/10.1038/s41929-022-00798-z}
}""",
    "EITLEM": r"""@article{Shen2024EITLEMKinetics,
  title = {EITLEM-Kinetics: A deep-learning framework for kinetic parameter prediction of mutant enzymes},
  author = {Shen, Xiaowei and Cui, Ziheng and Long, Jianyu and Zhang, Shiding and Chen, Biqiang and Tan, Tianwei},
  journal = {Chem Catalysis},
  volume = {4},
  number = {9},
  pages = {101094},
  year = {2024},
  doi = {10.1016/j.checat.2024.101094},
  url = {https://doi.org/10.1016/j.checat.2024.101094}
}""",
    "KinForm": r"""@article{Alwer2026KinForm,
  title = {KinForm: kinetics-informed feature optimised representation models for enzyme kcat and KM prediction},
  author = {Alwer, Saleh and Fleming, Ronan M. T.},
  journal = {npj Systems Biology and Applications},
  volume = {12},
  number = {1},
  year = {2026},
  doi = {10.1038/s41540-026-00692-5},
  url = {https://doi.org/10.1038/s41540-026-00692-5}
}""",
    "MMISA-KM": r"""@inproceedings{Song2025MMISAKM,
  title = {MMISA-KM: a deep-learning method using multi-modal information and self-attention mechanisms for the prediction of Michaelis constants},
  author = {Song, Aijie and Wang, Kai},
  booktitle = {2025 IEEE 14th Data Driven Control and Learning Systems (DDCLS)},
  pages = {2023--2028},
  year = {2025},
  doi = {10.1109/DDCLS66240.2025.11064981},
  url = {https://doi.org/10.1109/DDCLS66240.2025.11064981}
}""",
    "OmniESI": r"""@misc{Nie2025OmniESI,
  title = {OmniESI: A unified framework for enzyme-substrate interaction prediction with progressive conditional deep learning},
  author = {Nie, Zhiwei and Zhang, Hongyu and Jiang, Hao and Liu, Yutian and Huang, Xiansong and Xu, Fan and Fu, Jie and Ren, Zhixiang and Tian, Yonghong and Zhang, Wen-Bin and Chen, Jie},
  year = {2025},
  doi = {10.48550/arXiv.2506.17963},
  url = {https://doi.org/10.48550/arXiv.2506.17963}
}""",
    "RealKcat": r"""@article{Sajeevan2025RealKcat,
  title = {Robust Prediction of Enzyme Variant Kinetics with RealKcat},
  author = {Sajeevan, Karuna Anna and Osinuga, Abraham and B, Arunraj and Ferdous, Sakib and Shahreen, Nabia and Noor, Mohammed and Koneru, Shashank and Santa-Correa, Laura Mariana and Salehi, Rahil and Chowdhury, Niaz Bahar and Aryee, Randy and Calderon-Lopez, Brisa and Mali, Ankur and Saha, Rajib and Chowdhury, Ratul},
  year = {2025},
  doi = {10.1101/2025.02.10.637555},
  url = {https://doi.org/10.1101/2025.02.10.637555}
}""",
    "UniKP": r"""@article{Yu2023UniKP,
  title = {UniKP: a unified framework for the prediction of enzyme kinetic parameters},
  author = {Yu, Han and Deng, Huaxiang and He, Jiahui and Keasling, Jay D. and Luo, Xiaozhou},
  journal = {Nature Communications},
  volume = {14},
  number = {1},
  year = {2023},
  doi = {10.1038/s41467-023-44113-1},
  url = {https://doi.org/10.1038/s41467-023-44113-1}
}""",
    "IECata": r"""@article{Wang2025IECata,
  title = {IECata: interpretable bilinear attention network and evidential deep learning improve the catalytic efficiency prediction of enzymes},
  author = {Wang, Jingjing and Zhao, Yanpeng and Yang, Zhijiang and Yao, Ge and Han, Penggang and Liu, Jiajia and Chen, Chang and Zan, Peng and Wan, Xiukun and Bo, Xiaochen and Jiang, Hui},
  journal = {Briefings in Bioinformatics},
  volume = {26},
  number = {3},
  year = {2025},
  doi = {10.1093/bib/bbaf283},
  url = {https://doi.org/10.1093/bib/bbaf283}
}""",
}


class OpenKineticsScorerAbstract(ExternalDesignerAbstract, ABC):
    """Base class for OpenKinetics API-based kinetic scorers.

    Concrete subclasses fix the method and prediction type via
    :meth:`built_in_defaults`.
    """

    installed = True
    scorer_only = True
    __bibtex__ = {"OpenKineticsPredictor": _OPENKINETICS_PREDICTOR_BIBTEX}

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
        auto_register_api_key: bool = True,
        replace_existing_api_key: bool = False,
        default_method: str | None = None,
        default_prediction_type: str | None = None,
        poll_interval_seconds: int | None = None,
        timeout_seconds: int | None = None,
        cache_enabled: bool | None = None,
        cache_dir: str | None = None,
        substrate_smiles: str | None = None,
        chain: str | None = None,
        pdb_path: str | os.PathLike[str] | None = None,
    ) -> None:
        super().__init__(molecule or "")
        config = load_openkinetics_config()
        class_defaults = self.built_in_defaults()
        self.client = client or OpenKineticsClient(
            base_url=base_url,
            api_key=api_key,
            auto_register_api_key=auto_register_api_key,
            replace_existing_api_key=replace_existing_api_key,
            timeout_seconds=timeout_seconds,
        )
        self.default_method = default_method or class_defaults["method"] or config["default_method"]
        self.default_prediction_type = (
            default_prediction_type or class_defaults["prediction_type"] or config["default_prediction_type"]
        )
        self.poll_interval_seconds = int(poll_interval_seconds or config["poll_interval_seconds"])
        self.timeout_seconds = int(timeout_seconds or config["timeout_seconds"])
        self.cache_enabled = config["cache_enabled"] if cache_enabled is None else cache_enabled
        self.cache_dir = cache_dir or os.path.join(set_cache_dir(), "openkinetics")
        self.substrate_smiles = substrate_smiles
        self.chain = chain
        self.pdb_path = pdb_path
        self.initialized = False

    # -- ExternalDesignerAbstract interface --------------------------------

    def initialize(self, *args, **kwargs):
        if not self.substrate_smiles:
            if substrate_smiles := kwargs.get("substrate_smiles"):
                self.substrate_smiles = str(substrate_smiles)
            elif pdb_path := kwargs.get("pdb_path") or self.pdb_path:
                self.substrate_smiles = resolve_substrate_metadata(pdb_path)["substrate_smiles"]
        self.initialized = True

    def _sequence_from_mutant(self, mutant: Mutant | RosettaPyProteinSequence) -> tuple[str, str]:
        if isinstance(mutant, Mutant):
            chain_id = (
                self.chain
                if self.chain in mutant.wt_protein_sequence.all_chain_ids
                else mutant.wt_protein_sequence.all_chain_ids[0]
            )
            sequence = mutant.get_mutant_sequence_single_chain(chain_id=chain_id, ignore_missing=True).sequence
            return mutant.raw_mutant_id or "variant", sequence

        chain_id = self.chain if self.chain in mutant.all_chain_ids else mutant.all_chain_ids[0]
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

    def parallel_scorer(self, mutants: list[Mutant], nproc: int = 2, **kwargs) -> list[Mutant]:
        substrate_smiles = kwargs.get("substrate_smiles") or self.substrate_smiles
        if not substrate_smiles:
            raise OpenKineticsConfigurationError("OpenKinetics scoring requires a substrate SMILES string.")

        active_mutants = [mutant for mutant in mutants if not mutant.empty]
        if not active_mutants:
            return active_mutants

        # ponytail: OpenKinetics accepts a batch; joblib would create one remote job per mutant.
        rows = []
        for mutant in active_mutants:
            variant_id, sequence = self._sequence_from_mutant(mutant)
            rows.append({"variant_id": variant_id, "mutation": variant_id, "protein_sequence": sequence})
        result = self.score_variants(
            rows,
            substrate_smiles=substrate_smiles,
            method=kwargs.get("method"),
            prediction_type=kwargs.get("prediction_type"),
            wait=kwargs.get("wait", True),
            use_cache=kwargs.get("use_cache"),
        )
        scores = [float(row["predicted_value"]) for row in result["normalized_scores"]]
        return self.score_mutant_mapping(active_mutants, scores)

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
        self.cite()
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

        try:
            quota = self.client.check_quota()
            logging.warning("OpenKinetics daily quota: %s", quota)
        except Exception:
            logging.debug("OpenKinetics quota check failed", exc_info=True)

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
        if cache_enabled:
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


_SCORER_SPECS: tuple[tuple[str, str, str, str, str], ...] = (
    ("CataProKcatScorer", "OpenKinetics-CataPro-kcat", "CataPro", "kcat", "CataPro"),
    ("CatPredKcatScorer", "OpenKinetics-CatPred-kcat", "CatPred", "kcat", "CatPred"),
    ("DLKcatScorer", "OpenKinetics-DLKcat-kcat", "DLKcat", "kcat", "DLKcat"),
    ("EITLEMKcatScorer", "OpenKinetics-EITLEM-kcat", "EITLEM", "kcat", "EITLEM"),
    ("KinFormHKcatScorer", "OpenKinetics-KinForm-H-kcat", "KinForm-H", "kcat", "KinForm"),
    ("KinFormLKcatScorer", "OpenKinetics-KinForm-L-kcat", "KinForm-L", "kcat", "KinForm"),
    ("OmniESIKcatScorer", "OpenKinetics-OmniESI-kcat", "OmniESI", "kcat", "OmniESI"),
    ("RealKcatScorer", "OpenKinetics-RealKcat-kcat", "RealKcat", "kcat", "RealKcat"),
    ("UniKPKcatScorer", "OpenKinetics-UniKP-kcat", "UniKP", "kcat", "UniKP"),
    ("CataProKmScorer", "OpenKinetics-CataPro-Km", "CataPro", "Km", "CataPro"),
    ("CatPredKmScorer", "OpenKinetics-CatPred-Km", "CatPred", "Km", "CatPred"),
    ("EITLEMKmScorer", "OpenKinetics-EITLEM-Km", "EITLEM", "Km", "EITLEM"),
    ("KinFormHKmScorer", "OpenKinetics-KinForm-H-Km", "KinForm-H", "Km", "KinForm"),
    ("MMISAKMKmScorer", "OpenKinetics-MMISA-KM-Km", "MMISA-KM", "Km", "MMISA-KM"),
    ("OmniESIKmScorer", "OpenKinetics-OmniESI-Km", "OmniESI", "Km", "OmniESI"),
    ("RealKcatKmScorer", "OpenKinetics-RealKcat-Km", "RealKcat", "Km", "RealKcat"),
    ("UniKPKmScorer", "OpenKinetics-UniKP-Km", "UniKP", "Km", "UniKP"),
    ("CataProKcatKmScorer", "OpenKinetics-CataPro-kcat/Km", "CataPro", "kcat/Km", "CataPro"),
    ("IECataKcatKmScorer", "OpenKinetics-IECata-kcat/Km", "IECata", "kcat/Km", "IECata"),
)


def _built_in_defaults(method: str, prediction_type: str):
    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": method, "prediction_type": prediction_type}

    return built_in_defaults


OPENKINETICS_SCORER_CLASS_NAMES = tuple(spec[0] for spec in _SCORER_SPECS)

for class_name, scorer_name, method, prediction_type, citation_key in _SCORER_SPECS:
    globals()[class_name] = type(
        class_name,
        (OpenKineticsScorerAbstract,),
        {
            "__module__": __name__,
            "name": scorer_name,
            "prefer_lower": prediction_type.lower() == "km",
            "__bibtex__": {
                **OpenKineticsScorerAbstract.__bibtex__,
                citation_key: _PREDICTOR_BIBTEX[citation_key],
            },
            "built_in_defaults": _built_in_defaults(method, prediction_type),
        },
    )
