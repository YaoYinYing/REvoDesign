### tools.customized_widgets

- notify_box(message: str, exception: Optional[Exception]=None)
- decide(message: str, yes: Callable, no: Optional[Callable] = None)
- refresh_window()
- set_widget_value(widget, value)
- getExistingDirectory() -> str
- WorkerThread
- ValueDialog, AskedValueCollection
- AppendableValueDialog, ask_for_appendable_values(title, options, banner=None)
- ImageWidget
- REvoDesignWidget

Example: asking values and calling a function
```python
from REvoDesign.tools.customized_widgets import ask_for_appendable_values, AskedValue

@ask_for_appendable_values(
    title="Run job",
    options=[
        AskedValue(key="epochs", val=10, typing=int, reason="Number of epochs"),
        AskedValue(key="lr", val=1e-3, typing=float, reason="Learning rate"),
    ],
)
def run_job(epochs: int, lr: float):
    ...

run_job()
```