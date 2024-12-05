import os
from typing import Any, Mapping, Optional
from REvoDesign import issues


from .ui_driver import ConfigBus


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


