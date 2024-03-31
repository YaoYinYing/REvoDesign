import atexit
import datetime as dt
import json
import logging.handlers as python_logging_handlers
import logging as python_logging
import os
import queue
from typing import Union
from typing_extensions import override
from omegaconf import DictConfig


LOG_RECORD_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class REvoDesignLogFormatter(python_logging.Formatter):
    def __init__(
        self,
        *,
        fmt_keys: Union[dict[str, str], None] = None,
    ):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    @override
    def format(self, record: python_logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: python_logging.LogRecord):
        always_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }
        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: msg_val
            if (msg_val := always_fields.pop(val, None)) is not None
            else getattr(record, val)
            for key, val in self.fmt_keys.items()
        }
        message.update(always_fields)

        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message


class NonErrorFilter(python_logging.Filter):
    @override
    def filter(
        self, record: python_logging.LogRecord
    ) -> Union[bool, python_logging.LogRecord]:
        return record.levelno <= python_logging.INFO


def setup_logging_from_dictconfig(
    log_config: DictConfig,
) -> python_logging.Logger:
    # Directly access configuration values using native expressions
    file_filename = log_config.handlers.file.filename
    file_maxBytes = log_config.handlers.file.maxBytes
    file_backupCount = log_config.handlers.file.backupCount
    notebook_filename = log_config.handlers.notebook.filename
    notebook_maxBytes = log_config.handlers.notebook.maxBytes
    notebook_backupCount = log_config.handlers.notebook.backupCount

    # Create a queue for the QueueHandler
    log_queue = queue.Queue(-1)  # No limit on queue size

    # Initialize handlers
    stdout_handler = python_logging.StreamHandler()
    stdout_handler.setLevel(log_config.handlers.stdout.level)
    stdout_handler.setFormatter(
        python_logging.Formatter(log_config.formatters.simple.format)
    )

    # stderr_handler = python_logging.StreamHandler()
    # stderr_handler.setLevel(log_config.handlers.stderr.level)
    # stderr_handler.setFormatter(
    #     python_logging.Formatter(log_config.formatters.simple.format)
    # )

    file_handler = python_logging_handlers.RotatingFileHandler(
        filename=file_filename,
        maxBytes=file_maxBytes,
        backupCount=file_backupCount,
    )
    file_handler.setLevel(log_config.handlers.file.level)
    # Custom formatter needs to be implemented accordingly
    file_handler.setFormatter(
        REvoDesignLogFormatter(
            fmt_keys=dict(log_config.formatters.json.fmt_keys)
        )
    )

    notebook_handler = python_logging_handlers.RotatingFileHandler(
        filename=notebook_filename,
        maxBytes=notebook_maxBytes,
        backupCount=notebook_backupCount,
    )
    notebook_handler.setLevel(log_config.handlers.notebook.level)
    # Custom formatter needs to be implemented accordingly
    notebook_handler.setFormatter(
        REvoDesignLogFormatter(
            fmt_keys=dict(log_config.formatters.json.fmt_keys)
        )
    )

    # Set up the QueueHandler
    queue_handler = python_logging_handlers.QueueHandler(log_queue)
    queue_handler.setLevel(log_config.loggers.root.level)  # Capture all logs

    # Initialize the QueueListener with the handlers
    listener = python_logging_handlers.QueueListener(
        log_queue,
        stdout_handler,
        # stderr_handler,
        file_handler,
        notebook_handler,
        respect_handler_level=True,
    )

    # Configure the root logger
    python_logging.basicConfig(
        level=log_config.loggers.root.level,
        handlers=[queue_handler],
    )  # Adjust as needed
    # Start the listener
    listener.start()

    # Ensure the listener is stopped gracefully on program exit
    atexit.register(listener.stop)

    return python_logging.getLogger()


def setup_logging() -> python_logging.Logger:
    from REvoDesign import reload_config_file

    cfg: DictConfig = reload_config_file()
    logging_dir = os.path.dirname(
        os.path.abspath(cfg.log.handlers.file.filename)
    )
    notebook_dir = os.path.dirname(
        os.path.abspath(cfg.log.handlers.notebook.filename)
    )
    os.makedirs(logging_dir, exist_ok=True)
    os.makedirs(notebook_dir, exist_ok=True)
    logger = setup_logging_from_dictconfig(log_config=cfg.log)
    return logger
