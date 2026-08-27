# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Run minimal canonical-edge living tests for enabled REvoCompute task types.

This is an operator test, not part of pytest. It submits real work and keeps a
resumable JSON record. Authentication is read from a mode-0600 token file.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]

CASES = {
    "gremlin": ("tests/data/msa/2KL8.fasta", "2KL8.fasta", {"iter": 1, "maxfilt": 1000, "neffmax": 5}),
    "pythia_ddg": ("tests/data/pdb/2KL8.pdb", "2KL8.pdb", {}),
    "esm_msa": ("tests/data/msa/2KL8.i90c75_aln.fas", "2KL8.a3m", {"msa_samples": 1}),
    "esm_extract": (
        "tests/data/msa/2KL8.fasta",
        "2KL8.fasta",
        {"model": "esm2_t6_8M_UR50D", "repr_layers": "6", "include": "mean contacts", "toks_per_batch": 128},
    ),
    "esm_1v": ("tests/data/msa/2KL8.fasta", "2KL8.fasta", {}),
    "esm_if1": ("tests/data/pdb/2KL8.pdb", "2KL8.pdb", {"num_samples": 1, "chain": "A"}),
    "esmdynamic": (
        "tests/data/msa/2KL8.fasta",
        "2KL8.fasta",
        {"batch_size": 1, "chunk_size": 64, "num_recycles": 1},
    ),
    "opendde": (
        "tests/data/json/opendde_tiny.json",
        "tiny.json",
        {"num_samples": 1, "num_steps": 10, "num_cycles": 1, "use_msa": False, "use_template": False},
    ),
    "hypermpnn": ("tests/data/pdb/2KL8.pdb", "2KL8.pdb", {"num_seq_per_target": 1}),
    "proteinmpnn": ("tests/data/pdb/2KL8.pdb", "2KL8.pdb", {"num_seq_per_target": 1}),
    "solublempnn": ("tests/data/pdb/2KL8.pdb", "2KL8.pdb", {"num_seq_per_target": 1}),
    "ligandmpnn": (
        "tests/data/pdb/3fap_hf3_A_short_lig.pdb",
        "3fap_lig.pdb",
        {"number_of_batches": 1, "batch_size": 1, "pack_side_chains": 0},
    ),
    "lasermpnn": (
        "tests/data/pdb/2KL8.pdb",
        "2KL8.pdb",
        {"designs_per_input": 1, "designs_per_batch": 1},
    ),
    "thermompnn": ("tests/data/pdb/2KL8.pdb", "2KL8.pdb", {"chains": "A", "batch_size": 16}),
    "prime": ("tests/data/msa/2KL8.fasta", "2KL8.fasta", {}),
    "prime_dms": ("tests/data/msa/2KL8.fasta", "2KL8.fasta", {}),
    "rfdiffusion": (
        "tests/data/pdb/2KL8.pdb",
        "2KL8.pdb",
        {"num_designs": 1, "diffuser_T": 15},
    ),
    "placer": (
        "tests/data/pdb/3fap_hf3_A_short_lig.pdb",
        "3fap_lig.pdb",
        {"num_samples": 1, "predict_ligand": "lig", "rerank": "plddt_pde"},
    ),
    "bioemu": ("tests/data/msa/2KL8.fasta", "2KL8.fasta", {"num_samples": 1, "batch_size_100": 1}),
    "easifa": ("tests/data/pdb/2KL8.pdb", "2KL8.pdb", {"max_length": 100}),
    "freebindcraft": (
        "tests/data/freebindcraft/test_target.pdb",
        "test_target.pdb",
        {
            "length_min": 65,
            "length_max": 65,
            "number_of_final_designs": 1,
            "filters_preset": "no_filters",
            "max_trajectories": 1,
        },
    ),
    "alphafold": (
        "tests/data/msa/2KL8.fasta",
        "2KL8.fasta",
        {"model_preset": "monomer_ptm", "models_to_relax": "none"},
    ),
    "colabfold_af2": (
        "tests/data/msa/2KL8.fasta",
        "2KL8.fasta",
        {
            "model_type": "alphafold2_ptm",
            "msa_mode": "single_sequence",
            "num_recycle": 0,
            "num_models": 1,
            "num_relax": 0,
        },
    ),
}

WORKSPACES = {
    "rfdiffusion": {
        "version": 2,
        "capabilities": {
            "design_regions": {
                "mode": "unconditional",
                "segments": [{"kind": "generated", "min_length": 30, "max_length": 30}],
                "hotspots": [],
            }
        },
    }
}


