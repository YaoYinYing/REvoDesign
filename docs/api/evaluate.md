### evaluate.Evalutator

Assist inspecting and selecting mutants in the PyMOL scene and persisting choices.

Constructor:
- Evalutator()

Selected methods:
- activate_focused()
- mutant_decision(decision_to_accept: bool)
- walk_mutant_groups(walk_to_next, progressBar_mutant_choosing)

Example:
```python
from REvoDesign.evaluate import Evalutator
ev = Evalutator()
ev.activate_focused()
```