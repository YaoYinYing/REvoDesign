# Call Mutate Runners within a Python script/prompt

REvoDesign's mutate runners can be used programmatically to quickly generate
mutant PDB files for downstream tasks like molecular dynamics (MD) simulations.
This is useful when you already know which mutations you want and just need the
3D structures.

## Quick Mutant Generation (PyMOL / Dunbrack Rotamer Library)

`PyMOL_mutate` uses PyMOL's built-in Dunbrack rotamer library — no GPU, no
external dependencies beyond PyMOL itself. Ideal for quick single-point or
combinatorial mutants.

```python
from RosettaPy.common.mutation import RosettaPyProteinSequence
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id
from REvoDesign.sidechain.mutate_runner import PyMOL_mutate

pdb_file = 'protein.pdb'

# Read sequence from PDB. For xtal structures, use True to keep missing residues.
seq = RosettaPyProteinSequence.from_pdb(pdb_file, True)

# Define mutants as underscore-delimited strings.
# For homooligomers, prefix each mutation with the chain ID (e.g. AS15T = chain A, position 15, Ser→Thr).
mut_dict = {
    'M1_1': 'AS15T_BS15T',
    'M1_2': 'AD30E_BD30E',
    'M4':   'AS15T_AD30E_AK45M_AY60F_BS15T_BD30E_BK45M_BY60F',
}

# Convert to Mutant objects
mut_objs = {alias: extract_mutants_from_mutant_id(m, seq) for alias, m in mut_dict.items()}

# Instantiate worker and run
worker = PyMOL_mutate(pdb_file)
for alias, mut_obj in mut_objs.items():
    mut_pdb_path = worker.run_mutate(mut_obj)
    # Rename to a meaningful filename
    import os
    os.rename(mut_pdb_path, f'{alias}.pdb')
```

## Validate the Mutation Info

After generating mutants, verify the mutations were applied correctly:

```python
from RosettaPy.common.mutation import Mutant

wt_pdb = 'protein.WT.pdb'

def print_mut_info(wt: str, mut: str):
    m = Mutant.from_pdb(wt, [mut])
    print(f'Mutant {mut.removesuffix(".pdb")} (compare to {wt.removesuffix(".pdb")}): {m[0].format_as()}')

import glob
all_pdbs = glob.glob('*.pdb')
for pdb in all_pdbs:
    if pdb == wt_pdb:
        continue
    print_mut_info(wt_pdb, pdb)
```

Example output:

```
Mutant M4 (compare to protein.WT): AD30E_BD30E_AK45M_BS15T_BK45M_AY60F_AS15T_BY60F
Mutant M1_1 (compare to protein.WT): BS15T_AS15T
Mutant M1_2 (compare to protein.WT): BD30E_AD30E
```

## Cleanup

The runner creates intermediate files under `mutant_pdbs/`. Remove when done:

```bash
rm -r mutant_pdbs
```

## Other Runners

| Runner | `name` attribute | Requirements |
|--------|-----------------|--------------|
| `PyMOL_mutate` | `"Dunbrack Rotamer Library"` | PyMOL only |
| `DLPacker_worker` | `"DLPacker"` | PyTorch, DLPacker model |
| `DLPackerPytorch_worker` | `"DLPackerPytorch"` | PyTorch |
| `PIPPack_worker` | `"PIPPack"` | PyTorch, PIPPack model |
| `DiffPack_worker` | `"DiffPack"` | PyTorch, DiffPack model |
| `MutateRelax_worker` | `"Rosetta-MutateRelax"` | Rosetta installation |

All runners share the same `run_mutate(mutant)` / `run_mutate_parallel(mutants, nproc)`
interface. See [Adding a Sidechain Solver](../../../docs/dev-guide/adding-a-sidechain-solver.md)
for the extension API.
