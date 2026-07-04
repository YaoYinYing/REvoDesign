# OpenKinetics API Reference

This page documents the OpenKinetics API-backed kinetic scorers. The package provides an HTTP client for the OpenKinetics Predictor REST API, a family of dynamically-created scorer classes registered with the Magician plugin system, and helpers for PDB ligand discovery and SMILES resolution.

---

## Architecture

The OpenKinetics package is structured as a Magician designer subpackage under `REvoDesign.magician.designers.openkinetics/`.

```
openkinetics/
├── __init__.py      # Re-exports all public symbols + dynamic scorer classes
├── _client.py       # REST API client, config loading, data I/O, result normalisation
├── _models.py       # Exception hierarchy, dataclasses, endpoint constants
├── _scorers.py      # Abstract base scorer + dynamic subclass creation via _SCORER_SPECS
└── _pdb.py          # PDB ligand discovery, SMILES extraction, mutation label helpers
```

Scorer classes are generated dynamically at import time from the `_SCORER_SPECS` tuple in `_scorers.py`. Each spec produces a concrete subclass of `OpenKineticsScorerAbstract` with a fixed `method`, `prediction_type`, and citation key. The `__init__.py` re-exports these classes by name.

Beyond the core scoring workflow (submit, status, result), the `OpenKineticsClient` also wraps four additional service endpoints: `check_health()` (`/health/`), `list_methods()` (`/methods/`), `get_status()` (`/status/{job_id}/`), and `check_quota()` (`/quota/`). The `submit()` method accepts optional parameters `handle_long_sequences`, `use_experimental`, `include_similarity_columns`, and `canonicalize_substrates`.

---

## YAML Configuration

The package reads its runtime configuration from `config/third_party/scorers/openkinetics_api.yaml`:

```yaml
scorers:
  openkinetics:
    enabled: false
    base_url: "https://predictor.openkinetics.org/api/v1"
    default_method: "CataPro"
    default_prediction_type: "kcat/Km"
    poll_interval_seconds: 3
    timeout_seconds: 600
    cache_enabled: true
```

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `false` | Whether the OpenKinetics scorers are available. |
| `base_url` | `str` | `https://predictor.openkinetics.org/api/v1` | Base URL of the OpenKinetics Predictor API. |
| `default_method` | `str` | `CataPro` | Default prediction method. |
| `default_prediction_type` | `str` | `kcat/Km` | Default prediction target. |
| `poll_interval_seconds` | `int` | `3` | Seconds between status-poll requests. |
| `timeout_seconds` | `int` | `600` | Maximum overall wall-clock time for a prediction job. |
| `cache_enabled` | `bool` | `true` | Whether per-variant SQLite caching is on by default. |

The config is loaded at runtime via `load_openkinetics_config()`.

### API Key Configuration

The API key is auto-registered by default. `OpenKineticsScorerAbstract`
defaults `auto_register_api_key=True`, which triggers automatic key generation
and persistence on first use (see `resolve_api_key()` below). Manual setup in
`environ.yaml` is still supported as a fallback and takes precedence if set.

---

## Constants

::: REvoDesign.magician.designers.openkinetics._models.DEFAULT_OPENKINETICS_API_KEY_ENV
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._models.OPENKINETICS_ENDPOINTS
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._models.WATER_RESIDUE_NAMES
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._models.COFACTOR_EXCLUSIONS
    options:
      show_submodules: false

---

## Exception Hierarchy

::: REvoDesign.magician.designers.openkinetics._models.OpenKineticsError
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._models.OpenKineticsConfigurationError
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._models.OpenKineticsAPIError
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._models.OpenKineticsTimeoutError
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._models.OpenKineticsValidationError
    options:
      show_submodules: false

---

## Dataclasses

::: REvoDesign.magician.designers.openkinetics._models.LigandCandidate
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._models.OpenKineticsFixturePaths
    options:
      show_submodules: false

---

## Configuration Functions

::: REvoDesign.magician.designers.openkinetics._client.load_openkinetics_config
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.resolve_api_key
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.fetch_openkinetics_api_key
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.persist_openkinetics_api_key
    options:
      show_submodules: false

---

## Data I/O Helpers

::: REvoDesign.magician.designers.openkinetics._client.build_openkinetics_data_rows
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.build_openkinetics_request_payload
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.get_method_metadata
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.write_csv_rows
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.write_json
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.sha256_file
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client.write_normalized_scores_csv
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._client._normalize_result_rows
    options:
      show_submodules: false

