# Logging

How to use the REvoDesign logging system in your module.

## Quick start

```python
from REvoDesign.logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)
```

Every module gets its own child logger from `ROOT_LOGGER`. The logger name
matches the module path (e.g. `REvoDesign.application.launching`), so log
output is easy to trace to its source.

## Module-level child loggers

Use this pattern at module scope:

```python
# my_module.py
from REvoDesign.logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)

def do_work():
    logging.info("Starting work")
    logging.debug("Detail: %s", some_value)
```

## Instance loggers (plugin / window scope)

When a logger belongs to a specific plugin instance rather than the module,
store it as an instance attribute:

```python
class REvoDesignPlugin:
    def __init__(self):
        self.logging = ROOT_LOGGER.getChild(self.__class__.__name__)

    def make_window(self):
        self.logging.info("Window created")
```

This avoids cross-plugin state leakage that a module-level `logging` global
would cause when multiple plugin instances coexist.

## Circular import warning

Modules that are imported **before** the logger is initialized (early
bootstrap modules) must NOT create a child logger at import time — the
`ROOT_LOGGER` may not exist yet. For these early modules, either:

- Delay the `getChild` call to function scope, or
- Log via `ROOT_LOGGER` directly after the logger module has loaded

## Configuration

Log levels and handlers are configured in `src/REvoDesign/config/logger.yaml`:

| Setting | Purpose |
|---------|---------|
| `handlers.stdout.level` | Console output verbosity |
| `handlers.file.level` | Rotating file log verbosity |
| `handlers.notebook.level` | Notebook log verbosity |
| `loggers.root.level` | Root logger capture level |

The `logger_level_setter_ng()` function updates both the runtime handlers
and the persisted `logger.yaml` file.

## Log levels

Available levels (from `list_all_logger_levels()`):

`DEBUG` → `INFO` → `WARNING` → `ERROR` → `CRITICAL`

These are stored in `logger.yaml` under `levels` and cached at runtime.

## Structured (JSON) logging

File and notebook handlers use `REvoDesignLogFormatter` which emits each
record as a JSON object with configurable field keys:

```json
{"level": "INFO", "message": "Server started", "timestamp": "2026-07-09T...", "logger": "REvoDesign.server", ...}
```

Extra attributes added via `logging.info("msg", extra={"key": "val"})` are
included in the JSON output automatically.

## Known limitations

- **Windows file-race**: Parallel subprocess tasks (e.g. sidechain modeling)
  may contend for the rotating log file. The `QueueHandler` serialises writes
  within a single process but does not coordinate across processes.
