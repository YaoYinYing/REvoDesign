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

### API Key Auto-Registration

API key management is handled automatically by default. When
`OpenKineticsScorerAbstract` is initialized (with `auto_register_api_key=True`,
the default), the following happens:

1. `resolve_api_key()` checks for an existing key in the `OPENKINETICS_API_KEY`
   environment variable.
2. If no key is found, `fetch_openkinetics_api_key()` auto-generates a new key
   by POST to `/api-key/generate/` on the OpenKinetics service.
3. `persist_openkinetics_api_key()` saves the new key to `environ.yaml` and
   registers it into `os.environ` immediately -- **no restart is needed**.

Once the key is registered, the OpenKinetics predictors will appear in the
scorer dropdown.

### Manual Key Setup (Fallback)

You can still set the key manually under the `variables` section of the living
`environ.yaml` file. **Do not store the key in `main.yaml`.**

The living file location depends on your OS. On macOS it is typically:

```
~/Library/Application Support/REvoDesign/config/environ.yaml
```

Example entry:

```yaml
variables:
  OPENKINETICS_API_KEY: your-openkinetics-api-key
```

After manual setup, restart PyMOL (or reload the plugin) for the key to take
effect.

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

The OpenKinetics integration uses three API endpoints in sequence:

1. **Submission** — POST a JSON payload containing `targets`, `methods`, and
   `data` to `/api/v1/submit/` to start a prediction job.
2. **Status** — Poll `/api/v1/status/<job_id>/` for job progress (queued,
   running, completed, or failed).
3. **Results** — Fetch `/api/v1/result/<job_id>/?format=json` for the
   prediction output once the job completes.

## API Reference

For the full API documentation, including all endpoints, request/response
schemas, and error codes, see the [OpenKinetics API Reference](../api/openkinetics.md).
