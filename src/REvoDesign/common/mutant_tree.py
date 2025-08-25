from typing import List, Mapping, Optional, Protocol, Tuple, TypedDict, Union
from joblib_progress import joblib_progress
from RosettaPy.utils.tools import squeeze
from REvoDesign import issues
from REvoDesign.common.mutant import Mutant
class MutantDict(TypedDict):
    branch: str
    mutant_id: str
    mutant_obj: Mutant
class MutateRunner(Protocol):
    def run_mutate_parallel(
        self, mutants: List[Mutant], nproc: int = 2
    ) -> List[str]: ...
    def mutated_pdb_mapping(
        self, mutant_tree: "MutantTree", pdb_fps: List[str]
    ) -> "MutantTree": ...
    def cite(self) -> None: ...
class MutantTree:
    def __init__(self, mutant_tree: dict[str, dict[str, Mutant]] = {}):
        self.current_branch_id = ""
        self.current_mutant_id = ""
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
        if not self.current_branch_id:
            self.initialize_current_branch()
    def __str__(self) -> str:
        tree_str = "Mutant Tree:\n"
        for branch_id in self.mutant_tree.keys():
            tree_str += f"Branch: {branch_id}\n"
            for mutant_id, mutant_obj in self.mutant_tree[branch_id].items():
                tree_str += f"  Mutant: {mutant_id}\n"
                tree_str += f"    {str(mutant_obj)}\n"
        return tree_str
    @property
    def __copy__(self) -> "MutantTree":
        return MutantTree(self.mutant_tree.copy())
    @property
    def __deepcopy__(self) -> "MutantTree":
        import copy
        return MutantTree(copy.deepcopy(self.mutant_tree))
    def get_branch_index(self, branch_id) -> int:
        return self.all_mutant_branch_ids.index(branch_id)
    def has(self, obj: Union[str, Mutant]) -> bool:
        if isinstance(obj, str):
            return obj in self.all_mutant_ids
        return any(obj == m for m in self.all_mutant_objects)
    def get_a_branch(self, branch_id: str) -> dict[str, Mutant]:
        try:
            return self.mutant_tree[branch_id]
        except KeyError as e:
            raise issues.InvalidInputError(
                f"Branch ID {branch_id} not found in the tree."
            ) from e
    def search_a_branch(self, branch_kw) -> list:
        return [x for x in self.all_mutant_branch_ids if branch_kw in x]
    def get_mutant_index_in_branch(self, branch_id, mutant_id) -> int:
        return list(self.mutant_tree[branch_id].keys()).index(mutant_id)
    def get_mutant_index_in_all_mutants(self, mutant_id) -> int:
        return self.all_mutant_ids.index(mutant_id)
    def is_the_mutant_the_last_in_branch(self, branch_id, mutant_id) -> bool:
        return (
            list(self.mutant_tree[branch_id].keys())[
                self.get_mutant_index_in_branch(branch_id, mutant_id)
            ]
            == list(self.mutant_tree[branch_id].keys())[-1]
        )
    def is_this_branch_empty(self, branch_id) -> bool:
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
        self, new_branches: Union[dict[str, dict[str, Mutant]], "MutantTree"]
    ) -> None:
        if isinstance(new_branches, Mapping):
            for branch, leaves in new_branches.items():
                if branch not in self.all_mutant_branch_ids:
                    self.mutant_tree[branch] = leaves
                else:
                    self.mutant_tree[branch].update(leaves)
        self.refresh_mutants()
    def add_mutant_to_branch(
        self, branch: str, mutant: str, mutant_obj: Mutant
    ) -> None:
        if branch not in self.all_mutant_branch_ids:
            self.mutant_tree[branch] = {}
        if mutant in self.get_a_branch(branch_id=branch):
            print(f"Mutant {mutant} already exists and will be updated.")
        self.mutant_tree[branch].update({mutant: mutant_obj})
        self.refresh_mutants()
    def remove_mutant_from_branch(self, branch: str, mutant: str) -> None:
        if mutant in self.mutant_tree[branch].keys():
            self.mutant_tree[branch].pop(mutant)
        else:
            print(
                f"Mutant {mutant} does not exist in this branch and there's no need to remove it."
            )
        if self.is_this_branch_empty(branch):
            self.mutant_tree.pop(branch)
            print(f"Branch {branch} is empty and has been removed.")
        self.refresh_mutants()
    def create_mutant_tree_from_list(self, mutant_id_list) -> "MutantTree":
        new_mutant_tree = {}
        for branch_id in self.mutant_tree.keys():
            new_branch = {}
            for mutant_id, mutant_obj in self.mutant_tree[branch_id].items():
                if mutant_id in mutant_id_list:
                    new_branch[mutant_id] = mutant_obj
            if new_branch:
                new_mutant_tree[branch_id] = new_branch
        new_tree_instance = MutantTree(new_mutant_tree)
        return new_tree_instance
    def jump_to_the_best_mutant_in_branch(
        self, branch_id: str, ascending_order: bool = False
    ):
        self.current_mutant_id = self._jump_to_the_best_mutant_in_branch(
            branch_id, ascending_order
        )
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
        if not self.current_branch_id:
            self.initialize_current_branch()
            return
        (
            self.current_branch_id,
            self.current_mutant_id,
        ) = self._walk_the_mutants(walk_forward=walf_forward)
    def _walk_the_mutants(self, walk_forward: bool = True) -> Tuple[int, int]:
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
                current_branch_id = last_branch_id
                current_mutant_id = list(
                    self.mutant_tree[last_branch_id].keys()
                )[mutant_index + 1]
            else:
                if branch_index < len(self.all_mutant_branch_ids) - 1:
                    current_branch_id = self.all_mutant_branch_ids[
                        branch_index + 1
                    ]
                    current_mutant_id = list(
                        self.mutant_tree[last_branch_id].keys()
                    )[0]
                else:
                    current_branch_id = self.all_mutant_branch_ids[0]
                    current_mutant_id = list(
                        self.mutant_tree[current_branch_id].keys()
                    )[0]
        else:
            if mutant_index > 0:
                current_branch_id = last_branch_id
                current_mutant_id = list(
                    self.mutant_tree[last_branch_id].keys()
                )[mutant_index - 1]
            else:
                if branch_index > 0:
                    current_branch_id = self.all_mutant_branch_ids[
                        branch_index - 1
                    ]
                    current_mutant_id = list(
                        self.mutant_tree[current_branch_id].keys()
                    )[-1]
                else:
                    current_branch_id = self.all_mutant_branch_ids[-1]
                    current_mutant_id = list(
                        self.mutant_tree[current_branch_id].keys()
                    )[-1]
        return (
            current_branch_id,
            current_mutant_id,
        )
    def jump_to_branch(self, branch_id: str) -> None:
        if branch_id not in self.all_mutant_branch_ids:
            print(f"Could not find a branch with the specified id {branch_id}")
            return
        if self.is_this_branch_empty(branch_id):
            print(f"Branch {branch_id} is empty")
            return
        self.current_branch_id = branch_id
        self.current_mutant_id = list(
            self.mutant_tree[self.current_branch_id].keys()
        )[0]
    def list_mutants(self) -> List[MutantDict]:
        if self.empty:
            return []
        return [
            {
                "branch": branch_id,
                "mutant_id": mutant_id,
                "mutant_obj": mutant_obj,
            }
            for branch_id in self.all_mutant_branch_ids
            for mutant_id, mutant_obj in self.get_a_branch(
                branch_id=branch_id
            ).items()
        ]
    def diff_tree_from(
        self, incoming_tree: "MutantTree"
    ) -> Optional["MutantTree"]:
        if not isinstance(incoming_tree, MutantTree):
            raise ValueError("Input must be a MutantTree object.")
        diff_tree = MutantTree({})
        for branch_id in self.all_mutant_branch_ids:
            if branch_id not in incoming_tree.all_mutant_branch_ids:
                diff_tree.update_tree_with_new_branches(
                    {branch_id: self.get_a_branch(branch_id)}
                )
            else:
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
    def pop(self) -> Optional[tuple[str, str, Mutant]]:
        if self.empty:
            return None
        last_branch_id = self.all_mutant_branch_ids[-1]
        last_mutant_id, last_mutant = list(
            self.mutant_tree[last_branch_id].items()
        )[-1]
        self.remove_mutant_from_branch(last_branch_id, last_mutant_id)
        self.refresh_mutants()
        return last_branch_id, last_mutant_id, last_mutant
    @property
    def asOneMutant(self) -> Mutant:
        tmp_mutant_obj = Mutant(
            mutations=squeeze(
                [
                    _mut_info
                    for _mut_obj in self.all_mutant_objects
                    for _mut_info in _mut_obj.mutations
                ]
            ),
            wt_protein_sequence=self.all_mutant_objects[0].wt_protein_sequence,
        )
        return tmp_mutant_obj
    def run_mutate_parallel(
        self,
        mutate_runner: MutateRunner,
        nproc: int = 2,
    ) -> 'MutantTree':
        with joblib_progress(
            "Packing ...", total=len(self.all_mutant_objects)
        ):
            all_mutants_pdb_fp = mutate_runner.run_mutate_parallel(
                mutants=self.all_mutant_objects, nproc=nproc
            )
        updated_self = mutate_runner.mutated_pdb_mapping(
            mutant_tree=self, pdb_fps=all_mutants_pdb_fp
        )
        mutate_runner.cite()
        return updated_self