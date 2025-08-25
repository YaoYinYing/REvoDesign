'''
Module to manage external design tools.
Collect, Register, Heat up and Cool down.
'''
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import List, Mapping, Optional
from REvoDesign import ConfigBus, issues
from REvoDesign.basic import ExternalDesignerAbstract
from REvoDesign.basic.abc_singleton import SingletonAbstract
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.tools.utils import timing
from .designers import ColabDesigner_MPNN, ddg
logging = ROOT_LOGGER.getChild(__name__)
ALL_DESIGNER_CLASSES: List[type[ExternalDesignerAbstract]] = [
    ColabDesigner_MPNN,
    ddg,
]
IMPLEMENTED_DESIGNERS: Mapping[str, type[ExternalDesignerAbstract]] = (
    MappingProxyType({c.name: c for c in ALL_DESIGNER_CLASSES})
)
__all__ = ["ExternalDesignerAbstract", "ColabDesigner_MPNN"]
@dataclass(frozen=True)
class MagicianAssistant:
    """
    A class to manage the installation and usage of external design tools.
    """
    installed_worker: List[str] = field(
        default_factory=lambda: [
            c.name for c in ALL_DESIGNER_CLASSES if c.installed
        ]
    )
    def get(self, name, **kwargs) -> ExternalDesignerAbstract:
        designer_class = IMPLEMENTED_DESIGNERS[name]
        return designer_class(**kwargs)
class Magician(SingletonAbstract):
    """
    The Magician class inherits from SingletonAbstract, ensuring that there is only one instance of Magician.
    This class is responsible for setting up and managing the magician's gimmicks, including initializing
    and cooling down gimmicks based on different configurations.
    """
    def singleton_init(self):
        """
        Initializes the Magician instance, including setting up the configuration bus, initializing the gimmick,
        and creating an instance of the assistant.
        """
        
        self.bus: ConfigBus = ConfigBus()
        
        self.gimmick: Optional[ExternalDesignerAbstract] = None
        
        self.magician_assistant = MagicianAssistant()
    def setup(
        self,
        name_badget_id: Optional[str] = "",
        name_cfg_term: Optional[str] = "",
        gimmick_name: Optional[str] = "",
        **kwargs,
    ) -> "Magician":
        """
        Sets up the magician's gimmick based on different methods.
        Parameters:
        - name_badget_id: Optional[str] - The ID badge for obtaining the name.
        - name_cfg_term: Optional[str] - The configuration term for obtaining the name.
        - gimmick_name: Optional[str] - The directly provided name of the gimmick.
        - **kwargs: Additional parameters for setting up the gimmick.
        Returns:
        - Magician: Returns the instance of the Magician for method chaining.
        """
        
        if name_badget_id:
            name = self.bus.get_widget_value(name_badget_id, str)
        elif name_cfg_term:
            name = self.bus.get_value(name_cfg_term, str, reject_none=True)
        elif gimmick_name:
            name = gimmick_name
        
        else:
            if self.gimmick is not None:
                logging.info(f"Cooling down {self.gimmick.name} ...")
            self.gimmick = None
            return self
        
        if not (
            isinstance(self.gimmick, ExternalDesignerAbstract)
            and self.gimmick.name == name
        ):
            with timing(f"Pre-heating up Magician's gimmick {name}"):
                try:
                    
                    logging.info("This could take a while ...")
                    self.gimmick = self.magician_assistant.get(
                        name=name, **kwargs
                    )
                    self.gimmick.initialize(**kwargs)
                    return self
                except KeyError:
                    
                    return self.setup()
                except Exception as e:
                    raise issues.DependencyError(
                        f"Failed to setup Magician's gimmick {name}"
                    ) from e
        
        logging.info(f"Designer stays unchanged: {self.gimmick.name}")
        return self