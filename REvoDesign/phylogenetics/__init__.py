import os
import traceback
from REvoDesign.application.ui_driver import ConfigBus
from REvoDesign.sidechain_solver import (
    SidechainSolver,
)

from REvoDesign.tools.pymol_utils import (
    is_a_REvoDesign_session,
    make_temperal_input_pdb,
)
from REvoDesign.tools.utils import (
    cmap_reverser,
    dirname_does_exist,
)
from dataclasses import dataclass
from pymol import cmd


from REvoDesign.tools.logger import logging as logger

logging = logger.getChild(__name__)


@dataclass
class MutateWorkerConfig:
    bus: ConfigBus
    design_molecule: str
    design_chain_id: str
    design_sequence: str
    designable_sequences: dict[str, str]
    PWD: str
    sidechain_solver: SidechainSolver


class MutateWorker(MutateWorkerConfig):
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
                'ui.mutate.reverse_score'
            )
            output_pse = self.bus.get_value('ui.mutate.input.to_pse')
            nproc = self.bus.get_value('ui.header_panel.nproc', int)

            cmap = cmap_reverser(
                cmap=self.bus.get_value('ui.header_panel.cmap.default'),
                reverse=reversed_mutant_effect,
            )

            progressbar = self.bus.ui.progressBar

            if is_a_REvoDesign_session():
                logging.warning(
                    'Loading mutants into a REvoDesign session may trigger unexpected segmentation fault.\n'
                    'In order to keep the session\'s feature, you should always create seperate sessions according to '
                    'your dataset and merge them manually in PyMOL window.'
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

            self.design.mutate_runner = self.sidechain_solver.mutate_runner

            self.design.preffered_substitutions = preffered
            self.design.reject_aa = rejected
            self.design.nproc = nproc
            self.design.cmap = cmap
            self.design.create_full_pdb = False

            from REvoDesign.external_designer import EXTERNAL_DESIGNERS

            if design_profile_format in EXTERNAL_DESIGNERS.keys():
                self.design.design_protein_using_external_designer(
                    custom_indices_fp=custom_indices_fp,
                    progress_bar=progressbar,
                )
            else:
                (
                    mutation_json_fp,
                    mutation_png_fp,
                ) = self.design.setup_profile_design(
                    custom_indices_fp=custom_indices_fp,
                    cutoff=cutoff,
                )

                self.design.load_mutants_to_pymol_session(
                    mutant_json=mutation_json_fp,
                    progress_bar=progressbar,
                )

            assert self.design.output_pse and dirname_does_exist(
                self.design.output_pse
            ), f'No output PyMOL session is created.'

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


class VisualizingWorker(MutateWorkerConfig):
    def visualize_mutants(self):
        input_mut_table_csv = self.bus.get_value(
            'ui.visualize.input.from_mutant_txt'
        )

        output_pse = self.bus.get_value('ui.visualize.input.to_pse')
        best_leaf = self.bus.get_value('ui.visualize.input.best_leaf')
        totalscore = self.bus.get_value('ui.visualize.input.totalscore')
        nproc = self.bus.get_value('ui.header_panel.nproc', int)
        group_name = self.bus.get_value('ui.visualize.input.group_name',str)

        use_global_scores = self.bus.get_value(
            'ui.visualize.global_score_policy'
        )

        try:
            reversed_mutant_effect = self.bus.get_value(
                'ui.visualize.reverse_score'
            )
            cmap = cmap_reverser(
                cmap=self.bus.get_value('ui.header_panel.cmap.default'),
                reverse=reversed_mutant_effect,
            )

            design_profile = self.bus.get_value('ui.visualize.input.profile')
            design_profile_format = self.bus.get_value(
                'ui.visualize.input.profile_type'
            )

            progressBar_visualize_mutants = self.bus.ui.progressBar

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

            # logging.warning(f'{self.visualizer.profile_scoring_df}')

            if best_leaf:
                self.visualizer.key_col = best_leaf
            if totalscore:
                self.visualizer.score_col = totalscore

            self.visualizer.save_session = output_pse
            self.visualizer.full = False
            self.visualizer.group_name = group_name
            self.visualizer.cmap = cmap

            self.visualizer.mutate_runner = self.sidechain_solver.mutate_runner

            self.visualizer.run_with_progressbar(
                progress_bar=progressBar_visualize_mutants
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

