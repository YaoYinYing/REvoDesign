'''
Wrapper for DLPacker
'''
import gc
import os
from typing import List

from joblib import Parallel, delayed

from REvoDesign.basic import MutateRunnerAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.common.mutant import Mutant
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.tools.utils import timing, require_installed

logging = ROOT_LOGGER.getChild(__name__)

@require_installed
class DLPacker_worker(MutateRunnerAbstract):
    """
    Class for managing protein reconstruction and mutation using DLPacker.

    Usage:
    dlpacker = DLPacker_worker(pdb_file)
    relaxed_pdb = dlpacker.reconstruct()  # Reconstruct the protein

    mutant = Mutant()  # Create a Mutant object
    mutant_info = [
        {
            'chain_id': 'A',
            'position': 10,
            'mut_res': 'G',
            'wt_res': 'A'
        },
        # Add more mutation info as needed
    ]
    mutated_pdb = dlpacker.run_mutate(mutant, reconstruct_area_radius=5)  # Perform mutation

    # Further usage for other functionalities
    """

    name: str = "DLPacker"
    installed: bool = is_package_installed("DLPacker")

    def __init__(self, pdb_file: str, radius: float = 0.0, **kwargs):
        """
        Initialize DLPacker_worker with a PDB file.

        Args:
        - pdb_file: Path to the PDB file
        """
        super().__init__(pdb_file)

        from REvoDesign.bootstrap import set_cache_dir

        cache_dir = set_cache_dir()

        expected_dlpacker_weight_cache_dir = os.path.join(
            os.path.abspath(cache_dir), "weights", "DLPacker"
        )
        os.environ["DLPACKER_PRETRAINED_WEIGHT"] = (
            expected_dlpacker_weight_cache_dir
        )

        self.pdb_file = pdb_file
        self.reconstruct_area_radius = radius

        self.temp_dir = self.new_cache_dir

    def reconstruct(self):
        """
        Reconstruct the protein using DLPacker.

        Returns:
        - Path to the temporally relaxed PDB file
        """
        from DLPacker.dlpacker import DLPacker

        dlpacker_worker = DLPacker(str_pdb=self.pdb_file)

        temperal_relaxed_pdb = os.path.join(
            self.temp_dir,
            f'{os.path.basename(self.pdb_file).removesuffix(".pdb")}_reconstructed.pdb',
        )
        dlpacker_worker.reconstruct_protein(
            order="sequence", output_filename=temperal_relaxed_pdb
        )
        del dlpacker_worker
        return temperal_relaxed_pdb

    def run_mutate(
        self,
        mutant: Mutant,
    ):
        """
        Run mutation on the protein using DLPacker.

        Args:
        - mutant: Object containing mutation information
        - reconstruct_area_radius: Radius for reconstructing mutated area (default: -1)
        - relax_order: Order for relaxation (default: 'sequence')

        Returns:
        - Path to the mutated PDB file
        """
        from Bio.Data import IUPACData
        from DLPacker.dlpacker import DLPacker

        dlpacker_worker = DLPacker(str_pdb=self.pdb_file)

        logging.debug(f"Mutating {mutant=}")
        new_obj_name = mutant.short_mutant_id

        temp_pdb_path = os.path.join(self.temp_dir, f"{new_obj_name}.pdb")

        for mut_info in mutant.mutations:

            new_residue_3 = IUPACData.protein_letters_1to3[
                mut_info.mut_res
            ].upper()
            wt_residue_3 = IUPACData.protein_letters_1to3[
                mut_info.wt_res
            ].upper()

            dlpacker_worker.mutate_sequence(
                target=(mut_info.position, mut_info.chain_id, wt_residue_3),
                new_label=new_residue_3,
            )

        reconstruct_area = self._get_reconstruct_area(
            mutant_obj=mutant,
            reconstruct_area_radius=self.reconstruct_area_radius,
        )
        logging.debug(
            f"Reconstruct within {self.reconstruct_area_radius=}: {reconstruct_area=}"
        )
        dlpacker_worker.reconstruct_region(
            targets=reconstruct_area,
            order="natoms" if self.reconstruct_area_radius > 0 else "sequence",
            output_filename=temp_pdb_path,
        )

        del dlpacker_worker

        return temp_pdb_path

    def _get_reconstruct_area(
        self, mutant_obj: Mutant, reconstruct_area_radius: float = -1
    ):
        """
        Get the area for reconstruction based on mutation information.

        Args:
        - mutant_obj: Object containing mutation information
        - reconstruct_area_radius: Radius for reconstruction (default: -1)

        Returns:
        - List of targets for reconstruction
        """
        from Bio.Data import IUPACData
        from DLPacker.dlpacker import DLPacker

        dlpacker_worker = DLPacker(str_pdb=self.pdb_file)

        reconstruct_area = []
        for mut_info in mutant_obj.mutations:

            new_residue_3 = IUPACData.protein_letters_1to3[
                mut_info.mut_res
            ].upper()
            if reconstruct_area_radius <= 0:
                logging.debug(
                    f"Adding {(mut_info.position, mut_info.chain_id, new_residue_3)} for reconstruction ..."
                )
                reconstruct_area.append(
                    (mut_info.position, mut_info.chain_id, new_residue_3)
                )
            else:
                _ = dlpacker_worker.get_targets(
                    target=(
                        mut_info.position,
                        mut_info.chain_id,
                        new_residue_3,
                    ),
                    radius=reconstruct_area_radius,
                )
                print(f"Adding {_} for relax...")
                reconstruct_area.extend(_)

        if reconstruct_area:
            reconstruct_area = list(set(reconstruct_area))

        del dlpacker_worker
        return reconstruct_area

    def run_mutate_parallel(
        self,
        mutants: List[Mutant],
        nproc: int = 2,
    ) -> List[str]:
        """
        Perform mutation on the protein in parallel.

        Args:
        - mutants: List of Mutant objects containing mutation information
        - nproc: Number of parallel jobs to run (default: -1, which means using all available cores)

        Returns:
        - List of paths to the mutated PDB files
        """
        with timing('setting up DLPacker'):
            # call DLPacker to initialize with cache dir
            from DLPacker.dlpacker import DLPacker

        if nproc is None:
            nproc = os.cpu_count()

        if nproc > (num_task := len(mutants)):
            logging.warning(f"Fixed {nproc=} to {num_task=}")
            nproc = num_task

        results = Parallel(n_jobs=nproc, return_as="list")(
            delayed(self.run_mutate)(mutant) for mutant in mutants
        )

        gc.collect()
        return list(results)  # type: ignore

    __bibtex__ = {
        "DLPacker": r"""@article{https://doi.org/10.1002/prot.26311,
author = {Misiura, Mikita and Shroff, Raghav and Thyer, Ross and Kolomeisky, Anatoly B.},
title = {DLPacker: Deep learning for prediction of amino acid side chain conformations in proteins},
journal = {Proteins: Structure, Function, and Bioinformatics},
volume = {90},
number = {6},
pages = {1278-1290},
keywords = {3DCNN, DNN, protein structure prediction, side chain restoration, U-net},
doi = {https://doi.org/10.1002/prot.26311},
url = {https://onlinelibrary.wiley.com/doi/abs/10.1002/prot.26311},
eprint = {https://onlinelibrary.wiley.com/doi/pdf/10.1002/prot.26311},
abstract = {Abstract Prediction of side chain conformations of amino acids in proteins (also termed “packing”) is an important and challenging part of protein structure prediction with many interesting applications in protein design. A variety of methods for packing have been developed but more accurate ones are still needed. Machine learning (ML) methods have recently become a powerful tool for solving various problems in diverse areas of science, including structural biology. In this study, we evaluate the potential of deep neural networks (DNNs) for prediction of amino acid side chain conformations. We formulate the problem as image-to-image transformation and train a U-net style DNN to solve the problem. We show that our method outperforms other physics-based methods by a significant margin: reconstruction RMSDs for most amino acids are about 20\% smaller compared to SCWRL4 and Rosetta Packer with RMSDs for bulky hydrophobic amino acids Phe, Tyr, and Trp being up to 50\% smaller.},
year = {2022}
}

"""
    }
