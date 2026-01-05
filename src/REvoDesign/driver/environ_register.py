import os
from collections.abc import Mapping
from typing import Any

from omegaconf import DictConfig

from REvoDesign import issues

from ..tools.customized_widgets import ask_for_appendable_values
from .ui_driver import ConfigBus


def register_environment_variables():
    if ConfigBus._instance is None:
        raise issues.UnexpectedWorkflowError("ConfigBus must be initialized before creating EnvironBindItemCollection")

    bus = ConfigBus()

    EnvironBindItemCollection: Mapping[str, Any] | None = bus.get_value("variables", dict, cfg="environ")
    if EnvironBindItemCollection is None:
        return

    if isinstance(EnvironBindItemCollection, Mapping):
        for k, v in EnvironBindItemCollection.items():
            if v is not None:
                os.environ[k] = v


def add_new_environment_variables():
    """
    Adds new environment variables to the system.
    """

    if ConfigBus._instance is None:
        raise issues.UnexpectedWorkflowError("ConfigBus must be initialized.")

    bus = ConfigBus()

    EnvironBindItemCollection: DictConfig = bus.get_value("variables", DictConfig, cfg="environ")
    if EnvironBindItemCollection is None:
        EnvironBindItemCollection = DictConfig({})

    AskedEnvironBindItemCollection = ask_for_appendable_values()
    if not AskedEnvironBindItemCollection:
        return

    EnvironBindItemCollection.update(AskedEnvironBindItemCollection.asdict)
    bus.set_value("variables", EnvironBindItemCollection, cfg="environ")
    register_environment_variables()
    print(f"Environment variables are updated to configuration.\n {AskedEnvironBindItemCollection.asdict}")
    print("To apply these changes, a restart of the application may be required.")
    bus.cfg_group["environ"].save()


def drop_environment_variables():
    """
    Drop all environment variables that are bound to the configuration.
    """
    if ConfigBus._instance is None:
        raise issues.UnexpectedWorkflowError("ConfigBus must be initialized.")

    bus = ConfigBus()

    AskedEnvironBindItemCollection = ask_for_appendable_values()

    ev_in_cfg: DictConfig | None = bus.get_value("variables", DictConfig, cfg="environ")
    if not ev_in_cfg:
        print("No environment variables are currently bound to the configuration.")
        ev_in_cfg = DictConfig({})

    if AskedEnvironBindItemCollection:
        for key, val in AskedEnvironBindItemCollection.asdict.items():
            if key in ev_in_cfg:
                del ev_in_cfg[key]
            if key in os.environ:
                del os.environ[key]
        # update the config
        bus.set_value("variables", ev_in_cfg, cfg="environ")

        print("The environment variables are unbound against the configuration.")
        bus.cfg_group["environ"].save()
