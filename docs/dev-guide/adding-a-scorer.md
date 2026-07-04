# Adding a Scorer

This guide explains how to integrate a new scoring function or external design
tool into REvoDesign's "Magician" gimmick system. Scorers are auto-discovered
by the `PluginRegistry` -- no manual registration step is needed.

## Overview

A scorer plugin is a Python subpackage under `magician/designers/` that
subclasses `ExternalDesignerAbstract` and implements at minimum `initialize()`
and `scorer()`. The canonical example is the **OpenKinetics** scorer plugin at
`src/REvoDesign/magician/designers/openkinetics/`.

## Step 1: Create the subpackage

```
src/REvoDesign/magician/designers/
├── __init__.py          # Existing package init
└── your_scorer/
    ├── __init__.py      # Exports your classes
    ├── _scorers.py      # Scorer class definition(s)
    └── ...              # Supporting modules (client, models, helpers)
```

The `PluginRegistry` in `magician/__init__.py` imports all modules under
`REvoDesign.magician.designers` and discovers non-abstract subclasses of
`ExternalDesignerAbstract`, so the subpackage is found automatically.

## Step 2: Subclass ExternalDesignerAbstract

Define your scorer class in `_scorers.py`:

```python
from REvoDesign.basic.designer import ExternalDesignerAbstract


class YourScorer(ExternalDesignerAbstract):
    name = "Your-Scorer-Name"
    installed = True          # Set to True if dependencies are available
    scorer_only = True        # True if only scoring is implemented
    prefer_lower = False      # Whether lower scores are preferred

    def initialize(self, *args, **kwargs):
        # One-time setup: load config, validate dependencies, etc.
        self.initialized = True

    def scorer(self, mutant, **kwargs) -> float:
        # Score a single mutant, return a float.
        ...
        return score
```

Required class attributes:

| Attribute | Type | Description |
|---|---|---|
| `name` | `str` | Unique plugin name used in registry lookups and UI selection. |
| `installed` | `bool` | Signals availability to the registry (`installed_names`). |
| `scorer_only` | `bool` | When `True`, only `scorer()` is implemented. |
| `prefer_lower` | `bool` | If `True`, lower scores are treated as better. |
| `no_need_to_score_wt` | `bool` | If `True`, the wild-type is not scored separately (default `False`). |

Required methods:

- `initialize(self, *args, **kwargs)` -- Called once when the gimmick is
  "pre-heated" by `Magician.setup()`. Use it to load config, validate the
  environment, or initialize remote API clients.
- `scorer(self, mutant, **kwargs) -> float` -- Called for each mutant to be
  scored. The `mutant` parameter is a `Mutant` or
  `RosettaPyProteinSequence` object.

Optional methods:

- `designer(self, *args, **kwargs)` -- Only needed if your plugin can also
  generate new designs (not just score existing ones).
- `parallel_scorer(self, mutants, nproc, **kwargs) -> list[Mutant]` -- The
  base class provides a `joblib.Parallel` implementation. Override for
  custom batching logic (see OpenKinetics for an example that sends batch
  API requests).
- `preffer_substitutions(self, aa)` -- Optional amino-acid preference setup.

## Step 3: Create a YAML config

Config files live under `config/third_party/scorers/`. Create a YAML file
that follows the OpenKinetics pattern:

```yaml
# src/REvoDesign/config/third_party/scorers/your_scorer.yaml
# Loaded via reload_config_file("third_party/scorers/your_scorer")["third_party"]

scorers:
  your_scorer:
    enabled: false
    # Add runtime knobs here...
    some_option: "default_value"
```

The config is loaded in `initialize()` via:

```python
from REvoDesign.bootstrap import reload_config_file

config = reload_config_file("third_party/scorers/your_scorer")["third_party"]
```

## Step 4: Auto-discovery (it's automatic)

The `PluginRegistry` at module load time:

