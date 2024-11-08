import os
from abc import abstractmethod
from typing import List

from ..citations import CitableModules
from ..common.Mutant import Mutant
from ..common.MutantTree import MutantTree


class MutateRunnerAbstract(CitableModules):
    """
    Abstract base class for running mutation tools.

    Subclasses should implement the specific methods for protein mutation,
    and optionally, reconstruction.
    """

    def __init__(self, pdb_file: str):
        """
        Initialize the mutation runner with a PDB file path.

        Args:
            pdb_file (str): Path to the PDB file.
        """
        self.pdb_file = pdb_file

    @property
    def new_cache_dir(self):
        mutant_dir = os.path.abspath('mutant_pdbs')
        temp_dir = os.path.join(mutant_dir, self.__class__.__name__)
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    @staticmethod
    def mutated_pdb_mapping(mutants: MutantTree, pdb_fps: List[str]):
        if mutants.mutant_num != len(pdb_fps):
            raise RuntimeError(f"Mutant number does not match pdb_fps: {mutants.mutant_num=} != {len(pdb_fps)=}")

        for m, fp in zip(mutants.all_mutant_objects, pdb_fps):
            if not (fp and os.path.exists(fp)):
                raise ValueError(f'pdb for mutant is not valid. {fp=} {m=}')
            m.pdb_fp = fp

        return mutants

    def reconstruct(self):
        """
        Reconstruct the protein structure.

        This method can be overridden by subclasses that support reconstruction.
        By default, it raises a NotImplementedError.
        """
        raise NotImplementedError("This tool does not support reconstruction.")

    @abstractmethod
    def run_mutate(self, mutant: Mutant):
        """
        Perform mutation on the protein.

        Args:
            mutant: An object or data structure representing the mutation.

        This method should be implemented by subclasses to provide the specific
        mutation functionality.
        """

    @abstractmethod
    def run_mutate_parallel(
        self,
        mutants: list[Mutant],
        nproc: int = 2,
    ):
        """
        Perform mutation on the protein in parallel.

        Args:
            nproc: Nproc
            mutants: An list object or data structure representing the mutation.

        This method should be implemented by subclasses to provide the specific
        mutation functionality.
        """

    # Add any other common methods or properties that should be shared by all subclasses.
