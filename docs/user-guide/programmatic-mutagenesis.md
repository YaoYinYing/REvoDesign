# Programmatic Mutagenesis for Downstream Tasks

REvoDesign's sidechain solvers can be used outside the GUI — directly from a
Python script or PyMOL prompt — to rapidly generate mutant PDB structures for
downstream applications like molecular dynamics (MD) simulations, docking
studies, or free energy calculations.

This is the fastest path from "I know which mutations I want" to "I have the 3D
structures."

## Why Programmatic?

The full REvoDesign GUI workflow (Prepare → Mutate → Evaluate → Cluster) is
designed for *discovering* which mutations to make. When you already have a list
of target mutations — from literature, alanine scanning, or a previous design
round — the programmatic API skips the GUI and goes straight to structure
generation.

## Prerequisites

- REvoDesign installed and working in PyMOL
- A cleaned PDB structure of your wild-type protein
- A list of desired mutations

## Step 1: Prepare the Wild-Type Structure

Start with a clean PDB file. If your structure contains ligands, cofactors, or
crystallization artifacts, remove them before mutagenesis:

```bash
grep -v 'LIG' protein.pdb > protein.WT.pdb
```

## Step 2: Define Mutants

Mutants are specified as underscore-delimited strings in the format
`<chain><WT_residue><position><mutant_residue>`:

| Format | Example | Meaning |
|--------|---------|---------|
| Single chain | `S15T` | Chain A (default), position 15, Ser→Thr |
| Explicit chain | `AS15T` | Chain A, position 15, Ser→Thr |
| Homooligomer | `AS15T_BS15T` | Both chains A and B, position 15, Ser→Thr |
| Combinatorial | `AS15T_AD30E_AK45M` | Three simultaneous mutations on chain A |

!!! tip "Homooligomeric proteins"
    Prefix each mutation with the chain ID. For a dimer, `AS15T_BS15T` mutates
    position 15 on both chains. Without chain prefixes, REvoDesign defaults to
    chain A.

## Step 3: Generate Mutant PDBs

Open PyMOL and run the following in the Python prompt (`File → Python Prompt`):

```python
from RosettaPy.common.mutation import RosettaPyProteinSequence
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id
from REvoDesign.sidechain.mutate_runner import PyMOL_mutate
import os

pdb_file = 'protein.WT.pdb'

# Read sequence from PDB. Use True for xtal structures (keeps missing residues).
seq = RosettaPyProteinSequence.from_pdb(pdb_file, True)

# Define mutants
mut_dict = {
    'M1_1': 'AS15T_BS15T',
    'M1_2': 'AD30E_BD30E',
    'M1_3': 'AK45M_BK45M',
    'M1_4': 'AY60F_BY60F',
    'M4':   'AS15T_AD30E_AK45M_AY60F_BS15T_BD30E_BK45M_BY60F',
}

# Convert to mutant objects
mut_objs = {alias: extract_mutants_from_mutant_id(m, seq)
            for alias, m in mut_dict.items()}

# Generate each mutant
worker = PyMOL_mutate(pdb_file)
for alias, mut_obj in mut_objs.items():
    mut_pdb_path = worker.run_mutate(mut_obj)
    os.rename(mut_pdb_path, f'{alias}.pdb')
    print(f'Generated: {alias}.pdb')
```

### Choosing a Runner

| Runner | Best for | Requirements |
|--------|----------|--------------|
| `PyMOL_mutate` | Quick rotamer-based mutagenesis | PyMOL only (no GPU) |
| `DLPacker_worker` | Deep learning sidechain packing | PyTorch + DLPacker |
| `DLPackerPytorch_worker` | PyTorch-native packing | PyTorch |
| `PIPPack_worker` | Rotamer-based with PIPPack | PyTorch + PIPPack |
| `DiffPack_worker` | Diffusion-based packing | PyTorch + DiffPack |
| `MutateRelax_worker` | Full energy minimization | Rosetta installation |

All runners share the same `run_mutate(mutant)` / `run_mutate_parallel(mutants, nproc)`
interface — swap the import to change backends:

```python
# Use DLPacker instead of PyMOL
from REvoDesign.sidechain.mutate_runner import DLPacker_worker
worker = DLPacker_worker(pdb_file, radius=6.0)
```

## Step 4: Validate

Always verify the mutations were applied correctly:

```python
from RosettaPy.common.mutation import Mutant
import glob

wt_pdb = 'protein.WT.pdb'

def print_mut_info(wt, mut):
    m = Mutant.from_pdb(wt, [mut])
    print(f'Mutant {mut.removesuffix(".pdb")} '
          f'(vs {wt.removesuffix(".pdb")}): {m[0].format_as()}')

for pdb in sorted(glob.glob('*.pdb')):
    if pdb == wt_pdb:
        continue
    print_mut_info(wt_pdb, pdb)
```

Expected output:

```
Mutant M1_1 (vs protein.WT): BS15T_AS15T
Mutant M1_2 (vs protein.WT): BD30E_AD30E
Mutant M1_3 (vs protein.WT): BK45M_AK45M
Mutant M1_4 (vs protein.WT): BY60F_AY60F
Mutant M4 (vs protein.WT): AD30E_BD30E_AK45M_BS15T_BK45M_AY60F_AS15T_BY60F
```

## Step 5: Use in Downstream Tasks

The generated PDB files are standard protein structures ready for:

- **Molecular Dynamics** — Load into GROMACS, AMBER, NAMD, or OpenMM
- **Docking** — Use as receptor structures in AutoDock, RosettaLigand, or DiffDock
- **Free Energy Calculations** — Input for alchemical FEP, TI, or MM/PBSA
- **Visualization** — Open in PyMOL, ChimeraX, or VMD for inspection

## Cleanup

The runner stores intermediate files under `mutant_pdbs/`. Remove when done:

```bash
rm -r mutant_pdbs
```

## See Also

- [Sidechain Solver API Reference](../api/sidechain.md) — Full API documentation
- [Adding a Sidechain Solver](../dev-guide/adding-a-sidechain-solver.md) — Extension guide
- [Mutate Runner README](https://github.com/YaoYinYing/REvoDesign/blob/main/src/REvoDesign/sidechain/mutate_runner/README.md) — In-repo examples
