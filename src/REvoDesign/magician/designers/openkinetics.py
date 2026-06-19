"""OpenKinetics API-backed scorers and fixture helpers."""

from __future__ import annotations

import hashlib
import math
import json
import os
import re
import csv
import shutil
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from Bio.Data.IUPACData import protein_letters_3to1
from Bio.PDB import PDBParser
from platformdirs import user_cache_dir
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.basic.designer import ExternalDesignerAbstract
from REvoDesign.common.mutant import Mutant


DEFAULT_OPENKINETICS_BASE_URL = "https://predictor.openkinetics.org/api/v1"
DEFAULT_OPENKINETICS_API_KEY_ENV = "OPENKINETICS_API_KEY"
DEFAULT_OPENKINETICS_METHOD = "CataPro"
DEFAULT_OPENKINETICS_PREDICTION_TYPE = "kcat/Km"
DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS = 3
DEFAULT_OPENKINETICS_TIMEOUT_SECONDS = 600

OPENKINETICS_ENDPOINTS = {
    "methods": "/methods/",
    "validate": "/validate/",
    "submit": "/submit/",
    "status": "/status/{job_id}/",
    "result": "/result/{job_id}/",
}

OPENKINETICS_DOCS_ASSUMPTION = (
    "Official API docs could not be fetched automatically during implementation; "
    "the collector uses the documented fallback endpoint pattern from "
    "plan/openkinetics.md."
)

WATER_RESIDUE_NAMES = frozenset({"HOH", "WAT"})
COFACTOR_EXCLUSIONS = frozenset({"HEM"})

MANUAL_SUBSTRATE_FALLBACKS: dict[tuple[str, str], dict[str, str]] = {
    ("1SUO", "CPZ"): {
        "ligand_name": "chlorpromazine",
        "smiles": "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21",
        "source": "manual_fallback",
        "note": (
            "RDKit conversion from the PDB block does not preserve the expected "
            "phenothiazine aromaticity for the 1SUO CPZ ligand, so the script "
            "prefers this auditable manual fallback."
        ),
    }
}

AA3_TO_AA1 = {
    three_letter.capitalize(): one_letter.upper()
    for three_letter, one_letter in protein_letters_3to1.items()
}


class OpenKineticsError(RuntimeError):
    """Base OpenKinetics integration error."""


class OpenKineticsConfigurationError(OpenKineticsError):
    """Raised when required local configuration is missing or invalid."""


class OpenKineticsAPIError(OpenKineticsError):
    """Raised for HTTP or remote API failures."""


class OpenKineticsTimeoutError(OpenKineticsError):
    """Raised when a remote job does not complete within the timeout."""


class OpenKineticsValidationError(OpenKineticsError):
    """Raised when prepared OpenKinetics input data is invalid."""


@dataclass(frozen=True)
class PointMutation:
    chain_id: str
    wt_res: str
    position: int
    mut_res: str

    @property
    def label(self) -> str:
        return f"{self.chain_id}{self.wt_res}{self.position}{self.mut_res}"


@dataclass(frozen=True)
class LigandCandidate:
    residue_name: str
    residue_number: int
    chain_id: str
    atom_serials: tuple[int, ...]
    atom_count: int

    @property
    def ligand_identifier(self) -> str:
        return f"{self.residue_name}:{self.chain_id}:{self.residue_number}"


@dataclass(frozen=True)
class OpenKineticsFixturePaths:
    output_dir: Path
    manifest_path: Path
    readme_path: Path
    input_variants_path: Path
    api_input_path: Path
    substrate_path: Path


def parse_point_mutation_label(label: str, default_chain_id: str = "A") -> PointMutation:
    clean_label = label.strip()
    if not clean_label:
        raise OpenKineticsValidationError("Mutation label is empty")

    match = re.fullmatch(r"([A-Z]?)([A-Z])(\d+)([A-Z])", clean_label)
    if match is None:
        raise OpenKineticsValidationError(f"Unsupported mutation label format: {label!r}")

    chain_id = match.group(1) or default_chain_id
    return PointMutation(
        chain_id=chain_id,
        wt_res=match.group(2),
        position=int(match.group(3)),
        mut_res=match.group(4),
    )