def save(path: Path, state: dict) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def form_value(value: object) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


def poll_payload(response: requests.Response) -> dict | None:
    if response.status_code not in {200, 202, 404}:
        return None
    try:
        payload = response.json()
    except requests.JSONDecodeError:
        return None
    return payload if response.status_code != 404 or payload.get("status") == "failed" else None


def submit(session: requests.Session, base_url: str, name: str) -> str:
    relative_path, upload_name, params = CASES[name]
    path = REPO_ROOT / relative_path
    with path.open("rb") as handle:
        response = session.post(
            f"{base_url}/compute/api/post",
            files={"file": (upload_name, handle, "application/octet-stream")},
            data={
                "task_type": name,
                **({"workspace": json.dumps(WORKSPACES[name])} if name in WORKSPACES else {}),
                **{f"params[{key}]": form_value(value) for key, value in params.items()},
            },
            allow_redirects=False,
            timeout=60,
        )
    if response.status_code != 302:
        raise RuntimeError(f"{name} submission returned HTTP {response.status_code}: {response.text[:500]}")
    return response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]


def manifest_summary(manifest: dict) -> dict:
    artifacts = manifest.get("artifacts", [])
    return {
        "schema_version": manifest.get("schema_version"),
        "output_check": manifest.get("output_check"),
        "views": [
            {"id": view.get("id"), "plugin": view.get("plugin"), "sources": view.get("sources")}
            for view in manifest.get("views", [])
        ],
        "artifact_count": len(artifacts),
        "primary_artifacts": [artifact.get("path") for artifact in artifacts if artifact.get("role") == "primary"],
        "preview_kinds": sorted({artifact.get("preview") for artifact in artifacts if artifact.get("preview")}),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://revocompute.yaoyy.moe")
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, default=Path("/tmp/revocompute-live-matrix.json"))
    parser.add_argument("--types", default=",")
    parser.add_argument("--max-active", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=21600)
    args = parser.parse_args()

    selected = list(CASES) if args.types == "," else [name for name in args.types.split(",") if name]
    unknown = set(selected) - set(CASES)
    if unknown:
        parser.error(f"unknown task type(s): {', '.join(sorted(unknown))}")
    if not 1 <= args.max_active <= 5:
        parser.error("--max-active must be between 1 and 5")

    state = json.loads(args.state_file.read_text(encoding="utf-8")) if args.state_file.exists() else {"tasks": {}}
    tasks = state["tasks"]
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {args.token_file.read_text(encoding='utf-8').strip()}"
    started = time.monotonic()

    while True:
        active = {
            name: item
            for name, item in tasks.items()
            if name in selected and item.get("status") in {"pending", "queued", "running"}
        }
        pending = [name for name in selected if name not in tasks]
        while pending and len(active) < args.max_active:
            name = pending.pop(0)
            task_id = submit(session, args.base_url.rstrip("/"), name)
            tasks[name] = {"task_id": task_id, "status": "queued"}
            active[name] = tasks[name]
            save(args.state_file, state)
            print(f"SUBMITTED {name} {task_id}", flush=True)

        for name, item in list(active.items()):
            task_id = item["task_id"]
            response = session.get(f"{args.base_url}/compute/api/running/{task_id}", timeout=30)
            payload = poll_payload(response)
            if payload is None:
                print(f"POLL {name} HTTP {response.status_code}; retrying", flush=True)
                continue
            status = payload.get("status", "unknown")
            if status != item.get("status"):
                item["status"] = status
                save(args.state_file, state)
                print(f"STATUS {name} {status}", flush=True)
            if status not in {"finished", "failed", "cancelled"}:
                continue
            result = session.get(f"{args.base_url}/compute/api/results/{task_id}", timeout=30)
            if result.status_code == 200:
                item["manifest"] = manifest_summary(result.json())
            else:
                item["result_http"] = result.status_code
            save(args.state_file, state)
            print(f"DONE {name} {status} {json.dumps(item.get('manifest', {}), separators=(',', ':'))}", flush=True)

        if all(tasks.get(name, {}).get("status") in {"finished", "failed", "cancelled"} for name in selected):
            break
        if time.monotonic() - started > args.timeout:
            raise SystemExit("living-test matrix timed out; rerun with the same --state-file to resume")
        time.sleep(10)

    failed = [name for name in selected if tasks[name]["status"] != "finished"]
    print(f"SUMMARY total={len(selected)} failed={','.join(failed) or '-'} state={args.state_file}")
    raise SystemExit(bool(failed))


if __name__ == "__main__":
    main()
