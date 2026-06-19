# OpenKinetics

OpenKinetics support is being added as an optional API-based activity scorer.

- It is intended to call the remote OpenKinetics Predictor service.
- It does not bundle CataPro, UniKP, PyTorch, or local model weights.
- Credentials must be provided through `OPENKINETICS_API_KEY`.
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
- a substrate SMILES string using an auditable manual fallback when direct PDB-to-SMILES conversion is not robust

The live fixture collected in this repository currently shows:

- validation is done with a CSV upload to `/api/v1/validate/`
- submission can use inline JSON to `/api/v1/submit/`
- the JSON submit shape includes `targets`, `methods`, and `data`
- results can be fetched from `/api/v1/result/<job_id>/?format=json`

Runner example for a small mutant table:

```bash
export OPENKINETICS_API_KEY="..."
python scripts/dev/score_openkinetics_variants.py \
  --input-csv variants.csv \
  --output-csv openkinetics_scores.csv \
  --substrate-smiles "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21"
```

Expected input CSV columns for the runner:

- `protein_sequence` or `Protein Sequence`
- optional `variant_id`
- optional `mutation`
