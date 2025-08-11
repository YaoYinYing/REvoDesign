### phylogenetics

Classes:

- MutateWorker: orchestrate profile-based design or external designer runs.
- VisualizingWorker: utilities to render/visualize coevolution and designs. (see code for details)
- GremlinAnalyser: GREMLIN coevolution analysis helpers.

Example (design from profile):

```python
from REvoDesign.phylogenetics import MutateWorker
mw = MutateWorker()
mw.run_mutant_loading_from_profile()
```
