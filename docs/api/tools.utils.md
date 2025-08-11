### tools.utils

- run_command(cmd: list[str], env: Optional[dict] = None, verbose: bool = False) -> subprocess.CompletedProcess
- run_worker_thread_with_progress(func, ..., progress_bar)
- timing(msg: str, unit: Literal['ms','sec','min','hr'] = 'sec') as context manager
- generate_strong_password(length=16) -> str
- random_deduplicate(seq: np.ndarray, score: np.ndarray) -> tuple[np.ndarray, np.ndarray]
- minibatches(inputs_data, batch_size)
- minibatches_generator(inputs_data_generator, batch_size)
- extract_archive(archive_file, extract_to)
- get_color(cmap, data, min_value, max_value) -> tuple[float,float,float]
- cmap_reverser(cmap: str, reverse: bool=False) -> str
- rescale_number(number, min_value, max_value) -> float
- count_and_sort_characters(input_string, characters) -> dict
- device_picker() -> list[str]
- pairwise(iterable)

Examples:

```python
from REvoDesign.tools.utils import timing, generate_strong_password, extract_archive

with timing("do something"):
    ...

pwd = generate_strong_password(20)
extract_archive("/tmp/data.zip", "/tmp/out")
```
