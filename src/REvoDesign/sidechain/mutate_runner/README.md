# Call Mutate Runners within a Python script/prompt


## Mutate and Model

```python

from RosettaPy.common.mutation import RosettaPyProteinSequence
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id
from REvoDesign.sidechain.mutate_runner import DLPacker_worker 

pdb_file='8x3e.cleaned.pdb'

# read sequence from pdb file. If its a xtal structure, use True parameter to keep missing residues
seq=RosettaPyProteinSequence.from_pdb(pdb_file, True)

# construct the mutants string description 
mut_lists=['AQ122A', 'AQ266A', 'AL72M', 'AL72M_AQ122A', 'AQ122A_AQ266A']

# convert them into mutant objects
mut_objs=[extract_mutants_from_mutant_id(m, seq) for m in mut_lists]

# instantiate the worker
d=DLPacker_worker(pdb_file, 6)

# run the mutate
mfp=d.run_mutate_parallel(mut_objs, 6)
```

## Validate the mutation info

```python
from RosettaPy.common.mutation import Mutant

def print_mut_info(wt: str, mut: str):
    m=Mutant.from_pdb(wt, [mut])
    print(f'Mutant {mut.removesuffix(".pdb")} (compare to {wt.removesuffix(".pdb")}): {m[0].format_as()}')


for i in [1, 2, 3]:
    print_mut_info('WT.pdb', f'M{i}.pdb')
```
