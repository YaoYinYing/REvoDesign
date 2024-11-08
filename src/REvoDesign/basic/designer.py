from abc import abstractmethod

from ..citations import CitableModules


class ExternalDesignerAbstract(CitableModules):
    """
    Abstract class for external design, providing a framework for designing molecules.
    This class is abstract and must be inherited and implemented by concrete design classes.

    Attributes:
        pdb_filename (str): Name of the PDB file, initially set to None, indicating not specified.
        initialized (bool): Flag to indicate whether initialization has been performed, defaults to False.
        molecule: The molecule object, storing the molecule to be designed.
        reload (bool): A flag indicating whether to reload the design, defaults to False.

    """
    name: str = ''
    installed: bool = False


    def __init__(self, molecule):
        """
        Initialize the External Designer with a given molecule.

        Parameters:
            molecule: The molecular structure or data on which the design operations will be based.
        """
        self.pdb_filename = None
        self.initialized = False
        self.molecule = molecule
        self.reload = False

    def get_weights(self):
        """
        Retrieve the weights used in the design process.
        The implementation should define how these weights are calculated or retrieved.
        """

    @abstractmethod
    def initialize(self, *args, **kwargs):
        """
        Abstract method to initialize the design process.
        Must be implemented by subclasses to perform necessary setup steps.

        Parameters:
            *args, **kwargs: Flexible arguments that can be passed to perform specific initialization tasks.
        """

    def designer(self, *args, **kwargs):
        """
        Abstract method to execute the design algorithm.
        Subclasses must provide the actual design logic.

        Parameters:
            *args, **kwargs: Additional parameters that can be used during the design process.
        """
        raise NotImplementedError("Designer method not implemented")

    def scorer(self, sequence,):
        """
        Abstract method to evaluate or score a given sequence design.
        Determines the quality or fitness of the designed sequence.

        Parameters:
            sequence: The molecular sequence being evaluated.
            *args, **kwargs: Additional parameters for scoring, if required.
        """
        raise NotImplementedError("Scorer method not implemented")
