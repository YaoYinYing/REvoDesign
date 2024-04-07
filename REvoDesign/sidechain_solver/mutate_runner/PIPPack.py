import os

from REvoDesign import root_logger
from REvoDesign.common.Mutant import Mutant
from REvoDesign import reload_config_file, set_cache_dir

from REvoDesign.sidechain_solver.mutate_runner import MutateRunnerAbstract


logging = root_logger.getChild(__name__)


class PIPPack_worker(MutateRunnerAbstract):
    """
    Class for managing protein reconstruction and mutation using PIPPack.


    # Further usage for other functionalities
    """

    def __init__(self, pdb_file: str, use_model='ensemble', **kwargs):
        """
        Initialize DLPacker_worker with a PDB file.

        Args:
        - pdb_file: Path to the PDB file
        """
        super().__init__(pdb_file)

        self.use_model = use_model

        from pippack import PIPPack

        self.pdb_file = pdb_file
        ppcfg = reload_config_file('sidechain-solver/pippack')[
            'sidechain-solver'
        ]
        self.pippack_worker = PIPPack(model=self.use_model)

        logging.info(f'Initializing PIPPack_worker.')
        self.pippack_worker.n_recycle = ppcfg.inference.n_recycle
        self.pippack_worker.temperature = ppcfg.inference.temperature
        self.pippack_worker.force_cpu = ppcfg.inference.force_cpu
        self.pippack_worker.resample_args = ppcfg.inference.resample_args
        self.pippack_worker.seed = ppcfg.inference.seed
        self.pippack_worker.use_resample = ppcfg.inference.use_resample

        cache_dir = set_cache_dir()
        self.pippack_worker.weights_path = os.path.join(
            cache_dir, 'weights', 'pippack', 'model_weights'
        )
        if not self.pippack_worker.use_ensemble:
            self.pippack_worker._initialize_with_a_model()
        else:
            self.pippack_worker._initialize_with_ensemble()

        self.temp_dir = self.new_cache_dir

    def run_mutate(
        self,
        mutant_obj: Mutant,
        **kwargs,
    ):
        logging.debug(f'Mutating {mutant_obj=}')
        new_obj_name = mutant_obj.short_mutant_id

        mutant_sequence = [
            [
                seq.replace('X', '')
                for seq in mutant_obj.mutant_sequences.values()
            ]
        ]
        logging.debug(f'Mutated: {mutant_obj.mutant_sequences}')

        temp_pdb_path = os.path.join(self.temp_dir, f"{new_obj_name}.pdb")

        self.pippack_worker._run_repack_single(
            pdb_file=self.pdb_file,
            output_file=temp_pdb_path,
            mutant_sequence=mutant_sequence,
        )

        return temp_pdb_path

    def run_mutate_parallel(self, mutants: list[Mutant], *args, **kwargs):
        mutant_sequences = [
            [
                seq.replace('X', '')
                for seq in mutant_obj.mutant_sequences.values()
            ]
            for mutant_obj in mutants
        ]

        pdbs = self.pippack_worker._run_repack_batch(
            pdb_path=self.pdb_file,
            output_dir=self.temp_dir,
            mutant_sequence=mutant_sequences,
        )

        renamed_pdbs = [
            os.path.join(self.temp_dir, f'{m.short_mutant_id}.pdb')
            for i, m in enumerate(mutants)
        ]

        for i, pdb in enumerate(pdbs):
            try:
                os.rename(pdb, renamed_pdbs[i])
            except OSError as e:
                print(e)

        return renamed_pdbs

    @property
    def __bibtex__(self):
        return {
            'PIPPack': """@article{randolph2023pippack,
  title={Invariant point message passing for protein side chain packing},
  author={Randolph, Nicholas and Kuhlman, Brian},
  journal={bioRxiv preprint bioRxiv:10.1101/2023.08.03.551328},
  year={2023}
}"""
        }
