from abc import ABC, abstractmethod

from omegaconf import DictConfig

from REvoDesign.common.Mutant import Mutant


class MutateRunnerAbstract(ABC):
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
        pass

    # Add any other common methods or properties that should be shared by all subclasses.


from .DunbrackRotamerLib import PyMOL_mutate
from .DLPacker import DLPacker_worker
from .PIPPack import PIPPack_worker

__all__ = [
    'MutateRunnerAbstract',
    'PyMOL_mutate',
    'DLPacker_worker',
    'PIPPack_worker',
]
