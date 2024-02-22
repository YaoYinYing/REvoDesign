import os
import tempfile
from REvoDesign.common.Mutant import Mutant
from REvoDesign.tools.logger import logging as logger

logging = logger.getChild(__name__)


class DLPacker_worker:
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

    def __init__(self, pdb_file):
        from REvoDesign.tools.post_installed import set_cache_dir

        cache_dir = set_cache_dir()

        expected_dlpacker_weight_cache_dir = os.path.join(
            os.path.abspath(cache_dir), 'weights', 'DLPacker'
        )
        os.environ[
            'DLPACKER_PRETRAINED_WEIGHT'
        ] = expected_dlpacker_weight_cache_dir

        """
        Initialize DLPacker_worker with a PDB file.

        Args:
        - pdb_file: Path to the PDB file
        """
        self.pdb_file = pdb_file
        self.reconstruct_area_radius = 0

    def reconstruct(self):
        """
        Reconstruct the protein using DLPacker.

        Returns:
        - Path to the temporally relaxed PDB file
        """
        from DLPacker.dlpacker import DLPacker

        self.dlpacker_worker = DLPacker(str_pdb=self.pdb_file)
        temperal_relaxed_pdb = tempfile.mktemp(suffix=".pdb")
        self.dlpacker_worker.reconstruct_protein(
            order='sequence', output_filename=temperal_relaxed_pdb
        )
        return temperal_relaxed_pdb

    def run_mutate(
        self,
        mutant_obj: Mutant,
        **kwargs,
    ):
        """
        Run mutation on the protein using DLPacker.

        Args:
        - mutant_obj: Object containing mutation information
        - reconstruct_area_radius: Radius for reconstructing mutated area (default: -1)
        - relax_order: Order for relaxation (default: 'sequence')

        Returns:
        - Path to the mutated PDB file
        """
        from DLPacker.dlpacker import DLPacker
        from Bio.Data import IUPACData

        self.dlpacker_worker = DLPacker(str_pdb=self.pdb_file)
        new_obj_name = mutant_obj.short_mutant_id

        temp_dir = tempfile.mkdtemp(prefix='RD_design_dlp')
        temp_pdb_path = os.path.join(temp_dir, f"{new_obj_name}.pdb")

        for mut_info in mutant_obj.mutant_info:
            chain_id = mut_info['chain_id']
            position = mut_info['position']
            new_residue = mut_info['mut_res']
            wt_residue = mut_info['wt_res']

            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()
            wt_residue_3 = IUPACData.protein_letters_1to3[wt_residue].upper()

            self.dlpacker_worker.mutate_sequence(
                target=(position, chain_id, wt_residue_3),
                new_label=new_residue_3,
            )

        reconstruct_area = self._get_reconstruct_area(
            mutant_obj=mutant_obj,
            reconstruct_area_radius=self.reconstruct_area_radius,
        )
        self.dlpacker_worker.reconstruct_region(
            targets=reconstruct_area,
            order='natoms' if self.reconstruct_area_radius > 0 else 'sequence',
            output_filename=temp_pdb_path,
        )

        return temp_pdb_path

    def _get_reconstruct_area(
        self, mutant_obj: Mutant, reconstruct_area_radius: int = -1
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

        reconstruct_area = []
        for mut_info in mutant_obj.mutant_info:
            chain_id = mut_info['chain_id']
            position = mut_info['position']
            new_residue = mut_info['mut_res']
            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()
            if reconstruct_area_radius <= 0:
                print(
                    f'Adding {(position, chain_id, new_residue_3)} for relax...'
                )
                reconstruct_area.append((position, chain_id, new_residue_3))
            else:
                _ = self.dlpacker_worker.get_targets(
                    target=(position, chain_id, new_residue_3),
                    radius=reconstruct_area_radius,
                )
                print(f'Adding {_} for relax...')
                reconstruct_area.extend(_)

        if reconstruct_area:
            reconstruct_area = list(set(reconstruct_area))

        return reconstruct_area
