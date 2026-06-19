#!/usr/bin/env python3
"""Run the OpenKinetics scorer on a small CSV mutant table."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "src" / "REvoDesign" / "magician" / "designers" / "openkinetics.py"


def _load_openkinetics_module():
    spec = importlib.util.spec_from_file_location("revodesign_openkinetics_score", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load OpenKinetics module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


openkinetics = _load_openkinetics_module()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--substrate-smiles", required=True)
    parser.add_argument("--method", default=openkinetics.DEFAULT_OPENKINETICS_METHOD)
    parser.add_argument("--prediction-type", default=openkinetics.DEFAULT_OPENKINETICS_PREDICTION_TYPE)
    parser.add_argument("--api-key")
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--raw-result-json")
    parser.add_argument("--no-cache", action="store_true")
    return parser


def read_variants(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise RuntimeError(f"No rows found in {path}")
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scorer = openkinetics.OpenKineticsScorer(
        api_key=args.api_key,
        api_key_env=args.api_key_env,
    )
    variants = read_variants(args.input_csv)
    result = scorer.score_variants(
        variants,
        substrate_smiles=args.substrate_smiles,
        method=args.method,
        prediction_type=args.prediction_type,
        output_csv_path=args.output_csv,
        raw_result_path=args.raw_result_json,
        use_cache=not args.no_cache,
    )
    print(json.dumps({"job_id": result["job_id"], "rows": len(result["normalized_scores"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
