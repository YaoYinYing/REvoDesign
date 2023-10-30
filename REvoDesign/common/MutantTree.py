class MutantTree:
    def __init__(self, mutant_tree):
        self.current_branch_id = ''
        self.current_mutant_id = ''
        self.last_branch_id = ''
        self.last_mutant_id = ''

        self.all_mutant_branch_ids = []
        self.all_mutants = []
        self.all_mutant_ids = []
        self.empty = True

        self.mutant_tree = mutant_tree

        self.refresh_mutants()

    def refresh_mutants(self):
        self.all_mutant_branch_ids = list(self.mutant_tree.keys())
        self.empty = bool(len(self.all_mutant_branch_ids) == 0)

        if not self.current_branch_id:
            self.initialize_current_branch()

        self.all_mutants = [
            mutant
            for branch_id in self.mutant_tree.keys()
            for mutant in self.mutant_tree[branch_id].items()
        ]
        self.all_mutant_ids = [mutant for mutant, _ in self.all_mutants]

    def __str__(self):
        tree_str = "Mutant Tree:\n"
        for branch_id in self.mutant_tree.keys():
            tree_str += f"Branch: {branch_id}\n"
            for mutant_id, mutant_obj in self.mutant_tree[branch_id].items():
                tree_str += f"  Mutant: {mutant_id}\n"
                tree_str += f"    {str(mutant_obj)}\n"
        return tree_str

    def get_branch_index(self, branch_id):
        return self.all_mutant_branch_ids.index(branch_id)

    def get_a_branch(self, branch_id):
        return self.mutant_tree[branch_id]

    def search_a_branch(self, branch_kw):
        return [x for x in self.all_mutant_branch_ids if branch_kw in x]

    def get_mutant_index_in_branch(self, branch_id, mutant_id):
        return list(self.mutant_tree[branch_id].keys()).index(mutant_id)

    def get_mutant_index_in_all_mutants(self, mutant_id):
        return self.all_mutant_ids.index(mutant_id)

    def is_the_mutant_the_last_in_branch(self, branch_id, mutant_id):
        return (
            list(self.mutant_tree[branch_id].keys())[
                self.get_mutant_index_in_branch(branch_id, mutant_id)
            ]
            == list(self.mutant_tree[branch_id].keys())[-1]
        )

    def is_this_branch_empty(self, branch_id):
        return len(list(self.mutant_tree[branch_id].keys())) == 0

    def initialize_current_branch(self):
        for branch in self.all_mutant_branch_ids:
            if not self.is_this_branch_empty(branch):
                self.current_branch_id = branch
                self.current_mutant_id = list(
                    self.mutant_tree[self.current_branch_id].keys()
                )[0]
                return

    def extend_tree_with_new_branches(self, new_branches):
        for branch, leaves in new_branches.items():
            if branch not in self.all_mutant_branch_ids:
                self.mutant_tree[branch] = leaves
            else:
                self.mutant_tree[branch].extend(leaves)

        self.refresh_mutants()

    def add_mutant_to_branch(self, branch, mutant, mutant_info):
        if branch not in self.mutant_tree.keys():
            self.mutant_tree[branch] = {}

        if mutant in self.mutant_tree[branch].keys():
            print(f'Mutant {mutant} already exists and will be updated.')

        self.mutant_tree[branch].update({mutant: mutant_info})
        self.refresh_mutants()

    def remove_mutant_from_branch(self, branch, mutant):
        if mutant in self.mutant_tree[branch].keys():
            self.mutant_tree[branch].pop(mutant)
            self.refresh_mutants()
        else:
            print(
                f'Mutant {mutant} does not exist in this branch and there\'s no need to remove it.'
            )

        if self.is_this_branch_empty(branch):
            self.mutant_tree.pop(branch)
            print(f'Branch {branch} is empty and has been removed.')

    def create_mutant_tree_from_list(self, mutant_id_list):
        new_mutant_tree = {}

        # Iterate through the existing branches
        for branch_id in self.mutant_tree.keys():
            new_branch = {}

            # Iterate through mutants in the branch
            for mutant_id, mutant_obj in self.mutant_tree[branch_id].items():
                if mutant_id in mutant_id_list:
                    new_branch[mutant_id] = mutant_obj

            # Add the new branch to the new_mutant_tree if it's not empty
            if new_branch:
                new_mutant_tree[branch_id] = new_branch

        # Create a new MutantTree instance with the filtered mutant tree
        new_tree_instance = MutantTree(new_mutant_tree)
        return new_tree_instance

    def jump_to_the_best_mutant_in_branch(self, branch_id, reversed=False):
        mutants_scores = {
            mutant_id: mutant_obj.get_mutant_score()
            for mutant_id, mutant_obj in self.mutant_tree[branch_id].items()
        }
        sorted_mutants_scores = sorted(
            mutants_scores.items(), key=lambda x: x[1], reverse=not reversed
        )

        self.last_mutant_id = self.current_mutant_id
        self.current_mutant_id = sorted_mutants_scores[0][0]

    # Completed mutant_tree walking function
    def walk_the_mutants(self, walk_to_next_one=True):
        if not self.current_branch_id:
            self.initialize_current_branch()
            return

        # store the last one
        self.last_branch_id = self.current_branch_id
        self.last_mutant_id = self.current_mutant_id

        branch_index = self.get_branch_index(self.current_branch_id)
        mutant_index = self.get_mutant_index_in_branch(
            self.current_branch_id, self.current_mutant_id
        )

        if walk_to_next_one:
            if not self.is_the_mutant_the_last_in_branch(
                self.current_branch_id, self.current_mutant_id
            ):
                # Walk to the next mutant in the current branch
                self.current_mutant_id = list(
                    self.mutant_tree[self.current_branch_id].keys()
                )[mutant_index + 1]
            else:
                if branch_index < len(self.all_mutant_branch_ids) - 1:
                    # Move to the next branch
                    self.current_branch_id = self.all_mutant_branch_ids[
                        branch_index + 1
                    ]
                    self.current_mutant_id = list(
                        self.mutant_tree[self.current_branch_id].keys()
                    )[0]
                else:
                    # Reached the end of the tree, wrap around to the beginning
                    self.current_branch_id = self.all_mutant_branch_ids[0]
                    self.current_mutant_id = list(
                        self.mutant_tree[self.current_branch_id].keys()
                    )[0]
        else:
            if mutant_index > 0:
                # Walk to the previous mutant in the current branch
                self.current_mutant_id = list(
                    self.mutant_tree[self.current_branch_id].keys()
                )[mutant_index - 1]
            else:
                if branch_index > 0:
                    # Move to the previous branch
                    self.current_branch_id = self.all_mutant_branch_ids[
                        branch_index - 1
                    ]
                    self.current_mutant_id = list(
                        self.mutant_tree[self.current_branch_id].keys()
                    )[-1]
                else:
                    # Reached the beginning of the tree, wrap around to the end
                    self.current_branch_id = self.all_mutant_branch_ids[-1]
                    self.current_mutant_id = list(
                        self.mutant_tree[self.current_branch_id].keys()
                    )[-1]

    def jump_to_branch(self, branch_id):
        if branch_id not in self.all_mutant_branch_ids:
            print(f'Could not find a branch with the specified id {branch_id}')
            return
        elif self.is_this_branch_empty(branch_id):
            print(f'Branch {branch_id} is empty')
            return
        else:
            self.last_branch_id = self.current_branch_id
            self.last_mutant_id = self.current_mutant_id
            self.current_branch_id = branch_id
            self.current_mutant_id = list(
                self.mutant_tree[self.current_branch_id].keys()
            )[0]
