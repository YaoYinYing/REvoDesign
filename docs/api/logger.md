### logger

Exports:

- ROOT_LOGGER: logging.Logger
- setup_logging(level: int | str = "INFO") -> logging.Logger
- LoggerT: typing alias for the logger type

Example:

```python
from REvoDesign.logger import ROOT_LOGGER, setup_logging

setup_logging("DEBUG")
log = ROOT_LOGGER.getChild(__name__)
log.info("Hello")
```
