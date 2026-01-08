"""
Logger for REvoDesign
"""

import atexit
import datetime as dt
import json
import logging as python_logging
import logging.handlers as python_logging_handlers
import os
import queue
from logging import config as python_logging_config

from omegaconf import DictConfig
from platformdirs import user_log_path
from typing_extensions import override

from ..bootstrap import reload_config_file

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
        fmt_keys: dict[str, str] | None = None,
    ):
        super().__init__()
        self.fmt_keys = fmt_keys or {}

    @override
    def format(self, record: python_logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: python_logging.LogRecord):
        always_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(record.created, tz=dt.timezone.utc).isoformat(),
        }
        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: (msg_val if (msg_val := always_fields.pop(val, None)) is not None else getattr(record, val))
            for key, val in self.fmt_keys.items()
        }
        message.update(always_fields)

        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message


class NonErrorFilter(python_logging.Filter):
    @override
    def filter(self, record: python_logging.LogRecord) -> bool | python_logging.LogRecord:
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

    log_handlers = []

    # Create a queue for the QueueHandler
    log_queue = queue.Queue(10_000)

    # Initialize handlers
    stdout_handler = python_logging.StreamHandler()
    # TODO: if pytest is installed, use DEBUG level instead
    stdout_handler.setLevel(log_config.handlers.stdout.level)
    stdout_handler.setFormatter(python_logging.Formatter(log_config.formatters.simple.format))
    log_handlers.append(stdout_handler)

    # stderr_handler = python_logging.StreamHandler()
    # stderr_handler.setLevel(log_config.handlers.stderr.level)
    # stderr_handler.setFormatter(
    #     python_logging.Formatter(log_config.formatters.simple.format)
    # )

    if file_filename is not None:
        file_handler = python_logging_handlers.RotatingFileHandler(
            filename=file_filename,
            maxBytes=file_maxBytes,
            backupCount=file_backupCount,
        )
        file_handler.setLevel(log_config.handlers.file.level)
        # Custom formatter needs to be implemented accordingly
        file_handler.setFormatter(REvoDesignLogFormatter(fmt_keys=dict(log_config.formatters.json.fmt_keys)))
        log_handlers.append(file_handler)

    if notebook_filename is not None:
        notebook_handler = python_logging_handlers.RotatingFileHandler(
            filename=notebook_filename,
            maxBytes=notebook_maxBytes,
            backupCount=notebook_backupCount,
        )
        notebook_handler.setLevel(log_config.handlers.notebook.level)
        # Custom formatter needs to be implemented accordingly
        notebook_handler.setFormatter(REvoDesignLogFormatter(fmt_keys=dict(log_config.formatters.json.fmt_keys)))
        log_handlers.append(notebook_handler)

    # Set up the QueueHandler
    queue_handler = python_logging_handlers.QueueHandler(log_queue)
    queue_handler.setLevel(log_config.loggers.root.level)  # Capture all logs

    # Initialize the QueueListener with the handlers
    listener = python_logging_handlers.QueueListener(
        log_queue,
        *log_handlers,
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


LOGGER_CONFIG = reload_config_file("logger")


def setup_logging() -> python_logging.Logger:
    cfg = LOGGER_CONFIG

    logfile = cfg.handlers.file.filename
    notebookfile = cfg.handlers.notebook.filename

    if logfile == "AUTO":
        logfile = user_log_path("REvoDesign", ensure_exists=True)
        cfg.handlers.file.filename = os.path.join(logfile, "REvoDesign.runtime.log")

    if notebookfile == "AUTO":
        notebookfile = user_log_path("REvoDesign", ensure_exists=True)
        cfg.handlers.notebook.filename = os.path.join(notebookfile, "REvoDesign.notebook.log")

    if logfile is not None:
        logging_dir = os.path.dirname(os.path.abspath(logfile))
        os.makedirs(logging_dir, exist_ok=True)

    if notebookfile is not None:
        notebook_dir = os.path.dirname(os.path.abspath(notebookfile))

        os.makedirs(notebook_dir, exist_ok=True)
    logger = setup_logging_from_dictconfig(log_config=cfg)
    return logger


# 3. initialize logging config and root logger, depending on config
ROOT_LOGGER = setup_logging()

logging = ROOT_LOGGER.getChild(__name__)

LoggerT = python_logging.Logger


def logger_level_setter(**kwargs) -> None:
    """Set the logger level to the given value.

    Args:
        level (int): The level to set the logger to.
    """
    logger_level_setter_ng(kwargs)


def reload_logging_config():
    # Optional: Shut down existing logging gracefully
    python_logging.shutdown()

    # Reload the configuration from a file (e.g., logging.conf)
    # Note: Use logging.config.fileConfig for .conf files
    # or logging.config.dictConfig for dictionary/JSON/YAML configs
    from ..bootstrap.set_config import ConfigConverter

    python_logging_config.dictConfig(ConfigConverter.convert(LOGGER_CONFIG))


def logger_level_setter_ng(settings: dict[str, str]):
    from REvoDesign.driver.ui_driver import ConfigBus

    global ROOT_LOGGER
    logging.info(f"Setting logger level")

    all_logger_channels = list_all_logger_channels()

    root_setting = settings.pop("root", None)

    if root_setting:
        # apply to the config
        ConfigBus().set_value("loggers.root.level", root_setting.upper(), cfg="logger")
        # apply to the runtime
        ROOT_LOGGER.setLevel(level=root_setting.upper())

    for channel, level in settings.items():
        if channel not in all_logger_channels:
            logging.warning(f"Logger channel {channel} does not exist")
            continue
        # apply to the config
        ConfigBus().set_value(f"handlers.{channel}.level", level.upper(), cfg="logger")
        # apply to the runtime
        for handler in ROOT_LOGGER.handlers:
            if handler.name == channel:
                logging.debug(f"Setting logger level for {channel} to {level}")
                handler.setLevel(level)
                break

    # save the logger config
    logger_config = ConfigBus().cfg_group["logger"]

    # update the global variable out of the closure
    global LOGGER_CONFIG
    LOGGER_CONFIG = logger_config.cfg

    # save it to file
    logger_config.save()

    # reload the logger
    reload_logging_config()


def get_current_logger_level(channel: str = "root"):
    from REvoDesign.driver.ui_driver import ConfigBus

    if channel == "root":
        key = "loggers.root.level"
    else:
        key = f"handlers.{channel}.level"
    try:
        return ConfigBus().get_value(key, str, reject_none=True, cfg="logger")
    except Exception as e:
        logging.error(f"Logger channel {channel} does not exist like key: {key}")
        logging.error(f"Available channels: {list_all_logger_channels()}")
        logging.error(f'All config: {ConfigBus().cfg_group["logger"]}')
        raise e


list_all_logger_levels = lambda: ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
list_all_logger_channels = lambda: ["stdout", "stderr", "file", "notebook", "root"]
list_all_logger_formatters_non_json = lambda: ["simple", "complex", "detailed"]

get_current_channel_level = lambda channel: get_current_logger_level(channel)
