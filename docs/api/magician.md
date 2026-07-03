# Magician — Designer Plugin System

This page documents the Magician gimmick orchestration system, the plugin registry that discovers designer/scorer subclasses, and the two concrete built-in designers.

---

## Overview

The Magician system manages third-party design and scoring tools ("gimmicks") through a singleton-driven lifecycle. Plugins are auto-discovered at import time via a `PluginRegistry` that scans the `REvoDesign.magician.designers` package for non-abstract subclasses of `ExternalDesignerAbstract`.

### Plugin Discovery Mechanism

The registry is created in `REvoDesign.magician`:

```python
DESIGNER_REGISTRY = build_plugin_registry(
    base_class=ExternalDesignerAbstract,
    package="REvoDesign.magician.designers",
)
```

At module load time, `PluginRegistry.__post_init__` calls `_discover_classes()`, which:

1. Imports all modules under `REvoDesign.magician.designers` (including subpackages like `openkinetics/`).
2. Scans every module for non-abstract subclasses of `ExternalDesignerAbstract`.
3. Indexes them by their `.name` attribute, rejecting duplicates.
4. Exposes the results through `all_classes`, `implemented_map`, and `installed_names`.

The `designers/__init__.py` explicitly imports each known designer module to trigger class creation and also re-exports its top-level symbols. The OpenKinetics subpackage additionally uses a `_SCORER_SPECS` loop with `type()` to generate dynamic scorer subclasses at import time.

---

## Registry and Discovery

::: REvoDesign.magician.DESIGNER_REGISTRY
    options:
      show_submodules: false

::: REvoDesign.magician.ALL_DESIGNER_CLASSES
    options:
      show_submodules: false

::: REvoDesign.magician.IMPLEMENTED_DESIGNERS
    options:
      show_submodules: false

---

## Magician

::: REvoDesign.magician.Magician
    options:
      show_submodules: false

---

## MagicianAssistant

::: REvoDesign.magician.MagicianAssistant
    options:
      show_submodules: false

---

## PluginRegistry

::: REvoDesign.basic.plugin_registry.PluginRegistry
    options:
      show_submodules: false

---

## Built-in Designers

### ColabDesigner_MPNN

The `ColabDesigner_MPNN` class wraps ProteinMPNN (via the ColabDesign package) for sequence design and scoring.

::: REvoDesign.magician.designers.colabdesign.ColabDesigner_MPNN
    options:
      show_submodules: false

### Cartesian-ddG (ddg)

The `ddg` class wraps RosettaPy's Cartesian-ddG module for mutation stability scoring.

::: REvoDesign.magician.designers.cart_ddg.ddg
    options:
      show_submodules: false

### Module-level helpers

::: REvoDesign.magician.designers.cart_ddg.get_ddg_mut_id
    options:
      show_submodules: false

::: REvoDesign.magician.designers.cart_ddg.preprocess_ddg_values
    options:
      show_submodules: false
