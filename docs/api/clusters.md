### clusters.ClusterRunner

Run sequence combination and clustering workflows; optionally run mutate-relax scoring.

Constructor:
- ClusterRunner(PWD: str)

Methods:
- run_clustering() -> None

Example:
```python
from REvoDesign.clusters import ClusterRunner
cr = ClusterRunner(PWD="/path/to/workdir")
cr.run_clustering()
```