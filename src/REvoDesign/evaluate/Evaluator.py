'''
Evalutator for mutants
'''
import os
from functools import partial

from pymol import cmd
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign import ConfigBus
from REvoDesign.common import MutantTree
from REvoDesign.logger import root_logger
from REvoDesign.tools.customized_widgets import (decide, get_widget_value,
                                                 set_widget_value)
from REvoDesign.tools.mutant_tools import (existed_mutant_tree,
                                           extract_mutant_from_pymol_object,
                                           save_mutant_choices)

logging = root_logger.getChild(__name__)


class Evalutator:
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()

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

    def activate_focused(self):
        molecule = self.design_molecule
        chain_id = self.design_chain_id

        logging.debug(
            f"Current Mutant ID: {self.mutant_tree_candidates.current_mutant_id}"
        )

        mut_obj = extract_mutant_from_pymol_object(
            pymol_object=self.mutant_tree_candidates.current_mutant_id,
            sequences=self.designable_sequences,
        )
        resi = mut_obj.mutations[0].position

        if self.mutant_tree_candidates.current_mutant_id:
            cmd.enable(self.mutant_tree_candidates.current_mutant_id)
            cmd.show(
                "mesh",
                f"{self.mutant_tree_candidates.current_mutant_id} and (sidechain or n. CA)",
            )
            cmd.show(
                "sticks",
                f"{self.mutant_tree_candidates.current_mutant_id} and (sidechain or n. CA) and not hydrogen",
            )
            cmd.hide(
                "cartoon", f"{self.mutant_tree_candidates.current_mutant_id}"
            )
            if self.bus.get_value("ui.evaluate.show_wt") and resi:
                cmd.show(
                    "lines",
                    f"{molecule} and c. {chain_id} and i. {resi} and (sidechain or n. CA) and not hydrogens",
                )

        all_enabled_mutant_ids = cmd.get_names("nongroup_objects", 1)

        all_enabled_mutants_in_current_group = [
            mutant
            for mutant in cmd.get_object_list(
                f"({self.mutant_tree_candidates.current_branch_id})"
            )
            if mutant != self.mutant_tree_candidates.current_mutant_id
            and mutant in all_enabled_mutant_ids
        ]

        for mutant in all_enabled_mutants_in_current_group:
            cmd.disable(mutant)

        other_opened_group = [
            group
            for group in cmd.get_names("group_objects", 1)
            if group != self.mutant_tree_candidates.current_branch_id
        ]

        for group_id in other_opened_group:
            cmd.disable(group_id)
            cmd.group(group_id, action="close")

        # expand group object if activated
        if self.mutant_tree_candidates.current_branch_id:
            cmd.enable(self.mutant_tree_candidates.current_branch_id)
            cmd.group(
                self.mutant_tree_candidates.current_branch_id, action="open"
            )

        self.center_design_area(self.mutant_tree_candidates.current_mutant_id)

    def mutant_decision(self, decision_to_accept: bool):
        lcdNumber_selected_mutant = self.bus.ui.lcdNumber_selected_mutant
        if not self.is_this_pymol_object_a_mutant(
            self.mutant_tree_candidates.current_mutant_id
        ):
            logging.warning(
                f"Ingoring non mutant {self.mutant_tree_candidates.current_mutant_id}"
            )
            return

        logging.debug(
            f'{"Accepting" if decision_to_accept else "Rejecting"} mutant {self.mutant_tree_candidates.current_mutant_id}'
        )

        if decision_to_accept:
            self.mutant_tree_pssm_selected.add_mutant_to_branch(
                branch=self.mutant_tree_candidates.current_branch_id,
                mutant=self.mutant_tree_candidates.current_mutant_id,
                mutant_obj=self.mutant_tree_candidates.mutant_tree[
                    self.mutant_tree_candidates.current_branch_id
                ][self.mutant_tree_candidates.current_mutant_id],
            )

        else:
            if (
                self.mutant_tree_candidates.current_branch_id
                not in self.mutant_tree_pssm_selected.all_mutant_branch_ids
            ):
                logging.warning(
                    f"{self.mutant_tree_candidates.current_branch_id} does not exist. skipped"
                )
                return

            self.mutant_tree_pssm_selected.remove_mutant_from_branch(
                branch=self.mutant_tree_candidates.current_branch_id,
                mutant=self.mutant_tree_candidates.current_mutant_id,
            )

        set_widget_value(
            lcdNumber_selected_mutant,
            len(self.mutant_tree_pssm_selected.all_mutant_ids),
        )

        save_mutant_choices(
            self.bus.get_value("ui.evaluate.input.to_mutant_txt"),
            self.mutant_tree_pssm_selected,
        )

    def walk_mutant_groups(
        self,
        walk_to_next,
        progressBar_mutant_choosing,
    ):
        comboBox_group_ids = self.bus.ui.comboBox_group_ids
        comboBox_mutant_ids = self.bus.ui.comboBox_mutant_ids

        # self.mutant_tree_pssm.walk_the_mutants(walk_to_next_one=walk_to_next)

        (
            current_branch_id,
            current_mutant_id,
        ) = self.mutant_tree_candidates._walk_the_mutants(
            walk_forward=walk_to_next
        )

        set_widget_value(
            progressBar_mutant_choosing,
            self.mutant_tree_candidates.get_mutant_index_in_all_mutants(
                current_mutant_id
            ),
        )

        # feedback on two comboboxes
        if get_widget_value(comboBox_group_ids) != current_branch_id:
            set_widget_value(comboBox_group_ids, current_branch_id)
            set_widget_value(
                comboBox_mutant_ids,
                list(
                    self.mutant_tree_candidates.get_a_branch(
                        branch_id=self.mutant_tree_candidates.current_branch_id
                    ).keys()
                ),
            )

        if get_widget_value(comboBox_mutant_ids) != current_mutant_id:
            set_widget_value(comboBox_mutant_ids, current_mutant_id)

        self.activate_focused()
        logging.info(
            f'Walked to the {"next" if walk_to_next else "previous"} mutant {current_mutant_id}.'
        )

    def jump_to_branch(self):
        comboBox_group_ids = self.bus.ui.comboBox_group_ids
        comboBox_mutant_ids = self.bus.ui.comboBox_mutant_ids
        progressBar_mutant_choosing = self.bus.ui.progressBar

        branch = get_widget_value(comboBox_group_ids)
        if not branch:
            logging.warning("Branch id is empty or null, skipped.")
            return
        elif not self.mutant_tree_candidates:
            logging.error("Mutant tree is invalid.")
            return
        else:
            logging.info(f"Jump to {branch} as required.")
            self.mutant_tree_candidates.jump_to_branch(branch_id=branch)

            progress = (
                self.mutant_tree_candidates.get_mutant_index_in_all_mutants(
                    self.mutant_tree_candidates.current_mutant_id
                )
            )
            logging.info(
                f"Progressbar set to {progress}: {self.mutant_tree_candidates.current_mutant_id}"
            )
            set_widget_value(progressBar_mutant_choosing, progress)

            # Setting mutant ids to candidates box
            set_widget_value(
                comboBox_mutant_ids,
                list(
                    self.mutant_tree_candidates.get_a_branch(
                        branch_id=branch
                    ).keys()
                ),
            )
            set_widget_value(
                comboBox_mutant_ids,
                self.mutant_tree_candidates.current_mutant_id,
            )
            return

    # end of mutant switching machanism. This step will do focusing, centering, progress bar updating.
    def jump_to_a_mutant(self):
        comboBox_group_ids = self.bus.ui.comboBox_group_ids
        comboBox_mutant_ids = self.bus.ui.comboBox_mutant_ids
        progressBar_mutant_choosing = self.bus.ui.progressBar

        branch_id = get_widget_value(comboBox_group_ids)
        mutant_id = get_widget_value(comboBox_mutant_ids)

        if self.mutant_tree_candidates.empty:
            return

        if (not branch_id) or (not mutant_id):
            return

        if branch_id not in self.mutant_tree_candidates.all_mutant_branch_ids:
            return

        if mutant_id not in self.mutant_tree_candidates.get_a_branch(
            branch_id=branch_id
        ):
            logging.error(
                f"Mutant ID {branch_id} is not belong to this branch {self.mutant_tree_candidates.current_branch_id}."
            )
            return

        if branch_id != self.mutant_tree_candidates.current_branch_id:
            self.mutant_tree_candidates.current_branch_id = branch_id

        logging.info(f"Jump to {mutant_id} as required.")
        self.mutant_tree_candidates.current_mutant_id = mutant_id

        self.activate_focused()

        # update progress bar
        progress = self.mutant_tree_candidates.get_mutant_index_in_all_mutants(
            self.mutant_tree_candidates.current_mutant_id
        )
        logging.info(
            f"Progressbar set to {progress}: {self.mutant_tree_candidates.current_mutant_id}"
        )
        set_widget_value(progressBar_mutant_choosing, progress)

    def jump_to_the_best_mutant(self):
        comboBox_group_ids = self.bus.ui.comboBox_group_ids
        comboBox_mutant_ids = self.bus.ui.comboBox_mutant_ids
        if self.mutant_tree_candidates.empty:
            return

        branch_id = get_widget_value(comboBox_group_ids)

        best_mutant_id = (
            self.mutant_tree_candidates._jump_to_the_best_mutant_in_branch(
                branch_id=branch_id,
                ascending_order=self.bus.get_value(
                    "ui.header_panel.cmap.reverse_score"
                ),
            )
        )
        logging.info(f"Jump to the best hit of {branch_id}: {best_mutant_id}")

        set_widget_value(comboBox_mutant_ids, best_mutant_id)

    def find_all_best_mutants(self):
        comboBox_group_ids = self.bus.ui.comboBox_group_ids
        comboBox_mutant_ids = self.bus.ui.comboBox_mutant_ids
        if self.mutant_tree_candidates.empty:
            logging.error(
                "No available mutant tree. Please reinitialize it before picking mutants."
            )
            return

        if not self.mutant_tree_pssm_selected.empty:
            logging.warning("Your current mutant selection will be overrided!")

            # Ask whether to overide
            confirmed = decide(
                title="Override existed mutant table choices?",
                description="You currently have existed mutant table choices, which shall be overriden by using `I'm lucky`. \n \
                    Are you really sure? ",
            )

            if not confirmed:
                logging.warning("Cancelled.")
                return

        original_branch_id = get_widget_value(comboBox_group_ids)
        original_mutant_id = get_widget_value(comboBox_mutant_ids)

        self.mutant_tree_pssm_selected = MutantTree({})

        for branch_id in self.mutant_tree_candidates.all_mutant_branch_ids:
            logging.info(f"Jump to {branch_id} as required.")

            set_widget_value(comboBox_group_ids, branch_id)

            best_mutant_id = (
                self.mutant_tree_candidates._jump_to_the_best_mutant_in_branch(
                    branch_id=branch_id,
                    ascending_order=self.bus.get_value(
                        "ui.header_panel.cmap.reverse_score"
                    ),
                )
            )
            logging.info(
                f"Jump to the best hit of {branch_id}: {best_mutant_id}"
            )
            set_widget_value(comboBox_mutant_ids, best_mutant_id)

            self.mutant_decision(decision_to_accept=True)
            logging.info(
                f"Best hit of {self.mutant_tree_candidates.current_mutant_id} accepted."
            )
        # set back orignal values befor clicking this button
        set_widget_value(comboBox_group_ids, original_branch_id)
        set_widget_value(comboBox_mutant_ids, original_mutant_id)

        logging.info("Done.")

    # basic function that works for mutant_tree instantiation
    def is_this_pymol_object_a_mutant(self, mutant):
        _mutant_obj = extract_mutant_from_pymol_object(
            pymol_object=mutant, sequences=self.designable_sequences
        )
        return _mutant_obj is not None

    def recover_mutant_choices_from_checkpoint(
        self, mutant_choice_checkpoint_fn
    ):
        lcdNumber_selected_mutant = self.bus.ui.lcdNumber_selected_mutant

        if not mutant_choice_checkpoint_fn:
            logging.warning("Cancelled.")
            return

        if not os.path.exists(mutant_choice_checkpoint_fn):
            logging.warning(
                f"Invalid checkpoint file: {mutant_choice_checkpoint_fn}."
            )
            return

        mutants_from_checkpoint = (
            open(mutant_choice_checkpoint_fn).read().strip().split("\n")
        )

        self.mutant_tree_pssm_selected = (
            self.mutant_tree_candidates.create_mutant_tree_from_list(
                mutants_from_checkpoint
            )
        )
        logging.info(
            f"Recover mutants from checkpoint: {mutant_choice_checkpoint_fn}"
        )
        logging.info(mutants_from_checkpoint)

        set_widget_value(
            lcdNumber_selected_mutant,
            len(self.mutant_tree_pssm_selected.all_mutant_ids),
        )

    def initialize_design_candidates(
        self,
    ):
        (
            pushButton_previous_mutant,
            pushButton_next_mutant,
            pushButton_reject_this_mutant,
            pushButton_accept_this_mutant,
        ) = self.bus.buttons(
            (
                "previous_mutant",
                "next_mutant",
                "reject_this_mutant",
                "accept_this_mutant",
            )
        )

        lcdNumber_total_mutant = self.bus.ui.lcdNumber_total_mutant
        lcdNumber_selected_mutant = self.bus.ui.lcdNumber_selected_mutant
        progressBar_mutant_choosing = self.bus.ui.progressBar
        comboBox_group_ids = self.bus.ui.comboBox_group_ids

        lineEdit_output_mut_txt = self.bus.get_widget_from_cfg_item(
            "ui.evaluate.input.to_mutant_txt"
        )
        self.mutant_tree_candidates = existed_mutant_tree(
            sequences=self.designable_sequences, enabled_only=False
        )
        if self.mutant_tree_candidates.empty:
            logging.error("This sesion may not contain an mutant tree.")
            return None

        self.mutant_tree_pssm_selected = MutantTree({})

        # if mutant tree is available, disable the input box for saving.

        lineEdit_output_mut_txt.setEnabled(
            not self.mutant_tree_candidates.empty
        )

        if not self.mutant_tree_candidates:
            logging.warning(
                "Could not initialize mutant tree! This session may not be a REvoDesign session!"
            )
            return

        # clean the view
        cmd.disable(
            " or ".join(self.mutant_tree_candidates.all_mutant_branch_ids)
        )
        cmd.hide(
            "sticks", " or ".join(self.mutant_tree_candidates.all_mutant_ids)
        )
        cmd.disable(" or ".join(self.mutant_tree_candidates.all_mutant_ids))

        set_widget_value(
            progressBar_mutant_choosing,
            [0, len(self.mutant_tree_candidates.all_mutant_ids)],
        )

        set_widget_value(
            comboBox_group_ids,
            self.mutant_tree_candidates.all_mutant_branch_ids,
        )
        set_widget_value(
            comboBox_group_ids,
            self.mutant_tree_candidates.all_mutant_branch_ids[0],
        )

        self.activate_focused()

        # show the current branch and mutant
        cmd.enable(self.mutant_tree_candidates.current_mutant_id)
        cmd.enable(self.mutant_tree_candidates.current_branch_id)

        set_widget_value(
            lcdNumber_total_mutant,
            len(self.mutant_tree_candidates.all_mutant_ids),
        )
        set_widget_value(
            lcdNumber_selected_mutant,
            len(self.mutant_tree_pssm_selected.all_mutant_ids),
        )

        # initialize mutant walking

        # set state changes to pushbuttons accroding to the mutant tree
        for pushButton in [
            pushButton_previous_mutant,
            pushButton_next_mutant,
            pushButton_reject_this_mutant,
            pushButton_accept_this_mutant,
        ]:
            try:
                pushButton.clicked.disconnect()
            except Exception as e:
                logging.warning(f"Already disconnected. Do nothing. {e}")
            pushButton.setEnabled(bool(not self.mutant_tree_candidates.empty))

        pushButton_accept_this_mutant.clicked.connect(
            partial(self.mutant_decision, True)
        )
        pushButton_reject_this_mutant.clicked.connect(
            partial(self.mutant_decision, False)
        )

        pushButton_next_mutant.clicked.connect(
            partial(
                self.walk_mutant_groups,
                True,
                progressBar_mutant_choosing,
            )
        )

        pushButton_previous_mutant.clicked.connect(
            partial(
                self.walk_mutant_groups,
                False,
                progressBar_mutant_choosing,
            )
        )

    def center_design_area(self, mutant_id):
        if self.mutant_tree_candidates and mutant_id:
            logging.debug(f"Centering design area: {mutant_id}")
            cmd.center(mutant_id, animate=1)
        else:
            logging.debug(f"Giving up centering design area: {mutant_id}")
