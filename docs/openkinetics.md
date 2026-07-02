# OpenKinetics

OpenKinetics support is being added as an optional API-based activity scorer.

- It is intended to call the remote OpenKinetics Predictor service.
- It does not bundle CataPro, UniKP, PyTorch, or local model weights.
- The runtime scorer now lives under `src/REvoDesign/magician/designers/openkinetics.py`.
- It is registered as a magician scorer through `ExternalDesignerAbstract`.
- Add `OPENKINETICS_API_KEY` under `variables` in the living REvoDesign `environ.yaml`, then reload REvoDesign to make the API-backed predictors usable.
- On macOS the living file is usually `~/Library/Application Support/REvoDesign/config/environ.yaml`.
- `main.yaml` does not store the API key; keep the secret in `environ.yaml`.
- The manual real-fixture collection entry point is `scripts/dev/collect_openkinetics_fixtures.py`.
- Real fixture data belongs under `tests/data/kinetics`.
- Ordinary tests should use mocked fixture files and must not call the real service.

Example `environ.yaml` entry:

```yaml
variables:
  OPENKINETICS_API_KEY: your-openkinetics-api-key
```

Example manual collection command after reload:

```bash
python scripts/dev/collect_openkinetics_fixtures.py --overwrite
```

The current 1SUO collector derives:

- WT plus point-mutant protein sequences from `tests/data/mutations/1SUO.surf.entro.mutagenesis.besthits.mut.txt`
- the non-heme ligand `CPZ` from `tests/data/pdb/1SUO.pdb`
- a substrate SMILES string using an auditable manual fallback when direct PDB-to-SMILES conversion is not chemically reliable

The checked-in fixture currently contains all 16 input variants locally, but if `tests/data/kinetics/openkinetics_1SUO/manifest.json` reports `fixture_status: stale_partial_live_result`, the checked-in live prediction rows still come from an earlier limited API run. After adding the key to the living `environ.yaml` and reloading REvoDesign, refresh that dataset with:

```bash
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

The scorer reads `OPENKINETICS_API_KEY` from the registered environment.

Expected input CSV columns for the runner:

- `protein_sequence` or `Protein Sequence`
- optional `variant_id`
- optional `mutation`