---

## OpenKineticsClient

The HTTP client for the OpenKinetics Predictor REST API. Used by both the scoring workflow (`OpenKineticsScorerAbstract`) and the manual fixture-collection workflow.

::: REvoDesign.magician.designers.openkinetics._client.OpenKineticsClient
    options:
      show_submodules: false

---

## PDB / Ligand Functions

::: REvoDesign.magician.designers.openkinetics._pdb.discover_ligand_candidates
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._pdb.choose_primary_ligand
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._pdb.extract_ligand_pdb_block
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._pdb.smiles_from_ligand_pdb_block
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._pdb._canonicalize_smiles
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._pdb.resolve_substrate_metadata
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._pdb.load_chain_sequence_context
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._pdb.load_mutation_labels
    options:
      show_submodules: false

::: REvoDesign.magician.designers.openkinetics._pdb.relabel_pdb_position_to_sequential
    options:
      show_submodules: false

---

## Scorer Classes

### OpenKineticsScorerAbstract

Base class for all OpenKinetics API-based kinetic scorers. Concrete subclasses fix the `method` and `prediction_type` via the abstract `built_in_defaults()` class method.

::: REvoDesign.magician.designers.openkinetics._scorers.OpenKineticsScorerAbstract
    options:
      show_submodules: false

### Dynamically Created Scorer Subclasses

Rather than defining one class per prediction method, `_scorers.py` declares a `_SCORER_SPECS` tuple and creates concrete subclasses with `type()` at import time. Each subclass sets `name`, `prefer_lower`, `built_in_defaults`, and `__bibtex__`.

The following 19 scorer classes are generated from the spec:

| Class name | Scorer name | Method | Prediction type | Citation key |
|---|---|---|---|---|
| `CataProKcatScorer` | `OpenKinetics-CataPro-kcat` | CataPro | kcat | CataPro |
| `CatPredKcatScorer` | `OpenKinetics-CatPred-kcat` | CatPred | kcat | CatPred |
| `DLKcatScorer` | `OpenKinetics-DLKcat-kcat` | DLKcat | kcat | DLKcat |
| `EITLEMKcatScorer` | `OpenKinetics-EITLEM-kcat` | EITLEM | kcat | EITLEM |
| `KinFormHKcatScorer` | `OpenKinetics-KinForm-H-kcat` | KinForm-H | kcat | KinForm |
| `KinFormLKcatScorer` | `OpenKinetics-KinForm-L-kcat` | KinForm-L | kcat | KinForm |
| `OmniESIKcatScorer` | `OpenKinetics-OmniESI-kcat` | OmniESI | kcat | OmniESI |
| `RealKcatScorer` | `OpenKinetics-RealKcat-kcat` | RealKcat | kcat | RealKcat |
| `UniKPKcatScorer` | `OpenKinetics-UniKP-kcat` | UniKP | kcat | UniKP |
| `CataProKmScorer` | `OpenKinetics-CataPro-Km` | CataPro | Km | CataPro |
| `CatPredKmScorer` | `OpenKinetics-CatPred-Km` | CatPred | Km | CatPred |
| `EITLEMKmScorer` | `OpenKinetics-EITLEM-Km` | EITLEM | Km | EITLEM |
| `KinFormHKmScorer` | `OpenKinetics-KinForm-H-Km` | KinForm-H | Km | KinForm |
| `MMISAKMKmScorer` | `OpenKinetics-MMISA-KM-Km` | MMISA-KM | Km | MMISA-KM |
| `OmniESIKmScorer` | `OpenKinetics-OmniESI-Km` | OmniESI | Km | OmniESI |
| `RealKcatKmScorer` | `OpenKinetics-RealKcat-Km` | RealKcat | Km | RealKcat |
| `UniKPKmScorer` | `OpenKinetics-UniKP-Km` | UniKP | Km | UniKP |
| `CataProKcatKmScorer` | `OpenKinetics-CataPro-kcat/Km` | CataPro | kcat/Km | CataPro |
| `IECataKcatKmScorer` | `OpenKinetics-IECata-kcat/Km` | IECata | kcat/Km | IECata |

Km-targeting scorers set `prefer_lower = True` (lower scores are better). kcat and kcat/Km scorers set `prefer_lower = False` (higher scores are better).

### Re-exported list of scorer class names

::: REvoDesign.magician.designers.openkinetics._scorers.OPENKINETICS_SCORER_CLASS_NAMES
    options:
      show_submodules: false
