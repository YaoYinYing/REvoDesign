from abc import abstractmethod
from typing import Any, List, Union
from joblib import Parallel, delayed
from RosettaPy.common.mutation import RosettaPyProteinSequence
from REvoDesign.basic import ThirdPartyModuleAbstract
from REvoDesign.common.mutant import Mutant
class ExternalDesignerAbstract(ThirdPartyModuleAbstract):
    name: str = ""
    installed: bool = False
    scorer_only: bool = False
    no_need_to_score_wt: bool = False
    prefer_lower: bool = False
    def __init__(self, molecule):
        self.pdb_filename = None
        self.initialized = False
        self.molecule = molecule
        self.reload = False
    def get_weights(self):
        raise NotImplementedError("Get_weights method not implemented")
    @abstractmethod
    def initialize(self, *args, **kwargs):
    def designer(self, *args, **kwargs):
        raise NotImplementedError("Designer method not implemented")
    def scorer(
        self, mutant: Union[Mutant, RosettaPyProteinSequence], **kwargs
    ) -> float:
        raise NotImplementedError("Scorer method not implemented")
    def preffer_substitutions(self, aa: Any):
        raise NotImplementedError(
            f"Preffer_substitutions method not implemented in this subclass of {self.__class__.__name__}")
    def parallel_scorer(
        self, mutants: List[Mutant], nproc: int = 2, **kwargs
    ) -> List[Mutant]:
        mutants = [mutant for mutant in mutants if not mutant.empty]
        res = Parallel(n_jobs=nproc)(
            delayed(self.scorer)(mutant) for mutant in mutants
        )
        scores: List[float] = list(res)  
        return self.score_mutant_mapping(mutants, scores)
    @staticmethod
    def score_mutant_mapping(
        mutants: List[Mutant], scores: List[float]
    ) -> List[Mutant]:
        for mutant, score in zip(mutants, scores):
            mutant.mutant_score = score
        return mutants