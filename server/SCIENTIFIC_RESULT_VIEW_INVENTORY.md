# Scientific result-view inventory

This is the living evidence behind `config/task_types.yaml`. The canonical
API → worker → SLURM → Apptainer matrix ran on 2026-08-27 with the minimal
inputs in `tests/live_task_matrix.py`. All successful records used manifest
schema 3 and completed in SLURM. Cluster accounting storage was disabled, so
the API wall time and terminal SLURM outcome are authoritative; peak RSS is
unavailable.

Across every run, `debug/submission.json` and `debug/inputs/**` are provenance,
`execution/**`, `log/**`, completion markers, and failure reports are
diagnostics, and citations are provenance. Model checkpoints, tensors,
pickles, NPZ/TRB files, and tool-native HTML/ZIP archives remain bounded
downloads unless a stable scientific normalization is listed below. Empty
completion markers are intentionally excluded from scientific views.

| Task | Living task / wall time | Scientific artifact classes and question | Declared semantics | Presentation |
|---|---|---|---|---|
| PSSM-GREMLIN | `a2fd0f0c527aecc1fd2cdb7b448a6939` / 183 s | filtered MSA, ASCII PSSM, coupling/contact image; conservation and strongest co-evolution evidence | sequence/alignment order; residue-pair filenames are one-letter residue plus one-based position; coupling magnitude has no universal probability meaning | ordered evidence bundle; detailed pair tables/images remain artifacts |
| Pythia-ddG | `b0b3f5c504b1195ed0671d4716f465b0` / 22 s | substitution × zero-based sequence-position CSV; which substitutions are predicted stabilizing | ΔΔG in kcal/mol; lower is favourable; zero is the diverging-scale centre; no missing-value token | matrix |
| ESM-MSA-1b | `6ef3cf031fc287a3ba4ac7080d3eabbe` / 14 s | per-residue wild-type log probability and entropy plus aggregate JSON | one-based query positions; natural-log units; higher log probability and lower entropy indicate greater model compatibility/certainty; empty cells are missing | metric series + scalar summary |
| ESM-2 embedding | `a02964259735c55a0dd78a70bb876594` / 20 s | requested PyTorch tensor containing representations/contacts | tensor keys depend on requested layers/includes; no stable cross-run scalar, unit, ranking, or missing-value contract | generic authenticated download is scientifically correct |
| ESM-1v | `7680a6fd96a8c2822d533bbe48b86a05` / 109 s | mutation rows with five ensemble scores and mean | mutation labels use one-based positions; scores are mutant minus wild-type log likelihood; higher is more compatible; not experimental fitness | mutation entity table |
| ESM-IF1 | `0d1b9f6694a256200dedc6fa4b3b0143` / 34 s | sampled FASTA records; which sequences were proposed | runner order; designed chain is recorded in the run parameters; no score or calibrated confidence is emitted | candidate collection |
| ESMDynamic | `4702dcb5f9cf2c9124f1d3390adf6607` / 131 s | contact, frequency, and kinetics predictions at 320–450 K | matrix residue order follows the submitted sequence; temperatures are K; confidence CSVs accompany images; predictions are not MD frames | representative ordered evidence bundle; full temperature series remains downloadable |
| OpenDDE | `9e408edad592c1b0acd387d8bab3ce70` / 495 s | sampled CIF structures and per-sample confidence JSON | candidate order is artifact order; pLDDT/pTM/ranking higher is favourable, gPDE lower; B factors encode pLDDT | candidate collection + scalar summary |
| HyperMPNN | `e21b6c522884e709790488cc425b5e42` / 10 s | designed FASTA records | upstream FASTA order; sampling temperature is in the run record; no calibrated confidence | candidate collection |
| ProteinMPNN | `cb41ac485bcf1f44de145c4e16d877d7` / 10 s | designed FASTA records | upstream FASTA order; optional score/probability files remain downloads because their schema depends on requested mode | candidate collection |
| SolubleMPNN | `38600ac24bcbd6e98143077df445ea0d` / 10 s | designed FASTA records | upstream FASTA order; soluble checkpoint is a design prior, not confidence | candidate collection |
| LigandMPNN | `ca92aba0ffc37840cb0aa64c7a6a0326` / 14 s | designed FASTA plus optional packed/backbone PDBs | candidate order is runner order; supplied ligand context and packing parameters are in the run record | sequence candidates + optional structure evidence |
| LASErMPNN | `3d41aa296bfffed9e3c601d4cbf726f0` / 23 s | designed PDBs and FASTA | candidate order is artifact order; all-atom/protonation limitation is explicit; no calibrated confidence | candidate collection |
| ThermoMPNN-D | `bd56663de40119a1314c84e82666a7af` / 20 s | mutation and predicted ddG rows | mutation labels include chain and one-based residue position; kcal/mol; lower is favourable; rows are already threshold-filtered | mutation entity table |
| Pro-Prime | `7010c9e556100b515e02dbfa0f768588` / 30 s | one sequence-level OGT CSV row | OGT is model-estimated degrees Celsius, not a measurement; the table key is the FASTA record ID | sequence entity table |
| PRIME-DMS | `41e4b3aa1a8431b56275530c77979146` / 45 s | exhaustive single-substitution mutation score table | mutation labels are one-based; score is mutant-vs-wild-type log likelihood ratio; higher is more model-compatible, not measured fitness | mutation entity table |
| RFdiffusion | `9d1933a281026e10cc9d199380ee52aa` / 562 s | final backbone PDBs plus explicitly stem-associated multi-model PDB trajectories | final designs use artifact order; trajectory frames are diffusion steps, not time; topology association is by declared design stem | candidate collection + trajectory evidence |
| PLACER | `ebd22f41144e910412280aad96a3c40c` / 100 s | complex PDBs plus per-model FAPE/lDDT/RMSD/pRMSD/pLDDT/PDE table | candidate identity is label + model index; Å for RMSD/pRMSD; reranking direction is method/parameter-defined and is not guessed | candidate collection + metric entity table |
| BioEmu | `9bc9de660c8d86679635e5a008385267` / 262 s | PDB topology explicitly paired with XTC conformational samples | frames are samples, not physical time; sample order is not a population weight; ensemble limitation is explicit | trajectory |
| EasIFA2 | `3a5690d805abd4e1797a11f0a9cfcccf` / 40 s | residue class/probability table linked to enzyme PDB | label-sequence, one-based residue numbering; class probabilities are unitless; chain is explicit when upstream supplies it | linked residue entity table |
| FreeBindCraft | `12864ee4cb408a49efa53efb10e79288` / 789 s | accepted binder PDBs, ranked design metrics, plots, rejected/failure tables, and trajectory campaign artifacts | accepted order is runner order; table declares Rank, pLDDT, pTM/iPTM, PAE/iPAE, and ipSAE; missing CSV cells mean the stage did not emit that metric | candidate collection + metric entity table; plots/downloads remain available |
| AlphaFold2 | `e7dafb3f7be0be7471672c3e46c26e9e` / 1550 s | ranked PDBs, per-model pLDDT, PAE, ranking metadata, MSAs, and model internals | ranked filename order is authoritative; pLDDT 0–100 higher is better; PAE Å lower is better; B factors encode pLDDT; absent pTM/iPTM is not synthesized | candidates + metric series + matrices |
| ColabFold AF2 | `1ea9e9178737f7fbb7d3498ae05d31c6` / 171 s | ranked PDB, pLDDT series, PAE matrix/images, pTM/max-PAE scalars, and A3M | ranked filename order; pLDDT 0–100 and pTM higher are better; PAE Å lower is better; one-based sequence positions; null means missing | candidates + metric series + matrix + scalar summary + alignment |

All 23 enabled task types resolve their required selectors against stored
schema-3 manifests with passing output checks. The 2026-09-01 canonical
PRIME and PRIME-DMS runs completed through API, worker, SLURM, and Apptainer;
their checked local snapshots are now the scientific contract.
