import os
from collections.abc import Mapping
from typing import Any

from REvoDesign import issues

from .ui_driver import ConfigBus


def register_environment_variables():
    from REvoDesign import ROOT_LOGGER

    logging = ROOT_LOGGER.getChild("environ_register")

    if ConfigBus._instance is None:
        raise issues.UnexpectedWorkflowError("ConfigBus must be initialized before creating EnvironBindItemCollection")

    bus = ConfigBus()

    EnvironBindItemCollection: Mapping[str, Any] | None = bus.get_value("variables", dict, cfg="environ")
    if EnvironBindItemCollection is None:
        return

    logging.debug("Registering environment variables")
    if isinstance(EnvironBindItemCollection, Mapping):
        for k, v in EnvironBindItemCollection.items():
            if v is not None:
                logging.debug(f"Adding {k}: {v}")
                os.environ[k] = v
    logging.debug("Environment variables registered")
