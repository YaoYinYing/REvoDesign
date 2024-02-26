import glob
import os

from REvoDesign.tools.logger import logging as logger

logging = logger.getChild(__name__)

import tempfile


from REvoDesign.common.Mutant import Mutant
from REvoDesign.tools.post_installed import reload_config_file, set_cache_dir


class PIPPack_worker:
    """
    Class for managing protein reconstruction and mutation using PIPPack.


    # Further usage for other functionalities
    """

    def __init__(self, pdb_file: str, use_model: str = 'ensemble'):
        from pippack import PIPPack
        """
        Initialize DLPacker_worker with a PDB file.

        Args:
        - pdb_file: Path to the PDB file
        """
        self.pdb_file = pdb_file
        cfg = reload_config_file('sidechain-solver/pippack')[
            'sidechain-solver'
        ]
        self.pippack_worker = PIPPack(model=use_model)

        logging.info(f'Initializing PIPPack_worker.')
        self.pippack_worker.n_recycle = cfg.inference.n_recycle
        self.pippack_worker.temperature = cfg.inference.temperature
        self.pippack_worker.force_cpu = cfg.inference.force_cpu
        self.pippack_worker.resample_args = cfg.inference.resample_args
        self.pippack_worker.seed = cfg.inference.seed
        self.pippack_worker.use_resample = cfg.inference.use_resample

        cache_dir = set_cache_dir()
        self.pippack_worker.weights_path = os.path.join(
            cache_dir, 'weights', 'pippack', 'model_weights'
        )
        if not self.pippack_worker.use_ensemble:
            self.pippack_worker._initialize_with_a_model()
        else:
            self.pippack_worker._initialize_with_ensemble()

    def run_mutate(
        self,
        mutant_obj: Mutant,
        **kwargs,
    ):
        new_obj_name = mutant_obj.short_mutant_id

        mutant_sequence = [
            [
                seq.replace('X', '')
                for seq in mutant_obj.mutant_sequences.values()
            ]
        ]
        logging.debug(mutant_obj)
        logging.debug(f'Mutated: {mutant_obj.mutant_sequences}')

        temp_dir = tempfile.mkdtemp(prefix='RD_design_pipp')
        temp_pdb_path = os.path.join(temp_dir, f"{new_obj_name}.pdb")

        self.pippack_worker._run_repack_single(
            pdb_file=self.pdb_file,
            output_file=temp_pdb_path,
            mutant_sequence=mutant_sequence,
        )

        return temp_pdb_path
