# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


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
    environ_bind_items: Mapping[str, Any] | None = bus.get_value("variables", dict, cfg="environ")
    if not environ_bind_items:
        logging.debug("No environment variables to register")
        return
    override_existing = bool(bus.get_value("override_existing", bool, cfg="environ", default_value=False))

    # register environment variables
    logging.debug("Registering environment variables")
    if isinstance(environ_bind_items, Mapping):
        for k, v in environ_bind_items.items():
            if v is None:
                continue
            if k in os.environ and not override_existing:
                logging.debug("Skipping %s because it already exists in the process environment", k)
                continue
            logging.debug(f"Adding {k}: {v}")
            os.environ[k] = v
    logging.debug("Environment variables registered")
