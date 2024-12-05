import os
from typing import Any, Mapping, Optional
from REvoDesign import issues

from omegaconf import DictConfig

from .ui_driver import ConfigBus
from ..tools.customized_widgets import AskedValue, AskedValueCollection, ask_for_values, ask_for_appendable_values


def register_environment_variables():
    if ConfigBus._instance is None:
        raise issues.UnexpectedWorkflowError('ConfigBus must be initialized before creating EnvironBindItemCollection')

    bus=ConfigBus()

    EnvironBindItemCollection: Optional[Mapping[str, Any]]= bus.get_value('environment.variables')
    if EnvironBindItemCollection is None:
        return
    
    if isinstance(EnvironBindItemCollection,Mapping):
        for k,v in EnvironBindItemCollection.items():
            if v is not None:
                os.environ[k]=v


def add_new_environment_variables():
    """
    Adds new environment variables to the system.
    """
    if ConfigBus._instance is None:
        raise issues.UnexpectedWorkflowError('ConfigBus must be initialized.')
    
    bus=ConfigBus()

    EnvironBindItemCollection: Optional[DictConfig]= bus.get_value('environment.variables')
    if EnvironBindItemCollection is None:
        EnvironBindItemCollection= DictConfig({})

    AskedEnvironBindItemCollection = ask_for_appendable_values()
    if not AskedEnvironBindItemCollection:
        return
    
    EnvironBindItemCollection.update(AskedEnvironBindItemCollection.asdict)
    register_environment_variables()
    print(f'Environment variables are updated to configuration.\n {AskedEnvironBindItemCollection.asdict}')
    print('To apply these changes, a restart of the application may be required.')


def drop_environment_variables():
    """
    Drop all environment variables that are bound to the configuration.
    """
    if ConfigBus._instance is None:
        raise issues.UnexpectedWorkflowError('ConfigBus must be initialized.')
    
    bus=ConfigBus()

    AskedEnvironBindItemCollection = ask_for_appendable_values()
    if AskedEnvironBindItemCollection:
        for key, val in AskedEnvironBindItemCollection.asdict.items():
            if key in bus.cfg.environment.variables:
                del bus.cfg.environment.variables[key]
            if key in os.environ:
                del os.environ[key]


