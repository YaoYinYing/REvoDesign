# ALL External designners must get registed at here.


from REvoDesign.basic import ExternalDesignerAbstract
from REvoDesign.external_designer.designers import ColabDesigner_MPNN

EXTERNAL_DESIGNERS = {'ProteinMPNN': ColabDesigner_MPNN}

__all__ = ['ExternalDesignerAbstract', 'ColabDesigner_MPNN']
