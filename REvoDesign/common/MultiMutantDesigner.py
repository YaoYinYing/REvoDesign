import random
import os
from absl import logging
import itertools
from pymol import cmd, util

from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.common.Mutant import Mutant

from REvoDesign.tools.utils import (
    get_color,
    cmap_reverser,
    run_worker_thread_with_progress,
)


from REvoDesign.tools.pymol_utils import (
    is_distal_residue_pair,
)

from REvoDesign.tools.mutant_tools import extract_mutant_from_pymol_object

from REvoDesign.external_designer import EXTERNAL_DESIGNERS


class MultiMutantDesigner:
    def __init__(self, molecule, chain_id, sequence):
        self.molecule = molecule
        self.chain_id = chain_id
        self.sequence = sequence
        self.cmap = 'bwr_r'
        self.total_design_cases = 20

        self.all_design_multi_design_cases: list[list] = []
        self.all_design_multi_design_mutant_object: list[Mutant] = []
        self.in_design_multi_design_case: list[tuple] = []
        self.design_case_variant_objects: list[str] = []
        self.mutant_tree_multi_design_copy = None

        self.scorer = ''
        self.use_external_scorer = False
        self.external_scorer = None
        self.external_scorer_reversed_score = False

        self.color_by_scores = False
        self.minimal_distance = 10
        self.maximal_mutant_num = 10

        self.use_sidechain_angle = True
        self.bond_CA = True

        # Initialize mutant tree for design
        _mutant_tree = {
            group_id: {
                mutant_id: extract_mutant_from_pymol_object(
                    pymol_object=mutant_id, sequence=self.sequence
                )
                for mutant_id in cmd.get_object_list(f'({group_id})')
            }
            for group_id in cmd.get_names(type='group_objects', enabled_only=1)
            if not group_id.startswith('multi_design')
        }
        self.mutant_tree_multi_design = MutantTree(_mutant_tree)

        if self.mutant_tree_multi_design.empty:
            logging.error('MutantTree is empty!')
            return
        if len(self.mutant_tree_multi_design.all_mutant_branch_ids) < 2:
            logging.error('At least two groups of mutants should be included.')
            return

        self.design_case = cmd.get_unused_name('multi_design')

        logging.info(
            f'Mutant Tree for multi-design is initialized. {len(self.mutant_tree_multi_design.all_mutant_branch_ids)} groups with {len(self.mutant_tree_multi_design.all_mutant_ids)} mutants.'
        )

    def refresh_design_color(self):
        _total_num_design_cases = max(
            self.total_design_cases, len(self.design_case_variant_objects)
        )

        if not self.color_by_scores or not self.external_scorer:
            for i, item in enumerate(self.design_case_variant_objects):
                color = get_color(
                    cmap=cmap_reverser(
                        cmap=self.cmap,
                        reverse=self.external_scorer_reversed_score,
                    ),
                    data=i + 1,
                    min_value=0,
                    max_value=_total_num_design_cases,
                )
                cmd.set_color(f'color_{i}', color)
                cmd.color(
                    f'color_{i}',
                    f'{item}',
                )
                util.cnc(f'{item}', _self=cmd)
        else:
            for mut_obj in self.all_design_multi_design_mutant_object:
                if not mut_obj.get_mutant_score():
                    mut_obj.set_mutant_score(new_score=self.external_scorer.scorer(sequence=mut_obj.get_mutant_sequence())) 
            
            all_scores = [
                mut_obj.get_mutant_score()
                for mut_obj in self.all_design_multi_design_mutant_object
                if mut_obj.get_mutant_score()
            ]

            logging.debug('All design with score: \n')
            logging.debug('-' * 60)
            logging.debug(
                '\n\n'
                + '\n'.join(
                    [
                        _.get_mutant_id()
                        for _ in self.all_design_multi_design_mutant_object
                    ]
                )
                + '\n\n'
            )
            logging.debug('-' * 60)

            for (i_obj, obj), (j_des, des) in zip(
                enumerate(self.design_case_variant_objects),
                enumerate(self.all_design_multi_design_mutant_object),
            ):
                color = get_color(
                    cmap=cmap_reverser(
                        cmap=self.cmap,
                        reverse=self.external_scorer_reversed_score,
                    ),
                    data=des.get_mutant_score(),
                    min_value=min(all_scores),
                    max_value=max(all_scores),
                )

                cmd.set_color(f'color_{i_obj}', color)
                cmd.color(
                    f'color_{i_obj}',
                    f'{obj}',
                )
                util.cnc(f'{obj}', _self=cmd)

    def evaluate_design(self, design: list[Mutant]) -> Mutant:
        tmp_mutant_obj = Mutant(
            mutant_info=[
                _mut_info
                for _mut_obj in design
                for _mut_info in _mut_obj.mutant_info
            ],
            mutant_score=None,
        )

        tmp_mutant_obj.wt_sequence = self.sequence

        if not self.external_scorer:
            logging.warning(
                f'Abord design evaluation because no external scorer is defined.'
            )
            return tmp_mutant_obj

        tmp_mutant_obj.set_mutant_score(
            self.external_scorer.scorer(
                sequence=tmp_mutant_obj.get_mutant_sequence()
            )
        )
        return tmp_mutant_obj

    def initialize_scorer(self):
        # early return for non-scorer
        if self.scorer not in EXTERNAL_DESIGNERS:
            if self.external_scorer:
                logging.info(
                    f'Cooling down {self.external_scorer.__class__.__name__} ...'
                )
            self.external_scorer = None
            return

        magician = EXTERNAL_DESIGNERS[self.scorer]
        if (
            not self.external_scorer
            or magician.__name__ != self.external_scorer.__class__.__name__
        ):
            logging.info(
                f'Pre-heating {self.scorer} ... This could take a while...'
            )
            self.external_scorer = magician(molecule=self.molecule)
            run_worker_thread_with_progress(
                worker_function=self.external_scorer.initialize
            )

        return

    def start_new_design(self):
        if self.mutant_tree_multi_design.empty:
            logging.error('Mutant Tree for multi-design is empty!')
            return
        if self.in_design_multi_design_case:
            self.new_design()

        self.in_design_multi_design_case = []
        self.mutant_tree_multi_design_copy = (
            self.mutant_tree_multi_design.__deepcopy__()
        )
        self.design_case_variant = cmd.get_unused_name('multi_design_variant')
        cmd.create(
            self.design_case_variant,
            f'{self.molecule} and c. {self.chain_id} and polymer.protein and n. CA',
        )
        cmd.color('greencyan', self.design_case_variant)
        cmd.hide('everything', self.design_case_variant)
        cmd.show('sticks', self.design_case_variant)
        cmd.group(self.design_case, self.design_case_variant)
        logging.info(f'Starting design with {self.design_case_variant}')

    def _auto_pick_tryout(self, tryout=30):
        for i in range(tryout):
            try:
                branch, (mutant_id, mutant_obj) = self._select_random_mutant()
            except IndexError:
                return

            if not self._is_compatible_mutant(
                (mutant_id, mutant_obj),
                minimal_distance=self.minimal_distance,
                use_sidechain_angle=self.use_sidechain_angle,
            ):
                logging.warning(f'Skip {branch}: {mutant_id}.')
                # label this mutant deleted in this design.
                self.mutant_tree_multi_design_copy.remove_mutant_from_branch(
                    branch=branch, mutant=mutant_id
                )
                continue

            self.in_design_multi_design_case.append(
                (branch, mutant_id, mutant_obj)
            )
            self.mutant_tree_multi_design_copy.remove_mutant_from_branch(
                branch=branch, mutant=mutant_id
            )
            # a successful picking and return.
            return

    def pick_next_mutant(self):
        if not self.mutant_tree_multi_design:
            logging.error(f'Mutant Tree is not found.')
            return
        if self.mutant_tree_multi_design.empty:
            logging.error('Mutant Tree for multi-design is empty!')
            return

        if not self.mutant_tree_multi_design_copy:
            self.start_new_design()
            return

        if self.mutant_tree_multi_design_copy.empty:
            if self.in_design_multi_design_case:
                logging.warning(
                    'Temperal mutant tree for multi-design is empty after designing! This design is ended.'
                )
                self.new_design()
                return
            else:
                logging.error('Mutant Tree for multi-design is empty!')
                return

        len_in_design_multi_design_case = len(self.in_design_multi_design_case)
        self._auto_pick_tryout()
        if len_in_design_multi_design_case == len(
            self.in_design_multi_design_case
        ):
            # failed picking
            logging.warning(f'Failed auto picking. Please take anther try.')
            return

        (branch, mutant_id, mutant_obj) = self.in_design_multi_design_case[-1]

        resi_last_mutant = mutant_obj.get_mutant_info()[0]['position']
        cmd.set(
            'sphere_scale',
            0.4,
            f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_last_mutant} and n. CA',
        )
        cmd.show(
            'sphere',
            f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_last_mutant} and n. CA',
        )

        if self.bond_CA:
            # bond to the last previous design
            if len(self.in_design_multi_design_case) >= 2:
                second_mutant_to_the_last = self.in_design_multi_design_case[
                    -2
                ]
                resi_second_mutant_to_the_last = second_mutant_to_the_last[
                    2
                ].get_mutant_info()[-1]['position']

                cmd.bond(
                    atom1=f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_second_mutant_to_the_last} and n. CA',
                    atom2=f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_last_mutant} and n. CA',
                )

            # bond internal CAs in a multi-design mutant.
            current_mutant_info = mutant_obj.get_mutant_info()
            if len(current_mutant_info) > 1:
                positions_pairwise = [
                    x
                    for x in itertools.pairwise(
                        [_mut['position'] for _mut in current_mutant_info]
                    )
                ]
                logging.info(f'Pairwised position: {positions_pairwise}')

                for resi_a, resi_b in positions_pairwise:
                    cmd.bond(
                        atom1=f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_a} and n. CA',
                        atom2=f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_b} and n. CA',
                    )

        logging.info(f'{mutant_id} is added to {self.design_case_variant}')

        if len(self.in_design_multi_design_case) >= self.maximal_mutant_num:
            logging.info(
                f'Reaching {self.maximal_mutant_num} mutations. Stop current design.'
            )
            self.new_design()

    def undo_previous_mutant(self):
        if (
            not self.in_design_multi_design_case
            and not self.all_design_multi_design_cases
        ):
            logging.error("Nothing to undo.")
            return

        if (
            not self.in_design_multi_design_case
            and self.all_design_multi_design_cases
        ):
            # discard the last design mutant object
            self.all_design_multi_design_mutant_object.pop()
            self.in_design_multi_design_case = (
                self.all_design_multi_design_cases.pop()
            )
            self.design_case_variant = self.design_case_variant_objects.pop()
            cmd.color('greencyan', self.design_case_variant)
            self.refresh_design_color()

            logging.warning('Undoing the last design.')

        (
            undo_branch,
            undo_mutant_id,
            undo_mutant_obj,
        ) = self.in_design_multi_design_case.pop()

        # recover the whole mutant tree, as the deleted branch might be used in the future.
        self.mutant_tree_multi_design_copy = (
            self.mutant_tree_multi_design.__deepcopy__()
        )
        resi_undo_mutant = undo_mutant_obj.get_mutant_info()[0]['position']

        cmd.hide(
            'sphere',
            f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_undo_mutant} and n. CA',
        )

        if self.bond_CA:
            # unbond to the last previous design
            if len(self.in_design_multi_design_case) >= 1:
                last_mutant = self.in_design_multi_design_case[-1]
                resi_last_mutant = last_mutant[2].get_mutant_info()[-1][
                    'position'
                ]

                cmd.unbond(
                    atom1=f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_last_mutant} and n. CA',
                    atom2=f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_undo_mutant} and n. CA',
                )

            # bond internal CA in a multi-design mutant.
            current_mutant_info = undo_mutant_obj.get_mutant_info()
            if len(current_mutant_info) > 1:
                positions_pairwise = [
                    x
                    for x in itertools.pairwise(
                        [_mut['position'] for _mut in current_mutant_info]
                    )
                ]
                logging.info(f'Pairwised position: {positions_pairwise}')

                for resi_a, resi_b in positions_pairwise:
                    cmd.unbond(
                        atom1=f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_a} and n. CA',
                        atom2=f'{self.design_case_variant} and c. {self.chain_id} and i. {resi_b} and n. CA',
                    )

            logging.info(f'Undo: {undo_mutant_id} ')

        # remove the object if it is already empty
        if not self.in_design_multi_design_case:
            cmd.delete(self.design_case_variant)

    def new_design(self, continue_design=True):
        if not self.in_design_multi_design_case:
            logging.error("Design case is empty.")
            return
        logging.info(f'Stopping current design and start a new one.')
        self.design_case_variant_objects.append(self.design_case_variant)
        self.all_design_multi_design_cases.append(
            self.in_design_multi_design_case
        )

        # initialize scorer
        if self.color_by_scores and self.scorer and self.use_external_scorer:
            self.initialize_scorer()

        # evaluate mutant design after design case is closed.
        self.all_design_multi_design_mutant_object.append(
            self.evaluate_design(
                design=[
                    mut_obj
                    for _, __, mut_obj in self.in_design_multi_design_case
                ]
            )
        )

        self.in_design_multi_design_case = []
        self.refresh_design_color()
        if continue_design:
            self.start_new_design()

    def export_designed_variant(self, save_mutant_table=''):
        if not self.all_design_multi_design_cases:
            logging.error("No designed variants to export.")
            return

        self.save_mutant_table = (
            save_mutant_table if save_mutant_table else './multidesign.mut.txt'
        )

        logging.info(f'Exporting designs to {self.save_mutant_table}')
        mutant_list = []
        for decision in self.all_design_multi_design_cases:
            mutant_decision_list = []
            for branch, mut_id, mut_obj in decision:
                mutant_decision_list.extend(
                    [
                        f'{_mut["chain_id"]}{_mut["wt_res"]}{_mut["position"]}{_mut["mut_res"]}'
                        for _mut in mut_obj.get_mutant_info()
                    ]
                )
            mutant_list.append('_'.join(mutant_decision_list))

        os.makedirs(os.path.dirname(self.save_mutant_table), exist_ok=True)

        with open(self.save_mutant_table, 'w') as f:
            f.write('\n'.join(mutant_list))

    def _select_random_mutant(self):
        branch = random.choice(
            self.mutant_tree_multi_design_copy.all_mutant_branch_ids
        )
        mut = random.choice(
            list(
                self.mutant_tree_multi_design_copy.get_a_branch(branch).items()
            )
        )
        return branch, mut

    def _is_compatible_mutant(
        self, mutant, minimal_distance=20, use_sidechain_angle=True
    ):
        if not self.in_design_multi_design_case:
            # early return for initial design.
            return True

        mutant_id, mutant_obj = mutant
        for _picked_residue in mutant_obj.get_mutant_info():
            for (
                _,
                _existed_mutant_id,
                _existed_mutant_obj,
            ) in self.in_design_multi_design_case:
                _existed_residues = [
                    _mut for _mut in _existed_mutant_obj.get_mutant_info()
                ]

                if any(
                    [
                        _picked_residue["position"]
                        == _existed_residue["position"]
                        for _existed_residue in _existed_residues
                    ]
                ):
                    logging.warning(
                        f'Mutant has residue id existed in the previous design: \n'
                        f'{mutant_id}'
                    )
                    return False

                if any(
                    [
                        not is_distal_residue_pair(
                            molecule=self.molecule,
                            chain_id=self.chain_id,
                            resi_1=_picked_residue["position"],
                            resi_2=_existed_residue["position"],
                            minimal_distance=minimal_distance,
                            use_sidechain_angle=use_sidechain_angle,
                        )
                        for _existed_residue in _existed_residues
                    ]
                ):
                    logging.warning(
                        f'Mutant has residue id not distal with one position in the previous design: \n'
                        f'{mutant_id}'
                    )
                    return False
        return True
