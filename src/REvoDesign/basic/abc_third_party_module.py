'''
Abstract Third-Party module.
'''

from REvoDesign.citations import CitableModuleAbstract


class ThirdPartyModuleAbstract(CitableModuleAbstract):
    """
    Abstract class for third-party modules.

    Attributes:
        name (str): The name of the third-party module.
        installed (bool): A flag indicating whether the module is installed.
        __bibtex__ (dict): A dictionary containing the BibTeX entries for the module.
    """

    name: str = ""
    installed: bool = False
