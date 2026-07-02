#!/usr/bin/env python3
"""Run the OpenKinetics scorer on a small CSV mutant table."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from REvoDesign.magician.designers.openkinetics._scorers import CataProKcatKmScorer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--substrate-smiles", required=True)
    parser.add_argument("--method", default="CataPro")
    parser.add_argument("--prediction-type", default="kcat/Km")
    parser.add_argument("--api-key")
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
    scorer = CataProKcatKmScorer(api_key=args.api_key)
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