1. Imports all modules under `REvoDesign.magician.designers`.
2. Scans for non-abstract subclasses of `ExternalDesignerAbstract`.
3. Indexes them by their `name` attribute.
4. Exposes them via `DESIGNER_REGISTRY.all_classes`,
   `IMPLEMENTED_DESIGNERS`, and `DESIGNER_REGISTRY.installed_names`.

Your scorer will automatically appear in:

- `MagicianAssistant.installed_worker` (if `installed = True`)
- The UI's external scorer dropdown
- `Magician.setup(name_cfg_item="ui.interact.use_external_scorer")`

No manual registration or `__init__.py` export in `magician/designers/` is
needed, as long as the subpackage is importable.

## Example: OpenKinetics

The OpenKinetics scorer at `src/REvoDesign/magician/designers/openkinetics/`
is the reference implementation. Key design decisions:

### Class hierarchy

```python
class OpenKineticsScorerAbstract(ExternalDesignerAbstract, ABC):
    """Base class with shared client, caching, and scoring logic."""

    installed = True
    scorer_only = True
    __bibtex__ = {"OpenKineticsPredictor": _OPENKINETICS_PREDICTOR_BIBTEX}

    @classmethod
    @abstractmethod
    def built_in_defaults(cls) -> dict[str, str]:
        """Return {'method': ..., 'prediction_type': ...}."""

    def initialize(self, *args, **kwargs):
        # Resolve substrate SMILES from kwargs or PDB metadata
        ...

    def scorer(self, mutant, **kwargs) -> float:
        # Submit variant to the OpenKinetics API, return predicted value
        ...
```

### Dynamic subclasses

Instead of writing one class per prediction method, `_scorers.py` defines a
`_SCORER_SPECS` tuple and creates subclasses dynamically with `type()`:

```python
_SCORER_SPECS = (
    ("CataProKcatScorer", "OpenKinetics-CataPro-kcat", "CataPro", "kcat", "CataPro"),
    ("CatPredKcatScorer", "OpenKinetics-CatPred-kcat", "CatPred", "kcat", "CatPred"),
    # ... more specs ...
)

for class_name, scorer_name, method, prediction_type, citation_key in _SCORER_SPECS:
    globals()[class_name] = type(
        class_name,
        (OpenKineticsScorerAbstract,),
        {
            "name": scorer_name,
            "prefer_lower": prediction_type.lower() == "km",
            "built_in_defaults": _built_in_defaults(method, prediction_type),
            "__bibtex__": {citation_key: _PREDICTOR_BIBTEX[citation_key]},
        },
    )
```

Each subclass sets `name`, `prefer_lower`, `built_in_defaults`, and
`__bibtex__`. The OpenKinetics package's `__init__.py` re-exports these
dynamic classes by name.

### Package structure

```
openkinetics/
├── __init__.py        # Re-exports all public symbols, dynamic scorer classes
├── _scorers.py        # OpenKineticsScorerAbstract + dynamic subclass creation
├── _client.py         # OpenKinetics REST API client (submit, poll, get_result)
├── _models.py         # Dataclasses, exception types, constants
└── _pdb.py            # PDB/ligand helpers (SMILES extraction, metadata)
```

## Step 5 (optional): Add citation support

Set `__bibtex__` on your class to integrate with the citation system:

```python
class YourScorer(ExternalDesignerAbstract):
    __bibtex__ = {
        "your_method": r"""@article{...,
          title = {...},
          ...
        }"""
    }
```

Citations are collected when `self.cite()` is called and managed by
`CitationManager` (`citations/citation_manager.py`).

## Testing

Create a test file under `tests/` following the pattern in
`tests/magician/test_openkinetics_scorer.py`. Key things to test:

- Registry discovery: verify your class appears in
  `IMPLEMENTED_DESIGNERS` and `ALL_DESIGNER_CLASSES`.
- Initialization: test `initialize()` with valid and invalid config.
- Scoring: test `scorer()` with mock data or a known fixture.
- Config loading: test that your YAML config is loaded correctly.
- Skip tests when the external dependency is not installed (check
  `your_class.installed`).

Run with:

```bash
make kw-test PYTEST_KW='your_keyword'
```
