import asyncio
from functools import partial
import os
import traceback
from typing import Union

from immutabledict import immutabledict
from REvoDesign import ConfigBus
from REvoDesign.clients.QtSocketConnector import REvoDesignWebSocketServer
from REvoDesign.common.Mutant import Mutant
from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.phylogenetics.GREMLIN_Tools import CoevolvedPair, GREMLIN_Tools
from REvoDesign.sidechain_solver import MutateRunnerAbstract
from REvoDesign.tools.customized_widgets import QbuttonMatrix, set_widget_value
from REvoDesign.tools.mutant_tools import (
    extract_mutant_from_pymol_object,
    extract_mutants_from_mutant_id,
    save_mutant_choices,
)

from REvoDesign.tools.pymol_utils import (
    any_posision_has_been_selected,
    is_a_REvoDesign_session,
    make_temperal_input_pdb,
)
from REvoDesign.tools.utils import (
    cmap_reverser,
    dirname_does_exist,
    get_color,
    rescale_number,
    run_worker_thread_with_progress,
)
from pymol import cmd, CmdException
from typing import Literal
from dataclasses import dataclass
from REvoDesign import root_logger
import warnings
from REvoDesign import issues

logging = root_logger.getChild('phylogenetics')


@dataclass
class CoevolvedPairState:
    state2color: immutabledict = immutabledict(
        {
            'available': 'marine',
            'out_of_range': 'salmon',
            'in_design': 'tv_yellow',
        }
    )

    state_type = Literal['available', 'out_of_range', 'in_design']

    def color(self, state: state_type) -> str:
        if not (color := self.state2color.get(state)):
            raise ValueError(f'Invalid state keyword {state}')
        return color