def load_mutation_labels(mutation_path: str | Path, limit: int | None = None) -> list[str]:
    labels = [line.strip() for line in Path(mutation_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if limit is not None:
        labels = labels[:limit]
    return labels


def load_chain_sequence_context(
    pdb_path: str | Path,
    chain_id: str = "A",
) -> tuple[RosettaPyProteinSequence, str, tuple[int, ...]]:
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("structure", str(pdb_path))
    model = next(structure.get_models())
    if chain_id not in model:
        raise OpenKineticsConfigurationError(f"Chain {chain_id!r} not found in {pdb_path}")

    residue_numbers: list[int] = []
    sequence_codes: list[str] = []
    for residue in model[chain_id]:
        if residue.id[0] != " ":
            continue
        residue_number = int(residue.id[1])
        residue_name = residue.resname.capitalize()
        residue_code = AA3_TO_AA1.get(residue_name)
        if residue_code is None:
            raise OpenKineticsValidationError(
                f"Unsupported residue name {residue.resname!r} at {chain_id}{residue_number}"
            )
        residue_numbers.append(residue_number)
        sequence_codes.append(residue_code)

    if not residue_numbers:
        raise OpenKineticsValidationError(f"No protein residues found for chain {chain_id!r} in {pdb_path}")

    wt_sequences = RosettaPyProteinSequence.from_dict({chain_id: "".join(sequence_codes)})
    return wt_sequences, "".join(sequence_codes), tuple(residue_numbers)


def residue_index_for_pdb_position(
    residue_numbers: tuple[int, ...],
    pdb_position: int,
    chain_id: str = "A",
) -> int:
    try:
        return residue_numbers.index(int(pdb_position))
    except ValueError as exc:
        raise OpenKineticsValidationError(
            f"Residue position {pdb_position} is not present in chain {chain_id}"
        ) from exc


def residue_at_pdb_position(
    sequence: str,
    residue_numbers: tuple[int, ...],
    pdb_position: int,
    chain_id: str = "A",
) -> str:
    return sequence[residue_index_for_pdb_position(residue_numbers, pdb_position, chain_id)]


def apply_point_mutation(
    sequence: str,
    residue_numbers: tuple[int, ...],
    mutation: PointMutation,
    chain_id: str = "A",
) -> str:
    if mutation.chain_id != chain_id:
        raise OpenKineticsValidationError(
            f"Mutation {mutation.label} targets chain {mutation.chain_id}, expected {chain_id}"
        )

    residue_index = residue_index_for_pdb_position(residue_numbers, mutation.position, chain_id)
    wt_residue = sequence[residue_index]
    if wt_residue != mutation.wt_res:
        raise OpenKineticsValidationError(
            f"WT residue mismatch for {mutation.label}: PDB sequence has {wt_residue} at {mutation.position}"
        )

    mutant_sequence = list(sequence)
    mutant_sequence[residue_index] = mutation.mut_res
    return "".join(mutant_sequence)


def build_variant_rows(
    wt_sequence: str,
    residue_numbers: tuple[int, ...],
    mutation_labels: list[str],
    *,
    chain_id: str = "A",
) -> list[dict[str, str]]:
    rows = [
        {
            "variant_id": "WT",
            "mutation": "WT",
            "protein_sequence": wt_sequence,
        }
    ]
    for label in mutation_labels:
        mutation = parse_point_mutation_label(label, default_chain_id=chain_id)
        rows.append(
            {
                "variant_id": label,
                "mutation": label,
                "protein_sequence": apply_point_mutation(
                    wt_sequence,
                    residue_numbers,
                    mutation,
                    chain_id=chain_id,
                ),
            }
        )
    return rows


def discover_ligand_candidates(
    pdb_path: str | Path,
    excluded_residue_names: frozenset[str] = WATER_RESIDUE_NAMES | COFACTOR_EXCLUSIONS,
) -> list[LigandCandidate]:
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("structure", str(pdb_path))
    model = next(structure.get_models())
    ligands: list[LigandCandidate] = []
    for chain in model:
        for residue in chain:
            hetero_flag = residue.id[0]
            if hetero_flag == " ":
                continue
            residue_name = residue.resname.strip().upper()
            if residue_name in excluded_residue_names:
                continue
            atom_serials = tuple(int(atom.serial_number) for atom in residue.get_atoms())
            ligands.append(
                LigandCandidate(
                    residue_name=residue_name,
                    residue_number=int(residue.id[1]),
                    chain_id=chain.id,
                    atom_serials=atom_serials,
                    atom_count=len(atom_serials),
                )
            )
    return ligands


def choose_primary_ligand(pdb_path: str | Path) -> LigandCandidate:
    ligands = discover_ligand_candidates(pdb_path)
    if not ligands:
        raise OpenKineticsValidationError(f"No non-protein ligands were found in {pdb_path}")
    if len(ligands) > 1:
        raise OpenKineticsValidationError(
            f"Expected a single ligand candidate in {pdb_path}, found {[ligand.ligand_identifier for ligand in ligands]}"
        )
    return ligands[0]


def extract_ligand_pdb_block(pdb_path: str | Path, ligand: LigandCandidate) -> str:
    atom_serials = set(ligand.atom_serials)
    block_lines: list[str] = []
    for line in Path(pdb_path).read_text(encoding="utf-8").splitlines():
        if line.startswith("HETATM"):
            residue_name = line[17:20].strip().upper()
            chain_id = line[21].strip()
            residue_number = int(line[22:26].strip())
            if (
                residue_name == ligand.residue_name
                and chain_id == ligand.chain_id
                and residue_number == ligand.residue_number
            ):
                block_lines.append(line)
        elif line.startswith("CONECT"):
            source_serial = int(line[6:11].strip())
            if source_serial in atom_serials:
                block_lines.append(line)
    block_lines.append("END")
    return "\n".join(block_lines) + "\n"


def _canonicalize_smiles(smiles: str) -> str:
    from rdkit import Chem

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise OpenKineticsValidationError(f"Invalid SMILES string: {smiles!r}")
    return Chem.MolToSmiles(molecule)


def smiles_from_ligand_pdb_block(pdb_block: str) -> str | None:
    try:
        from rdkit import Chem
    except ImportError:
        return None

    molecule = Chem.MolFromPDBBlock(pdb_block, sanitize=True, removeHs=False)
    if molecule is None:
        return None
    return Chem.MolToSmiles(molecule)


def resolve_substrate_metadata(
    pdb_path: str | Path,
    structure_id: str = "1SUO",
) -> dict[str, Any]:
    ligand = choose_primary_ligand(pdb_path)
    ligand_pdb_block = extract_ligand_pdb_block(pdb_path, ligand)
    automatic_smiles = smiles_from_ligand_pdb_block(ligand_pdb_block)

    fallback = MANUAL_SUBSTRATE_FALLBACKS.get((structure_id, ligand.residue_name))
    resolved_smiles = automatic_smiles
    resolution = "automatic_rdkit"
    note = ""

    if fallback is not None:
        fallback_smiles = fallback["smiles"]
        if automatic_smiles is None:
            resolved_smiles = fallback_smiles
            resolution = fallback["source"]
            note = fallback["note"]
        else:
            try:
                if _canonicalize_smiles(automatic_smiles) != _canonicalize_smiles(fallback_smiles):
                    resolved_smiles = fallback_smiles
                    resolution = fallback["source"]
                    note = fallback["note"]
            except OpenKineticsValidationError:
                resolved_smiles = fallback_smiles
                resolution = fallback["source"]
                note = fallback["note"]

    if not resolved_smiles:
        raise OpenKineticsValidationError(
            f"Unable to resolve a substrate SMILES string for {ligand.ligand_identifier}"
        )

    metadata = {
        "structure_id": structure_id,
        "ligand_identifier": ligand.ligand_identifier,
        "ligand_residue_name": ligand.residue_name,
        "ligand_residue_number": ligand.residue_number,
        "ligand_chain_id": ligand.chain_id,
        "ligand_atom_count": ligand.atom_count,
        "automatic_smiles": automatic_smiles,
        "substrate_smiles": resolved_smiles,
        "smiles_resolution": resolution,
        "resolution_note": note,
        "pdb_block_sha256": hashlib.sha256(ligand_pdb_block.encode("utf-8")).hexdigest(),
    }

    if fallback is not None:
        metadata["manual_fallback"] = fallback

    return metadata


def normalize_variant_rows_for_local_table(
    variant_rows: list[dict[str, str]],
    substrate_smiles: str,
) -> list[dict[str, str]]:
    normalized = []
    for row in variant_rows:
        normalized.append(
            {
                "variant_id": row["variant_id"],
                "mutation": row["mutation"],
                "protein_sequence": row["protein_sequence"],
                "substrate_smiles": substrate_smiles,
            }
        )
    return normalized


def build_openkinetics_data_rows(
    variant_rows: list[dict[str, str]],
    substrate_smiles: str,
) -> list[dict[str, str]]:
    data_rows = []
    for row in variant_rows:
        data_rows.append(
            {
                "Protein Sequence": row["protein_sequence"],
                "Substrate": substrate_smiles,
            }
        )
    return data_rows


def get_method_metadata(
    methods_response: dict[str, Any],
    *,
    method: str,
    prediction_type: str,
) -> dict[str, Any]:
    methods_by_prediction = methods_response.get("methods", {})
    if not isinstance(methods_by_prediction, dict):
        raise OpenKineticsValidationError("OpenKinetics methods response did not include a methods mapping")

    candidates = methods_by_prediction.get(prediction_type, [])
    if not isinstance(candidates, list):
        raise OpenKineticsValidationError(
            f"OpenKinetics methods response had an invalid entry for prediction type {prediction_type!r}"
        )

    for candidate in candidates:
        if candidate.get("id") == method or candidate.get("displayName") == method:
            return candidate

    raise OpenKineticsValidationError(
        f"Method {method!r} is not available for prediction type {prediction_type!r}"
    )


def build_openkinetics_request_payload(
    *,
    data_rows: list[dict[str, str]],
    method_metadata: dict[str, Any],
    method: str,
    prediction_type: str,
) -> dict[str, Any]:
    payload = {
        "data": data_rows,
        "targets": [prediction_type],
        "methods": {
            prediction_type: method_metadata.get("id", method),
        },
        "handleLongSequences": "truncate",
        "useExperimental": True,
        "includeSimilarityColumns": True,
        "canonicalizeSubstrates": True,
    }

    return payload


def write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise OpenKineticsValidationError(f"No rows were provided for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit_hash(repo_root: Path) -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            .strip()
            or None
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _python_version() -> str:
    return sys.version.split()[0]


def _redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered_key = key.lower()
            if any(token in lowered_key for token in ("authorization", "api_key", "token")):
                redacted[key] = "[redacted]"
            elif any(token in lowered_key for token in ("user", "account", "quota", "email")):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = _redact_payload(item)
        return redacted
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _runtime_cache_dir_from_config() -> str:
    try:
        from REvoDesign import set_cache_dir

        return os.path.join(set_cache_dir(), "openkinetics")
    except Exception:
        return os.path.join(user_cache_dir("REvoDesign"), "openkinetics")


def load_openkinetics_config() -> dict[str, Any]:
    config = {
        "base_url": DEFAULT_OPENKINETICS_BASE_URL,
        "api_key": None,
        "api_key_env": DEFAULT_OPENKINETICS_API_KEY_ENV,
        "default_method": DEFAULT_OPENKINETICS_METHOD,
        "default_prediction_type": DEFAULT_OPENKINETICS_PREDICTION_TYPE,
        "poll_interval_seconds": DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS,
        "timeout_seconds": DEFAULT_OPENKINETICS_TIMEOUT_SECONDS,
        "max_retries": 3,
        "cache_enabled": True,
        "cache_dir": _runtime_cache_dir_from_config(),
    }
    try:
        from REvoDesign import ConfigBus

        bus = ConfigBus()
        config["base_url"] = bus.get_value(
            "scorers.openkinetics.base_url",
            str,
            default_value=config["base_url"],
        )
        config["api_key"] = bus.get_value("scorers.openkinetics.api_key", str, default_value=None)
        config["api_key_env"] = bus.get_value(
            "scorers.openkinetics.api_key_env",
            str,
            default_value=config["api_key_env"],
        )
        config["default_method"] = bus.get_value(
            "scorers.openkinetics.default_method",
            str,
            default_value=config["default_method"],
        )
        config["default_prediction_type"] = bus.get_value(
            "scorers.openkinetics.default_prediction_type",
            str,
            default_value=config["default_prediction_type"],
        )
        config["poll_interval_seconds"] = bus.get_value(
            "scorers.openkinetics.poll_interval_seconds",
            int,
            default_value=config["poll_interval_seconds"],
        )
        config["timeout_seconds"] = bus.get_value(
            "scorers.openkinetics.timeout_seconds",
            int,
            default_value=config["timeout_seconds"],
        )
        config["max_retries"] = bus.get_value(
            "scorers.openkinetics.max_retries",
            int,
            default_value=config["max_retries"],
        )
        config["cache_enabled"] = bus.get_value(
            "scorers.openkinetics.cache_enabled",
            bool,
            default_value=config["cache_enabled"],
        )
        config["cache_dir"] = os.path.expanduser(
            bus.get_value(
                "scorers.openkinetics.cache_dir",
                str,
                default_value=config["cache_dir"],
            )
        )
    except Exception:
        pass
    return config


def resolve_api_key(*, api_key: str | None = None, api_key_env: str = DEFAULT_OPENKINETICS_API_KEY_ENV) -> str:
    direct_api_key = (api_key or "").strip()
    if direct_api_key:
        return direct_api_key

    env_var_name = (api_key_env or DEFAULT_OPENKINETICS_API_KEY_ENV).strip()
    env_api_key = os.environ.get(env_var_name, "").strip()
    if env_api_key:
        return env_api_key

    raise OpenKineticsConfigurationError(
        "Missing OpenKinetics API key. Set scorers.openkinetics.api_key in YAML "
        f"or define the {env_var_name} environment variable."
    )


def _normalize_result_rows(
    result_payload: Any,
    *,
    method: str,
    prediction_type: str,
    substrate_smiles: str,
    variant_rows: list[dict[str, str]] | None = None,
    job_id: str = "",
) -> list[dict[str, Any]]:
    if isinstance(result_payload, dict):
        result_columns = result_payload.get("columns")
        if isinstance(result_columns, list) and isinstance(result_payload.get("data"), list):
            records = result_payload["data"]
        else:
            result_columns = None
        
        for key in ("results", "predictions", "data"):
            if isinstance(result_payload.get(key), list):
                records = result_payload[key]
                break
        else:
            if "variant_id" in result_payload or "mutation" in result_payload:
                records = [result_payload]
            else:
                raise OpenKineticsValidationError(
                    "Unable to locate prediction records in the OpenKinetics result payload"
                )
    elif isinstance(result_payload, list):
        records = result_payload
    else:
        raise OpenKineticsValidationError("Unexpected OpenKinetics result payload type")

    score_direction = "lower_is_better" if prediction_type.lower() == "km" else "higher_is_better"
    variant_lookup = {
        row["protein_sequence"]: row
        for row in (variant_rows or [])
        if row.get("protein_sequence")
    }

    score_column = None
    result_payload_job_id = result_payload.get("jobId") if isinstance(result_payload, dict) else None
    if isinstance(result_payload, dict) and isinstance(result_payload.get("columns"), list):
        for column_name in result_payload["columns"]:
            if isinstance(column_name, str) and column_name.lower().startswith(prediction_type.lower()):
                score_column = column_name
                break

    normalized_rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise OpenKineticsValidationError("Prediction record must be a JSON object")

        protein_sequence = record.get("protein_sequence") or record.get("Protein Sequence") or record.get("sequence") or ""
        matched_variant = variant_lookup.get(protein_sequence, {})
        variant_id = record.get("variant_id") or matched_variant.get("variant_id") or record.get("id") or record.get("name") or "unknown"
        mutation = record.get("mutation") or matched_variant.get("mutation") or variant_id
        status = record.get("status") or "completed"
        row_job_id = record.get("job_id") or record.get("job") or result_payload_job_id or job_id

        predicted_value = None
        for key in (
            "predicted_value",
            "value",
            "prediction",
            prediction_type,
            prediction_type.lower(),
            prediction_type.upper(),
            score_column,
        ):
            if key and key in record:
                predicted_value = record[key]
                break
        if predicted_value is None:
            raise OpenKineticsValidationError(
                f"Unable to locate predicted value for record {variant_id!r}"
            )

        normalized_rows.append(
            {
                "variant_id": variant_id,
                "mutation": mutation,
                "method": method,
                "prediction_type": prediction_type,
                "predicted_value": predicted_value,
                "score_direction": score_direction,
                "protein_sequence": protein_sequence,
                "substrate_smiles": substrate_smiles,
                "job_id": row_job_id,
                "status": status,
                "source": "openkinetics_api",
            }
        )
    return normalized_rows


class OpenKineticsFixtureCollectorClient:
    """Small client used only by the manual fixture-collection workflow."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_env: str | None = None,
        timeout_seconds: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        config = load_openkinetics_config()
        resolved_base_url = str(base_url or config["base_url"]).rstrip("/")
        resolved_api_key_env = str(api_key_env or config["api_key_env"]).strip() or DEFAULT_OPENKINETICS_API_KEY_ENV
        resolved_timeout = int(timeout_seconds or config["timeout_seconds"])

        self.base_url = resolved_base_url
        self.api_key = (api_key if api_key is not None else config["api_key"]) or None
        self.api_key_env = resolved_api_key_env
        self.timeout_seconds = resolved_timeout
        self.session = session or requests.Session()

    def _require_api_key(self) -> str:
        return resolve_api_key(api_key=self.api_key, api_key_env=self.api_key_env)

    def _request(self, method: str, path: str, *, json_payload: Any | None = None) -> Any:
        api_key = self._require_api_key()
        response = self.session.request(
            method=method,
            url=f"{self.base_url}{path}",
            json=json_payload,
            timeout=self.timeout_seconds,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        if response.status_code >= 400:
            raise OpenKineticsAPIError(
                f"OpenKinetics API request failed: {response.status_code} {response.text[:200]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise OpenKineticsAPIError("OpenKinetics API returned a non-JSON response") from exc

    def list_methods(self) -> Any:
        return self._request("GET", OPENKINETICS_ENDPOINTS["methods"])

    def validate(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", OPENKINETICS_ENDPOINTS["validate"], json_payload=payload)

    def submit(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", OPENKINETICS_ENDPOINTS["submit"], json_payload=payload)

    def validate_file(
        self,
        csv_path: str | Path,
        *,
        run_similarity: bool = False,
    ) -> Any:
        api_key = self._require_api_key()
        with Path(csv_path).open("rb") as handle:
            response = self.session.post(
                f"{self.base_url}{OPENKINETICS_ENDPOINTS['validate']}",
                timeout=self.timeout_seconds,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
                files={"file": handle},
                data={"runSimilarity": "true" if run_similarity else "false"},
            )
        if response.status_code >= 400:
            raise OpenKineticsAPIError(
                f"OpenKinetics API request failed: {response.status_code} {response.text[:200]}"
            )
        return response.json()

    def get_status(self, job_id: str) -> Any:
        return self._request("GET", OPENKINETICS_ENDPOINTS["status"].format(job_id=job_id))

    def get_result(self, job_id: str) -> Any:
        path = OPENKINETICS_ENDPOINTS["result"].format(job_id=job_id)
        return self._request("GET", f"{path}?format=json")

    def poll_until_complete(
        self,
        job_id: str,
        *,
        poll_interval_seconds: int = DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS,
        timeout_seconds: int = DEFAULT_OPENKINETICS_TIMEOUT_SECONDS,
    ) -> list[Any]:
        started = time.monotonic()
        responses: list[Any] = []
        while True:
            status_payload = self.get_status(job_id)
            responses.append(status_payload)

            top_level_status = str(status_payload.get("status", "")).strip().lower()
            if top_level_status == "completed":
                return responses
            if top_level_status in {"failed", "error"}:
                raise OpenKineticsAPIError(f"OpenKinetics job {job_id} failed: {status_payload}")

            status_value = json.dumps(status_payload).lower()
            if '"status": "completed"' in status_value:
                return responses
            if '"status": "failed"' in status_value or '"status": "error"' in status_value:
                raise OpenKineticsAPIError(f"OpenKinetics job {job_id} failed: {status_payload}")

            if time.monotonic() - started > timeout_seconds:
                raise OpenKineticsTimeoutError(f"Timed out while waiting for OpenKinetics job {job_id}")
            time.sleep(poll_interval_seconds)


class OpenKineticsClient(OpenKineticsFixtureCollectorClient):
    """Lightweight client for the OpenKinetics Predictor REST API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_env: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        config = load_openkinetics_config()
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            api_key_env=api_key_env,
            timeout_seconds=timeout_seconds,
            session=session,
        )
        self.max_retries = int(max_retries or config["max_retries"])

    @staticmethod
    def _normalize_score_variants_input(
        variants: list[str] | list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        normalized_rows: list[dict[str, str]] = []
        for index, variant in enumerate(variants):
            if isinstance(variant, str):
                normalized_rows.append(
                    {
                        "variant_id": f"variant_{index}",
                        "mutation": "",
                        "protein_sequence": variant,
                    }
                )
                continue

            if not isinstance(variant, dict):
                raise OpenKineticsValidationError("Each variant must be a protein sequence string or a mapping")

            sequence = (
                variant.get("protein_sequence")
                or variant.get("Protein Sequence")
                or variant.get("sequence")
            )
            if not sequence:
                raise OpenKineticsValidationError("Each variant row must include protein_sequence")

            normalized_rows.append(
                {
                    "variant_id": str(variant.get("variant_id", f"variant_{index}")),
                    "mutation": str(variant.get("mutation", "")),
                    "protein_sequence": str(sequence),
                }
            )
        if not normalized_rows:
            raise OpenKineticsValidationError("At least one variant row is required")
        return normalized_rows

    def validate(
        self,
        rows: list[dict[str, Any]],
        *,
        run_similarity: bool = False,
    ) -> dict[str, Any]:
        normalized_rows = self._normalize_score_variants_input(rows)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            write_csv_rows(
                temp_path,
                [
                    {
                        "Protein Sequence": row["protein_sequence"],
                        "Substrate": str(row.get("Substrate", row.get("substrate_smiles", ""))),
                    }
                    for row in rows
                ],
            )
            return self.validate_file(temp_path, run_similarity=run_similarity)
        finally:
            temp_path.unlink(missing_ok=True)

    def submit(
        self,
        rows: list[dict[str, Any]],
        method: str,
        prediction_type: str,
        *,
        handle_long_sequences: str = "truncate",
        use_experimental: bool = True,
        include_similarity_columns: bool = True,
        canonicalize_substrates: bool = True,
    ) -> str:
        if not rows:
            raise OpenKineticsValidationError("At least one row is required for submission")
        methods_response = self.list_methods()
        method_metadata = get_method_metadata(
            methods_response,
            method=method,
            prediction_type=prediction_type,
        )
        payload = build_openkinetics_request_payload(
            data_rows=[
                {
                    "Protein Sequence": str(row["Protein Sequence"]),
                    "Substrate": str(row["Substrate"]),
                }
                for row in rows
            ],
            method_metadata=method_metadata,
            method=method,
            prediction_type=prediction_type,
        )
        payload["handleLongSequences"] = handle_long_sequences
        payload["useExperimental"] = use_experimental
        payload["includeSimilarityColumns"] = include_similarity_columns
        payload["canonicalizeSubstrates"] = canonicalize_substrates

        submit_response = self._request("POST", OPENKINETICS_ENDPOINTS["submit"], json_payload=payload)
        job_id = (
            submit_response.get("jobId")
            or submit_response.get("job_id")
            or submit_response.get("id")
            or submit_response.get("job")
        )
        if not job_id:
            raise OpenKineticsValidationError("Submit response did not contain a job identifier")
        return str(job_id)

    def get_status(self, job_id: str) -> dict[str, Any]:
        return super().get_status(job_id)

    def get_result(self, job_id: str, result_format: str = "json") -> dict[str, Any] | str:
        path = OPENKINETICS_ENDPOINTS["result"].format(job_id=job_id)
        if result_format == "json":
            return self._request("GET", f"{path}?format=json")
        if result_format == "csv":
            api_key = self._require_api_key()
            response = self.session.get(
                f"{self.base_url}{path}",
                timeout=self.timeout_seconds,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "text/csv",
                },
            )
            if response.status_code >= 400:
                raise OpenKineticsAPIError(
                    f"OpenKinetics API request failed: {response.status_code} {response.text[:200]}"
                )
            return response.text
        raise OpenKineticsValidationError(f"Unsupported result_format: {result_format!r}")


def _default_openkinetics_cache_dir() -> str:
    return os.path.expanduser(load_openkinetics_config()["cache_dir"])


def _stable_cache_key(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def write_normalized_scores_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    write_csv_rows(Path(path), rows)


class OpenKineticsScorerAbstract(ExternalDesignerAbstract, ABC):
    """External activity scorer using the OpenKinetics Predictor API."""

    installed = True
    scorer_only = True
    default_method = DEFAULT_OPENKINETICS_METHOD
    default_prediction_type = DEFAULT_OPENKINETICS_PREDICTION_TYPE

    @classmethod
    @abstractmethod
    def built_in_defaults(cls) -> dict[str, str]:
        """Return class-specific default method and prediction type."""

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
            default_prediction_type
            or class_defaults["prediction_type"]
            or config["default_prediction_type"]
        )
        self.prefer_lower = self.default_prediction_type.lower() == "km"
        self.poll_interval_seconds = int(poll_interval_seconds or config["poll_interval_seconds"])
        self.timeout_seconds = int(timeout_seconds or config["timeout_seconds"])
        self.cache_enabled = config["cache_enabled"] if cache_enabled is None else cache_enabled
        self.cache_dir = os.path.expanduser(cache_dir or config["cache_dir"])
        self.substrate_smiles = substrate_smiles
        self.initialized = False

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
            raise OpenKineticsConfigurationError(
                "OpenKinetics scoring requires a substrate SMILES string."
            )
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

    def _prepare_rows(
        self,
        variants: list[str] | list[dict[str, Any]],
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

        job_id = self.client.submit(
            api_rows,
            method=selected_method,
            prediction_type=selected_prediction_type,
        )
        if not wait:
            return {"job_id": job_id, "status": "submitted"}

        status_responses = self.client.poll_until_complete(
            job_id,
            poll_interval_seconds=self.poll_interval_seconds,
            timeout_seconds=self.timeout_seconds,
        )
        result_payload = self.client.get_result(job_id, result_format="json")
        if not isinstance(result_payload, dict):
            raise OpenKineticsValidationError("Expected JSON result payload")

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


class OpenKineticsScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": DEFAULT_OPENKINETICS_METHOD, "prediction_type": DEFAULT_OPENKINETICS_PREDICTION_TYPE}


class CataProKcatKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-CataPro-kcat/Km"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "CataPro", "prediction_type": "kcat/Km"}


class UniKPKcatScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-UniKP-kcat"

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "UniKP", "prediction_type": "kcat"}


class UniKPKmScorer(OpenKineticsScorerAbstract):
    name = "OpenKinetics-UniKP-Km"
    prefer_lower = True

    @classmethod
    def built_in_defaults(cls) -> dict[str, str]:
        return {"method": "UniKP", "prediction_type": "Km"}


def _build_fixture_paths(output_dir: str | Path) -> OpenKineticsFixturePaths:
    root = Path(output_dir)
    return OpenKineticsFixturePaths(
        output_dir=root,
        manifest_path=root / "manifest.json",
        readme_path=root / "README.md",
        input_variants_path=root / "input_variants.csv",
        api_input_path=root / "api_input.csv",
        substrate_path=root / "substrate.json",
    )


def _write_fixture_readme(paths: OpenKineticsFixturePaths, manifest: dict[str, Any]) -> None:
    lines = [
        "# OpenKinetics 1SUO Fixture",
        "",
        "This directory is produced by `scripts/dev/collect_openkinetics_fixtures.py`.",
        "",
        f"- Structure: `{manifest['source_structure_id']}`",
        f"- Mutation source: `{manifest['source_mutation_file']}`",
        f"- Ligand identifier: `{manifest['ligand_identifier']}`",
        f"- Substrate SMILES: `{manifest['substrate_smiles']}`",
        f"- Method: `{manifest['openkinetics_method']}`",
        f"- Prediction type: `{manifest['prediction_type']}`",
        f"- API base URL: `{manifest['api_base_url']}`",
        f"- Collected at: `{manifest['collected_at_utc']}`",
        f"- Mutation count: `{manifest['number_of_mutations_parsed']}`",
        f"- Variant count: `{manifest['number_of_variants_submitted']}`",
        "",
        "Notes:",
        "- API keys and Authorization headers are never stored here.",
        "- The CPZ substrate uses a manually verified chlorpromazine SMILES fallback because direct PDB-to-SMILES conversion is not chemically reliable for this ligand.",
        f"- Schema assumption: {manifest['schema_assumption_note']}",
    ]
    if manifest.get("fixture_status") == "stale_partial_live_result":
        lines.extend(
            [
                f"- Fixture status: `{manifest['fixture_status']}`",
                "- The checked-in live prediction files still cover only a limited subset.",
                "- Regenerate the full live fixture with `export OPENKINETICS_API_KEY=\"...\" && python scripts/dev/collect_openkinetics_fixtures.py --overwrite`.",
            ]
        )
    paths.readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_openkinetics_fixture_dataset(
    *,
    mutation_path: str | Path,
    pdb_path: str | Path,
    output_dir: str | Path,
    chain_id: str = "A",
    structure_id: str = "1SUO",
    base_url: str = DEFAULT_OPENKINETICS_BASE_URL,
    api_key_env: str = DEFAULT_OPENKINETICS_API_KEY_ENV,
    method: str = DEFAULT_OPENKINETICS_METHOD,
    prediction_type: str = DEFAULT_OPENKINETICS_PREDICTION_TYPE,
    poll_interval_seconds: int = DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS,
    timeout_seconds: int = DEFAULT_OPENKINETICS_TIMEOUT_SECONDS,
    overwrite: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    paths = _build_fixture_paths(output_dir)
    if paths.output_dir.exists():
        if not overwrite:
            raise OpenKineticsConfigurationError(
                f"{paths.output_dir} already exists. Pass --overwrite to replace it."
            )
        shutil.rmtree(paths.output_dir)
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    _, wt_sequence, residue_numbers = load_chain_sequence_context(pdb_path, chain_id=chain_id)
    mutation_labels = load_mutation_labels(mutation_path, limit=limit)
    if not mutation_labels:
        raise OpenKineticsValidationError(f"No mutation labels found in {mutation_path}")

    substrate_metadata = resolve_substrate_metadata(pdb_path, structure_id=structure_id)
    variant_rows = build_variant_rows(wt_sequence, residue_numbers, mutation_labels, chain_id=chain_id)
    local_rows = normalize_variant_rows_for_local_table(variant_rows, substrate_metadata["substrate_smiles"])
    api_data_rows = build_openkinetics_data_rows(variant_rows, substrate_metadata["substrate_smiles"])

    write_csv_rows(paths.input_variants_path, local_rows)
    write_csv_rows(paths.api_input_path, api_data_rows)
    write_json(paths.substrate_path, substrate_metadata)

    manifest = {
        "api_base_url": base_url,
        "collected_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "openkinetics_method": method,
        "prediction_type": prediction_type,
        "source_mutation_file": str(Path(mutation_path)),
        "source_structure_id": structure_id,
        "source_pdb_file": str(Path(pdb_path)),
        "ligand_identifier": substrate_metadata["ligand_identifier"],
        "substrate_smiles": substrate_metadata["substrate_smiles"],
        "ligand_id": substrate_metadata["ligand_residue_name"],
        "collection_limited": limit is not None,
        "number_of_mutations_parsed": len(mutation_labels),
        "number_of_variants_submitted": len(local_rows),
        "input_hash": sha256_file(paths.input_variants_path),
        "result_hash": None,
        "normalized_input_table_sha256": sha256_file(paths.input_variants_path),
        "raw_result_sha256": None,
        "python_version": _python_version(),
        "revodesign_commit_hash": _git_commit_hash(repo_root),
        "api_key_policy": f"Read from YAML api_key or environment variable {api_key_env} and never stored",
        "schema_assumption_note": OPENKINETICS_DOCS_ASSUMPTION,
        "dry_run": dry_run,
        "secrets_policy": "Authorization headers and API keys are redacted and never stored",
    }
    manifest["substrate_metadata_source"] = substrate_metadata["smiles_resolution"]

    if dry_run:
        api_payload = {
            "targets": [prediction_type],
            "methods": {prediction_type: method},
            "handleLongSequences": "truncate",
            "useExperimental": True,
            "includeSimilarityColumns": True,
            "canonicalizeSubstrates": True,
            "data": api_data_rows,
        }
        write_json(paths.manifest_path, manifest)
        _write_fixture_readme(paths, manifest)
        return {
            "manifest": manifest,
            "paths": {key: str(value) for key, value in paths.__dict__.items()},
            "api_payload": _redact_payload(api_payload),
        }

    client = OpenKineticsFixtureCollectorClient(
        base_url=base_url,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
    )

    methods_response = client.list_methods()
    write_json(paths.output_dir / "methods_response.json", _redact_payload(methods_response))
    method_metadata = get_method_metadata(
        methods_response,
        method=method,
        prediction_type=prediction_type,
    )

    api_payload = build_openkinetics_request_payload(
        data_rows=api_data_rows,
        method_metadata=method_metadata,
        method=method,
        prediction_type=prediction_type,
    )

    validate_response = client.validate_file(paths.api_input_path, run_similarity=False)
    write_json(
        paths.output_dir / "validate_request.redacted.json",
        {
            "file": paths.api_input_path.name,
            "runSimilarity": False,
            "file_sha256": sha256_file(paths.api_input_path),
        },
    )
    write_json(paths.output_dir / "validate_response.json", _redact_payload(validate_response))

    submit_response = client.submit(api_payload)
    write_json(paths.output_dir / "submit_request.redacted.json", _redact_payload(api_payload))
    write_json(paths.output_dir / "submit_response.json", _redact_payload(submit_response))

    job_id = (
        submit_response.get("jobId")
        or submit_response.get("job_id")
        or submit_response.get("id")
        or submit_response.get("job")
    )
    if not job_id:
        raise OpenKineticsValidationError("Submit response did not contain a job identifier")

    status_responses = client.poll_until_complete(
        job_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
    )
    write_json(paths.output_dir / "status_responses.json", _redact_payload(status_responses))

    result_response = client.get_result(job_id)
    write_json(paths.output_dir / "result_response.json", _redact_payload(result_response))
    write_json(paths.output_dir / "raw_result.json", _redact_payload(result_response))

    normalized_scores = _normalize_result_rows(
        result_response,
        method=method,
        prediction_type=prediction_type,
        substrate_smiles=substrate_metadata["substrate_smiles"],
        variant_rows=local_rows,
        job_id=job_id,
    )
    normalized_scores_path = paths.output_dir / "normalized_scores.csv"
    write_csv_rows(normalized_scores_path, normalized_scores)

    manifest["raw_result_sha256"] = sha256_file(paths.output_dir / "raw_result.json")
    manifest["result_hash"] = manifest["raw_result_sha256"]
    manifest["job_id"] = job_id
    write_json(paths.manifest_path, manifest)
    _write_fixture_readme(paths, manifest)

    return {
        "manifest": manifest,
        "paths": {key: str(value) for key, value in paths.__dict__.items()},
        "job_id": job_id,
    }
