from typing import List, Union, Protocol, Iterable

from REvoDesign.common.Mutant import Mutant


class MutateRunner(Protocol):
    def run_mutate_parallel(self, *args, **kwargs) -> List[str]:
        ...

    def mutated_pdb_mapping(
        self, mutants: 'MutantTree', pdb_fps: Iterable[str]
    ) -> 'MutantTree':
        ...

    def cite(self) -> None:
        ...


class MutantTree:
    def __init__(self, mutant_tree: dict[str, dict[str, Mutant]] = {}):
        """
        Initialize MutantTree object with a mutant tree dictionary.

        Parameters:
        - mutant_tree (dict): Dictionary representing the mutant tree.

        Usage:
        tree = MutantTree(mutant_tree_dict)
        """
        self.current_branch_id = ''
        self.current_mutant_id = ''

        self.mutant_tree = mutant_tree

        self.refresh_mutants()

    @property
    def all_mutant_objects(self) -> list[Mutant]:
        return [mutant[1] for mutant in self.all_mutants]

    @property
    def all_mutant_scores(self) -> list[float]:
        return [mutant.mutant_score for mutant in self.all_mutant_objects]

    @property
    def all_mutant_branch_ids(self) -> list[str]:
        return list(self.mutant_tree.keys())

    @property
    def empty(self) -> bool:
        return not bool(self.all_mutant_objects)

    @property
    def all_mutants(self) -> list[tuple[str, Mutant]]:
        return [
            mutant
            for branch_id in self.mutant_tree.keys()
            for mutant in self.mutant_tree[branch_id].items()
        ]

    @property
    def all_mutant_ids(self) -> list[str]:
        return [mutant for mutant, _ in self.all_mutants]

    @property
    def branch_num(self) -> int:
        return len(self.all_mutant_branch_ids)

    @property
    def mutant_num(self) -> int:
        return len(self.all_mutant_objects)

    def refresh_mutants(self):
        """
        Refreshes mutant-related attributes in the MutantTree object.

        Usage:
        tree.refresh_mutants()
        """

        if not self.current_branch_id:
            self.initialize_current_branch()

    def __str__(self) -> str:
        """
        Returns a string representation of the MutantTree object.

        Usage:
        print(tree)
        """
        tree_str = "Mutant Tree:\n"
        for branch_id in self.mutant_tree.keys():
            tree_str += f"Branch: {branch_id}\n"
            for mutant_id, mutant_obj in self.mutant_tree[branch_id].items():
                tree_str += f"  Mutant: {mutant_id}\n"
                tree_str += f"    {str(mutant_obj)}\n"
        return tree_str

    @property
    def __copy__(self) -> 'MutantTree':
        """
        Returns a shallow copy of the MutantTree object.

        Usage:
        copied_tree = tree.__copy__()
        """
        return MutantTree(self.mutant_tree.copy())

    @property
    def __deepcopy__(self) -> 'MutantTree':
        """
        Returns a deep copy of the MutantTree object.

        Usage:
        deep_copied_tree = tree.__deepcopy__()
        """
        import copy

        return MutantTree(copy.deepcopy(self.mutant_tree))

    def get_branch_index(self, branch_id) -> int:
        """
        Gets the index of a branch ID in the MutantTree object.

        Parameters:
        - branch_id (str): ID of the branch.

        Usage:
        index = tree.get_branch_index('branch_id')
        """
        return self.all_mutant_branch_ids.index(branch_id)

    def get_a_branch(self, branch_id: str) -> dict[str, Mutant]:
        """
        Gets a specific branch from the MutantTree object.

        Parameters:
        - branch_id (str): ID of the branch.

        Usage:
        branch = tree.get_a_branch('branch_id')
        """
        return self.mutant_tree.get(branch_id)

    def search_a_branch(self, branch_kw) -> list:
        """
        Searches for branches containing a specific keyword in the MutantTree object.

        Parameters:
        - branch_kw (str): Keyword to search for in branch IDs.

        Usage:
        matching_branches = tree.search_a_branch('keyword')
        """
        return [x for x in self.all_mutant_branch_ids if branch_kw in x]

    def get_mutant_index_in_branch(self, branch_id, mutant_id) -> int:
        """
        Gets the index of a mutant in a specific branch of the MutantTree object.

        Parameters:
        - branch_id (str): ID of the branch.
        - mutant_id (str): ID of the mutant.

        Usage:
        index = tree.get_mutant_index_in_branch('branch_id', 'mutant_id')
        """
        return list(self.mutant_tree[branch_id].keys()).index(mutant_id)

    def get_mutant_index_in_all_mutants(self, mutant_id) -> int:
        """
        Gets the index of a mutant in all mutants of the MutantTree object.

        Parameters:
        - mutant_id (str): ID of the mutant.

        Usage:
        index = tree.get_mutant_index_in_all_mutants('mutant_id')
        """
        return self.all_mutant_ids.index(mutant_id)

    def is_the_mutant_the_last_in_branch(self, branch_id, mutant_id) -> bool:
        """
        Checks if the specified mutant is the last in a branch.

        Parameters:
        - branch_id (str): ID of the branch.
        - mutant_id (str): ID of the mutant.

        Usage:
        result = tree.is_the_mutant_the_last_in_branch('branch_id', 'mutant_id')
        """
        return (
            list(self.mutant_tree[branch_id].keys())[
                self.get_mutant_index_in_branch(branch_id, mutant_id)
            ]
            == list(self.mutant_tree[branch_id].keys())[-1]
        )

    def is_this_branch_empty(self, branch_id) -> bool:
        """
        Checks if a specific branch in the MutantTree object is empty.

        Parameters:
        - branch_id (str): ID of the branch.

        Usage:
        result = tree.is_this_branch_empty('branch_id')
        """
        return len(list(self.mutant_tree[branch_id].keys())) == 0

    def initialize_current_branch(self) -> None:
        for branch in self.all_mutant_branch_ids:
            if not self.is_this_branch_empty(branch):
                self.current_branch_id = branch
                self.current_mutant_id = list(
                    self.mutant_tree[self.current_branch_id].keys()
                )[0]
                return

    def update_tree_with_new_branches(
        self, new_branches: Union[dict[str, dict[str, Mutant]], 'MutantTree']
    ) -> None:
        """
        Update the MutantTree object with new branches.

        Parameters:
        - new_branches (dict): Dictionary of new branches and their mutants.

        Usage:
        tree.update_tree_with_new_branches({'new_branch': {'mutant1': info1, 'mutant2': info2}})
        """
        for branch, leaves in new_branches.items():
            if branch not in self.all_mutant_branch_ids:
                self.mutant_tree[branch] = leaves
            else:
                self.mutant_tree[branch].update(leaves)

        self.refresh_mutants()

    def add_mutant_to_branch(
        self, branch: str, mutant: str, mutant_obj: Mutant
    ) -> None:
        """
        Adds a mutant to a specific branch in the MutantTree object.

        Parameters:
        - branch (str): ID of the branch.
        - mutant (str): ID of the mutant.
        - mutant_info (object): Information about the mutant.

        Usage:
        tree.add_mutant_to_branch('branch_id', 'mutant_id', mutant_info)
        """
        if branch not in self.all_mutant_branch_ids:
            self.mutant_tree[branch] = {}

        if mutant in self.get_a_branch(branch_id=branch):
            print(f'Mutant {mutant} already exists and will be updated.')

        self.mutant_tree[branch].update({mutant: mutant_obj})
        self.refresh_mutants()

    def remove_mutant_from_branch(self, branch: str, mutant: str) -> None:
        """
        Removes a mutant from a specific branch in the MutantTree object.

        Parameters:
        - branch (str): ID of the branch.
        - mutant (str): ID of the mutant.

        Usage:
        tree.remove_mutant_from_branch('branch_id', 'mutant_id')
        """
        if mutant in self.mutant_tree[branch].keys():
            self.mutant_tree[branch].pop(mutant)
        else:
            print(
                f'Mutant {mutant} does not exist in this branch and there\'s no need to remove it.'
            )

        if self.is_this_branch_empty(branch):
            self.mutant_tree.pop(branch)
            print(f'Branch {branch} is empty and has been removed.')

        self.refresh_mutants()

    def create_mutant_tree_from_list(self, mutant_id_list) -> 'MutantTree':
        """
        Creates a new MutantTree instance from a filtered list of mutant IDs.

        Parameters:
        - mutant_id_list (list): List of mutant IDs.

        Usage:
        new_tree = tree.create_mutant_tree_from_list(['mutant_id_1', 'mutant_id_2'])
        """
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

    def jump_to_the_best_mutant_in_branch(
        self, branch_id: str, ascending_order: bool = False
    ):
        """
        Jumps to the best mutant in a specific branch based on scores.

        Parameters:
        - branch_id (str): ID of the branch.
        - ascending_order (bool): Optional - Set to True to reverse sorting
            by sorting with assending order (from smaller to larger).

        Usage:
        tree.jump_to_the_best_mutant_in_branch('branch_id')
        """
        self.current_mutant_id = self._jump_to_the_best_mutant_in_branch(
            branch_id, ascending_order
        )

    # internal function that returns instead of changes the current stored values
    def _jump_to_the_best_mutant_in_branch(
        self, branch_id: str, ascending_order: bool = False
    ):
        mutants_scores = {
            mutant_id: mutant_obj.mutant_score
            for mutant_id, mutant_obj in self.mutant_tree[branch_id].items()
        }
        sorted_mutants_scores = sorted(
            mutants_scores.items(),
            key=lambda x: x[1],
            reverse=not ascending_order,
        )

        return sorted_mutants_scores[0][0]

    def walk_the_mutants(self, walf_forward: bool = True):
        # Completed mutant_tree walking function
        """
        Walks through mutants in the MutantTree object.

        Parameters:
        - walf_forward (bool): Optional - Set to False to walk backward.

        Usage:
        tree.walk_the_mutants()
        """
        if not self.current_branch_id:
            self.initialize_current_branch()
            return

        (
            self.current_branch_id,
            self.current_mutant_id,
        ) = self._walk_the_mutants(walk_forward=walf_forward)

    # internal function that returns instead of changes the current stored values
    def _walk_the_mutants(self, walk_forward: bool = True) -> tuple[int]:
        # store the last one
        last_branch_id = self.current_branch_id
        last_mutant_id = self.current_mutant_id

        branch_index = self.get_branch_index(last_branch_id)
        mutant_index = self.get_mutant_index_in_branch(
            last_branch_id, last_mutant_id
        )

        if walk_forward:
            if not self.is_the_mutant_the_last_in_branch(
                last_branch_id, last_mutant_id
            ):
                # Walk to the next mutant in the current branch
                current_branch_id = last_branch_id
                current_mutant_id = list(
                    self.mutant_tree[last_branch_id].keys()
                )[mutant_index + 1]
            else:
                if branch_index < len(self.all_mutant_branch_ids) - 1:
                    # Move to the next branch
                    current_branch_id = self.all_mutant_branch_ids[
                        branch_index + 1
                    ]
                    current_mutant_id = list(
                        self.mutant_tree[last_branch_id].keys()
                    )[0]
                else:
                    # Reached the end of the tree, wrap around to the beginning
                    current_branch_id = self.all_mutant_branch_ids[0]
                    current_mutant_id = list(
                        self.mutant_tree[current_branch_id].keys()
                    )[0]
        else:
            if mutant_index > 0:
                # Walk to the previous mutant in the current branch
                current_branch_id = last_branch_id
                current_mutant_id = list(
                    self.mutant_tree[last_branch_id].keys()
                )[mutant_index - 1]
            else:
                if branch_index > 0:
                    # Move to the previous branch
                    current_branch_id = self.all_mutant_branch_ids[
                        branch_index - 1
                    ]
                    current_mutant_id = list(
                        self.mutant_tree[current_branch_id].keys()
                    )[-1]
                else:
                    # Reached the beginning of the tree, wrap around to the end
                    current_branch_id = self.all_mutant_branch_ids[-1]
                    current_mutant_id = list(
                        self.mutant_tree[current_branch_id].keys()
                    )[-1]
        return (
            current_branch_id,
            current_mutant_id,
        )

    def jump_to_branch(self, branch_id: str) -> None:
        """
        Jumps to a specified branch in the MutantTree object.

        Parameters:
        - branch_id (str): ID of the branch to jump to.

        Usage:
        tree.jump_to_branch('branch_id')
        """
        if branch_id not in self.all_mutant_branch_ids:
            print(f'Could not find a branch with the specified id {branch_id}')
            return
        elif self.is_this_branch_empty(branch_id):
            print(f'Branch {branch_id} is empty')
            return
        else:
            self.current_branch_id = branch_id
            self.current_mutant_id = list(
                self.mutant_tree[self.current_branch_id].keys()
            )[0]

    def list_mutants(self) -> list[dict]:
        if self.empty:
            return []

        return [
            {
                'branch': branch_id,
                'mutant_id': mutant_id,
                'mutant_obj': mutant_obj,
            }
            for branch_id in self.all_mutant_branch_ids
            for mutant_id, mutant_obj in self.get_a_branch(
                branch_id=branch_id
            ).items()
        ]

    def diff_tree_from(self, incoming_tree: 'MutantTree') -> 'MutantTree':
        """
        Compares two MutantTree objects and returns the differences as a new MutantTree.

        Args:
        - incoming_tree (MutantTree): The incoming MutantTree object to compare with.

        Returns:
        - MutantTree or None: A MutantTree object containing the differences between self and other_tree,
        or None if there are no differences.

        Raises:
        - ValueError: If the input other_tree is not a MutantTree object.
        """
        if not isinstance(incoming_tree, MutantTree):
            raise ValueError("Input must be a MutantTree object.")

        diff_tree = MutantTree({})

        # Compare branches in self with other_tree
        for branch_id in self.all_mutant_branch_ids:
            if branch_id not in incoming_tree.all_mutant_branch_ids:
                # Branch exists in self but not in other_tree
                diff_tree.update_tree_with_new_branches(
                    {branch_id: self.get_a_branch(branch_id)}
                )
            else:
                # Branch exists in both trees, compare branch contents
                self_branch = self.get_a_branch(branch_id)
                incoming_tree_branch = incoming_tree.get_a_branch(branch_id)

                diff_branch_contents = {
                    k: v
                    for k, v in self_branch.items()
                    if k not in incoming_tree_branch
                }

                if diff_branch_contents:
                    diff_tree.update_tree_with_new_branches(
                        {branch_id: diff_branch_contents}
                    )

        return diff_tree if not diff_tree.empty else None

    def pop(self) -> tuple[str, str, Mutant]:
        """
        Pops out the last mutant from the last branch of the MutantTree object.

        Returns:
        - Mutant or None: The last mutant in the last branch if it exists, otherwise None.

        Usage:
        last_mutant = tree.pop()
        """
        if self.empty:
            return None

        # Get the ID of the last branch
        last_branch_id = self.all_mutant_branch_ids[-1]

        # Get the last mutant ID and object from the last branch
        last_mutant_id, last_mutant = list(
            self.mutant_tree[last_branch_id].items()
        )[-1]

        # Remove the last mutant from the branch
        self.remove_mutant_from_branch(last_branch_id, last_mutant_id)

        # Refresh the mutant-related attributes
        self.refresh_mutants()

        return last_branch_id, last_mutant_id, last_mutant

    @property
    def asOneMutant(self) -> Mutant:
        tmp_mutant_obj = Mutant(
            mutant_info=[
                _mut_info
                for _mut_obj in self.all_mutant_objects
                for _mut_info in _mut_obj.mutant_info
            ]
        )
        tmp_mutant_obj.wt_sequences = self.all_mutant_objects[0].wt_sequences
        return tmp_mutant_obj

    def run_mutate_parallel(
        self, mutate_runner: MutateRunner, *args, **kwargs
    ) -> None:
        all_mutants_pdb_fp = mutate_runner.run_mutate_parallel(
            mutants=self.all_mutant_objects, *args, kwargs=kwargs
        )

        self = mutate_runner.mutated_pdb_mapping(
            mutants=self, pdb_fps=all_mutants_pdb_fp
        )
        mutate_runner.cite()
