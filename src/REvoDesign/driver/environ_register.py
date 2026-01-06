import os
from collections.abc import Mapping
from typing import Any

from REvoDesign import issues

from .ui_driver import ConfigBus


def register_environment_variables():
    from REvoDesign import ROOT_LOGGER

    logging = ROOT_LOGGER.getChild(__name__)

    if ConfigBus._instance is None:
        raise issues.UnexpectedWorkflowError("ConfigBus must be initialized before creating EnvironBindItemCollection")

    bus = ConfigBus()

    # force to reload from the yaml file
    bus.cfg_group["environ"].reload()

    # retrieve the environment variables from config object
    EnvironBindItemCollection: Mapping[str, Any] | None = bus.get_value("variables", dict, cfg="environ")
    if not EnvironBindItemCollection:
        logging.debug("No environment variables to register")
        return

    # register environment variables
    logging.debug("Registering environment variables")
    if isinstance(EnvironBindItemCollection, Mapping):
        for k, v in EnvironBindItemCollection.items():
            if v is None:
                continue
            logging.debug(f"Adding {k}: {v}")
            os.environ[k] = v
    logging.debug("Environment variables registered")
