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
from REvoDesign.logger import root_logger
from REvoDesign.tools.utils import timing

# 1. implement and import the designer
from .designers import ColabDesigner_MPNN, ddg

logging = root_logger.getChild(__name__)

# 2. add the designer class to this list
all_designer_classes: List[type[ExternalDesignerAbstract]] = [
    ColabDesigner_MPNN,
    ddg,
]
implemented_designers: Mapping[str, type[ExternalDesignerAbstract]] = (
    MappingProxyType({c.name: c for c in all_designer_classes})
)


__all__ = ["ExternalDesignerAbstract", "ColabDesigner_MPNN"]


@dataclass(frozen=True)
class MagicianManager:
    """
    A class to manage the installation and usage of external design tools.
    """

    installed_worker: List[str] = field(
        default_factory=lambda: [
            c.name for c in all_designer_classes if c.installed
        ]
    )

    def get(self, name, **kwargs) -> ExternalDesignerAbstract:
        designer_class = implemented_designers[name]
        return designer_class(**kwargs)


class Magician(SingletonAbstract):
    def singleton_init(self):
        self.bus: ConfigBus = ConfigBus()
        self.magician: Optional[ExternalDesignerAbstract] = None
        self.magician_manager = MagicianManager()

    def setup(
        self,
        name_badget_id: Optional[str] = "",
        name_cfg_term: Optional[str] = "",
        magician_name: Optional[str] = "",
        **kwargs,
    ) -> "Magician":
        if name_badget_id:
            name = self.bus.get_widget_value(name_badget_id, str)
        elif name_cfg_term:
            name = self.bus.get_value(name_cfg_term, str, reject_none=True)
        elif magician_name:
            name = magician_name

        # if the name is empty and the magician is initialized, cool it down
        else:
            if self.magician is not None:
                logging.info(f"Cooling down {self.magician.name} ...")
            self.magician = None

            return self

        if not (
            isinstance(self.magician, ExternalDesignerAbstract)
            and self.magician.name == name
        ):

            with timing(f"Pre-heating up Magician {name}"):
                try:
                    # if not ready, initialize it and return
                    logging.info("This could take a while ...")
                    self.magician = self.magician_manager.get(
                        name=name, **kwargs
                    )
                    self.magician.initialize(**kwargs)
                    return self
                except KeyError:
                    # not a valid class, return with cooled down.
                    return self.setup()
                except Exception as e:
                    raise issues.DependencyError(
                        f"Failed to setup Magician {name}"
                    ) from e

        logging.info(f"Designer stays unchanged: {self.magician.name}")
        return self