class MutateWorker:
    def __init__(self, PWD, mutate_runner):
        self.bus: ConfigBus = ConfigBus()

        self.PWD: str = PWD
        self.mutate_runner: MutateRunnerAbstract = mutate_runner

        self.design_molecule: str = self.bus.get_value(
            'ui.header_panel.input.molecule'
        )
        self.design_chain_id: str = self.bus.get_value(
            'ui.header_panel.input.chain_id'
        )
        self.designable_sequences: dict = self.bus.get_value(
            'designable_sequences'
        )
        self.design_sequence: str = self.designable_sequences.get(
            self.design_chain_id
        )

    def run_mutant_loading_from_profile(self):
        try:
            design_profile = self.bus.get_value('ui.mutate.input.profile')
            design_profile_format = self.bus.get_value(
                'ui.mutate.input.profile_type'
            )
            preffered = self.bus.get_value('ui.mutate.accept')
            rejected = self.bus.get_value('ui.mutate.reject')

            temperature = self.bus.get_value(
                'ui.mutate.designer.temperature', float
            )
            num_designs = self.bus.get_value(
                'ui.mutate.designer.num_sample', int
            )
            batch = self.bus.get_value('ui.mutate.designer.batch', int)
            homooligomeric = self.bus.get_value(
                'ui.mutate.designer.homooligomeric'
            )
            deduplicate_designs = self.bus.get_value(
                'ui.mutate.designer.deduplicate_designs'
            )
            randomized_sample = self.bus.get_value(
                'ui.mutate.designer.enable_randomized_sampling'
            )
            randomized_sample_num = self.bus.get_value(
                'ui.mutate.designer.randomized_sampling', int
            )
            design_case = self.bus.get_value('ui.mutate.input.design_case')
            custom_indices_fp = self.bus.get_value(
                'ui.mutate.input.residue_ids'
            )
            cutoff = [
                (self.bus.get_value('ui.mutate.min_score', float)),
                (self.bus.get_value('ui.mutate.max_score', float)),
            ]
            reversed_mutant_effect = self.bus.get_value(
                'ui.header_panel.cmap.reverse_score'
            )
            output_pse = self.bus.get_value('ui.mutate.input.to_pse')
            nproc = self.bus.get_value('ui.header_panel.nproc', int)

            cmap = cmap_reverser(
                cmap=self.bus.get_value('ui.header_panel.cmap.default'),
                reverse=reversed_mutant_effect,
            )

            if is_a_REvoDesign_session():
                warnings.warn(
                    issues.REvoDesignSessionsWarning(
                        'Loading mutants into a REvoDesign session may trigger unexpected segmentation fault.\n'
                        'In order to keep the session\'s feature, you should always create seperate sessions according to '
                        'your dataset and merge them manually in PyMOL window.'
                    )
                )

            input_pse = make_temperal_input_pdb(
                molecule=self.design_molecule,
                format='pdb',
                wd=os.path.join(self.PWD, 'temperal_pdb'),
                reload=False,
            )

            from REvoDesign.phylogenetics.REvoDesigner import REvoDesigner

            self.design = REvoDesigner(design_profile)
            self.design.input_pse = input_pse
            self.design.output_pse = output_pse
            self.design.input_profile_format = design_profile_format

            self.design.molecule = self.design_molecule
            self.design.chain_id = self.design_chain_id
            self.design.sequence = self.design_sequence
            self.design.pwd = self.PWD
            self.design.design_case = design_case

            self.design.external_designer_temperature = temperature
            self.design.external_designer_num_samples = num_designs
            self.design.batch = batch
            self.design.homooligomeric = homooligomeric
            self.design.deduplicate_designs = deduplicate_designs
            self.design.randomized_sample = randomized_sample
            self.design.randomized_sample_num = randomized_sample_num

            self.design.mutate_runner = self.mutate_runner

            self.design.preffered_substitutions = preffered
            self.design.reject_aa = rejected
            self.design.nproc = nproc
            self.design.cmap = cmap
            self.design.create_full_pdb = False

            from REvoDesign.external_designer import EXTERNAL_DESIGNERS

            if design_profile_format in EXTERNAL_DESIGNERS.keys():
                run_worker_thread_with_progress(
                    worker_function=self.design.design_protein_using_external_designer,
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

            if not dirname_does_exist(self.design.output_pse):
                warnings.warn(
                    issues.NoResultsWarning(
                        f'No output PyMOL session is created.'
                    )
                )
                return

            cmd.reinitialize()
            cmd.load(input_pse, object=self.design_molecule)
            cmd.load(self.design.output_pse, partial=2)

            cmd.center(self.design_molecule)
            cmd.set('surface_color', 'gray70')
            cmd.set('cartoon_color', 'gray70')
            cmd.set('surface_cavity_mode', 4)
            cmd.set('transparency', 0.6)
            cmd.set(
                'cartoon_cylindrical_helices',
            )
            cmd.set('cartoon_transparency', 0.3)
            cmd.save(output_pse)

        except Exception:
            traceback.print_exc()


class VisualizingWorker:
    def __init__(self, PWD, mutate_runner):
        self.bus: ConfigBus = ConfigBus()

        self.PWD: str = PWD
        self.mutate_runner: MutateRunnerAbstract = mutate_runner

        self.design_molecule: str = self.bus.get_value(
            'ui.header_panel.input.molecule'
        )
        self.design_chain_id: str = self.bus.get_value(
            'ui.header_panel.input.chain_id'
        )
        self.designable_sequences: dict = self.bus.get_value(
            'designable_sequences'
        )
        self.design_sequence: str = self.designable_sequences.get(
            self.design_chain_id
        )

    def visualize_mutants(self):
        input_mut_table_csv = self.bus.get_value(
            'ui.visualize.input.from_mutant_txt'
        )

        output_pse = self.bus.get_value('ui.visualize.input.to_pse')
        best_leaf = self.bus.get_value('ui.visualize.input.best_leaf')
        totalscore = self.bus.get_value('ui.visualize.input.totalscore')
        nproc = self.bus.get_value('ui.header_panel.nproc', int)
        group_name = self.bus.get_value('ui.visualize.input.group_name', str)

        use_global_scores = self.bus.get_value(
            'ui.visualize.global_score_policy'
        )

        try:
            reversed_mutant_effect = self.bus.get_value(
                'ui.header_panel.cmap.reverse_score'
            )
            cmap = cmap_reverser(
                cmap=self.bus.get_value('ui.header_panel.cmap.default'),
                reverse=reversed_mutant_effect,
            )

            design_profile = self.bus.get_value('ui.visualize.input.profile')
            design_profile_format = self.bus.get_value(
                'ui.visualize.input.profile_type'
            )

            from REvoDesign.common.MutantVisualizer import MutantVisualizer

            self.visualizer = MutantVisualizer(
                molecule=self.design_molecule,
                chain_id=self.design_chain_id,
            )
            self.visualizer.mutfile = input_mut_table_csv
            self.visualizer.input_session = make_temperal_input_pdb(
                molecule=self.design_molecule,
                wd=os.path.join(os.path.dirname(output_pse), 'temperal_pdb'),
                reload=False,
            )
            self.visualizer.nproc = nproc
            self.visualizer.parallel_run = nproc > 1
            self.visualizer.sequence = self.design_sequence

            self.visualizer.consider_global_score_from_profile = (
                use_global_scores
            )

            self.visualizer.profile_scoring_df = None
            self.visualizer.consider_global_score_from_profile = False

            self.visualizer.profile_scoring_df = self.visualizer.parse_profile(
                profile_fp=design_profile,
                profile_format=design_profile_format,
            )

            if best_leaf:
                self.visualizer.key_col = best_leaf
            if totalscore:
                self.visualizer.score_col = totalscore

            self.visualizer.save_session = output_pse
            self.visualizer.full = False
            self.visualizer.group_name = group_name
            self.visualizer.cmap = cmap

            self.visualizer.mutate_runner = self.mutate_runner

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
            cmd.set('surface_color', 'gray70')
            cmd.set('cartoon_color', 'gray70')
            cmd.set('surface_cavity_mode', 4)
            cmd.set('transparency', 0.6)
            cmd.set(
                'cartoon_cylindrical_helices',
            )
            cmd.set('cartoon_transparency', 0.3)
            cmd.save(output_pse)

        except Exception:
            logging.error('Error while running the visualization: ')
            traceback.print_exc()


class GREMLIN_Analyser:
    def __init__(self, PWD, mutate_runner, ws_server=None):
        self.bus: ConfigBus = ConfigBus()

        self.PWD: str = PWD
        self.mutate_runner: MutateRunnerAbstract = mutate_runner
        self.ws_server: REvoDesignWebSocketServer = ws_server

        self.design_molecule: str = self.bus.get_value(
            'ui.header_panel.input.molecule'
        )
        self.design_chain_id: str = self.bus.get_value(
            'ui.header_panel.input.chain_id'
        )
        self.designable_sequences: dict = self.bus.get_value(
            'designable_sequences'
        )
        self.design_sequence: str = self.designable_sequences.get(
            self.design_chain_id
        )
        self.ce_object_name = None

    def load_gremlin_mrf(
        self,
    ):
        self.gremlin_external_scorer = None
        gremlin_mrf_fp = self.bus.get_value('ui.interact.input.gremlin_pkl')

        topN_gremlin_candidates = self.bus.get_value(
            'ui.interact.topN_pairs', int
        )
        if (not self.design_molecule) or (not self.design_chain_id):
            logging.error(
                f'Molecule Info not complete. \n\tmolecule: {self.design_molecule}\n\tchain: {self.design_chain_id}.'
            )
            return

        if not os.path.exists(gremlin_mrf_fp):
            logging.error(
                "Could not run GREMLIN tools. Please check your configuration"
            )
            return

        pushButton_run_interact_scan = self.bus.button('run_interact_scan')
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
            set_widget_value(lineEdit, '')

        # Reinitialize Gremlin mutant tree
        self.mutant_tree_coevolved = MutantTree({})

        self.gremlin_tool = GREMLIN_Tools(molecule=self.design_molecule)

        self.gremlin_tool.sequence = self.design_sequence

        run_worker_thread_with_progress(
            worker_function=self.gremlin_tool.load_msa_and_mrf,
            mrf_path=gremlin_mrf_fp,
            progress_bar=self.bus.ui.progressBar,
        )

        pushButton_run_interact_scan.setEnabled(bool(self.gremlin_tool))

        if not self.gremlin_tool:
            logging.error(
                f'Failed to create gremlin tool object. Please check the inputs.'
            )

            return

        self.gremlin_tool.pwd = self.PWD
        self.gremlin_tool.topN = topN_gremlin_candidates

        self.gremlin_tool.get_to_coevolving_pairs()
        plot_mtx_fp = self.gremlin_tool.plot_mtx()

        try:
            set_widget_value(gridLayout_interact_pairs, plot_mtx_fp)
        except AttributeError:
            logging.info(
                f'Work Space is cleaned. Click once again to reinitialize. '
            )

    def run_gremlin_tool(self):
        self.coevolved_pairs: dict[int, CoevolvedPair] = {}

        if any_posision_has_been_selected():
            logging.info(f'One vs All mode.')
            self.gremlin_tool_a2a_mode = False
            resi = int(cmd.get_model('sele and n. CA').atom[0].resi)
            logging.info(f'{resi} is selected.')

            self.gremlin_workpath = os.path.join(
                self.PWD, 'gremlin_co_evolved_pairs', f'resi_{resi}'
            )
            os.makedirs(self.gremlin_workpath, exist_ok=True)
            self.gremlin_tool.pwd = self.gremlin_workpath

            self.coevolved_pairs: dict[
                int, CoevolvedPair
            ] = run_worker_thread_with_progress(
                worker_function=self.gremlin_tool.plot_w_o2a,
                resi=resi - 1,
                progress_bar=self.bus.ui.progressBar,
            )

            if not self.coevolved_pairs:
                warnings.warn(
                    issues.NoResultsWarning(
                        f'No Available co-evolutionary signal against {resi}'
                    )
                )
                # early return if no data.
                return

            logging.info(
                f'Found {len(self.coevolved_pairs.keys())} pairs against {resi}.'
            )

            self.coevolved_pairs: dict[int, CoevolvedPair] = self.reorder_dict(
                self.coevolved_pairs
            )

        else:
            logging.info(
                f'No selection `sele` is picked, use All vs All mode.'
            )
            self.gremlin_tool_a2a_mode = True

            self.gremlin_workpath = os.path.join(
                self.PWD, 'gremlin_co_evolved_pairs', 'all_vs_all'
            )
            os.makedirs(self.gremlin_workpath, exist_ok=True)
            self.gremlin_tool.pwd = self.gremlin_workpath

            self.coevolved_pairs: dict[
                int, CoevolvedPair
            ] = run_worker_thread_with_progress(
                worker_function=self.gremlin_tool.plot_w_a2a,
                progress_bar=self.bus.ui.progressBar,
            )

            if not self.coevolved_pairs:
                warnings.warn(
                    issues.NoResultsWarning(
                        f'No Available co-evolutionary signal in global'
                    )
                )
                # early return if no data.
                return

            logging.info(
                f'Found {len(self.coevolved_pairs.keys())} pairs in global'
            )

        logging.debug(self.coevolved_pairs)

        self.plot_coevolved_pair_in_pymol()

        try:
            self.bus.button('previous').clicked.disconnect()
            self.bus.button('next').clicked.disconnect()
        except Exception as e:
            warnings.warn(
                issues.AlreadyDisconnectedWarning(
                    'button is already disconnected. do nothing'
                )
            )

        self.bus.button('previous').clicked.connect(
            partial(self.load_co_evolving_pairs, False)
        )

        self.bus.button('next').clicked.connect(
            partial(self.load_co_evolving_pairs, True)
        )

        # intitialize
        set_widget_value(
            self.bus.ui.progressBar, [0, len(self.coevolved_pairs.keys())]
        )
        self.picked_gremlin_pair_idx = -1

        self.picked_gremlin_mutant_id = ''
        self.last_gremlin_mutant_id = ''

        self.picked_gremlin_group_id = ''
        self.last_gremlin_co_evoving_pair_group_id = ''

        self.load_co_evolving_pairs()

        # visualize co-evolved pair in pymol UI

    def plot_coevolved_pair_in_pymol(self):
        max_interact_dist: float = self.bus.get_value(
            'ui.interact.max_interact_dist', float
        )
        min_gremlin_score = min(
            [
                min([i.zscore for i in self.coevolved_pairs.values()]),
                0,
            ]
        )
        max_gremlin_score = max(
            [i.zscore for i in self.coevolved_pairs.values()]
        )

        self.ce_object_name = cmd.get_unused_name(
            f"ce_pairs_{self.design_molecule}_{self.design_chain_id}"
        )

        cmd.create(
            self.ce_object_name,
            f'{self.design_molecule} and c. {self.design_chain_id} and n. CA',
        )
        cmd.hide('cartoon', self.ce_object_name)
        cmd.hide('surface', self.ce_object_name)

        i_out_of_range = []
        for i, pair in self.coevolved_pairs.items():
            atom1 = f'{self.design_molecule} and c. {self.design_chain_id} and i. {pair.i_1} and n. CA'
            atom2 = f'{self.design_molecule} and c. {self.design_chain_id} and i. {pair.j_1} and n. CA'
            pair.dist = cmd.get_distance(
                atom1=atom1,
                atom2=atom2,
            )

            pair.dist_cutoff = max_interact_dist
            cmd.bond(
                f'{self.ce_object_name} and c. {self.design_chain_id} and i. {pair.i_1} and n. CA',
                f'{self.ce_object_name} and c. {self.design_chain_id} and i. {pair.j_1} and n. CA',
            )
            cmd.set(
                'stick_radius',
                rescale_number(
                    pair.zscore,
                    min_value=min_gremlin_score,
                    max_value=max_gremlin_score,
                ),
                f'({self.ce_object_name}  and c. {self.design_chain_id} and resi {pair.i_1}+{pair.j_1} and n. CA)',
            )
            if pair.is_out_of_range:
                logging.info(
                    f'Resi {pair.i_1} is {pair.dist:.2f} Å away from {pair.j_1}, out of distance {pair.dist_cutoff} Å.'
                )
                i_out_of_range.append(i)
                self.mark_pair_state(pair=pair, state='out_of_range')
            else:
                self.mark_pair_state(pair=pair, state='available')

        cmd.show('sticks', self.ce_object_name)
        cmd.set('stick_use_shader', 0)
        cmd.set('stick_round_nub', 0)

        # remove pairs that distal
        for i in i_out_of_range:
            logging.info(
                f'Pair {self.coevolved_pairs[i].i_aa}-{self.coevolved_pairs[i].j_aa} will be removed:  out of range.'
            )
            self.coevolved_pairs.pop(i)

        if i_out_of_range:
            self.coevolved_pairs = self.reorder_dict(self.coevolved_pairs)

        return

    def mark_pair_state(
        self,
        pair: CoevolvedPair,
        state: CoevolvedPairState.state_type = 'available',
        recover: bool = False,
    ):
        if not self.ce_object_name:
            raise issues.UnexpectedWorkflowError(
                f'Cannot mark pair state because {self.ce_object_name=} is not set'
            )
        color = CoevolvedPairState().color(state)

        stick_selection = f'({self.ce_object_name}  and c. {self.design_chain_id} and i. {pair.i+1}+{pair.j+1} and n. CA)'

        cmd.set(
            'stick_color',
            color,
            stick_selection,
        )

        if state != 'in_design':
            cmd.set('stick_transparency', 0.7, stick_selection)
            return

        logging.warning(f'Marking pair {str(pair)} {state=}')
        cmd.set('stick_transparency', 0.1, stick_selection)
        cmd.orient(selection=f'byres ({stick_selection}) around 15', animate=1)

        # if it is in design,recover color according to pair dist.
        if not recover:
            return

        for i, p in self.coevolved_pairs.items():
            if p == pair:
                continue
            self.mark_pair_state(
                pair=p,
                state='out_of_range' if p.is_out_of_range else 'available',
            )

    @staticmethod
    def reorder_dict(ordered_dict: dict):
        logging.info('Renumbering anaysis results.')
        reordered_dict = {}
        for new_idx, data in enumerate(ordered_dict.values()):
            reordered_dict[new_idx] = data
        return reordered_dict

    def load_co_evolving_pairs(
        self,
        walk_to_next=True,
    ):
        ignore_wt = self.bus.get_value('ui.interact.interact_ignore_wt')

        lineEdit_current_pair = self.bus.ui.lineEdit_current_pair
        lineEdit_current_pair_score = self.bus.ui.lineEdit_current_pair_score

        if not self.design_chain_id or not self.design_molecule:
            logging.error(f'No available molecule or chain id.')
            return

        if walk_to_next:
            if self.picked_gremlin_pair_idx == -1:
                logging.info('Initialized.')
                self.picked_gremlin_pair_idx = 0
            elif self.picked_gremlin_pair_idx == len(self.coevolved_pairs) - 1:
                logging.info(
                    "Co-vary pairs are already reach the last one, returning to the first."
                )
                self.picked_gremlin_pair_idx = 0
            else:
                self.picked_gremlin_pair_idx += 1
        else:
            if self.picked_gremlin_pair_idx == -1:
                logging.info('Initialized.')
                self.picked_gremlin_pair_idx = len(self.coevolved_pairs) - 1
            elif self.picked_gremlin_pair_idx == 0:
                logging.info(
                    "Co-vary pairs are already reach the first one, returning to the last."
                )
                self.picked_gremlin_pair_idx = len(self.coevolved_pairs) - 1
            else:
                self.picked_gremlin_pair_idx -= 1

        set_widget_value(self.bus.ui.progressBar, self.picked_gremlin_pair_idx)

        pair = self.coevolved_pairs[self.picked_gremlin_pair_idx]

        # Clear the existing widgets from gridLayout_interact_pairs
        for i in reversed(
            range(self.bus.ui.gridLayout_interact_pairs.count())
        ):
            widget = self.bus.ui.gridLayout_interact_pairs.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        self.mark_pair_state(pair=pair, state='in_design', recover=True)

        button_matrix = QbuttonMatrix(pair)
        button_matrix.sequence = self.gremlin_tool.sequence

        button_matrix.init_ui()

        button_matrix.report_axes_signal.connect(
            lambda row, col: self.mutate_with_gridbuttons(
                row,
                col,
                button_matrix.matrix,
                button_matrix.min_value,
                button_matrix.max_value,
                pair,
                ignore_wt,
            )
        )

        self.bus.ui.gridLayout_interact_pairs.addWidget(button_matrix)

        set_widget_value(
            lineEdit_current_pair,
            f'{pair.i_aa.replace("_","")}-{pair.j_aa.replace("_","")}, {pair.dist:.1f} Å',
        )

        set_widget_value(lineEdit_current_pair_score, f'{pair.zscore:.3f}')

        if pair.is_out_of_range:
            logging.warning(
                f'Resi {pair.i+1} ({pair.i_aa}) is {pair.dist:.2f} Å away from {pair.j+1} {pair.j_aa}, out of distance {pair.dist_cutoff} Å '
            )
            set_widget_value(lineEdit_current_pair, 'Out of range.')

        # To disable the QbuttonMatrix:
        button_matrix.setEnabled(not pair.is_out_of_range)

    def coevoled_mutant_decision(self, decision_to_accept):
        logging.debug(
            f'{"Accepting" if decision_to_accept else "Rejecting"}  co-evolved mutant {self.picked_gremlin_mutant_id}'
        )

        if decision_to_accept:
            cmd.enable(self.picked_gremlin_mutant_id)

            self.mutant_tree_coevolved.add_mutant_to_branch(
                self.picked_gremlin_group_id,
                self.picked_gremlin_mutant_id,
                extract_mutant_from_pymol_object(
                    pymol_object=self.picked_gremlin_mutant_id,
                    sequences=self.designable_sequences,
                ),
            )
        else:
            cmd.disable(self.picked_gremlin_mutant_id)
            if (
                self.picked_gremlin_mutant_id
                not in self.mutant_tree_coevolved.all_mutant_ids
            ):
                logging.warning(
                    f'{self.picked_gremlin_mutant_id} has not been accepted yet. Skipped.'
                )
                return
            else:
                self.mutant_tree_coevolved.remove_mutant_from_branch(
                    self.picked_gremlin_group_id,
                    self.picked_gremlin_mutant_id,
                )

        save_mutant_choices(
            self.bus.get_value('ui.interact.input.to_mutant_txt'),
            self.mutant_tree_coevolved,
        )

    def activate_focused_interaction(self):
        if self.picked_gremlin_mutant_id == self.last_gremlin_mutant_id:
            return

        if self.picked_gremlin_mutant_id:
            cmd.enable(self.picked_gremlin_mutant_id)
            cmd.show(
                'sticks',
                f'{self.picked_gremlin_mutant_id} and (sidechain or n. CA) and not hydrogen',
            )
            cmd.show(
                'mesh',
                f'{self.picked_gremlin_mutant_id} and (sidechain or n. CA)',
            )
            cmd.hide('cartoon', f'{self.picked_gremlin_mutant_id}')
        if self.last_gremlin_mutant_id:
            cmd.disable(self.last_gremlin_mutant_id)
            cmd.hide(
                'mesh',
                f'{self.last_gremlin_mutant_id} and (sidechain or n. CA)',
            )
            cmd.hide(
                'sticks',
                f'{self.last_gremlin_mutant_id} and (sidechain or n. CA) and not hydrogen',
            )
            cmd.hide('cartoon', f'{self.picked_gremlin_mutant_id}')

        # close group object if deactivated
        if (
            self.last_gremlin_co_evoving_pair_group_id != ''
            and self.picked_gremlin_group_id
            != self.last_gremlin_co_evoving_pair_group_id
        ):
            cmd.disable(self.last_gremlin_co_evoving_pair_group_id)
            cmd.group(
                self.last_gremlin_co_evoving_pair_group_id, action='close'
            )

        # expand group object if activated
        if (
            self.picked_gremlin_group_id
            and self.last_gremlin_co_evoving_pair_group_id
            != self.picked_gremlin_group_id
        ):
            cmd.enable(self.picked_gremlin_group_id)
            cmd.group(self.picked_gremlin_group_id, action='open')

        cmd.center(self.picked_gremlin_mutant_id)

    def mutate_with_gridbuttons(
        self,
        col,
        row,
        matrix,
        min_score,
        max_score,
        pair: CoevolvedPair,
        ignore_wt=False,
    ):
        import matplotlib

        matplotlib.use('Agg')

        from REvoDesign.common.MutantVisualizer import MutantVisualizer

        lineEdit_current_pair_wt_score = (
            self.bus.ui.lineEdit_current_pair_wt_score
        )
        lineEdit_current_pair_mut_score = (
            self.bus.ui.lineEdit_current_pair_mut_score
        )

        external_scorer = self.bus.get_value('ui.interact.use_external_scorer')

        from REvoDesign.external_designer import EXTERNAL_DESIGNERS

        if external_scorer and external_scorer in EXTERNAL_DESIGNERS:
            magician = EXTERNAL_DESIGNERS[external_scorer]
            if (
                not self.gremlin_external_scorer  # non-scorer is set
                or magician.__name__  # scorer is switched to another
                != self.gremlin_external_scorer.__class__.__name__
            ):
                logging.info(
                    f'Pre-heating {external_scorer} ... This could take a while ...'
                )
                self.gremlin_external_scorer = magician(
                    molecule=self.design_molecule
                )
                run_worker_thread_with_progress(
                    worker_function=self.gremlin_external_scorer.initialize,
                    ignore_missing=bool('X' in self.design_sequence),
                    progress_bar=self.bus.ui.progressBar,
                )

        else:
            if self.gremlin_external_scorer:
                logging.info(
                    f'Cooling down {self.gremlin_external_scorer.__class__.__name__} ...'
                )
            self.gremlin_external_scorer = None

        visualizer = MutantVisualizer(
            molecule=self.design_molecule, chain_id=self.design_chain_id
        )
        visualizer.sequence = self.design_sequence
        alphabet = self.gremlin_tool.alphabet

        visualizer.mutate_runner = self.mutate_runner

        visualizer.group_name = '_vs_'.join(
            [
                wt.replace('_', '')
                for wt in (
                    pair.i_aa,
                    pair.j_aa,
                )
            ]
        )
        if self.picked_gremlin_group_id:
            self.last_gremlin_co_evoving_pair_group_id = (
                self.picked_gremlin_group_id
            )

        self.picked_gremlin_group_id = visualizer.group_name

        # aa from wt
        wt_A = pair.i_aa.split('_')[0]  # in column
        wt_B = pair.j_aa.split('_')[0]  # in row

        wt_score = (
            matrix[alphabet.index(wt_A)][alphabet.index(wt_B)]
            if not self.gremlin_external_scorer
            else self.gremlin_external_scorer.scorer(
                sequence=self.design_sequence.replace('X', '')
            )
        )

        # aa from clicked button, mutant
        mut_A = alphabet[col]
        mut_B = alphabet[row]

        _mutant = []

        if self.picked_gremlin_mutant_id:
            self.last_gremlin_mutant_id = self.picked_gremlin_mutant_id

        for mut, idx, wt in zip(
            [mut_A, mut_B], [pair.i + 1, pair.j + 1], [wt_A, wt_B]
        ):
            _ = f'{self.design_chain_id}{wt}{idx}{mut}'
            if wt == mut and ignore_wt:
                logging.debug(f'Ignore WT to WT mutagenese {_}')

            elif mut == '-':
                logging.info(f'Igore deletion {_}')
            else:
                logging.debug(f'Adding mutagenesis {_}')
                _mutant.append(_)

        if not _mutant:
            logging.info(
                'No mutagenesis will be performed since the picked pair is a wt-wt pair'
            )
            return

        mutant = '_'.join(_mutant)

        mutant_obj: Mutant = extract_mutants_from_mutant_id(
            mutant_string=mutant,
            sequences=self.designable_sequences,
        )

        mutant_obj.wt_sequences = self.designable_sequences

        mut_score = (
            matrix[col][row]
            if not self.gremlin_external_scorer
            else self.gremlin_external_scorer.scorer(
                sequence=mutant_obj.get_mutant_sequence_single_chain(
                    chain_id=self.design_chain_id, ignore_missing=True
                )
            )
        )
        mutant_obj.mutant_score = mut_score

        set_widget_value(lineEdit_current_pair_wt_score, f'{wt_score:.4f}')
        set_widget_value(lineEdit_current_pair_mut_score, f'{mut_score:.4f}')

        # update mutant id from Mutant object.
        mutant = mutant_obj.short_mutant_id

        if mutant in cmd.get_names(
            type='nongroup_objects',
            enabled_only=0,
        ):
            logging.info(
                f'Picked mutant: {mutant} already exists. Do nothing.'
            )
        else:
            logging.info(f'Picked mutant: {mutant} ')

            color = get_color(
                self.bus.get_value('ui.header_panel.cmap.default'),
                mut_score,
                min_score,
                max_score,
            )

            logging.info(f" Visualizing {mutant}: {color}")

            run_worker_thread_with_progress(
                worker_function=visualizer.create_mutagenesis_objects,
                mutant_obj=mutant_obj,
                color=color,
                progress_bar=self.bus.ui.progressBar,
            )
            cmd.hide('everything', 'hydrogens and polymer.protein')
            cmd.hide('cartoon', mutant)

        self.picked_gremlin_mutant_id = mutant
        self.activate_focused_interaction()

        mutant_tree = MutantTree(
            {visualizer.group_name: {mutant_obj.short_mutant_id: mutant_obj}}
        )

        self.to_broadcaster(mutant_tree)

    def to_broadcaster(self, mutant_tree: MutantTree):
        if (
            self.ws_server
            and self.ws_server.is_running
            and not mutant_tree.empty
        ):
            asyncio.run(
                self.ws_server.broadcast_object(
                    obj=mutant_tree,
                    data_type='MutantTree',
                )
            )
