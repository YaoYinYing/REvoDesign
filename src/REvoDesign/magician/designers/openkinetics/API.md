# OpenKinetics Predictor API

This package talks to the OpenKinetics Predictor service at:

```text
https://predictor.openkinetics.org/api/v1
```

This document is a local snapshot of the living API page at
`https://predictor.openkinetics.org/api-docs` and the public
`GET /api/v1/methods/` registry, checked on 2026-07-02. When the service
changes, update this file and the endpoint constants in `_models.py` together.

## Authentication

The API expects an API key on authenticated calls:

```http
Authorization: Bearer <OPENKINETICS_API_KEY>
Accept: application/json
```

REvoDesign reads the key from the `OPENKINETICS_API_KEY` environment variable.
For normal use, add it under `variables` in the living REvoDesign
`environ.yaml` and reload REvoDesign.

## Endpoints

| Method | Path | Purpose | REvoDesign client method |
| --- | --- | --- | --- |
| `GET` | `/health/` | Service health check | `check_health()` |
| `GET` | `/methods/` | Method registry grouped by prediction target | `list_methods()` |
| `GET` | `/quota/` | Account quota | `check_quota()` |
| `POST` | `/validate/` | Validate a CSV upload | `validate_file()` |
| `POST` | `/submit/` | Submit a prediction job | `submit()` |
| `GET` | `/status/{job_id}/` | Poll job status | `get_status()` |
| `GET` | `/result/{job_id}/` | Fetch completed results | `get_result()` |

The live page also shows example URLs such as
`/api/v1/status/aB3kX9z/` and `/api/v1/result/aB3kX9z/`.

## Input Rows

The single-substrate predictors used by REvoDesign send rows with these
columns:

```json
[
  {
    "Protein Sequence": "MST...",
    "Substrate": "CCO"
  }
]
```

`Protein Sequence` is the amino acid sequence. `Substrate` is a SMILES string.
REvoDesign keeps local `variant_id` and `mutation` fields outside the remote
payload and merges them back during result normalization.

## Method Registry

`GET /methods/` returns a JSON object with a `methods` mapping. Keys are
prediction targets and values are method metadata entries. REvoDesign uses each
entry's `id` when constructing the submit payload.

The public registry currently advertises these methods:

| Method | API targets | Required columns |
| --- | --- | --- |
| `CataPro` | `kcat`, `Km`, `kcat/Km` | `Protein Sequence`, `Substrate` |
| `CatPred` | `kcat`, `Km` | `Protein Sequence`, `Substrate` |
| `DLKcat` | `kcat` | `Protein Sequence`, `Substrate` |
| `EITLEM` | `kcat`, `Km` | `Protein Sequence`, `Substrate` |
| `IECata` | `kcat/Km` | `Protein Sequence`, `Substrate` |
| `KinForm-H` | `kcat`, `Km` | `Protein Sequence`, `Substrate` |
| `KinForm-L` | `kcat` | `Protein Sequence`, `Substrate` |
| `MMISA-KM` | `Km` | `Protein Sequence`, `Substrate` |
| `OmniESI` | `kcat`, `Km` | `Protein Sequence`, `Substrate` |
| `OmniESI-O2DENet` | `kcat`, `Km` | `Protein Sequence`, `Substrate` |
| `RealKcat` | `kcat`, `Km` | `Protein Sequence`, `Substrate` |
| `TurNup` | `kcat` | `Protein Sequence`, `Substrates`, `Products` |
| `UniKP` | `kcat`, `Km` | `Protein Sequence`, `Substrate` |

The scorer classes generated in `_scorers.py` mirror the single-substrate
subset used by REvoDesign. `OmniESI-O2DENet` is not currently wrapped. `TurNup`
is intentionally excluded because it requires full-reaction rows with
`Substrates` and `Products`, and REvoDesign currently provides only a single
substrate SMILES to this API path. TODO: add a full-reaction scorer path before
exposing `TurNup`.

## Validation

`POST /validate/` accepts multipart form data:

```text
file=<csv file>
runSimilarity=false
```

REvoDesign uses this for fixture collection and preflight validation. The
wrapper sends `runSimilarity` as the string `true` or `false`, matching the
live form contract.

## Submit

`POST /submit/` accepts JSON:

```json
{
  "data": [
    {
      "Protein Sequence": "MST...",
      "Substrate": "CCO"
    }
  ],
  "targets": ["kcat/Km"],
  "methods": {
    "kcat/Km": "CataPro"
  },
  "handleLongSequences": "truncate",
  "useExperimental": false,
  "includeSimilarityColumns": true,
  "canonicalizeSubstrates": true
}
```

`targets` is a list of requested prediction targets. `methods` maps each target
to one method id from `/methods/`. The client currently submits one target and
one method per scorer instance.

The expected response includes a job id:

```json
{
  "jobId": "aB3kX9z"
}
```

## Status

`GET /status/{job_id}/` returns the server-side state for the job. The living
page includes states such as `queued`, `running`, `completed`, and `failed`.
REvoDesign polls this endpoint until completion or timeout.

## Results

`GET /result/{job_id}/?format=json` returns a JSON table:

```json
{
  "jobId": "aB3kX9z",
  "columns": ["Protein Sequence", "Substrate", "kcat/Km"],
  "data": [
    {
      "Protein Sequence": "MST...",
      "Substrate": "CCO",
      "kcat/Km": 1.23
    }
  ]
}
```

REvoDesign locates the predicted value by first matching a column whose name
starts with the requested prediction target, then falling back to
`predicted_value` or the exact target name. `Km` results are marked
`lower_is_better`; `kcat` and `kcat/Km` results are marked `higher_is_better`.

`GET /result/{job_id}/` without `format=json` can be used for CSV output.
The REvoDesign client requests `Accept: text/csv` for that path.

## Error Codes

The living page documents these common failures:

| Status | Meaning |
| --- | --- |
| `400` | Bad request or invalid input |
| `401` | Missing or invalid API key |
| `403` | Account suspended |
| `404` | Job id not found |
| `405` | Wrong HTTP method |
| `409` | Results are not ready |
| `429` | Daily quota exceeded |
| `500` | Internal server error |

The client raises `OpenKineticsAPIError` for HTTP 4xx or 5xx responses and
`OpenKineticsValidationError` for locally detected shape mismatches.
