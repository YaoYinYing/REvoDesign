# OpenKinetics

OpenKinetics is an optional API-based activity predictor that scores mutant
libraries by predicting kinetic parameters (kcat, KM, etc.) for enzyme
variants. It is integrated into REvoDesign as a magician scorer via
`ExternalDesignerAbstract`.

## Prerequisites

- A valid OpenKinetics API key (obtained from the OpenKinetics service
  provider).
- Network access to the OpenKinetics Predictor API.

## Configuration

### 1. Set the API Key

Add your API key under the `variables` section of the living `environ.yaml`
file. **Do not store the key in `main.yaml`.**

The living file location depends on your OS. On macOS it is typically:

```
~/Library/Application Support/REvoDesign/config/environ.yaml
```

Example entry:

```yaml
variables:
  OPENKINETICS_API_KEY: your-openkinetics-api-key
```

### 2. Reload REvoDesign

Restart PyMOL (or reload the plugin) for the key to take effect. Once
loaded, the OpenKinetics predictors will appear in the scorer dropdown.

## Running Predictions

Use the `collect_openkinetics_fixtures.py` script to run batch predictions
on a set of variants:

```bash
python scripts/dev/collect_openkinetics_fixtures.py --overwrite
```

For a single run against a variant CSV file, use the runner script:

```bash
python scripts/dev/score_openkinetics_variants.py \
  --input-csv variants.csv \
  --output-csv openkinetics_scores.csv \
  --substrate-smiles "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21"
```

The scorer reads `OPENKINETICS_API_KEY` from the environment at runtime.

## Expected Input Format

The input CSV for the runner must contain the following columns:

| Column | Required | Description |
|---|---|---|
| `protein_sequence` or `Protein Sequence` | Yes | Full-length protein amino acid sequence of the variant |
| `variant_id` | No | Unique identifier for each variant |
| `mutation` | No | Human-readable mutation string (e.g. `A123V`) |

A minimal valid CSV has a single `protein_sequence` column with one sequence
per row.

## API Workflow

The OpenKinetics integration uses three API endpoints:

1. **Validation** — POST the CSV to `/api/v1/validate/` to check formatting
   and required fields.
2. **Submission** — POST a JSON payload containing `targets`, `methods`, and
   `data` to `/api/v1/submit/` to start a prediction job.
3. **Results** — Poll `/api/v1/result/<job_id>/?format=json` for the
   prediction output.

## API Reference

For the full API documentation, including all endpoints, request/response
schemas, and error codes, see the [OpenKinetics API Reference](../api/openkinetics.md).
