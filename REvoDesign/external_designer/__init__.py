# ALL External designners must get registed at here.

from REvoDesign.external_designer.designers import (
    ExternalDesignerAbstract,
    ColabDesigner_MPNN,
)

EXTERNAL_DESIGNERS = {'ProteinMPNN': ColabDesigner_MPNN}

__all__ = ['ExternalDesignerAbstract', 'ColabDesigner_MPNN']
