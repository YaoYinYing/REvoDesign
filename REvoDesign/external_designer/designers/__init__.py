from abc import abstractmethod
from REvoDesign.citations import CitableModules

'''
#### Hot replacement of designers ####

from REvoDesign.external_designer import EXTERNAL_DESIGNERS

if external_scorer and external_scorer in EXTERNAL_DESIGNERS:
    magician = EXTERNAL_DESIGNERS[external_scorer]
    if (
        not self.scorer  # non-scorer is set
        or magician.__name__  # a new magician is introduced here,
        != self.scorer.__class__.__name__  #  causing the class name of previous not matching that of the new one.
    ):
        logging.info(
            f'Pre-heating {external_scorer} ... This could take a while ...'
        )

        # instantialization of magician
        self.scorer = magician(
            molecule=self.design_molecule
        )
        # send initializing to progress bar.
        run_worker_thread_with_progress(
            worker_function=self.scorer.initialize,
            progress_bar=self.ui.progressBar,
        )

else:
    if self.scorer:
        logging.info(
            f'Cooling down {self.scorer.__class__.__name__} ...'
        )
    self.scorer = None


'''

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
        ...

    @abstractmethod
    def initialize(self, *args, **kwargs):
        """
        Abstract method to initialize the design process.
        Must be implemented by subclasses to perform necessary setup steps.

        Parameters:
            *args, **kwargs: Flexible arguments that can be passed to perform specific initialization tasks.
        """
        ...


    def designer(self, *args, **kwargs):
        """
        Abstract method to execute the design algorithm.
        Subclasses must provide the actual design logic.

        Parameters:
            *args, **kwargs: Additional parameters that can be used during the design process.
        """
        raise NotImplementedError("Designer method not implemented")

    def scorer(self, sequence, *args, **kwargs):
        """
        Abstract method to evaluate or score a given sequence design.
        Determines the quality or fitness of the designed sequence.

        Parameters:
            sequence: The molecular sequence being evaluated.
            *args, **kwargs: Additional parameters for scoring, if required.
        """
        raise NotImplementedError("Scorer method not implemented")



from .colabdesign import ColabDesigner_MPNN