### sidechain.SidechainSolver
Manage and run sidechain mutation runners.

Config model:
- SidechainSolverConfig(molecule: str, sidechain_solver_name: str, sidechain_solver_radius: Optional[float], sidechain_solver_model: Optional[str])

Usage:
```python
from REvoDesign.sidechain import SidechainSolver
solver = SidechainSolver()
solver.setup()  # picks runner based on UI/config
solver.refresh()  # reconfigure if config changed
```

Runners available:
- PyMOL_mutate
- DLPacker_worker
- PIPPack_worker

Helper constants:
- ALL_RUNNER_CLASSES
- IMPLEMENTED_RUNNER: dict[name -> class]