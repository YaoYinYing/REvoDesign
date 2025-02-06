'''
Running Randomized Multi-Design

'''
import itertools
import os
import random
import warnings

try:
    from itertools import pairwise # type: ignore
except ImportError:

    def pairwise(iterable):
        """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
        a, b = itertools.tee(iterable)
        next(b, None)
        return zip(a, b)


from pymol import cmd, util
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign import ConfigBus, issues, ROOT_LOGGER
from REvoDesign.common import Mutant, MutantTree
from REvoDesign.magician import Magician
from REvoDesign.tools.mutant_tools import existed_mutant_tree
from REvoDesign.tools.pymol_utils import is_distal_residue_pair
from REvoDesign.tools.utils import cmap_reverser, get_color

logging = ROOT_LOGGER.getChild(__name__)


class MultiMutantDesigner:
    def __init__(self):
        """
        Initialize MultiMutantDesigner.

        Args:
        - molecule: The molecule identifier.
        - chain_id: The chain identifier.
        - sequence: The sequence of the protein.

        This method initializes the MultiMutantDesigner with the given parameters,
        sets up necessary attributes, and initializes the mutant tree for design.
        """
        # get the bus
        self.bus = ConfigBus()
        self.refresh_options()
        self.get_input_and_initialize()

    def refresh_options(self):
        # bootstrap options
        self.molecule = str(
            self.bus.get_value("ui.header_panel.input.molecule")
        )
        self.chain_id = str(
            self.bus.get_value("ui.header_panel.input.chain_id")
        )
        self.designable_sequences = RosettaPyProteinSequence.from_dict(
            dict(self.bus.get_value("designable_sequences"))
        )
        self.sequence: str = self.designable_sequences.get_sequence_by_chain(
            self.chain_id
        )

        self.cmap = self.bus.get_value("ui.header_panel.cmap.default")
        self.external_scorer_reversed_score: bool = bool(
            self.bus.get_value("ui.header_panel.cmap.reverse_score")
        )
        self.color_style = cmap_reverser(
            cmap=self.cmap, reverse=self.external_scorer_reversed_score
        )

        self.total_design_cases = self.bus.get_value(
            "ui.visualize.multi_design.num_variant_max"
        )

        self.use_external_scorer = self.bus.get_value(
            "ui.visualize.multi_design.use_external_scorer"
        )

        self.color_by_scores = self.bus.get_value(
            "ui.visualize.multi_design.color_by_scores"
        )
        self.minimal_distance = self.bus.get_value(
            "ui.visualize.multi_design.spatial_dist"
        )
        self.maximal_mutant_num = self.bus.get_value(
            "ui.visualize.multi_design.num_mut_max"
        )

        self.use_sidechain_angle = self.bus.get_value(
            "ui.visualize.multi_design.use_sidechain_orientation"
        )
        self.bond_CA = self.bus.get_value(
            "ui.visualize.multi_design.use_bond_CA"
        )

        self.save_mutant_table = self.bus.get_value(
            "ui.visualize.input.multi_design.to_mutant_txt"
        )
        self.magician = Magician().setup(
            name_cfg_term="ui.visualize.input.profile_type",
            ignore_missing=bool("X" in self.sequence),
            molecule=self.molecule,
            chain=self.chain_id,
        )

    def get_input_and_initialize(self):
        # Initialize mutant tree for design
        self.design_pool_tree = existed_mutant_tree(
            sequences=self.designable_sequences, enabled_only=0
        )
        if self.design_pool_tree.empty:
            raise issues.NoResultsError("MutantTree is empty!")

        if len(self.design_pool_tree.all_mutant_branch_ids) < 2:
            raise issues.InvalidInputError(
                "At least two groups of mutants should be included."
            )

        # get inputs
        self.in_design_multi_design_case: MutantTree = MutantTree()
        self.all_design_multi_design_cases: list[MutantTree] = []

        # save variants as Mutant
        self.all_design_multi_design_mutant_object: list[Mutant] = []

        self.design_case_variant_objects: list[str] = []
        self.design_pool_tree_copy = None

        self.design_case = cmd.get_unused_name("multi_design")

        logging.info(
            f"Mutant Tree for multi-design is initialized. {len(self.design_pool_tree.all_mutant_branch_ids)} groups with {len(self.design_pool_tree.all_mutant_ids)} mutants."
        )

    @staticmethod
    def recolor_pymol_obj(i, color, item):
        cmd.set_color(f"color_{i}", color)
        cmd.color(
            f"color_{i}",
            f"{item}",
        )
        util.cnc(f"{item}", _self=cmd)

    def refresh_design_color(self):
        """
        Refreshes the color representation of designed mutants.

        This method updates the color representation based on scores or other criteria
        for the designed mutants.
        """
        _total_num_design_cases = max(
            self.total_design_cases, len(self.design_case_variant_objects)
        )

        # color via magician
        if self.color_by_scores and self.magician.gimmick is not None:
            for mut_obj in self.all_design_multi_design_mutant_object:
                mut_obj.wt_protein_sequence = self.designable_sequences
                if mut_obj.mutant_score:
                    continue

                mut_obj.mutant_score = self.magician.gimmick.scorer(
                    mutant=mut_obj
                )

            all_scores = [
                mut_obj.mutant_score
                for mut_obj in self.all_design_multi_design_mutant_object
                if mut_obj.mutant_score
            ]

            for (i_obj, obj), (j_des, des) in zip(
                enumerate(self.design_case_variant_objects),
                enumerate(self.all_design_multi_design_mutant_object),
            ):
                color = get_color(
                    cmap=cmap_reverser(
                        cmap=self.cmap,
                        reverse=self.external_scorer_reversed_score,
                    ),
                    data=des.mutant_score,
                    min_value=min(all_scores),
                    max_value=max(all_scores),
                )

                self.recolor_pymol_obj(i=i_obj, color=color, item=obj)

        # if magician is not specified, color them one after another
        else:
            for i, item in enumerate(self.design_case_variant_objects):
                color = get_color(
                    cmap=self.color_style,
                    data=i + 1,
                    min_value=0,
                    max_value=_total_num_design_cases,
                )
                self.recolor_pymol_obj(i=i, color=color, item=item)

        logging.debug("All design with score: \n")
        logging.debug("-" * 60)
        logging.debug(
            "\n\n"
            + "\n".join(
                [
                    _.full_mutant_id
                    for _ in self.all_design_multi_design_mutant_object
                ]
            )
            + "\n\n"
        )
        logging.debug("-" * 60)

    def evaluate_design(self) -> Mutant:
        """
        Evaluate the designed mutant.

        Args:
        - design: A list of Mutant objects representing the designed mutants.

        Returns:
        - Mutant: The evaluated Mutant object with a calculated score.
        """
        tmp_mutant_obj = self.in_design_multi_design_case.asOneMutant
        tmp_mutant_obj.mutant_score = 0.0
        tmp_mutant_obj.wt_protein_sequence = self.designable_sequences

        if not self.magician.gimmick:
            warnings.warn(
                issues.ConflictWarning(
                    "Abord design evaluation because no external scorer is defined."
                )
            )

        else:
            tmp_mutant_obj.mutant_score = self.magician.gimmick.scorer(
                mutant=tmp_mutant_obj
            )

        for m in self.in_design_multi_design_case.all_mutant_objects:
            m.mutant_score = tmp_mutant_obj.mutant_score

        return

    def start_new_design(self):
        """
        Starts a new mutant design.

        This method initiates the start of a new mutant design process.
        """
        if self.design_pool_tree.empty:
            logging.error("Mutant Tree for multi-design is empty!")
            return
        if not self.in_design_multi_design_case.empty:
            self.terminate_picking()

        self.in_design_multi_design_case = MutantTree({})
        self.design_pool_tree_copy = self.design_pool_tree.__deepcopy__
        self.design_case_id_in_pymol = cmd.get_unused_name(
            "multi_design_variant"
        )
        cmd.create(
            self.design_case_id_in_pymol,
            f"{self.molecule} and c. {self.chain_id} and polymer.protein and n. CA",
        )
        cmd.color("greencyan", self.design_case_id_in_pymol)
        cmd.hide("everything", self.design_case_id_in_pymol)
        cmd.show("sticks", self.design_case_id_in_pymol)
        cmd.group(self.design_case, self.design_case_id_in_pymol)
        logging.info(f"Starting design with {self.design_case_id_in_pymol=}")

    def _auto_pick_tryout(self, tryout=30):
        """
        Attempts to auto-pick mutants for design.

        Args:
        - tryout: Number of attempts to auto-pick mutants (default: 30).

        This method tries to automatically pick mutants for the design process.
        """
        for i in range(tryout):
            try:
                branch, (mutant_id, mutant_obj) = self._select_random_mutant()
            except IndexError:
                return

            mutant_obj.mutant_description = mutant_id

            if not self._is_compatible_mutant(mutant_obj):
                logging.warning(f"Skip {branch}: {mutant_id}.")
                # label this mutant deleted in this design.
                self.design_pool_tree_copy.remove_mutant_from_branch(
                    branch=branch, mutant=mutant_id
                )
                continue

            # add picked mutant to as a new branch
            self.in_design_multi_design_case.add_mutant_to_branch(
                branch=self.in_design_multi_design_case.branch_num,
                mutant=mutant_id,
                mutant_obj=mutant_obj,
            )

            self.design_pool_tree_copy.remove_mutant_from_branch(
                branch=branch, mutant=mutant_id
            )
            # a successful picking and return.
            return

    def pick_next_mutant(self):
        """
        Picks the next mutant for design.

        This method selects the next mutant to be included in the design process.
        """
        if not self.design_pool_tree:
            logging.error("Mutant Tree is not found.")
            return
        if self.design_pool_tree.empty:
            logging.error("Mutant Tree for multi-design is empty!")
            return

        if self.design_pool_tree_copy.empty:
            warnings.warn(
                issues.NoInputWarning(
                    "Temperal mutant tree for multi-design is empty after designing! This design is ended."
                )
            )
            self.start_new_design()
            return

        # run a normal picking
        num_mut_before_picking = self.in_design_multi_design_case.mutant_num
        self._auto_pick_tryout()
        if (
            num_mut_before_picking
            == self.in_design_multi_design_case.mutant_num
        ):
            # failed picking
            warnings.warn(
                issues.NoResultsWarning(
                    "Failed auto picking. Please take anther try."
                )
            )
            return

        # last mutant
        mutant_id = self.in_design_multi_design_case.all_mutant_ids[-1]
        mutant_obj = self.in_design_multi_design_case.all_mutant_objects[-1]

        resi_last_mutant = mutant_obj.mutations[0].position
        cmd.set(
            "sphere_scale",
            0.4,
            f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_last_mutant} and n. CA",
        )
        cmd.show(
            "sphere",
            f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_last_mutant} and n. CA",
        )

        if self.bond_CA:
            # bond to the last previous design
            if self.in_design_multi_design_case.mutant_num >= 2:
                second_mutant_to_the_last: Mutant = (
                    self.in_design_multi_design_case.all_mutant_objects[-2]
                )
                resi_second_mutant_to_the_last = (
                    second_mutant_to_the_last.mutations[-1].position
                )

                cmd.bond(
                    atom1=f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_second_mutant_to_the_last} and n. CA",
                    atom2=f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_last_mutant} and n. CA",
                )

            # bond internal CAs in a multi-design mutant.
            current_mutant_info = mutant_obj.mutations
            if len(current_mutant_info) > 1:
                positions_pairwise = [
                    x
                    for x in pairwise(
                        [_mut.position for _mut in current_mutant_info]
                    )
                ]
                logging.info(f"Pairwised position: {positions_pairwise}")

                for resi_a, resi_b in positions_pairwise:
                    cmd.bond(
                        atom1=f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_a} and n. CA",
                        atom2=f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_b} and n. CA",
                    )

        logging.info(f"{mutant_id} is added to {self.design_case_id_in_pymol}")

        if (
            self.in_design_multi_design_case.mutant_num
            >= self.maximal_mutant_num
        ):
            logging.info(
                f"Reaching {self.maximal_mutant_num} mutations. Stop current design."
            )
            self.terminate_picking()

    def undo_previous_mutant(self):
        """
        Undoes the last mutant addition in the design.

        This method removes the last mutant added to the design.
        """
        if (
            self.in_design_multi_design_case.empty
            and not self.all_design_multi_design_cases
        ):
            logging.error("Nothing to undo.")
            return

        if (
            self.in_design_multi_design_case.empty
            and self.all_design_multi_design_cases
        ):
            # discard the last design mutant object
            self.all_design_multi_design_mutant_object.pop()

            # omit
            self.in_design_multi_design_case = (
                self.all_design_multi_design_cases.pop()
            )
            self.design_case_id_in_pymol = (
                self.design_case_variant_objects.pop()
            )

            cmd.color("greencyan", self.design_case_id_in_pymol)
            self.refresh_design_color()

            logging.warning("Undoing the last design.")

        (
            undo_branch,
            undo_mutant_id,
            undo_mutant_obj,
        ) = self.in_design_multi_design_case.pop()

        # recover the whole mutant tree, as the deleted branch might be used in the future.
        self.design_pool_tree_copy = self.design_pool_tree.__deepcopy__
        resi_undo_mutant = undo_mutant_obj.mutations[0].position

        cmd.hide(
            "sphere",
            f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_undo_mutant} and n. CA",
        )

        if self.bond_CA:
            # unbond to the last previous design
            if self.in_design_multi_design_case.mutant_num >= 1:
                last_mutant = (
                    self.in_design_multi_design_case.all_mutant_objects[-1]
                )
                resi_last_mutant = last_mutant.mutations[-1].position

                cmd.unbond(
                    atom1=f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_last_mutant} and n. CA",
                    atom2=f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_undo_mutant} and n. CA",
                )

            # bond internal CA in a multi-design mutant.
            current_mutant_info = undo_mutant_obj.mutations
            if len(current_mutant_info) > 1:
                positions_pairwise = [
                    x
                    for x in pairwise(
                        [_mut.position for _mut in current_mutant_info]
                    )
                ]
                logging.info(f"Pairwised position: {positions_pairwise}")

                for resi_a, resi_b in positions_pairwise:
                    cmd.unbond(
                        atom1=f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_a} and n. CA",
                        atom2=f"{self.design_case_id_in_pymol} and c. {self.chain_id} and i. {resi_b} and n. CA",
                    )

            logging.info(f"Undo: {undo_mutant_id} ")

        # remove the object if it is already empty
        if self.in_design_multi_design_case.empty:
            cmd.delete(self.design_case_id_in_pymol)

    def terminate_picking(self, continue_design=True):
        """
        Completes the current design and starts a new one.

        Args:
        - continue_design: Boolean flag to continue the design process.

        This method finalizes the current design, starts a new one if requested,
        and evaluates the designed mutants.
        """
        if self.in_design_multi_design_case.empty:
            logging.error("Design case is empty.")
            return

        logging.warning(
            f"Design case {self.in_design_multi_design_case.all_mutant_ids}"
        )

        logging.info("Stopping current design and start a new one.")
        self.design_case_variant_objects.append(self.design_case_id_in_pymol)

        self.all_design_multi_design_cases.append(
            self.in_design_multi_design_case
        )

        self.evaluate_design()
        # evaluate mutant design after design case is closed.
        self.all_design_multi_design_mutant_object.append(
            self.in_design_multi_design_case.asOneMutant
        )

        self.in_design_multi_design_case = MutantTree({})
        logging.warning(
            f"Design case {self.in_design_multi_design_case.all_mutant_ids}"
        )
        self.refresh_design_color()

        if continue_design:
            self.start_new_design()

    def export_designed_variant(self):
        """
        Exports the designed variants.

        Args:
        - save_mutant_table: File path to save the mutant variants.

        This method exports the designed mutant variants to a specified file path.
        """
        if not self.all_design_multi_design_cases:
            logging.error("No designed variants to export.")
            return

        self.save_mutant_table = (
            self.save_mutant_table
            if self.save_mutant_table
            else f"./{self.design_case}.mut.txt"
        )

        logging.info(f"Exporting designs to {self.save_mutant_table}")
        mutant_list = []
        for decision in self.all_design_multi_design_cases:
            mutant_decision_list = [
                mut_obj.raw_mutant_id
                for mut_obj in decision.all_mutant_objects
            ]
            mutant_list.append(",".join(mutant_decision_list))

        os.makedirs(os.path.dirname(self.save_mutant_table), exist_ok=True)

        with open(self.save_mutant_table, "w", encoding="utf8") as f:
            f.write("\n".join(mutant_list))

    def _select_random_mutant(self) -> tuple[str, tuple[str, Mutant]]:
        """
        Selects a random mutant for design.

        Returns:
        - Tuple: Branch identifier and a randomly selected mutant.

        This method randomly selects a mutant for the design process.
        """
        branch = random.choice(
            self.design_pool_tree_copy.all_mutant_branch_ids
        )
        mut = random.choice(
            list(self.design_pool_tree_copy.get_a_branch(branch).items())
        )
        return branch, mut

    def _is_compatible_mutant(
        self,
        mutant: Mutant,
    ):
        """
        Checks compatibility of mutants.

        Args:
        - mutant: Tuple containing mutant information.

        Returns:
        - bool: True if mutants are compatible, False otherwise.

        This method checks if the selected mutant is compatible with existing mutants
        based on distance and sidechain angle criteria.
        """
        if self.in_design_multi_design_case.empty:
            # early return for initial design.
            return True

        existed_mutant_obj = self.in_design_multi_design_case.asOneMutant

        mutant_id = mutant.mutant_description
        for _picked_residue in mutant.mutations:
            if any(
                _picked_residue.position == _existed_residue.position
                for _existed_residue in existed_mutant_obj.mutations
            ):
                logging.warning(
                    f"Mutant has residue id existed in the previous design: \n"
                    f"{mutant_id}"
                )
                return False

            if any(
                not is_distal_residue_pair(
                    molecule=self.molecule,
                    chain_id=self.chain_id,
                    resi_1=_picked_residue.position,
                    resi_2=_existed_residue.position,
                    minimal_distance=self.minimal_distance,
                    use_sidechain_angle=self.use_sidechain_angle,
                )
                for _existed_residue in existed_mutant_obj.mutations
            ):
                logging.warning(
                    f"Mutant has residue id not distal with one position in the previous design: \n"
                    f"{mutant_id}"
                )
                return False
        return True
