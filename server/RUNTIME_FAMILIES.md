# REvoCompute Runtime Families

The current runtime families and the stacks they pin, used to match a new
task type to an existing runner before creating a new family. Versions are
what the pinned `docker/runners/<family>/Dockerfile` installs — re-read the
file when matching; do not trust this table after a bump. GPU flags are the
registry's `gpus:` declarations.

| Family | Tasks | Base image / CUDA | Python | Frameworks | GPU |
| --- | --- | --- | --- | --- | --- |
| `gremlin` | gremlin | condaforge/mambaforge (legacy conda env) | 3.6 (legacy conda env) | GREMLIN conda env | no |
| `pythia_ddg` | pythia_ddg | python:3.12-slim | 3.12 | torch (CPU wheels), pytorch-lightning | no |
| `esm` | esm_msa, esm_extract, esm_1v, esm_if1 | nvidia/cuda:12.1.1-cudnn8 | 3.11 | torch 2.2.0+cu121, fair-esm | yes |
| `esmdynamic` | esmdynamic | nvidia/cuda:12.6.3-cudnn | 3.11 | torch 2.7.1+cu126, fair-esm, OpenFold | yes |
| `opendde` | opendde | python:3.11-slim | 3.11 | opendde[gpu] 1.0.3 | yes |
| `mpnn` | hypermpnn, proteinmpnn, solublempnn, ligandmpnn, lasermpnn, thermompnn | python:3.11-slim | 3.11 | torch (CPU wheels) | no |
| `prime` | prime, prime_dms | python:3.10-slim | 3.10 | torch 2.3.1, transformers 4.36.2 | yes |
| `placer-rfdiffusion` | rfdiffusion, placer | nvidia/cuda:12.1.1-cudnn8 | 3.10 | torch 2.3.1, DGL 2.4.0, e3nn 0.5.4 (+ bool-override patch) | yes |
| `bioemu` | bioemu | python:3.11-slim | 3.11 | torch 2.7.1, jax[cuda12] 0.5.3, bioemu 1.4.1 | yes |
| `easifa` | easifa | debian:bookworm-slim (builder builds torchdrug CUDA ext) | 3.11 | torch + torchdrug CUDA extension | yes |
| `alphafold` | alphafold | ghcr.io/sokrypton/colabfold:1.6.2-cuda12 | upstream | ColabFold 1.6.2, AlphaFold2, JAX CUDA 12, OpenMM; public MMseqs2 MSA service | yes |
| `freebindcraft` | freebindcraft | python:3.11-slim | 3.11 | jax 0.6.0, ColabDesign, OpenMM, FASPR, sc-rs | yes |

Sharing a family deduplicates Docker/SIF storage; it must not force CPU tasks
to inherit a large GPU stack or allow incompatible package upgrades. A new
family is justified only when dependencies, accelerator needs, system ABI, or
license make sharing unsafe — see the adapter guide's §11/§12.
