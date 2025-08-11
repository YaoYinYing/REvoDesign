### structure.PocketSearcher
Search pocket residues around ligand/cofactor and save selections and residue lists.

Constructor:
- PocketSearcher(input_pse: str, save_dir: str = "./pockets/")

Methods:
- search_pockets() -> None

Example:
```python
from REvoDesign.structure import PocketSearcher
ps = PocketSearcher(input_pse="session.pse")
ps.search_pockets()
```

### structure.SurfaceFinder
Find surface residues and export selections and residue list by cutoff.

Constructor:
- SurfaceFinder(input_pse: str)

Methods:
- process_surface_residues() -> None

Example:
```python
from REvoDesign.structure import SurfaceFinder
sf = SurfaceFinder(input_pse="session.pse")
sf.process_surface_residues()
```