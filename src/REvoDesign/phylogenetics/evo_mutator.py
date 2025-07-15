import asyncio
import itertools
import os
import traceback
import warnings
from dataclasses import dataclass
from functools import partial
from typing import List, Literal, Optional, Tuple, Union

import Bio.PDB.PDBParser as PDBParser
import matplotlib
import pandas as pd
from immutabledict import immutabledict
from joblib import Parallel, delayed
from pymol import CmdException, cmd
from RosettaPy.common.mutation import Mutation, RosettaPyProteinSequence

from REvoDesign import ConfigBus, issues
from REvoDesign.basic import IterableLoop
from REvoDesign.citations import CitationManager
from REvoDesign.clients.QtSocketConnector import REvoDesignWebSocketServer
from REvoDesign.common import Mutant, MutantTree
from REvoDesign.common.mutant_visualise import MutantVisualizer
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.magician import IMPLEMENTED_DESIGNERS, Magician
from REvoDesign.phylogenetics.gremlin_tools import CoevolvedPair, GREMLIN_Tools
from REvoDesign.phylogenetics.revo_designer import REvoDesigner
from REvoDesign.sidechain import SidechainSolver
from REvoDesign.tools.customized_widgets import (QButtonMatrixGremlin,
                                                 hold_trigger_button,
                                                 refresh_window,
                                                 set_widget_value)
from REvoDesign.tools.mutant_tools import save_mutant_choices
from REvoDesign.tools.pymol_utils import (any_posision_has_been_selected,
                                          is_a_REvoDesign_session,
                                          make_temperal_input_pdb)
from REvoDesign.tools.utils import (cmap_reverser, get_color, rescale_number,
                                    run_worker_thread_with_progress, timing)

matplotlib.use("Agg")


logging = ROOT_LOGGER.getChild(__name__)


@dataclass
class CoevolvedPairState:
    """A data class that represents the state-color mapping for
    coevolved pairs.

    `state2color`: mapping states to colors:
        - 'available' -> 'marine'
        - 'out_of_range' -> 'salmon'
        - 'in_design' -> 'tv_yellow'
    """

    state2color: immutabledict = immutabledict(
        {
            "available": "marine",
            "out_of_range": "salmon",
            "in_design": "tv_yellow",
        }
    )

    state_type = Literal["available", "out_of_range", "in_design"]

    def color(self, state: state_type) -> str:
        """Returns the color associated with a given state keyword

        Args:
            state (state_type): the state for the corresponding color.


        Returns:
            str: `color` corresponding to the `state` keyword
        """
        if not (color := self.state2color.get(state)):
            raise ValueError(f"Invalid state keyword {state}")
        return color


# tab mutate
class MutateWorker:
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()
        self.PWD: str = self.bus.get_value("work_dir", str)

        self.design_molecule: str = self.bus.get_value(
            "ui.header_panel.input.molecule"
        )
        self.design_chain_id: str = self.bus.get_value(
            "ui.header_panel.input.chain_id"
        )
        self.designable_sequences = RosettaPyProteinSequence.from_dict(
            dict(self.bus.get_value("designable_sequences"))
        )
        self.design_sequence: str = (
            self.designable_sequences.get_sequence_by_chain(
                self.design_chain_id
            )
        )

    def run_mutant_loading_from_profile(self):
        try:
            design_profile = self.bus.get_value("ui.mutate.input.profile")
            design_profile_format = self.bus.get_value(
                "ui.mutate.input.profile_type"
            )
            preffered = self.bus.get_value("ui.mutate.accept")
            rejected = self.bus.get_value("ui.mutate.reject")

            temperature = self.bus.get_value(
                "ui.mutate.designer.temperature", float
            )
            num_designs = self.bus.get_value(
                "ui.mutate.designer.num_sample", int
            )
            batch = self.bus.get_value("ui.mutate.designer.batch", int)
            homooligomeric = self.bus.get_value(
                "ui.mutate.designer.homooligomeric"
            )
            deduplicate_designs = self.bus.get_value(
                "ui.mutate.designer.deduplicate_designs"
            )
            randomized_sample = self.bus.get_value(
                "ui.mutate.designer.enable_randomized_sampling"
            )
            randomized_sample_num = self.bus.get_value(
                "ui.mutate.designer.randomized_sampling", int
            )
            design_case = self.bus.get_value("ui.mutate.input.design_case")
            custom_indices_fp = self.bus.get_value(
                "ui.mutate.input.residue_ids"
            )
            cutoff = [
                (self.bus.get_value("ui.mutate.min_score", float)),
                (self.bus.get_value("ui.mutate.max_score", float)),
            ]
            reversed_mutant_effect = self.bus.get_value(
                "ui.header_panel.cmap.reverse_score"
            )
            output_pse = self.bus.get_value("ui.mutate.input.to_pse")
            nproc = self.bus.get_value("ui.header_panel.nproc", int)

            cmap = cmap_reverser(
                cmap=self.bus.get_value("ui.header_panel.cmap.default"),
                reverse=reversed_mutant_effect,
            )

            is_a_REvoDesign_session()

            input_pse = make_temperal_input_pdb(
                molecule=self.design_molecule,
                save_as_format="pdb",
                wd=os.path.join(self.PWD, "temperal_pdb"),
                reload=False,
            )

            self.design = REvoDesigner(design_profile)
            self.design.designable_sequences = self.designable_sequences
            self.design.input_pse = input_pse
            self.design.output_pse = output_pse
            self.design.input_profile_format = design_profile_format

            self.design.molecule = self.design_molecule
            self.design.chain_id = self.design_chain_id
            self.design.sequence = self.design_sequence
            self.design.pwd = self.PWD
            self.design.design_case = design_case

            self.design.magician_temperature = temperature
            self.design.magician_num_samples = num_designs
            self.design.batch = batch
            self.design.homooligomeric = homooligomeric
            self.design.deduplicate_designs = deduplicate_designs
            self.design.randomized_sample = randomized_sample
            self.design.randomized_sample_num = randomized_sample_num

            self.design.mutate_runner = (
                SidechainSolver().refresh().mutate_runner
            )

            self.design.preffered_substitutions = preffered
            self.design.reject_aa = rejected
            self.design.nproc = nproc
            self.design.cmap = cmap
            self.design.create_full_pdb = False

            if design_profile_format in IMPLEMENTED_DESIGNERS:
                run_worker_thread_with_progress(
                    worker_function=self.design.design_protein_via_magician,
                    custom_indices_fp=custom_indices_fp,
                    progress_bar=self.bus.ui.progressBar,
                )
            else:
                (
                    mutation_json_fp,
                    mutation_png_fp,
                ) = self.design.setup_profile_design(
                    custom_indices_fp=custom_indices_fp,
                    cutoff=cutoff,
                )

                run_worker_thread_with_progress(
                    worker_function=self.design.load_mutants_to_pymol_session,
                    mutant_json=mutation_json_fp,
                    progress_bar=self.bus.ui.progressBar,
                )

            if not os.path.isdir(os.path.dirname(self.design.output_pse)):
                warnings.warn(
                    issues.NoResultsWarning(
                        "No output PyMOL session is created."
                    )
                )
                return

            cmd.reinitialize()
            cmd.load(input_pse, object=self.design_molecule)
            cmd.load(self.design.output_pse, partial=2)

            cmd.center(self.design_molecule)
            cmd.set("surface_color", "gray70")
            cmd.set("cartoon_color", "gray70")
            cmd.set("surface_cavity_mode", 4)
            cmd.set("transparency", 0.6)
            cmd.set(
                "cartoon_cylindrical_helices",
            )
            cmd.set("cartoon_transparency", 0.3)
            cmd.save(output_pse)

        except Exception:
            traceback.print_exc()

        finally:
            CitationManager().output()


