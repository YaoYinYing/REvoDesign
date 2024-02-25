from dataclasses import dataclass

from REvoDesign.application.ui_driver import ConfigBus
from REvoDesign.tools.customized_widgets import (
    hold_trigger_button,
    set_widget_value,
)

from REvoDesign.tools.logger import logging as logger

logging = logger.getChild(__name__)


@dataclass
class ClusterRunnerConfig:
    bus: ConfigBus = None
    design_molecule: str = None
    design_chain_id: str = None
    design_sequence: str = None
    PWD: str = None
    cluster_batch_size: int = 100
    cluster_number: int = 15
    min_mut_num: int = 1
    max_mut_num: int = 1
    cluster_substitution_matrix: str = 'PAM30'
    shuffle_variant: bool = False
    nproc: int = 10
    input_mutant_table: str = None


class ClusterRunner(ClusterRunnerConfig):
    # combination and clustering
    def run_clustering(self):
        # lazy module loading to fasten plugin initializing
        from REvoDesign.clusters.combine_positions import Combinations
        from REvoDesign.clusters.cluster_sequence import Clustering

        # output space
        self.plot_space = self.bus.ui.stackedWidget
        progressbar = self.bus.ui.progressBar

        input_fasta_file = (
            f'{self.PWD}/{self.design_molecule}_{self.design_chain_id}.fasta'
        )
        open(input_fasta_file, 'w').write(
            f'>{self.design_molecule}_{self.design_chain_id}\n{self.design_sequence}'
        )
        logging.info(f'Sequence file is saved as {input_fasta_file}')

        # output files
        cluster_outputs = {}

        for num_mut in range(self.min_mut_num, self.max_mut_num + 1):
            # combination
            combinations = Combinations()
            combinations.fastasequence = self.design_sequence
            combinations.chain_id = self.design_chain_id
            combinations.fastafile = input_fasta_file
            combinations.inputfile = self.input_mutant_table
            combinations.combi = num_mut
            combinations.path = self.PWD
            combinations.processors = self.nproc

            # expected design combination file

            combinations.run_combinations()
            expected_design_combinations = combinations.expected_output_fasta

            # clustering

            clustering = Clustering(fastafile=expected_design_combinations)
            clustering.batch_size = self.cluster_batch_size
            clustering.num_proc = self.nproc
            clustering.num_clusters = self.cluster_number
            clustering.shuffle_variant = self.shuffle_variant
            clustering.substitution_matrix = self.cluster_substitution_matrix
            clustering._save_dir = self.PWD

            clustering.initialize_aligner()

            clustering.run_clustering(progressbar=progressbar)
            cluster_outputs.update({num_mut: clustering.cluster_output_fp})

        cluster_imgs = [
            _cluster['score'] for _, _cluster in cluster_outputs.items()
        ]
        set_widget_value(self.plot_space, cluster_imgs)
