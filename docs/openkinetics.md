# OpenKinetics

OpenKinetics support is being added as an optional API-based activity scorer.

- It is intended to call the remote OpenKinetics Predictor service.
- It does not bundle CataPro, UniKP, PyTorch, or local model weights.
- The runtime scorer now lives under `src/REvoDesign/magician/designers/openkinetics.py`.
- It is registered as a magician scorer through `ExternalDesignerAbstract`.
- Credentials can be provided directly in `src/REvoDesign/config/main.yaml` as `scorers.openkinetics.api_key`.
- `OPENKINETICS_API_KEY` remains the fallback when the YAML key is empty.
- The manual real-fixture collection entry point is `scripts/dev/collect_openkinetics_fixtures.py`.
- Real fixture data belongs under `tests/data/kinetics`.
- Ordinary tests should use mocked fixture files and must not call the real service.

Example manual collection command:

```bash
export OPENKINETICS_API_KEY="..."
python scripts/dev/collect_openkinetics_fixtures.py --overwrite
```

The current 1SUO collector derives:

- WT plus point-mutant protein sequences from `tests/data/mutations/1SUO.surf.entro.mutagenesis.besthits.mut.txt`
- the non-heme ligand `CPZ` from `tests/data/pdb/1SUO.pdb`
- a substrate SMILES string using an auditable manual fallback when direct PDB-to-SMILES conversion is not chemically reliable

The checked-in fixture currently contains all 16 input variants locally, but if `tests/data/kinetics/openkinetics_1SUO/manifest.json` reports `fixture_status: stale_partial_live_result`, the checked-in live prediction rows still come from an earlier limited API run. Refresh that dataset with:

```bash
export OPENKINETICS_API_KEY="..."
python scripts/dev/collect_openkinetics_fixtures.py --overwrite
```

The live fixture collected in this repository currently shows:

- validation is done with a CSV upload to `/api/v1/validate/`
- submission can use inline JSON to `/api/v1/submit/`
- the JSON submit shape includes `targets`, `methods`, and `data`
- results can be fetched from `/api/v1/result/<job_id>/?format=json`

Runner example for a small mutant table:

```bash
python scripts/dev/score_openkinetics_variants.py \
  --input-csv variants.csv \
  --output-csv openkinetics_scores.csv \
  --substrate-smiles "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21"
```

The scorer script reads `scorers.openkinetics.api_key` from YAML first. Use `OPENKINETICS_API_KEY` only when you prefer environment-based secrets or leave the YAML key empty.

Expected input CSV columns for the runner:

- `protein_sequence` or `Protein Sequence`
- optional `variant_id`
- optional `mutation`