# tab visualize
class VisualizingWorker:
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()

        self.PWD: str = self.bus.get_value("work_dir", str)

        self.design_molecule: str = self.bus.get_value(
            "ui.header_panel.input.molecule"
        )
        self.design_chain_id: str = self.bus.get_value(
            "ui.header_panel.input.chain_id"
        )
        self.designable_sequences = RosettaPyProteinSequence.from_dict(
            dict(self.bus.get_value("designable_sequences"))
        )

        self.design_sequence: str = (
            self.designable_sequences.get_sequence_by_chain(
                self.design_chain_id
            )
        )

    def visualize_mutants(self):
        input_mut_table_csv = self.bus.get_value(
            "ui.visualize.input.from_mutant_txt"
        )

        output_pse = self.bus.get_value("ui.visualize.input.to_pse")
        best_leaf = self.bus.get_value("ui.visualize.input.best_leaf")
        totalscore = self.bus.get_value("ui.visualize.input.totalscore", str)
        nproc = self.bus.get_value("ui.header_panel.nproc", int)
        group_name = self.bus.get_value("ui.visualize.input.group_name", str)

        use_global_scores = self.bus.get_value(
            "ui.visualize.global_score_policy"
        )

        try:
            reversed_mutant_effect = self.bus.get_value(
                "ui.header_panel.cmap.reverse_score"
            )
            cmap = cmap_reverser(
                cmap=self.bus.get_value("ui.header_panel.cmap.default"),
                reverse=reversed_mutant_effect,
            )

            design_profile = self.bus.get_value("ui.visualize.input.profile")
            design_profile_format: str = str(
                self.bus.get_value("ui.visualize.input.profile_type")
            )

            self.visualizer = MutantVisualizer(
                molecule=self.design_molecule,
                chain_id=self.design_chain_id,
            )
            self.visualizer.designable_sequences = self.designable_sequences
            self.visualizer.mutfile = input_mut_table_csv
            self.visualizer.input_session = make_temperal_input_pdb(
                molecule=self.design_molecule,
                wd=os.path.join(os.path.dirname(output_pse), "temperal_pdb"),
                reload=False,
            )
            self.visualizer.nproc = nproc
            self.visualizer.sequence = self.design_sequence

            self.visualizer.consider_global_score_from_profile = (
                use_global_scores
            )

            self.visualizer.profile_scoring_df = None
            self.visualizer.consider_global_score_from_profile = False

            if design_profile_format == '':
                logging.debug("No profile is given. Expected to use score labels")

            elif design_profile_format in IMPLEMENTED_DESIGNERS:
                run_worker_thread_with_progress(
                    worker_function=self.visualizer.magician.setup,
                    magician_name=design_profile_format,
                    molecule=self.design_molecule,
                    chain=self.design_chain_id,
                    progress_bar=self.bus.ui.progressBar,
                )

            else:
                self.visualizer.magician.setup()  # cool it down
                self.visualizer.profile_scoring_df = (
                    self.visualizer.parse_profile(
                        profile_fp=design_profile,
                        profile_format=design_profile_format,
                    )
                )

            self.visualizer.key_col = best_leaf or self.visualizer.key_col
            self.visualizer.score_col = totalscore or self.visualizer.score_col

            self.visualizer.save_session = output_pse
            self.visualizer.full = False
            self.visualizer.group_name = group_name
            self.visualizer.cmap = cmap

            self.visualizer.mutate_runner = (
                SidechainSolver().refresh().mutate_runner
            )

            run_worker_thread_with_progress(
                worker_function=self.visualizer.run,
                progress_bar=self.bus.ui.progressBar,
            )

            cmd.reinitialize()
            cmd.load(
                self.visualizer.input_session, object=self.design_molecule
            )

            cmd.load(self.visualizer.save_session, partial=2)
            cmd.center(self.design_molecule)
            cmd.set("surface_color", "gray70")
            cmd.set("cartoon_color", "gray70")
            cmd.set("surface_cavity_mode", 4)
            cmd.set("transparency", 0.6)
            cmd.set(
                "cartoon_cylindrical_helices",
            )
            cmd.set("cartoon_transparency", 0.3)
            cmd.save(output_pse)

        except Exception:
            logging.error("Error while running the visualization: ")
            traceback.print_exc()
        finally:
            CitationManager().output()


