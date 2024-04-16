import asyncio
from functools import partial
import os
import traceback
import itertools

from immutabledict import immutabledict
from REvoDesign import ConfigBus
from REvoDesign.basic import IterableLoop
from REvoDesign.clients.QtSocketConnector import REvoDesignWebSocketServer
from REvoDesign.common.Mutant import Mutant
from REvoDesign.common.MutantVisualizer import MutantVisualizer
from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.phylogenetics.GREMLIN_Tools import CoevolvedPair, GREMLIN_Tools
from REvoDesign.citations import CitationManager
from REvoDesign.sidechain_solver import SidechainSolver
from REvoDesign.tools.customized_widgets import QbuttonMatrix, set_widget_value
from REvoDesign.tools.mutant_tools import save_mutant_choices

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
from typing import Dict, List, Literal, Tuple, Union
from dataclasses import dataclass
from REvoDesign import root_logger
import warnings
from REvoDesign import issues

logging = root_logger.getChild(__name__)


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
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()
        self.PWD: str = self.bus.get_value('work_dir', str)

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
            self.design.designable_sequences = self.designable_sequences
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

            self.design.mutate_runner = (
                SidechainSolver().refresh().mutate_runner
            )

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

        finally:
            CitationManager().output()


class VisualizingWorker:
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()

        self.PWD: str = self.bus.get_value('work_dir', str)

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
            self.visualizer.designable_sequences = self.designable_sequences
            self.visualizer.mutfile = input_mut_table_csv
            self.visualizer.input_session = make_temperal_input_pdb(
                molecule=self.design_molecule,
                wd=os.path.join(os.path.dirname(output_pse), 'temperal_pdb'),
                reload=False,
            )
            self.visualizer.nproc = nproc
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
        finally:
            CitationManager().output()


