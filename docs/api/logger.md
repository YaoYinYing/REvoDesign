# Logger

The logging system provides JSON-formatted structured logging with support for multiple output channels (stdout, rotating file, notebook file) via a queue-based asynchronous handler architecture. Configuration is driven by a `logger.yaml` OmegaConf file.

---

## Module-Level Exports

### ROOT_LOGGER

The root `logging.Logger` instance for the application. All child loggers should be obtained via `ROOT_LOGGER.getChild(__name__)`. Created by `setup_logging()` at module import time.

### LoggerT

Type alias for `logging.Logger`. Useful for type annotations throughout the codebase.

### LOGGER_CONFIG

The `DictConfig` loaded from `logger.yaml` via `reload_config_file("logger")`. Holds the structured logging configuration (formatters, handlers, loggers). Modified at runtime by `logger_level_setter_ng` to persist level changes.

### LOG_RECORD_BUILTIN_ATTRS

A set of built-in LogRecord attribute names, used by `REvoDesignLogFormatter` to separate standard fields from extra custom fields during JSON serialization.

---

## Setup and Initialization

### setup_logging

Initializes the logging system by resolving `AUTO` paths via `platformdirs.user_log_path`, ensuring log directories exist, then delegating to `setup_logging_from_dictconfig`. Called once at module import time to create `ROOT_LOGGER`.

::: REvoDesign.logger.logger.setup_logging

### setup_logging_from_dictconfig

Builds the logging infrastructure from a `DictConfig`: creates stdout, file, and notebook handlers, wires them through a `QueueHandler`/`QueueListener` pair for non-blocking I/O, and registers the listener for graceful shutdown via `atexit`.

::: REvoDesign.logger.logger.setup_logging_from_dictconfig

---

## Log Level Management

### logger_level_setter

Convenience function that accepts keyword arguments (`root="DEBUG"`, `stdout="INFO"`, etc.) and delegates to `logger_level_setter_ng`.

::: REvoDesign.logger.logger.logger_level_setter

### logger_level_setter_ng

Core function that sets logger levels for different channels. Updates both the runtime handlers and the persisted `logger.yaml` configuration, then reloads logging config.

::: REvoDesign.logger.logger.logger_level_setter_ng

### get_current_logger_level

Returns the current log level for a given channel (e.g. `"root"`, `"file"`, `"stdout"`).

::: REvoDesign.logger.logger.get_current_logger_level

### get_current_channel_level

Shortcut that delegates to `get_current_logger_level`.

::: REvoDesign.logger.logger.get_current_channel_level

---

## Channel and Level Discovery

### list_all_logger_levels

Returns the list of available log levels: `["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]`.

::: REvoDesign.logger.logger.list_all_logger_levels

### list_all_logger_channels

Returns the list of available logging channels: `["stdout", "stderr", "file", "notebook", "root"]`.

::: REvoDesign.logger.logger.list_all_logger_channels

### list_all_logger_formatters_non_json

Returns the list of non-JSON formatter names: `["simple", "complex", "detailed"]`.

::: REvoDesign.logger.logger.list_all_logger_formatters_non_json

---

## Configuration Reload

### reload_logging_config

Shuts down the existing logging system, then reloads configuration from the `LOGGER_CONFIG` DictConfig using `logging.config.dictConfig`.

::: REvoDesign.logger.logger.reload_logging_config

---

## Custom Formatters and Filters

### REvoDesignLogFormatter

A JSON-based log formatter. Formats each log record as a JSON dictionary with user-controllable field keys. Extra attributes not in `LOG_RECORD_BUILTIN_ATTRS` are included automatically.

::: REvoDesign.logger.logger.REvoDesignLogFormatter
    options:
        members:
            - format
            - _prepare_log_dict

### NonErrorFilter

A logging filter that passes only records with level `INFO` or below (i.e., excludes `WARNING`, `ERROR`, `CRITICAL`). Intended for use on stdout handlers to keep stderr clean for errors.

::: REvoDesign.logger.logger.NonErrorFilter
    options:
        members:
            - filter
