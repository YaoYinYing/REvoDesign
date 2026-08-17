# Goal: Adapt gmx_MMPBSA to REvoCompute

Status: intake collected, not yet implemented. This document is the pinned
adaptation contract — the implementation follows `OPERATIONS_AND_TASK_ADAPTER_GUIDE.md`
§12 (new runtime family) and the root CLAUDE.md intake checklist.

## Tool and versions

- gmx_MMPBSA (Valdés-Tresanco et al., JCTC 2021) — MM/PBSA binding free energy
  from GROMACS trajectories. Latest release **1.6.5** (2026-05), constrained by
  its official conda pins: Python 3.11, `ambertools<=23.3` (env.yml: 23.6),
  `mpi4py 4.0.1`, numpy 1.26.4, scipy 1.14.1, pandas 1.5.3, `gromacs<=2024.3`.
- Host reference GROMACS (user-provided, `/mnt/data/software/gromacs/2025.3-cuda-nompi-avx2_256`):
  2025.3, mixed precision, thread_mpi (no real MPI), OpenMP ≤128 threads,
  CUDA + cuFFT, AVX2_256, fftw 3.3.8, clang 17. Adapter smoke decides whether
  the image builds the pinned gromacs or mirrors this 2025.3 build.
- MPI policy: thread_mpi now; keep forward support from the start so a
  real-MPI GROMACS can be dropped in later (build arg or sibling image) —
  no single-node assumptions hard-wired into `run.sh`. gmx_MMPBSA's own
  engine keeps `mpi4py` (its hard pin) but runs single-process.

## Resources (user-specified SLURM defaults)

- Walltime: 10 days (`max_runtime_seconds: 864000`), memory: 64 GB,
  max CPU: 16, GPU: yes — but the MMPBSA engine is CPU-bound; confirm at
  implement time whether the GPU allocation is for gmx steps or can be dropped.
- Thread affinity: mdrun handles it internally (`-pin on`); no `srun --cpu-bind`
  needed for GROMACS. User's standard invocation:
  `gmx mdrun -deffnm … -nb gpu -bonded gpu -pme gpu -update gpu -pin on -ntomp ${SLURM_CPUS_PER_TASK}`.

## Inputs / outputs contract

- Inputs: `.tpr` (primary), `.xtc` trajectory, optional `.ndx`, plus an
  `mmpbsa.in` options file. Multiple auxiliary files with preserved
  relative paths (the existing `files` capability covers this).
- Outputs: `FINAL_RESULTS_MMPBSA.dat` (+ per-frame CSVs); success = the dat
  file exists with results and exit 0; silent failure = empty/missing dat
  despite exit 0.

## Open intake items (ask before building)

1. Upstream repo + full commit hash to pin (github.com/Valdes-Tresanco-MS/gmx_MMPBSA).
2. Which `mmpbsa.in` keys become typed params (igb model, salt, temperature,
   entropy, …) — the rest stays fixed or an advanced free-text field.
3. One minimal working command line + sample tpr/xtc/ndx for `tests/data`
   (the upstream repo ships example files).
4. GPU decision (see Resources) and the gromacs-version decision (pinned ≤2024.3
   vs mirror 2025.3).

## Deliverable checklist

Registry entry (`gmx_mmpbsa` task + `gmx-mmpbsa` family) → runner YAML with
resource defaults → Dockerfile (conda env per the official pins) → run.sh
(protocol v2) → `.def` → contract tests → offline docker smoke → delete-old-SIF
+ `restart --use-proxy --build-sif` → API living test under the group test
account with SLURM monitoring → CHANGELOG + `RUNTIME_FAMILIES.md` row.

## References

- Official docs (1.6.5): https://valdes-tresanco-ms.github.io/gmx_MMPBSA/1.6.5/installation/
- env.yml: https://valdes-tresanco-ms.github.io/gmx_MMPBSA/dev/env.yml
- Repo: https://github.com/Valdes-Tresanco-MS/gmx_MMPBSA
- Tutorial for living-test inputs: https://github.com/wuyichao71/How_to_perform_MMPBSA
- Verify after install: `gmx_MMPBSA_test -f tests -n 10`
