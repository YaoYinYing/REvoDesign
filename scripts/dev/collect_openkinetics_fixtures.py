#!/usr/bin/env python3
"""Collect a small permanent OpenKinetics fixture dataset for 1SUO."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
MODULE_PATH = SRC_DIR / "REvoDesign" / "evaluate" / "openkinetics.py"


def _load_openkinetics_module():
    spec = importlib.util.spec_from_file_location("revodesign_openkinetics", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load OpenKinetics module from {MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


openkinetics = _load_openkinetics_module()


DEFAULT_MUTATION_PATH = REPO_ROOT / "tests" / "data" / "mutations" / "1SUO.surf.entro.mutagenesis.besthits.mut.txt"
DEFAULT_PDB_PATH = REPO_ROOT / "tests" / "data" / "pdb" / "1SUO.pdb"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tests" / "data" / "kinetics" / "openkinetics_1SUO"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutation-path", default=str(DEFAULT_MUTATION_PATH))
    parser.add_argument("--pdb-path", default=str(DEFAULT_PDB_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--chain-id", default="A")
    parser.add_argument("--structure-id", default="1SUO")
    parser.add_argument("--base-url", default=openkinetics.DEFAULT_OPENKINETICS_BASE_URL)
    parser.add_argument("--api-key-env", default=openkinetics.DEFAULT_OPENKINETICS_API_KEY_ENV)
    parser.add_argument("--method", default=openkinetics.DEFAULT_OPENKINETICS_METHOD)
    parser.add_argument("--prediction-type", default=openkinetics.DEFAULT_OPENKINETICS_PREDICTION_TYPE)
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=openkinetics.DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=openkinetics.DEFAULT_OPENKINETICS_TIMEOUT_SECONDS,
    )
    parser.add_argument("--limit", type=int, default=4, help="Number of mutant rows to include alongside WT.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    print(f"[openkinetics] output_dir={args.output_dir}")
    print(f"[openkinetics] mutation_path={args.mutation_path}")
    print(f"[openkinetics] pdb_path={args.pdb_path}")
    print(f"[openkinetics] dry_run={args.dry_run}")

    try:
        result = openkinetics.collect_openkinetics_fixture_dataset(
            mutation_path=args.mutation_path,
            pdb_path=args.pdb_path,
            output_dir=args.output_dir,
            chain_id=args.chain_id,
            structure_id=args.structure_id,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            method=args.method,
            prediction_type=args.prediction_type,
            poll_interval_seconds=args.poll_interval_seconds,
            timeout_seconds=args.timeout_seconds,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    except openkinetics.OpenKineticsError as exc:
        print(f"[openkinetics] error: {exc}", file=sys.stderr)
        return 1

    print("[openkinetics] complete")
    print(json.dumps(result["manifest"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