@dataclass
class ChainBinder:
    """
    A class for managing chain binding distance calculations in molecular structures.

    Attributes:
    - design_molecule (str): Name of the design molecule.
    - design_chain_id (str): ID of the main chain for calculations.
    - max_interact_dist (float): Maximum distance to consider two residues as interacting.
    - chain_binding_enabled (bool): Enable interchain binding calculations.
    - chains_to_bind (tuple): Chains to bind in interchain binding mode.
    - n_jobs (int): Number of jobs for parallel execution.
    """
    design_molecule: str
    design_chain_id: str
    max_interact_dist: float
    chain_binding_enabled: bool = False
    chains_to_bind: tuple = None
    n_jobs: int = -1
    structure = None

    def get_input_pdb(self):
        """
        Retrieve and parse the input PDB file into a Biopython structure.
        Returns:
        - Structure object parsed from PDB.
        """
        pdb_file = make_temperal_input_pdb(molecule=self.design_molecule, reload=False)
        parser = PDBParser(QUIET=True)
        self.structure = parser.get_structure(self.design_molecule, pdb_file)
        return self.structure

    def _get_ca_atom(self, chain_id: str, residue_id: Union[int, str]):
        """
        Retrieve the alpha-carbon (CA) atom for a given chain and residue.

        Parameters:
        - chain_id (str): Chain identifier.
        - residue_id (Union[int, str]): Residue number.

        Returns:
        - Atom object of the CA atom.

        Raises:
        - ValueError: If the atom is not found.
        """
        for chain in self.structure[0]:  # Access the first model
            if chain.id == chain_id:
                for residue in chain:
                    if residue.id[1] == int(residue_id):  # Match residue number
                        if 'CA' in residue:
                            return residue['CA']
        raise ValueError(f"CA atom not found in chain {chain_id}, residue {residue_id}")

    def _get_dist(
        self,
        chain_1: str,
        chain_2: str,
        i_1: Union[int, str],
        j_1: Union[int, str],
    ) -> float:
        """
        Calculate the distance between two alpha-carbon (CA) atoms.

        Parameters:
        - chain_1 (str): Chain ID of the first atom.
        - chain_2 (str): Chain ID of the second atom.
        - i_1 (Union[int, str]): Residue ID of the first atom.
        - j_1 (Union[int, str]): Residue ID of the second atom.

        Returns:
        - float: Distance between the two atoms, or -1 if atoms are not found.
        """
        try:
            atom1 = self._get_ca_atom(chain_1, i_1)
            atom2 = self._get_ca_atom(chain_2, j_1)
            return atom1 - atom2
        except ValueError as e:
            warnings.warn(f"Error calculating distance: {e}", category=UserWarning)
            return -1

    def bind_chains(self, coevolved_pairs: Tuple[CoevolvedPair]) -> Tuple[CoevolvedPair]:
        """
        Record chain binding: distances and maximum distance to be accepted.

        Parameters:
        - coevolved_pairs (tuple): Coevolved pairs for which distances are calculated.

        Returns:
        - Tuple of updated CoevolvedPair objects with distance data.
        """
        self.structure = self.get_input_pdb()

        if not (self.chain_binding_enabled and self.chains_to_bind):
            logging.info("Intrachain connections.")
            results = Parallel(n_jobs=self.n_jobs)(
                delayed(self._calculate_intrachain_dist)(pair)
                for pair in coevolved_pairs
            )
            return tuple(results)

        results = Parallel(n_jobs=self.n_jobs)(
            delayed(self._calculate_interchain_dist)(pair)
            for pair in coevolved_pairs
        )

        return tuple(results)

    def _calculate_intrachain_dist(self, pair: CoevolvedPair) -> CoevolvedPair:
        """
        Calculate distances for intrachain interactions.

        Parameters:
        - pair (CoevolvedPair): The coevolved pair for distance calculation.

        Returns:
        - Updated CoevolvedPair with distance data.
        """
        pair.dist_cutoff = self.max_interact_dist
        dist = self._get_dist(
            chain_1=self.design_chain_id,
            chain_2=self.design_chain_id,
            i_1=pair.i_1,
            j_1=pair.j_1,
        )
        if dist >= 0:
            pair.homochains_dist.update(
                {f"{self.design_chain_id}{self.design_chain_id}": dist}
            )
        return pair

    def _calculate_interchain_dist(self, pair: CoevolvedPair) -> CoevolvedPair:
        """
        Calculate distances for interchain interactions.

        Parameters:
        - pair (CoevolvedPair): The coevolved pair for distance calculation.

        Returns:
        - Updated CoevolvedPair with distance data.
        """
        pair.dist_cutoff = self.max_interact_dist
        for c1, c2 in itertools.product(self.chains_to_bind, repeat=2):
            dist = self._get_dist(
                chain_1=c1, chain_2=c2, i_1=pair.i_1, j_1=pair.j_1
            )
            if 0 <= dist <= self.max_interact_dist:
                pair.homochains_dist.update({f"{c1}{c2}": dist})
        return pair


