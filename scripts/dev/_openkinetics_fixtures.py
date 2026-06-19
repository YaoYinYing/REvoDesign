# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Manual fixture-collection workflow for the OpenKinetics API.

This module is only used by the developer script
``scripts/dev/collect_openkinetics_fixtures.py`` — the scoring path
does **not** depend on it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from REvoDesign.magician.designers.openkinetics import (
    OPENKINETICS_DOCS_ASSUMPTION,
    OPENKINETICS_ENDPOINTS,
    DEFAULT_OPENKINETICS_API_KEY_ENV,
    DEFAULT_OPENKINETICS_BASE_URL,
    DEFAULT_OPENKINETICS_METHOD,
    DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS,
    DEFAULT_OPENKINETICS_PREDICTION_TYPE,
    DEFAULT_OPENKINETICS_TIMEOUT_SECONDS,
    OpenKineticsClient,
    OpenKineticsConfigurationError,
    OpenKineticsFixturePaths,
    OpenKineticsValidationError,
    _normalize_result_rows,
    build_openkinetics_data_rows,
    build_openkinetics_request_payload,
    get_method_metadata,
    load_chain_sequence_context,
    load_mutation_labels,
    normalize_variant_rows_for_local_table,
    relabel_pdb_position_to_sequential,
    resolve_substrate_metadata,
    sha256_file,
    write_csv_rows,
    write_json,
)
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _git_commit_hash(repo_root: Path) -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, text=True
            ).strip()
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


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


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
        "- Substrate SMILES are resolved via RDKit PDB-to-SMILES conversion.",
        f"- Schema assumption: {manifest['schema_assumption_note']}",
    ]
    if manifest.get("fixture_status") == "stale_partial_live_result":
        lines.extend(
            [
                f"- Fixture status: `{manifest['fixture_status']}`",
                "- The checked-in live prediction files cover only a limited subset of variants.",
                "- Regenerate the full live fixture with "
                '`export OPENKINETICS_API_KEY="..." && python scripts/dev/collect_openkinetics_fixtures.py --overwrite`.',
            ]
        )
    paths.readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main collection entry point
# ---------------------------------------------------------------------------


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
    repo_root = Path(__file__).resolve().parents[2]
    paths = _build_fixture_paths(output_dir)
    if paths.output_dir.exists():
        if not overwrite:
            raise OpenKineticsConfigurationError(f"{paths.output_dir} already exists. Pass --overwrite to replace it.")
        shutil.rmtree(paths.output_dir)
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    # Load wild-type sequence and residue numbering from the PDB file.
    wt_sequences, wt_sequence, residue_numbers = load_chain_sequence_context(pdb_path, chain_id=chain_id)

    # Read mutation labels from the mutation file.
    mutation_labels = load_mutation_labels(mutation_path, limit=limit)
    if not mutation_labels:
        raise OpenKineticsValidationError(f"No mutation labels found in {mutation_path}")

    # Resolve substrate SMILES from the PDB ligand.
    substrate_metadata = resolve_substrate_metadata(pdb_path, structure_id=structure_id)

    # Build variant rows via mutant_tools for mutation parsing and
    # Mutant.mutated_sequence for variant sequences.  Mutation labels use PDB
    # residue numbering which may be non-contiguous, so we convert to
    # sequential positions before parsing.
    variant_rows: list[dict[str, str]] = [{"variant_id": "WT", "mutation": "WT", "protein_sequence": wt_sequence}]
    for label in mutation_labels:
        seq_label = relabel_pdb_position_to_sequential(label, residue_numbers, chain_id=chain_id)
        mutant = extract_mutants_from_mutant_id(seq_label, wt_sequences)
        variant_seq = mutant.mutated_sequence.get_sequence_by_chain(chain_id=chain_id)
        variant_rows.append(
            {
                "variant_id": label,
                "mutation": label,
                "protein_sequence": variant_seq,
            }
        )

    local_rows = normalize_variant_rows_for_local_table(variant_rows, substrate_metadata["substrate_smiles"])
    api_data_rows = build_openkinetics_data_rows(variant_rows, substrate_metadata["substrate_smiles"])

    write_csv_rows(paths.input_variants_path, local_rows)
    write_csv_rows(paths.api_input_path, api_data_rows)
    write_json(paths.substrate_path, substrate_metadata)

    manifest: dict[str, Any] = {
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
        "python_version": _python_version(),
        "revodesign_commit_hash": _git_commit_hash(repo_root),
        "api_key_policy": f"Read from YAML api_key or environment variable {api_key_env} and never stored",
        "schema_assumption_note": OPENKINETICS_DOCS_ASSUMPTION,
        "dry_run": dry_run,
        "secrets_policy": "Authorization headers and API keys are redacted and never stored",
        "substrate_metadata_source": substrate_metadata["smiles_resolution"],
    }

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

    client = OpenKineticsClient(
        base_url=base_url,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
    )

    methods_response = client.list_methods()
    write_json(paths.output_dir / "methods_response.json", _redact_payload(methods_response))
    method_metadata = get_method_metadata(methods_response, method=method, prediction_type=prediction_type)

    api_payload = build_openkinetics_request_payload(
        data_rows=api_data_rows,
        method_metadata=method_metadata,
        method=method,
        prediction_type=prediction_type,
    )

    validate_response = client.validate_file(paths.api_input_path, run_similarity=False)
    write_json(paths.output_dir / "validate_response.json", _redact_payload(validate_response))

    submit_response = client._request("POST", OPENKINETICS_ENDPOINTS["submit"], json_payload=api_payload)
    write_json(paths.output_dir / "submit_response.json", _redact_payload(submit_response))
    job_id = submit_response.get("jobId")
    if not job_id:
        raise OpenKineticsValidationError("Submit response did not contain a job identifier (jobId)")

    status_responses = client.poll_until_complete(
        job_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
    )
    write_json(paths.output_dir / "status_responses.json", _redact_payload(status_responses))

    result_response = client.get_result(job_id)
    write_json(paths.output_dir / "result_response.json", _redact_payload(result_response))

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

    manifest["result_hash"] = sha256_file(paths.output_dir / "result_response.json")
    manifest["job_id"] = job_id
    write_json(paths.manifest_path, manifest)
    _write_fixture_readme(paths, manifest)

    return {
        "manifest": manifest,
        "paths": {key: str(value) for key, value in paths.__dict__.items()},
        "job_id": job_id,
    }
