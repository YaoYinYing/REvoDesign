import os
from abc import abstractmethod
from typing import List, Tuple
from ..basic.abc_third_party_module import ThirdPartyModuleAbstract
from ..common.mutant import Mutant
from ..common.mutant_tree import MutantTree
class MutateRunnerAbstract(ThirdPartyModuleAbstract):
    name: str = ""
    installed: bool = False
    weights_preset: Tuple[str, ...] = ()
    default_weight_preset: str = ""
    def __init__(self, pdb_file: str):
        self.pdb_file = pdb_file
    @property
    def new_cache_dir(self):
        mutant_dir = os.path.abspath("mutant_pdbs")
        temp_dir = os.path.join(mutant_dir, self.__class__.__name__)
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir
    @staticmethod
    def mutated_pdb_mapping(
        mutant_tree: MutantTree, pdb_fps: List[str]
    ) -> MutantTree:
        if mutant_tree.mutant_num != len(pdb_fps):
            raise RuntimeError(
                f"Mutant number does not match pdb_fps: {mutant_tree.mutant_num=} != {len(pdb_fps)=}"
            )
        for m, fp in zip(mutant_tree.all_mutant_objects, pdb_fps):
            if not (fp and os.path.exists(fp)):
                raise ValueError(f"pdb for mutant is not valid. {fp=} {m=}")
            m.pdb_fp = fp
        return mutant_tree
    def reconstruct(self):
        raise NotImplementedError("This tool does not support reconstruction.")
    @abstractmethod
    def run_mutate(self, mutant: Mutant) -> str:
    @abstractmethod
    def run_mutate_parallel(
        self,
        mutants: List[Mutant],
        nproc: int = 2,
    ) -> List[str]:
    # Add any other common methods or properties that should be shared by all subclasses.