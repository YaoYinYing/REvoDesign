# ALL External designners must get registed at here.

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import List, Mapping, Optional

from REvoDesign import ConfigBus, issues
from REvoDesign.logger import root_logger

from REvoDesign.basic.abc_singleton import SingletonAbstract
from REvoDesign.tools.utils import timing
from ..basic import ExternalDesignerAbstract

from .designers import ColabDesigner_MPNN
from .designers.cart_ddg import ddg

logging = root_logger.getChild(__name__)

all_designer_classes: List[type[ExternalDesignerAbstract]]=[ColabDesigner_MPNN, ddg]
implemented_designer: Mapping[str, type[ExternalDesignerAbstract]] = MappingProxyType(
    {
        c.name: c
        for c in all_designer_classes
    }
)



# TODO: deprecation
EXTERNAL_DESIGNERS = {'ProteinMPNN': ColabDesigner_MPNN}

__all__ = ['ExternalDesignerAbstract', 'ColabDesigner_MPNN']

@dataclass(frozen=True)
class MagicianManager:
    """
    A class to manage the installation and usage of external design tools.
    """
    installed_worker: List[str] = field(
        default_factory=lambda: [c.name for c in all_designer_classes if c.installed]
    )

    def get(self, name, **kwargs):
        designer_class=implemented_designer[name]
        return designer_class(**kwargs)
    


class Magician(SingletonAbstract):
    def __init__(self):
        if not hasattr(self,'initialized'):
            self.bus: ConfigBus = ConfigBus()
            self.magician: Optional[ExternalDesignerAbstract]=None
            self.magician_manager = MagicianManager()

            self.initialized=True

    def setup(self,name_badget_id:Optional[str]='', name_cfg_term:Optional[str]='',**kwargs) -> 'Magician':
        if name_badget_id:
            name: str=str(self.bus.get_widget_value(name_badget_id))
        elif name_cfg_term:
            name: str=str(self.bus.get_value(name_cfg_term))
        else:
            raise issues.InvalidInputError('At lease one of name_badget_id or name_cfg_term should be provided.')

        # if the name is empty and the magician is initialized, cool it down
        if name is None or name =='' or name not in implemented_designer:
            if self.magician is not None:
                logging.info(
                f'Cooling down {self.magician.name} ...'
            )
            self.magician=None

            return self

        if not (isinstance(self.magician, ExternalDesignerAbstract) and self.magician.name==name):

            with timing(f'Pre-heating up Magician {name}'):
                try:
                    # if not ready, initialize it and return
                    logging.info(
                        'This could take a while ...'
                    )
                    self.magician = self.magician_manager.get(name=name,**kwargs)
                    self.magician.initialize(**kwargs)
                    return self
                except Exception as e:
                    raise issues.DependencyError(f'Failed to setup Magician {name}') from e
        
        logging.info(f'Designer stays unchanged: {self.magician.name}')
        return self
    