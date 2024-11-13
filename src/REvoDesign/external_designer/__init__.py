# ALL External designners must get registed at here.

from typing import List
from ..basic import ExternalDesignerAbstract

from .designers import ColabDesigner_MPNN
from .designers.cart_ddg import ddg

all_designer_classes: List[type[ExternalDesignerAbstract]]=[ColabDesigner_MPNN, ddg]

# TODO: deprecation
EXTERNAL_DESIGNERS = {'ProteinMPNN': ColabDesigner_MPNN}

__all__ = ['ExternalDesignerAbstract', 'ColabDesigner_MPNN']