class GremlinAnalyser:
    def __init__(self):
        # Check if the instance has already been initialized

        self.bus: ConfigBus = ConfigBus()
        self.alphabet: str = None  # type: ignore

        self.PWD: str = self.bus.get_value("work_dir", str)
        self.ws_server: REvoDesignWebSocketServer = REvoDesignWebSocketServer()

        self.design_molecule: str = self.bus.get_value(
            "ui.header_panel.input.molecule"
        )
        self.design_chain_id: str = self.bus.get_value(
            "ui.header_panel.input.chain_id"
        )
        self.designable_sequences = RosettaPyProteinSequence.from_dict(
            dict(self.bus.get_value("designable_sequences"))
        )
        self.design_sequence: str = (
            self.designable_sequences.get_sequence_by_chain(
                self.design_chain_id
            )
        )
        self.ce_object_group_valid: str = None
        self.ce_object_group_invalid: str = None

        self.coevolved_pairs: IterableLoop[CoevolvedPair] = None

        self.max_interact_dist: float = -1
        self.chain_binding_enabled: bool = False
        self.chains_to_bind: tuple = []

        self.explored_mutant_tree: MutantTree = MutantTree({})
        self.mutant_tree_coevolved = MutantTree({})
        self.picked_gremlin_mutant: Mutant = None

        self.magician: Magician = Magician()

    def load_gremlin_mrf(self):

        gremlin_mrf_fp = self.bus.get_value("ui.interact.input.gremlin_pkl")

        topN_gremlin_candidates = self.bus.get_value(
            "ui.interact.topN_pairs", int
        )
        if (not self.design_molecule) or (not self.design_chain_id):
            logging.error(
                "Molecule Info not complete. \n"
                f"molecule: {self.design_molecule}\n"
                f"chain: {self.design_chain_id}."
            )
            return

        if not os.path.exists(gremlin_mrf_fp):
            logging.error(
                "Could not run GREMLIN tools. Please check your configuration"
            )
            raise issues.InvalidInputError(
                f"GREMLIN MRF file {gremlin_mrf_fp} does not exist."
            )

        pushButton_run_interact_scan = self.bus.button("run_interact_scan")
        gridLayout_interact_pairs = self.bus.ui.gridLayout_interact_pairs

        # reset design info
        lineEdit_current_pair_wt_score = (
            self.bus.ui.lineEdit_current_pair_wt_score
        )
        lineEdit_current_pair_mut_score = (
            self.bus.ui.lineEdit_current_pair_mut_score
        )
        lineEdit_current_pair = self.bus.ui.lineEdit_current_pair
        lineEdit_current_pair_score = self.bus.ui.lineEdit_current_pair_score

        for lineEdit in [
            lineEdit_current_pair,
            lineEdit_current_pair_score,
            lineEdit_current_pair_wt_score,
            lineEdit_current_pair_mut_score,
        ]:
            set_widget_value(lineEdit, "")

        # Reinitialize Gremlin mutant tree
        self.mutant_tree_coevolved = MutantTree({})

        self.gremlin_tool = GREMLIN_Tools(molecule=self.design_molecule)

        self.gremlin_tool.sequence = self.design_sequence
        self.alphabet = self.gremlin_tool.alphabet

        run_worker_thread_with_progress(
            worker_function=self.gremlin_tool.load_msa_and_mrf,
            mrf_path=gremlin_mrf_fp,
            progress_bar=self.bus.ui.progressBar,
        )

        pushButton_run_interact_scan.setEnabled(bool(self.gremlin_tool))

        if not self.gremlin_tool:
            logging.error(
                "Failed to create gremlin tool object. Please check the inputs."
            )
            return

        self.gremlin_tool.pwd = self.PWD
        self.gremlin_tool.topN = topN_gremlin_candidates

        run_worker_thread_with_progress(
            worker_function=self.gremlin_tool.get_to_coevolving_pairs,
            progress_bar=self.bus.ui.progressBar,
        )

        plot_mtx_fp = self.gremlin_tool.plot_mtx()

        try:
            set_widget_value(gridLayout_interact_pairs, plot_mtx_fp)
        except AttributeError:
            logging.info(
                "Work Space is cleaned. Click once again to reinitialize. "
            )

    def run_gremlin_tool(self):
        self.chain_binding_enabled: bool = self.bus.get_value(
            "ui.interact.chain_binding.enabled", bool
        )
        self.chains_to_bind: tuple = tuple(
            set(
                self.bus.get_value(
                    "ui.interact.chain_binding.chains_to_bind", str
                )
            )
        )
        self.max_interact_dist: float = self.bus.get_value(
            "ui.interact.max_interact_dist", float
        )

        # name this subdir for every analysis
        chains = "".join(self.chains_to_bind)
        if self.chain_binding_enabled and self.chains_to_bind:
            subdir = (
                f"{self.design_molecule}_{self.design_chain_id}.homo.{chains}"
            )
        else:
            subdir = f"{self.design_molecule}_{self.design_chain_id}.mono"

        if any_posision_has_been_selected():
            logging.info("One vs All mode.")
            self.gremlin_tool_a2a_mode = False
            resi = int(cmd.get_model("sele and n. CA").atom[0].resi)
            logging.info(f"{resi} is selected.")

            self.gremlin_workpath = os.path.join(
                self.PWD,
                "gremlin_co_evolved_pairs",
                subdir,
                f"resi_{resi}",
            )
            os.makedirs(self.gremlin_workpath, exist_ok=True)
            self.gremlin_tool.pwd = self.gremlin_workpath

            coevolved_pairs: tuple[CoevolvedPair] = (
                run_worker_thread_with_progress(
                    worker_function=self.gremlin_tool.plot_w_o2a,
                    resi=resi - 1,
                    progress_bar=self.bus.ui.progressBar,
                )
            )

        else:
            logging.info("No selection `sele` is picked, use All vs All mode.")
            self.gremlin_tool_a2a_mode = True

            self.gremlin_workpath = os.path.join(
                self.PWD,
                "gremlin_co_evolved_pairs",
                subdir,
                "all_vs_all",
            )
            os.makedirs(self.gremlin_workpath, exist_ok=True)
            self.gremlin_tool.pwd = self.gremlin_workpath

            coevolved_pairs: tuple[CoevolvedPair] = (
                run_worker_thread_with_progress(
                    worker_function=self.gremlin_tool.plot_w_a2a,
                    progress_bar=self.bus.ui.progressBar,
                )
            )

        if not coevolved_pairs:
            warnings.warn(
                issues.NoResultsWarning(
                    "No Available co-evolutionary signal in global"
                )
            )
            # early return if no data.
            return

        logging.info(f"Found {len(coevolved_pairs)} pairs")

        logging.debug(coevolved_pairs)

        logging.info("Binding Chains ...")
        chain_binder = ChainBinder(
            design_molecule=self.design_molecule,
            design_chain_id=self.design_chain_id,
            chain_binding_enabled=self.chain_binding_enabled,
            max_interact_dist=self.max_interact_dist,
            chains_to_bind=self.chains_to_bind,
            n_jobs=self.bus.get_value("ui.header_panel.nproc", int),
        )

        coevolved_pairs: tuple[CoevolvedPair] = (
            run_worker_thread_with_progress(
                worker_function=chain_binder.bind_chains,
                coevolved_pairs=coevolved_pairs,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.coevolved_pairs = IterableLoop(
            iterable=tuple(
                filter(self.coevolved_pairs_filter, coevolved_pairs)
            )
        )

        del coevolved_pairs
        del chain_binder

        if self.coevolved_pairs.empty:
            warnings.warn(
                issues.NoResultsWarning("No coevolved_pairs passes filter.")
            )
            return

        logging.info("Visualizing as bonds ...")
        self.plot_coevolved_pair_in_pymol()

        try:
            self.bus.button("previous").clicked.disconnect()
            self.bus.button("next").clicked.disconnect()
        except Exception as e:
            warnings.warn(
                issues.AlreadyDisconnectedWarning(
                    f"button is already disconnected. do nothing. {e=}"
                )
            )

        self.bus.button("previous").clicked.connect(
            partial(self.load_co_evolving_pairs, False)
        )

        self.bus.button("next").clicked.connect(
            partial(self.load_co_evolving_pairs, True)
        )

        # intitialize
        set_widget_value(
            self.bus.ui.progressBar, [0, len(self.coevolved_pairs.iterable)]
        )

        self.picked_gremlin_group_id = ""

        self.load_co_evolving_pairs()

        self.gremlin_tool.cite()

    @staticmethod
    def coevolved_pairs_filter(p: CoevolvedPair) -> bool:
        if p.empty:
            return False
        if not [x for x in p.all_res_pairs_selections.values()]:
            return False

        return True

    def plot_coevolved_pair_in_pymol(self):
        # visualize co-evolved pair in pymol UI
        min_gremlin_score = min(
            [
                min([p.zscore for p in self.coevolved_pairs.iterable]),
                0,
            ]
        )
        max_gremlin_score = max(
            [p.zscore for p in self.coevolved_pairs.iterable]
        )

        self.ce_object_group_valid = cmd.get_unused_name(
            f"cep_{self.design_molecule}_"
        )

        self.ce_object_group_invalid = cmd.get_unused_name(
            f"invalid_{self.ce_object_group_valid}_"
        )

        _tmp_obj = f"_tmp_object_for_{self.ce_object_group_valid}"

        cmd.create(_tmp_obj, f"{self.design_molecule} and n. CA")
        cmd.hide("cartoon", _tmp_obj)
        cmd.hide("surface", _tmp_obj)

        i_out_of_range: List[CoevolvedPair] = []
        discarded: List[CoevolvedPair] = []
        set_widget_value(
            self.bus.ui.progressBar, (0, len(self.coevolved_pairs.iterable))
        )
        for i, pair in enumerate(self.coevolved_pairs.iterable):
            set_widget_value(self.bus.ui.progressBar, i)
            refresh_window()

            sele_name = repr(pair)
            logging.debug(f"{sele_name=}")
            pair.selection_string = cmd.get_unused_name(f"{sele_name}_")
            _sele = " or ".join(
                [x for x in pair.all_res_pairs_selections.values()]
            )
            sele = f"{_tmp_obj} and ({_sele}) and n. CA"

            try:
                logging.debug(
                    f"trying to get all atom from {pair.selection_string=}: {sele=}"
                )
                cmd.create(
                    pair.selection_string,
                    sele,
                )
            except CmdException:
                logging.debug("Failed, now discard this pair!")
                warnings.warn(
                    issues.BadDataWarning(
                        f"This atom selection is invalid: {sele}"
                    )
                )
                discarded.append(pair)
                continue
            refresh_window()
            cmd.hide("cartoon", pair.selection_string)
            cmd.hide("surface", pair.selection_string)
            cmd.show("sticks", pair.selection_string)
            refresh_window()
            zscore = rescale_number(
                pair.zscore,
                min_value=min_gremlin_score,
                max_value=max_gremlin_score,
            )
            refresh_window()
            logging.debug(
                f"Setting stick_radius as {zscore=} for {pair.selection_string=}"
            )
            cmd.set(
                "stick_radius",
                zscore,
                pair.selection_string,
            )

            refresh_window()
            if pair.all_out_of_range:
                i_out_of_range.append(pair)
                logging.debug(
                    f"Grouping {pair.selection_string=} to {self.ce_object_group_invalid=}"
                )
                cmd.group(self.ce_object_group_invalid, pair.selection_string)

            else:
                logging.debug(
                    f"Grouping {pair.selection_string=} to {self.ce_object_group_valid=}"
                )
                cmd.group(self.ce_object_group_valid, pair.selection_string)

            # bond w/o colors
            # out-of-range residue pair in valid pair will be not considered.
            for cc, res_pair in pair.all_res_pairs.items():
                refresh_window()
                if pair.is_out_of_range(cc):
                    logging.info(
                        f"Resi {pair.i_1}({cc[0]}) is {pair.dist(chain_pair=cc):.2f} Å away from {pair.j_1}({cc[1]}), out of distance {pair.dist_cutoff} Å."
                    )

                    continue

                logging.debug(
                    f"Bonding {pair.selection_string}: {res_pair[0]} and {res_pair[1]}"
                )

                cmd.bond(
                    f"{pair.selection_string} and {res_pair[0]} and n. CA",
                    f"{pair.selection_string} and {res_pair[1]} and n. CA",
                )
        refresh_window()
        cmd.delete(_tmp_obj)
        cmd.group(self.ce_object_group_valid, action="close")
        cmd.group(self.ce_object_group_invalid, action="close")
        refresh_window()
        for p in i_out_of_range:
            logging.info(
                f"Pair {p.i_aa}-{p.j_aa} will be removed: out of range."
            )

        self.mark_pair_state(
            pairs=tuple(p for p in i_out_of_range),
            state="out_of_range",
        )

        # remove pairs that distal or discarded
        self.coevolved_pairs = IterableLoop(
            iterable=tuple(
                filter(
                    lambda p: not (p in i_out_of_range or p in discarded),
                    self.coevolved_pairs.iterable,
                )
            )
        )
        self.mark_pair_state(
            pairs=self.coevolved_pairs.iterable,
            state="available",
        )

        cmd.set("stick_use_shader", 0)
        cmd.set("stick_round_nub", 0)

        logging.warning(f"Out of range: {len(i_out_of_range)}")
        logging.warning(f"Discarded pairs: {len(discarded)}")
        logging.warning(
            f"Filtered pairs: {len(self.coevolved_pairs.iterable)}"
        )

        set_widget_value(
            self.bus.ui.progressBar, (0, len(self.coevolved_pairs.iterable))
        )

        CitationManager().output()
        return

    def mark_pair_state(
        self,
        pairs: Union[CoevolvedPair, List[CoevolvedPair], Tuple[CoevolvedPair]],
        state: CoevolvedPairState.state_type = "available",
    ):
        if not self.ce_object_group_valid:
            raise issues.UnexpectedWorkflowError(
                f"Cannot mark pair state because {self.ce_object_group_valid=} is not set"
            )
        color = CoevolvedPairState().color(state)

        if isinstance(pairs, CoevolvedPair):
            pairs = (pairs,)

        for p in pairs:
            refresh_window()
            cmd.set(
                "stick_color",
                color,
                p.selection_string,
            )
            cmd.set(
                "stick_transparency",
                0.7 if state != "in_design" else 0.1,
                p.selection_string,
            )

        logging.debug(f"Marking pair as {state=}: {[str(p) for p in pairs]}")

        if state != "in_design":
            return

        _sele = " or ".join([p.selection_string for p in pairs])

        logging.debug(f"{_sele=}")

        cmd.orient(selection=f"byres ({_sele}) around 15", animate=1)

    def load_co_evolving_pairs(
        self,
        walk_to_next=True,
    ):
        def mutate_with_gridbuttons(
            col,
            row,
            matrix: pd.DataFrame,
            min_score,
            max_score,
            pair: CoevolvedPair,
            ignore_wt=False,
        ):

            self.picked_gremlin_group_id = "_vs_".join(
                [
                    wt.replace("_", "")
                    for wt in (
                        pair.i_aa,
                        pair.j_aa,
                    )
                ]
            )

            # aa from wt
            wt_i = pair.wt("i")  # in column
            wt_j = pair.wt("j")  # in row

            # aa from clicked button, mutant
            mut_i = self.alphabet[col]
            mut_j = self.alphabet[row]

            # construct this Mutant obj from scratch.
            _mutant: List[Mutation] = []

            for chain_id_pair in pair.homochains:
                for chain_id, mut, idx, wt in zip(
                    chain_id_pair,
                    [mut_i, mut_j],
                    [pair.i_1, pair.j_1],
                    [wt_i, wt_j],
                ):
                    expected_mutant = Mutation(
                        chain_id=chain_id,
                        position=int(idx),
                        wt_res=wt,
                        mut_res=mut,
                    )
                    if expected_mutant in _mutant:
                        logging.warning(
                            f"Ignore existed mutagenese {expected_mutant}"
                        )
                        continue
                    if wt == mut and ignore_wt:
                        logging.debug(
                            f"Ignore WT to WT mutagenese {expected_mutant}"
                        )
                        continue

                    if mut == "-":
                        logging.warning(f"Igore deletion {expected_mutant}")
                        continue

                    logging.debug(f"Adding mutagenesis {expected_mutant}")
                    _mutant.append(expected_mutant)
            logging.debug(_mutant)

            # early return if nothing is created.
            if not _mutant:
                logging.info(
                    "No mutagenesis will be performed since the picked pair is a wt-wt pair"
                )
                return

            mutant_obj = Mutant(
                mutations=_mutant, wt_protein_sequence=self.designable_sequences
            )

            self.refresh_magician()

            # call scorer to evaluate wt and mutant
            if not self.magician.gimmick:
                wt_score = matrix.loc[wt_i, wt_j]
                mut_score = matrix.loc[mut_i, mut_j]
            else:
                if self.magician.gimmick.no_need_to_score_wt:
                    wt_score = 0
                else:
                    wt_score = run_worker_thread_with_progress(
                        worker_function=self.magician.gimmick.scorer,
                        mutant=self.designable_sequences,
                        progress_bar=self.bus.ui.progressBar,
                    )
                mut_score = run_worker_thread_with_progress(
                    worker_function=self.magician.gimmick.scorer,
                    mutant=mutant_obj,
                    progress_bar=self.bus.ui.progressBar,
                )

            mutant_obj.wt_score = wt_score
            mutant_obj.mutant_score = mut_score

            self.picked_gremlin_mutant = mutant_obj

            # if mutant obj exists, activate it and return early.
            if self.explored_mutant_tree.has(mutant_obj.full_mutant_id):
                logging.info(f"Picked mutant: {mutant_obj.short_mutant_id} ({mutant_obj.full_mutant_id}) "
                             f"already exists. Do nothing.")
                self.activate_focused_interaction()
                return

            with timing(f"Visualizing {mutant_obj.short_mutant_id}"):
                # otherwise, call MutantVisualizer to display it.
                logging.info(
                    f"Picked mutant:{(mutant := mutant_obj.short_mutant_id)} "
                    f"{(full_mutant_id := mutant_obj.full_mutant_id)} "
                )

                color = get_color(
                    self.bus.get_value("ui.header_panel.cmap.default"),
                    mut_score,
                    min_score,
                    max_score,
                )

                logging.info(f"Visualizing {mutant} ({full_mutant_id}): {color}")

                visualizer = MutantVisualizer(
                    molecule=self.design_molecule, chain_id=self.design_chain_id
                )

                run_worker_thread_with_progress(
                    worker_function=SidechainSolver().refresh,
                    progress_bar=self.bus.ui.progressBar,
                )

                visualizer.mutate_runner = SidechainSolver().mutate_runner
                visualizer.designable_sequences = self.designable_sequences
                visualizer.sequence = self.design_sequence

                visualizer.group_name = self.picked_gremlin_group_id

                run_worker_thread_with_progress(
                    worker_function=visualizer.create_mutagenesis_objects,
                    mutant_obj=mutant_obj,
                    color=color,
                    progress_bar=self.bus.ui.progressBar,
                )
                cmd.hide("everything", "hydrogens and polymer.protein")
                cmd.hide("cartoon", mutant)

                # create a new record.
                self.explored_mutant_tree.add_mutant_to_branch(
                    branch=visualizer.group_name,
                    mutant=mutant,
                    mutant_obj=mutant_obj,
                )

            self.activate_focused_interaction()

            del visualizer

            # create a small mutant tree and send to broadcaster.
            mutant_tree = MutantTree(
                {self.picked_gremlin_group_id: {mutant: mutant_obj}}
            )
            self.to_broadcaster(mutant_tree)

        with hold_trigger_button(
            buttons=self.bus.buttons(button_ids=("previous", "next"))
        ):
            ignore_wt = self.bus.get_value("ui.interact.interact_ignore_wt")

            lineEdit_current_pair = self.bus.ui.lineEdit_current_pair
            lineEdit_current_pair_score = (
                self.bus.ui.lineEdit_current_pair_score
            )

            if not self.design_chain_id or not self.design_molecule:
                logging.error("No available molecule or chain id.")
                return

            # before walking the index, set this pair back
            self.mark_pair_state(
                pairs=(p := self.coevolved_pairs.current_item),
                state=(
                    "available" if not p.all_out_of_range else "out_of_range"
                ),
            )

            self.coevolved_pairs.walker(direction=walk_to_next)

            set_widget_value(
                self.bus.ui.progressBar, self.coevolved_pairs.current_idx
            )

            pair = self.coevolved_pairs.current_item

            # Clear the existing widgets from gridLayout_interact_pairs
            for i in reversed(
                range(self.bus.ui.gridLayout_interact_pairs.count())
            ):
                widget = self.bus.ui.gridLayout_interact_pairs.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()

            # after walking and widget is updated, mark it as in design
            self.mark_pair_state(pairs=pair, state="in_design")

            button_matrix = QButtonMatrixGremlin(
                df_matrix=pair.df,
                sequence=self.design_sequence,
                pair_i=pair.i,
                pair_j=pair.j,
                cmap=self.bus.get_value("ui.header_panel.cmap.default"))

            button_matrix.alphabet_col = list("ARNDCQEGHILKMFPSTWYV-")
            button_matrix.alphabet_row = list("ARNDCQEGHILKMFPSTWYV-")

            button_matrix.init_ui()
            button_matrix.active_func = partial(
                mutate_with_gridbuttons,
                matrix=button_matrix.df_matrix,
                min_score=button_matrix.min_value,
                max_score=button_matrix.max_value,
                pair=pair,
                ignore_wt=ignore_wt,
            )

            self.bus.ui.gridLayout_interact_pairs.addWidget(button_matrix)

            set_widget_value(
                lineEdit_current_pair,
                f'{pair.i_aa.replace("_", "")}-{pair.j_aa.replace("_", "")}, {pair.min_dist:.1f} Å',
            )

            set_widget_value(lineEdit_current_pair_score, f"{pair.zscore:.3f}")

            if pair.all_out_of_range:
                logging.warning(f"Resi {pair.i_1} ({pair.i_aa}) is {pair.min_dist:.2f} Å away "
                                f"from {pair.j_1} {pair.j_aa}, out of distance {pair.dist_cutoff} Å")
                set_widget_value(lineEdit_current_pair, "Out of range.")

            # To disable the QbuttonMatrix:
            button_matrix.setEnabled(not pair.all_out_of_range)

    def coevoled_mutant_decision(self, accept: bool):
        if self.explored_mutant_tree.empty or not self.picked_gremlin_mutant:
            raise issues.UnexpectedWorkflowError("Nothing to decide.")

        picked_gremlin_mutant_id = self.picked_gremlin_mutant.short_mutant_id

        if accept:
            logging.debug(
                f"Accepting co-evolved mutant {picked_gremlin_mutant_id}"
            )
            cmd.enable(picked_gremlin_mutant_id)

            self.mutant_tree_coevolved.add_mutant_to_branch(
                self.picked_gremlin_group_id,
                picked_gremlin_mutant_id,
                self.picked_gremlin_mutant,
            )
        else:
            logging.debug(
                f" Rejecting co-evolved mutant {picked_gremlin_mutant_id}"
            )
            cmd.disable(picked_gremlin_mutant_id)
            if not self.mutant_tree_coevolved.has(picked_gremlin_mutant_id):
                logging.warning(
                    f"{picked_gremlin_mutant_id} has not been accepted yet. Skipped."
                )
                return

            self.mutant_tree_coevolved.remove_mutant_from_branch(
                self.picked_gremlin_group_id,
                picked_gremlin_mutant_id,
            )

        save_mutant_choices(
            self.bus.get_value("ui.interact.input.to_mutant_txt"),
            self.mutant_tree_coevolved,
        )

    @staticmethod
    def show_mutant(mutant_id: str, group_id: Optional[str] = None):
        cmd.enable(mutant_id)
        cmd.show(
            "sticks",
            f"{mutant_id} and (sidechain or n. CA) and not hydrogen",
        )
        cmd.show(
            "mesh",
            f"{mutant_id} and (sidechain or n. CA)",
        )
        cmd.hide("cartoon", f"{mutant_id}")
        cmd.center(mutant_id)

        # expand group object if activated
        if group_id:
            cmd.enable(group_id)
            cmd.group(group_id, action="open")

    def hide_all_mutants(self):
        for group_id in self.explored_mutant_tree.all_mutant_branch_ids:
            cmd.disable(group_id)
            cmd.group(group_id, action="close")

    def activate_focused_interaction(self):
        if not self.picked_gremlin_mutant or self.picked_gremlin_mutant.empty:
            raise issues.UnexpectedWorkflowError(
                "Co-evolved pairs are not loaded. "
            )

        if self.explored_mutant_tree.has(self.picked_gremlin_mutant.full_mutant_id):
            logging.warning(f"Igore repetative picking: {self.picked_gremlin_mutant.short_mutant_id} "
                            f"({self.picked_gremlin_mutant.full_mutant_id})")
        self.hide_all_mutants()
        self.show_mutant(
            mutant_id=self.picked_gremlin_mutant.short_mutant_id,
            group_id=self.picked_gremlin_group_id,
        )

        # display scores
        lineEdit_current_pair_wt_score = (
            self.bus.ui.lineEdit_current_pair_wt_score
        )
        lineEdit_current_pair_mut_score = (
            self.bus.ui.lineEdit_current_pair_mut_score
        )

        set_widget_value(
            lineEdit_current_pair_wt_score,
            f"{self.picked_gremlin_mutant.wt_score:.4f}",
        )
        set_widget_value(
            lineEdit_current_pair_mut_score,
            f"{self.picked_gremlin_mutant.mutant_score:.4f}",
        )

        return

    def refresh_magician(self):

        magician = run_worker_thread_with_progress(
            worker_function=self.magician.setup,
            name_cfg_item="ui.interact.use_external_scorer",
            molecule=self.design_molecule,
            ignore_missing=bool("X" in self.design_sequence),
            chain=",".join(
                self.chains_to_bind
                if self.chain_binding_enabled
                else self.design_chain_id
            ),
            homooligomeric=self.chain_binding_enabled and self.chains_to_bind,
            progress_bar=self.bus.ui.progressBar,
        )
        if magician is None:
            raise issues.UnexpectedWorkflowError(
                "Magician failed to initialize."
            )
        self.magician = magician

        return

    def to_broadcaster(self, mutant_tree: MutantTree):
        if (
            self.ws_server
            and self.ws_server.is_running
            and not mutant_tree.empty
        ):
            asyncio.run(
                self.ws_server.broadcast_object(
                    obj=mutant_tree,
                    data_type="MutantTree",
                )
            )
