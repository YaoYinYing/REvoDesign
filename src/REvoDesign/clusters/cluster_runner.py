# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Clustering workflow
"""

from RosettaPy.node import NodeHintT

from REvoDesign import ConfigBus
from REvoDesign.citations import CitationManager
from REvoDesign.clusters.score_clusters import score_clusters
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.tools.customized_widgets import set_widget_value
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb
from REvoDesign.tools.utils import run_worker_thread_in_pool

logging = ROOT_LOGGER.getChild(__name__)


class ClusterRunner:
    def __init__(self, PWD):
        bus: ConfigBus = ConfigBus()

        self.PWD: str = PWD
        self.design_molecule: str = bus.get_value("ui.header_panel.input.molecule")
        self.design_chain_id: str = bus.get_value("ui.header_panel.input.chain_id")
        self.designable_sequences: dict = bus.get_value("designable_sequences", dict, cfg="runtime")
        self.design_sequence: str = self.designable_sequences.get(self.design_chain_id)

        self.input_mutant_table = bus.get_value("ui.cluster.input.from_mutant_txt")

        self.cluster_batch_size = bus.get_value("ui.cluster.batch_size", int)
        self.cluster_number = bus.get_value("ui.cluster.num_cluster", int)
        self.min_mut_num = bus.get_value("ui.cluster.mut_num_min", int)
        self.max_mut_num = bus.get_value("ui.cluster.mut_num_max", int)
        self.cluster_substitution_matrix = bus.get_value("ui.cluster.score_matrix.default")

        self.shuffle_variant = bus.get_value("ui.cluster.shuffle")
        self.run_mutate_relax = bus.get_value("ui.cluster.mutate_relax")

        self.nproc = bus.get_value("ui.header_panel.nproc", int)

    # combination and clustering
    def run_clustering(self):
        # lazy module loading to fasten plugin initializing
        from .cluster_sequence import Clustering
        from .combine_positions import Combinations

        bus: ConfigBus = ConfigBus()

        # output space
        self.plot_space = bus.ui.stackedWidget
        progressbar = bus.ui.progressBar

        input_fasta_file = f"{self.PWD}/{self.design_molecule}_{self.design_chain_id}.fasta"
        with open(input_fasta_file, "w") as f:
            f.write(f">{self.design_molecule}_{self.design_chain_id}\n{self.design_sequence}")
        logging.info(f"Sequence file is saved as {input_fasta_file}")

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

            if self.run_mutate_relax:
                pdb_file = make_temperal_input_pdb(
                    molecule=self.design_molecule,
                    chain_id=self.design_chain_id,
                    selection="not hetatm",
                    reload=False,
                )

                node_hint: NodeHintT | None = bus.get_value("rosetta.node_hint", default_value="native")  # type: ignore

                run_worker_thread_in_pool(
                    worker_function=score_clusters,
                    pdb=pdb_file,
                    chain_id=self.design_chain_id,
                    node_hint=node_hint,
                    tasks_dir=str(clustering.save_dir),
                )

            clustering.cite()

        cluster_imgs = [_cluster["score"] for _, _cluster in cluster_outputs.items()]
        set_widget_value(self.plot_space, cluster_imgs)

        CitationManager().output()
