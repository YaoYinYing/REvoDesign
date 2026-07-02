#!/usr/bin/env python3
"""Collect a small permanent OpenKinetics fixture dataset for 1SUO."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _openkinetics_fixtures import collect_openkinetics_fixture_dataset

from REvoDesign.magician.designers.openkinetics import (
    DEFAULT_OPENKINETICS_BASE_URL,
    DEFAULT_OPENKINETICS_METHOD,
    DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS,
    DEFAULT_OPENKINETICS_PREDICTION_TYPE,
    DEFAULT_OPENKINETICS_TIMEOUT_SECONDS,
    OpenKineticsError,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

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
    parser.add_argument("--base-url", default=DEFAULT_OPENKINETICS_BASE_URL)
    parser.add_argument("--method", default=DEFAULT_OPENKINETICS_METHOD)
    parser.add_argument("--prediction-type", default=DEFAULT_OPENKINETICS_PREDICTION_TYPE)
    parser.add_argument("--poll-interval-seconds", type=int, default=DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_OPENKINETICS_TIMEOUT_SECONDS)
    parser.add_argument(
        "--limit", type=int, default=None, help="Optional number of mutant rows to include alongside WT."
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    print(f"[openkinetics] output_dir={args.output_dir}")
    print(f"[openkinetics] mutation_path={args.mutation_path}")
    print(f"[openkinetics] pdb_path={args.pdb_path}")
    print(f"[openkinetics] dry_run={args.dry_run}")
    print(f"[openkinetics] limit={args.limit if args.limit is not None else 'all'}")

    try:
        result = collect_openkinetics_fixture_dataset(
            mutation_path=args.mutation_path,
            pdb_path=args.pdb_path,
            output_dir=args.output_dir,
            chain_id=args.chain_id,
            structure_id=args.structure_id,
            base_url=args.base_url,
            method=args.method,
            prediction_type=args.prediction_type,
            poll_interval_seconds=args.poll_interval_seconds,
            timeout_seconds=args.timeout_seconds,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    except OpenKineticsError as exc:
        print(f"[openkinetics] error: {exc}", file=sys.stderr)
        return 1

    print("[openkinetics] complete")
    print(json.dumps(result["manifest"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
