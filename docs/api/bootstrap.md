# Configuration Bootstrapping

This page documents the `REvoDesign.bootstrap` module, which initialises the REvoDesign configuration system using Hydra and OmegaConf. It handles copying the template configuration tree to the user's data directory, verifying and repairing the config structure, saving and reloading config files, and managing experiment and cache directories.

---

## Module-Level Constants

These constants are set at import time by `REvoDesign.bootstrap.__init__`:

- **`REVODESIGN_CONFIG_FILE`** (str) -- Absolute path to the user's `main.yaml` configuration file, determined by `set_REvoDesign_config_file()`.
- **`REVODESIGN_CONFIG_DIR`** (str) -- Directory containing all user configuration YAML files (`os.path.dirname(REVODESIGN_CONFIG_FILE)`).
- **`EXPERIMENTS_CONFIG_DIR`** (str) -- Directory for experiment-specific configuration files, created by `experiment_config("experiments")`.
- **`CACHE_CONFIG_DIR`** (str) -- Directory for cached intermediate YAML files, created by `experiment_config("cache")`.

---

## Functions

::: REvoDesign.bootstrap.set_config.set_REvoDesign_config_file
::: REvoDesign.bootstrap.set_config.reload_config_file
::: REvoDesign.bootstrap.set_config.save_configuration
::: REvoDesign.bootstrap.set_config.experiment_config
::: REvoDesign.bootstrap.set_config.set_cache_dir
::: REvoDesign.bootstrap.set_config.verify_config_tree_structure
::: REvoDesign.bootstrap.set_config.enforce_config_key_structure

---

## Classes

::: REvoDesign.bootstrap.set_config.ConfigConverter

---

## Config YAML Schema

The configuration tree lives under `src/REvoDesign/config/` as the template and is copied to the user's platform data directory (`platformdirs.user_data_dir("REvoDesign")/config`). The directory structure is:

### Top-Level Files

| File | Purpose |
|------|---------|
| `main.yaml` | Primary configuration for UI widgets, design parameters, file paths, and algorithm settings. This is the file the user edits most often. |
| `environ.yaml` | Environment variable overrides and build-time flags (e.g., paths to third-party executables). Ignored by `enforce_config_key_structure` to allow local customisation. |
| `logger.yaml` | Logging system configuration (log levels, handlers, formatters). |
| `openmm.yaml` | OpenMM simulation setup parameters (force fields, integrator, thermostats). |
| `runtime.yaml` | Runtime-specific configuration for plugin operation mode. |

### Subdirectory Presets

**`rfdiffusion/`** -- Parameter presets for RFdiffusion, organised by use case:

- `base.yaml` -- Default diffusion parameters.
- `enzyme.yaml` -- Enzyme-specific diffusion settings.
- `motif_scaffoldding.yaml` -- Motif scaffolding parameters.
- `partial_diffusion.yaml` -- Partial diffusion configuration.
- `symmetry.yaml` -- Symmetric diffusion settings.

**`rosetta-node/`** -- Rosetta execution presets for different deployment modes:

- `native.yaml` -- Native (local) Rosetta execution.
- `docker.yaml` / `docker_mpi.yaml` -- Docker-based execution (serial and MPI).
- `wsl.yaml` / `wsl_mpi.yaml` -- WSL-based execution (serial and MPI).
- `mpi.yaml` -- General MPI execution.

**`sidechain-solver/`** -- Sidechain solver configurations:

- `pippack.yaml` -- PIPPack configuration for sidechain packing.

**`third_party/scorers/`** -- Third-party scorer API configurations:

- `openkinetics_api.yaml` -- OpenKinetics REST API endpoint and authentication settings.
