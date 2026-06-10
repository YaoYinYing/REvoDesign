# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Clustering workflow
"""

from pathlib import Path

from Bio import SeqIO
from RosettaPy.node import NodeHintT

from REvoDesign import ConfigBus
from REvoDesign.citations import CitationManager
from REvoDesign.clusters.cluster_sequence import ClusterMethodManager
from REvoDesign.clusters.score_clusters import score_clusters
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.tools.customized_widgets import set_widget_value
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
        self.rosetta_override_representatives = bool(
            bus.get_value("ui.cluster.rosetta.override_representatives", default_value=False)
        )
        self.cluster_method = bus.get_value("ui.cluster.method.use", default_value="AgglomerativeCluster")
        self.cluster_random_seed = int(bus.get_value("ui.cluster.random_seed", default_value=0))

        self.evo_pssm_profile = bus.get_value("ui.cluster.evo.inputs.pssm_profile", default_value="")
        self.evo_esm1v_table = bus.get_value("ui.cluster.evo.inputs.esm1v_table", default_value="")
        self.evo_structure_pdb = bus.get_value("ui.cluster.evo.inputs.structure_pdb", default_value="")
        self.evo_esm_mutation_col = bus.get_value("ui.cluster.evo.esm.mutation_col", default_value="mutation")
        self.evo_weights = {
            "seq": float(bus.get_value("ui.cluster.evo.weights.seq", default_value=1.0)),
            "physchem": float(bus.get_value("ui.cluster.evo.weights.physchem", default_value=0.0)),
            "spatial": float(bus.get_value("ui.cluster.evo.weights.spatial", default_value=0.0)),
            "pssm": float(bus.get_value("ui.cluster.evo.weights.pssm", default_value=0.0)),
            "esm": float(bus.get_value("ui.cluster.evo.weights.esm", default_value=0.0)),
        }

        self.nproc = bus.get_value("ui.header_panel.nproc", int)

    @staticmethod
    def _sanitize_worker_count(num_proc: int) -> int:
        sanitized = int(num_proc)
        if sanitized < 1:
            logging.warning("Invalid worker count %s detected. Falling back to 1.", num_proc)
            return 1
        return sanitized

    @staticmethod
    def _representative_policy(clustering) -> str:
        if hasattr(clustering, "get_method_spec"):
            try:
                return clustering.get_method_spec().representative_policy
            except Exception:
                pass
        return "Representative selection policy is not provided by this clustering backend."

    @staticmethod
    def _make_input_pdb(design_molecule: str, design_chain_id: str) -> str:
        from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

        return make_temperal_input_pdb(
            molecule=design_molecule,
            chain_id=design_chain_id,
            selection="not hetatm",
            reload=False,
        )

    @staticmethod
    def _count_variants(fasta_path: str) -> int:
        with open(fasta_path, encoding="utf-8") as handle:
            return sum(1 for _ in SeqIO.parse(handle, "fasta"))

    def _validate_general_configuration(self, variant_count: int):
        if self.cluster_batch_size < 1:
            raise ValueError("Cluster batch size must be a positive integer.")
        if self.cluster_number < 1:
            raise ValueError("Number of clusters must be a positive integer.")
        if variant_count < 1:
            raise ValueError("No variants were generated for clustering.")
        if self.cluster_number > variant_count:
            raise ValueError(
                f"Requested {self.cluster_number} clusters for only {variant_count} variants. "
                "Reduce the cluster count or generate more variants."
            )
        if self.min_mut_num > self.max_mut_num:
            raise ValueError("Minimum mutation count cannot exceed the maximum mutation count.")

    def _validate_evo_configuration(self):
        if self.cluster_method != "EvoCluster":
            return

        positive_weights = {name: weight for name, weight in self.evo_weights.items() if weight > 0}
        if not positive_weights:
            raise ValueError("EvoCluster requires at least one positive distance-component weight.")

        required_paths = []
        if self.evo_weights["pssm"] > 0:
            required_paths.append(("PSSM profile", self.evo_pssm_profile))
        if self.evo_weights["esm"] > 0:
            required_paths.append(("ESM-1v table", self.evo_esm1v_table))

        for label, path in required_paths:
            if not str(path).strip():
                raise ValueError(f"EvoCluster requires a {label} path when its weight is positive.")
            if not Path(path).exists():
                raise ValueError(f"EvoCluster {label} does not exist: {path}")

        if self.evo_weights["spatial"] > 0 and self.evo_structure_pdb and not Path(self.evo_structure_pdb).exists():
            raise ValueError(f"EvoCluster structure PDB does not exist: {self.evo_structure_pdb}")

    def _log_method_configuration(self, clustering):
        logging.info("Selected clustering method: %s", clustering.name)
        logging.info("Representative selection policy: %s", self._representative_policy(clustering))
        logging.info(
            "Rosetta post-clustering scoring enabled: %s; representative override enabled: %s",
            bool(self.run_mutate_relax),
            bool(self.run_mutate_relax and self.rosetta_override_representatives),
        )
        if clustering.name == "EvoCluster":
            logging.info(
                "EvoCluster inputs: pssm=%s esm=%s structure=%s esm_mutation_col=%s",
                bool(str(self.evo_pssm_profile).strip()),
                bool(str(self.evo_esm1v_table).strip()),
                bool(str(clustering.structure_pdb).strip()),
                self.evo_esm_mutation_col,
            )
            logging.info("EvoCluster requested weights: %s", self.evo_weights)

    # combination and clustering
    def run_clustering(self):
        # lazy module loading to fasten plugin initializing
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

            clustering = ClusterMethodManager.get(
                cluster_method_name=self.cluster_method,
                fastafile=expected_design_combinations,
            )
            clustering.batch_size = self.cluster_batch_size
            clustering.num_proc = self.nproc
            clustering.num_clusters = self.cluster_number
            clustering.shuffle_variant = self.shuffle_variant
            clustering.random_seed = self.cluster_random_seed
            clustering.substitution_matrix = self.cluster_substitution_matrix
            clustering._save_dir = self.PWD
            clustering.chain_id = self.design_chain_id
            clustering.wt_sequence = self.design_sequence
            clustering.evo_pssm_profile = self.evo_pssm_profile
            clustering.evo_esm1v_table = self.evo_esm1v_table
            clustering.evo_esm_mutation_col = self.evo_esm_mutation_col
            clustering.evo_weights = dict(self.evo_weights)
            clustering.structure_pdb = self.evo_structure_pdb
            if clustering.name == "EvoCluster" and not clustering.structure_pdb:
                clustering.structure_pdb = self._make_input_pdb(self.design_molecule, self.design_chain_id)

            self.nproc = self._sanitize_worker_count(self.nproc)
            clustering.num_proc = self.nproc
            variant_count = self._count_variants(expected_design_combinations)
            self._validate_general_configuration(variant_count)
            self._validate_evo_configuration()
            self._log_method_configuration(clustering)
            clustering.initialize_aligner()

            clustering.run_clustering(progressbar=progressbar)
            cluster_outputs.update({num_mut: clustering.cluster_output_fp})

            if self.run_mutate_relax:
                pdb_file = self._make_input_pdb(self.design_molecule, self.design_chain_id)

                node_hint: NodeHintT | None = bus.get_value("rosetta.node_hint", default_value="native")  # type: ignore

                rosetta_results = run_worker_thread_in_pool(
                    worker_function=score_clusters,
                    pdb=pdb_file,
                    chain_id=self.design_chain_id,
                    node_hint=node_hint,
                    tasks_dir=str(clustering.save_dir),
                )
                if rosetta_results:
                    if self.rosetta_override_representatives:
                        clustering.override_cluster_centers_with_rosetta(rosetta_results)
                    else:
                        logging.info(
                            "Rosetta cluster scoring finished without overriding representative FASTA files."
                        )

            clustering.cite()

        cluster_imgs = [_cluster["score"] for _, _cluster in cluster_outputs.items()]
        set_widget_value(self.plot_space, cluster_imgs)

        CitationManager().output()
