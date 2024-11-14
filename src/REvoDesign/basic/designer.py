from abc import abstractmethod
from typing import Any, List, Union

from joblib import Parallel, delayed
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.common.Mutant import Mutant

from REvoDesign.citations import CitableModules


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

    name: str = ""
    installed: bool = False
    scorer_only: bool = False
    no_need_to_score_wt: bool = False
    # whether lower scores are preferred
    prefer_lower: bool = False

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

    def scorer(
        self, mutant: Union[Mutant, RosettaPyProteinSequence], **kwargs
    ):
        """
        Abstract method to evaluate or score a given sequence design.
        Determines the quality or fitness of the designed sequence.

        Parameters:
            mutant: The molecular sequence being evaluated.
            *args, **kwargs: Additional parameters for scoring, if required.
        """
        raise NotImplementedError("Scorer method not implemented")

    def preffer_substitutions(self, aa: Any): ...

    def parallel_scorer(
        self, mutants: List[Mutant], nproc: int = 2, **kwargs
    ) -> List[Mutant]:
        """
        Parallelize the scoring of a list of mutants.
        """
        mutants = [mutant for mutant in mutants if not mutant.empty]
        res = Parallel(n_jobs=nproc)(
            delayed(self.scorer)(mutant) for mutant in mutants
        )
        scores: List[float] = list(res)  # type: ignore
        return self.score_mutant_mapping(mutants, scores)

    @staticmethod
    def score_mutant_mapping(
        mutants: List[Mutant], scores: List[float]
    ) -> List[Mutant]:
        """
        Assign scores to mutants.
        """
        for mutant, score in zip(mutants, scores):
            mutant.mutant_score = score
        return mutants