class GREMLIN_Analyser:
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()

        self.PWD: str = self.bus.get_value('work_dir', str)
        self.ws_server: REvoDesignWebSocketServer = REvoDesignWebSocketServer()

        self.design_molecule: str = self.bus.get_value(
            'ui.header_panel.input.molecule'
        )
        self.design_chain_id: str = self.bus.get_value(
            'ui.header_panel.input.chain_id'
        )
        self.designable_sequences: dict = self.bus.get_value(
            'designable_sequences', dict
        )
        self.design_sequence: str = self.designable_sequences.get(
            self.design_chain_id
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

    def load_gremlin_mrf(self):
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

        run_worker_thread_with_progress(
            worker_function=self.gremlin_tool.get_to_coevolving_pairs,
            progress_bar=self.bus.ui.progressBar,
        )

        plot_mtx_fp = run_worker_thread_with_progress(
            worker_function=self.gremlin_tool.plot_mtx,
            progress_bar=self.bus.ui.progressBar,
        )

        try:
            set_widget_value(gridLayout_interact_pairs, plot_mtx_fp)
        except AttributeError:
            logging.info(
                f'Work Space is cleaned. Click once again to reinitialize. '
            )

    def _get_dist(
        self,
        chain_1: str,
        chain_2: str,
        i_1: Union[int, str],
        j_1: Union[int, str],
    ) -> float:
        atom1 = (
            f'{self.design_molecule} and c. {chain_1} and i. {i_1} and n. CA'
        )
        atom2 = (
            f'{self.design_molecule} and c. {chain_2} and i. {j_1} and n. CA'
        )
        try:
            dist = cmd.get_distance(atom1=atom1, atom2=atom2)
            return dist
        except CmdException:
            warnings.warn(
                issues.BadDataWarning(
                    f'No such atom pair {atom1=} and {atom2=}'
                )
            )
            return -1

    # record chain binding: distances and maximum distance to be accepted
    def bind_chains(
        self, coevolved_pairs: tuple[CoevolvedPair]
    ) -> tuple[CoevolvedPair]:
        self.max_interact_dist: float = self.bus.get_value(
            'ui.interact.max_interact_dist', float
        )

        # fix chain id if chain binding is enabled.
        # monomer pairs
        if not (self.chain_binding_enabled and self.chains_to_bind):
            logging.info('Intrachain connections.')
            for pair in coevolved_pairs:
                pair.dist_cutoff = self.max_interact_dist

                dist = self._get_dist(
                    chain_1=self.design_chain_id,
                    chain_2=self.design_chain_id,
                    i_1=pair.i_1,
                    j_1=pair.j_1,
                )

                # invalid distance, raised from residue missing in PDB structure.
                if dist < 0:
                    continue
                pair.homochains_dist.update(
                    {f'{self.design_chain_id}{self.design_chain_id}': dist}
                )

            return coevolved_pairs

        invalid_coevolved_chain_pair: int = 0

        # homomer pairs
        for pair in coevolved_pairs:
            pair.dist_cutoff = self.max_interact_dist
            for c1, c2 in itertools.product(self.chains_to_bind, repeat=2):
                dist = self._get_dist(
                    chain_1=c1, chain_2=c2, i_1=pair.i_1, j_1=pair.j_1
                )
                if dist < 0 or dist > self.max_interact_dist:
                    invalid_coevolved_chain_pair += 1
                    continue
                pair.homochains_dist.update({f'{c1}{c2}': dist})

        if invalid_coevolved_chain_pair:
            warnings.warn(
                issues.BadDataWarning(
                    f'Discarded: {invalid_coevolved_chain_pair=}'
                )
            )

        return coevolved_pairs

    def run_gremlin_tool(self):
        self.chain_binding_enabled: bool = self.bus.get_value(
            'ui.interact.chain_binding.enabled', bool
        )
        self.chains_to_bind: tuple = tuple(
            set(
                self.bus.get_value(
                    'ui.interact.chain_binding.chains_to_bind', str
                )
            )
        )
        # name this subdir for every analysis
        chains = "".join(self.chains_to_bind)
        if self.chain_binding_enabled and self.chains_to_bind:
            subdir = (
                f'{self.design_molecule}_{self.design_chain_id}.homo.{chains}'
            )
        else:
            subdir = f'{self.design_molecule}_{self.design_chain_id}.mono'

        if any_posision_has_been_selected():
            logging.info(f'One vs All mode.')
            self.gremlin_tool_a2a_mode = False
            resi = int(cmd.get_model('sele and n. CA').atom[0].resi)
            logging.info(f'{resi} is selected.')

            self.gremlin_workpath = os.path.join(
                self.PWD,
                'gremlin_co_evolved_pairs',
                f'resi_{resi}',
                subdir,
            )
            os.makedirs(self.gremlin_workpath, exist_ok=True)
            self.gremlin_tool.pwd = self.gremlin_workpath

            coevolved_pairs: tuple[
                CoevolvedPair
            ] = run_worker_thread_with_progress(
                worker_function=self.gremlin_tool.plot_w_o2a,
                resi=resi - 1,
                progress_bar=self.bus.ui.progressBar,
            )

            if not coevolved_pairs:
                warnings.warn(
                    issues.NoResultsWarning(
                        f'No Available co-evolutionary signal against {resi}'
                    )
                )
                # early return if no data.
                return

            logging.info(f'Found {len(coevolved_pairs)} pairs against {resi}.')

        else:
            logging.info(
                f'No selection `sele` is picked, use All vs All mode.'
            )
            self.gremlin_tool_a2a_mode = True

            self.gremlin_workpath = os.path.join(
                self.PWD,
                'gremlin_co_evolved_pairs',
                'all_vs_all',
                subdir,
            )
            os.makedirs(self.gremlin_workpath, exist_ok=True)
            self.gremlin_tool.pwd = self.gremlin_workpath

            coevolved_pairs: tuple[
                CoevolvedPair
            ] = run_worker_thread_with_progress(
                worker_function=self.gremlin_tool.plot_w_a2a,
                progress_bar=self.bus.ui.progressBar,
            )

            if not coevolved_pairs:
                warnings.warn(
                    issues.NoResultsWarning(
                        f'No Available co-evolutionary signal in global'
                    )
                )
                # early return if no data.
                return

            logging.info(f'Found {len(coevolved_pairs)} pairs in global')

        logging.debug(coevolved_pairs)

        logging.info('Binding Chains ...')
        coevolved_pairs: tuple[
            CoevolvedPair
        ] = run_worker_thread_with_progress(
            worker_function=self.bind_chains,
            coevolved_pairs=coevolved_pairs,
            progress_bar=self.bus.ui.progressBar,
        )

        coevolved_pairs: tuple[CoevolvedPair] = self.coevolved_pairs_filter(
            coevolved_pairs
        )
        self.coevolved_pairs = IterableLoop(iterable=coevolved_pairs)
        if self.coevolved_pairs.empty:
            warnings.warn(
                issues.NoResultsWarning('No coevolved_pairs passes filter.')
            )
            return

        logging.info('Visualizing as bonds ...')
        run_worker_thread_with_progress(
            worker_function=self.plot_coevolved_pair_in_pymol,
            progress_bar=self.bus.ui.progressBar,
        )

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
            self.bus.ui.progressBar, [0, len(self.coevolved_pairs.iterable)]
        )

        self.picked_gremlin_group_id = ''

        self.load_co_evolving_pairs()

        self.gremlin_tool.cite()

    @staticmethod
    def coevolved_pairs_filter(
        coevolved_pairs: tuple[CoevolvedPair],
    ) -> tuple[CoevolvedPair]:
        _: list[CoevolvedPair] = []
        for p in coevolved_pairs:
            if p.empty:
                continue
            if not [x for x in p.all_res_pairs_selections.values()]:
                continue
            _.append(p)
        return tuple(_)

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

        _tmp_obj = f'_tmp_object_for_{self.ce_object_group_valid}'

        cmd.create(_tmp_obj, f'{self.design_molecule} and n. CA')
        cmd.hide('cartoon', _tmp_obj)
        cmd.hide('surface', _tmp_obj)

        i_out_of_range: List[CoevolvedPair] = []
        discarded: List[CoevolvedPair] = []
        for pair in self.coevolved_pairs.iterable:
            try:
                sele_name = repr(pair)
                logging.debug(f'{sele_name=}')
                pair.selection_string = cmd.get_unused_name(f"{sele_name}_")
                _sele = " or ".join(
                    [x for x in pair.all_res_pairs_selections.values()]
                )
                cmd.create(
                    pair.selection_string,
                    sele := f'{_tmp_obj} and ({_sele}) and n. CA',
                )
            except CmdException:
                warnings.warn(
                    issues.BadDataWarning(
                        f'This atom selection is invalid: {sele}'
                    )
                )
                discarded.append(pair)
                continue

            cmd.hide('cartoon', pair.selection_string)
            cmd.hide('surface', pair.selection_string)
            cmd.show('sticks', pair.selection_string)

            zscore = rescale_number(
                pair.zscore,
                min_value=min_gremlin_score,
                max_value=max_gremlin_score,
            )

            cmd.set(
                'stick_radius',
                zscore,
                pair.selection_string,
            )

            if pair.all_out_of_range:
                i_out_of_range.append(pair)
                cmd.group(self.ce_object_group_invalid, pair.selection_string)
            else:
                cmd.group(self.ce_object_group_valid, pair.selection_string)

            # bond w/o colors
            # out-of-range residue pair in valid pair will be not considered.
            for cc, res_pair in pair.all_res_pairs.items():
                if pair.is_out_of_range(cc):
                    logging.info(
                        f'Resi {pair.i_1}({cc[0]}) is {pair.dist(chain_pair=cc):.2f} Å away from {pair.j_1}({cc[1]}), out of distance {pair.dist_cutoff} Å.'
                    )

                    continue

                cmd.bond(
                    f'{pair.selection_string} and {res_pair[0]} and n. CA',
                    f'{pair.selection_string} and {res_pair[1]} and n. CA',
                )

        cmd.delete(_tmp_obj)
        cmd.group(self.ce_object_group_valid, action='close')
        cmd.group(self.ce_object_group_invalid, action='close')

        self.mark_pair_state(
            pairs=tuple([i for i in i_out_of_range]),
            state='out_of_range',
        )
        self.mark_pair_state(
            pairs=tuple(
                [
                    p
                    for p in self.coevolved_pairs.iterable
                    if not (p in i_out_of_range or p in discarded)
                ]
            ),
            state='available',
        )

        cmd.set('stick_use_shader', 0)
        cmd.set('stick_round_nub', 0)

        # remove pairs that distal

        for p in i_out_of_range:
            logging.info(
                f'Pair {p.i_aa}-{p.j_aa} will be removed: out of range.'
            )

        self.coevolved_pairs = IterableLoop(
            iterable=tuple(
                [
                    p
                    for p in self.coevolved_pairs.iterable
                    if not (p in i_out_of_range or p in discarded)
                ]
            )
        )

        logging.warning(f'Out of range: {len(i_out_of_range)}')
        logging.warning(f'Discarded pairs: {len(discarded)}')
        logging.warning(
            f'Filtered pairs: {len(self.coevolved_pairs.iterable)}'
        )

        CitationManager().output()
        return

    def mark_pair_state(
        self,
        pairs: Union[CoevolvedPair, List[CoevolvedPair], Tuple[CoevolvedPair]],
        state: CoevolvedPairState.state_type = 'available',
    ):
        if not self.ce_object_group_valid:
            raise issues.UnexpectedWorkflowError(
                f'Cannot mark pair state because {self.ce_object_group_valid=} is not set'
            )
        color = CoevolvedPairState().color(state)

        if isinstance(pairs, CoevolvedPair):
            pairs = (pairs,)

        _sele = ' or '.join([p.selection_string for p in pairs])

        logging.debug(f'{_sele=}')

        for p in pairs:
            cmd.set(
                'stick_color',
                color,
                p.selection_string,
            )

        if state != 'in_design':
            for p in pairs:
                cmd.set('stick_transparency', 0.7, p.selection_string)

            logging.debug(
                f'Marking pair as {state=}: {[str(pair) for pair in pairs]} ({_sele=})'
            )
            return

        logging.warning(
            f'Marking pair as {state=}: {[str(pair) for pair in pairs]} ({_sele=})'
        )
        for p in pairs:
            cmd.set('stick_transparency', 0.1, p.selection_string)
        cmd.orient(selection=f'byres ({_sele}) around 15', animate=1)

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

        # before walking the index, set this pair back
        self.mark_pair_state(
            pairs=(p := self.coevolved_pairs.current_item),
            state='available' if not p.all_out_of_range else 'out_of_range',
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
        self.mark_pair_state(pairs=pair, state='in_design')

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
            f'{pair.i_aa.replace("_","")}-{pair.j_aa.replace("_","")}, {pair.min_dist:.1f} Å',
        )

        set_widget_value(lineEdit_current_pair_score, f'{pair.zscore:.3f}')

        if pair.all_out_of_range:
            logging.warning(
                f'Resi {pair.i_1} ({pair.i_aa}) is {pair.min_dist:.2f} Å away from {pair.j_1} {pair.j_aa}, out of distance {pair.dist_cutoff} Å '
            )
            set_widget_value(lineEdit_current_pair, 'Out of range.')

        # To disable the QbuttonMatrix:
        button_matrix.setEnabled(not pair.all_out_of_range)

    def coevoled_mutant_decision(self, accept: bool):
        if self.explored_mutant_tree.empty or not self.picked_gremlin_mutant:
            raise issues.UnexpectedWorkflowError('Nothing to decide.')
        logging.debug(
            f'{"Accepting" if accept else "Rejecting"}  co-evolved mutant {(picked_gremlin_mutant_id:=self.picked_gremlin_mutant.short_mutant_id)}'
        )

        if accept:
            cmd.enable(picked_gremlin_mutant_id)

            self.mutant_tree_coevolved.add_mutant_to_branch(
                self.picked_gremlin_group_id,
                picked_gremlin_mutant_id,
                self.picked_gremlin_mutant,
            )
        else:
            cmd.disable(picked_gremlin_mutant_id)
            if (
                picked_gremlin_mutant_id
                not in self.mutant_tree_coevolved.all_mutant_ids
            ):
                logging.warning(
                    f'{picked_gremlin_mutant_id} has not been accepted yet. Skipped.'
                )
                return
            else:
                self.mutant_tree_coevolved.remove_mutant_from_branch(
                    self.picked_gremlin_group_id,
                    picked_gremlin_mutant_id,
                )

        save_mutant_choices(
            self.bus.get_value('ui.interact.input.to_mutant_txt'),
            self.mutant_tree_coevolved,
        )

    @staticmethod
    def show_mutant(mutant_id: str, group_id: str = None):
        cmd.enable(mutant_id)
        cmd.show(
            'sticks',
            f'{mutant_id} and (sidechain or n. CA) and not hydrogen',
        )
        cmd.show(
            'mesh',
            f'{mutant_id} and (sidechain or n. CA)',
        )
        cmd.hide('cartoon', f'{mutant_id}')
        cmd.center(mutant_id)

        # expand group object if activated
        if group_id:
            cmd.enable(group_id)
            cmd.group(group_id, action='open')

    def hide_all_mutants(self):
        for group_id in self.explored_mutant_tree.all_mutant_branch_ids:
            cmd.disable(group_id)
            cmd.group(group_id, action='close')

    def activate_focused_interaction(self):
        if not self.picked_gremlin_mutant or self.picked_gremlin_mutant.empty:
            raise issues.UnexpectedWorkflowError(
                'Co-evolved pairs are not loaded. '
            )

        if (
            self.picked_gremlin_mutant
            in self.explored_mutant_tree.all_mutant_objects
        ):
            logging.warning(
                f'Igore repetative picking: {self.picked_gremlin_mutant.short_mutant_id} ({self.picked_gremlin_mutant.full_mutant_id})'
            )
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
            f'{self.picked_gremlin_mutant.wt_score:.4f}',
        )
        set_widget_value(
            lineEdit_current_pair_mut_score,
            f'{self.picked_gremlin_mutant.mutant_score:.4f}',
        )

        return

    def refresh_scorer(self):
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
                    chain=','.join(
                        self.chains_to_bind
                        if self.chain_binding_enabled
                        else self.design_chain_id
                    ),
                    homooligomeric=self.chain_binding_enabled
                    and self.chains_to_bind,
                    progress_bar=self.bus.ui.progressBar,
                )

        else:
            if self.gremlin_external_scorer:
                logging.info(
                    f'Cooling down {self.gremlin_external_scorer.__class__.__name__} ...'
                )
            self.gremlin_external_scorer = None

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

        self.refresh_scorer()

        alphabet = self.gremlin_tool.alphabet

        self.picked_gremlin_group_id = '_vs_'.join(
            [
                wt.replace('_', '')
                for wt in (
                    pair.i_aa,
                    pair.j_aa,
                )
            ]
        )

        # aa from wt
        wt_i = pair.wt('i')  # in column
        wt_j = pair.wt('j')  # in row

        # aa from clicked button, mutant
        mut_i = alphabet[col]
        mut_j = alphabet[row]

        # construct this Mutant obj from scratch.
        _mutant: List[Dict[str, Union[str, int]]] = []

        for chain_id_pair in pair.homochains:
            for chain_id, mut, idx, wt in zip(
                chain_id_pair,
                [mut_i, mut_j],
                [pair.i_1, pair.j_1],
                [wt_i, wt_j],
            ):
                expected_mutant = {
                    'chain_id': chain_id,
                    'position': int(idx),
                    'wt_res': wt,
                    'mut_res': mut,
                }
                if expected_mutant in _mutant:
                    logging.warning(
                        f'Ignore existed mutagenese {expected_mutant}'
                    )
                    continue
                if wt == mut and ignore_wt:
                    logging.debug(
                        f'Ignore WT to WT mutagenese {expected_mutant}'
                    )
                    continue

                if mut == '-':
                    logging.warning(f'Igore deletion {expected_mutant}')
                    continue

                logging.debug(f'Adding mutagenesis {expected_mutant}')
                _mutant.append(expected_mutant)
        logging.debug(_mutant)

        # early return if nothing is created.
        if not _mutant:
            logging.info(
                'No mutagenesis will be performed since the picked pair is a wt-wt pair'
            )
            return

        mutant_obj: Mutant = Mutant(mutant_info=_mutant)
        mutant_obj.wt_sequences = self.designable_sequences

        # call scorer to evaluate wt and mutant
        if not self.gremlin_external_scorer:
            wt_score = matrix[alphabet.index(wt_i)][alphabet.index(wt_j)]
            mut_score = matrix[col][row]
        else:
            wt_score = run_worker_thread_with_progress(
                worker_function=self.gremlin_external_scorer.scorer,
                sequence=self.design_sequence.replace('X', ''),
                progress_bar=self.bus.ui.progressBar,
            )
            mut_score = run_worker_thread_with_progress(
                worker_function=self.gremlin_external_scorer.scorer,
                sequence=mutant_obj.get_mutant_sequence_single_chain(
                    chain_id=self.design_chain_id,
                    ignore_missing=True),
                    progress_bar=self.bus.ui.progressBar,
                )


        mutant_obj.wt_score = wt_score
        mutant_obj.mutant_score = mut_score

        self.picked_gremlin_mutant = mutant_obj

        # if mutant obj exists, activate it.
        if mutant_obj in self.explored_mutant_tree.all_mutant_objects:
            logging.info(
                f'Picked mutant: {mutant_obj.short_mutant_id} ({mutant_obj.full_mutant_id}) already exists. Do nothing.'
            )
            self.activate_focused_interaction()
            return

        # otherwise, call MutantVisualizer to display it.
        logging.info(
            f'Picked mutant:{(mutant := mutant_obj.short_mutant_id)} {(full_mutant_id:=mutant_obj.full_mutant_id)} '
        )

        color = get_color(
            self.bus.get_value('ui.header_panel.cmap.default'),
            mut_score,
            min_score,
            max_score,
        )

        logging.info(f" Visualizing {mutant} ({full_mutant_id}): {color}")

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
        cmd.hide('everything', 'hydrogens and polymer.protein')
        cmd.hide('cartoon', mutant)

        # create a new record.
        self.explored_mutant_tree.add_mutant_to_branch(
            branch=visualizer.group_name,
            mutant=mutant,
            mutant_obj=mutant_obj,
        )

        # create a small mutant tree and send to broadcaster.
        mutant_tree = MutantTree(
            {self.picked_gremlin_group_id: {mutant: mutant_obj}}
        )
        self.to_broadcaster(mutant_tree)

    def to_broadcaster(self, mutant_tree: MutantTree):
        if self.ws_server and not mutant_tree.empty:
            asyncio.run(
                self.ws_server.broadcast_object(
                    obj=mutant_tree,
                    data_type='MutantTree',
                )
            )
