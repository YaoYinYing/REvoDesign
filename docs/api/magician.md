### magician.Magician
Singleton manager for external design tools (designers).

Usage:
```python
from REvoDesign.magician import Magician
m = Magician()
# Configure by UI or directly by name
m.setup(gimmick_name="ColabDesigner_MPNN", molecule="objA")
# Access the current designer
if m.gimmick is not None:
    m.gimmick.initialize()
```

### magician.ExternalDesignerAbstract
Base class for external designers.

Attributes:
- name: str
- installed: bool
- scorer_only: bool
- prefer_lower: bool

Key methods:
- initialize(...)
- designer(...)
- scorer(mutant) -> float
- parallel_scorer(mutants, nproc=2) -> list[Mutant]

Implemented designers:
- ColabDesigner_MPNN
- ddg