import datetime as dt
import json
import logging.config as python_logging_config
import logging as python_logging
import os
import traceback
from typing_extensions import override
from omegaconf import DictConfig
from REvoDesign.tools.post_installed import reload_config_file
from REvoDesign.tools.post_installed import ConfigConverter
from queue import Queue

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


class MyJSONFormatter(python_logging.Formatter):
    def __init__(
        self,
        *,
        fmt_keys: dict[str, str] | None = None,
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
    def filter(self, record: python_logging.LogRecord) -> bool | python_logging.LogRecord:
        return record.levelno <= python_logging.INFO
    
LOGGER_QUEUE=Queue()

def setup_logging():
    c=ConfigConverter()
    try:
        cfg:DictConfig=reload_config_file()
        log_cfg=c.convert(cfg.log)
        logging_dir=os.path.dirname(os.path.abspath(cfg.log.handlers.file.filename))
        os.makedirs(logging_dir,exist_ok=True)
        python_logging_config.dictConfig(log_cfg)
    except Exception:
        traceback.print_exc()


logging = python_logging.getLogger('REvoDesign')
