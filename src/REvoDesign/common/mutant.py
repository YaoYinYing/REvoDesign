import hashlib
import os
from dataclasses import dataclass
from typing import TypeVar, Union
from RosettaPy.common.mutation import Chain
from RosettaPy.common.mutation import Mutant as RpMutant
from RosettaPy.common.mutation import RosettaPyProteinSequence
from REvoDesign import issues
T = TypeVar("T")
@dataclass
class Mutant(RpMutant):
    def __str__(self):
        return (
            f"Mutant Info: {self.mutations}, Mutant Score: {self.mutant_score}"
        )
    @property
    def empty(self) -> bool:
        return not bool(self.mutations)
    @property
    def mutant_description(self) -> str:
        return self._mutant_description
    @mutant_description.setter
    def mutant_description(self, new_description: str):
        self._mutant_description = new_description
    @property
    def pdb_fp(self) -> str:
        if not (self._pdb_fp and os.path.exists(self._pdb_fp)):
            self._pdb_fp = ""
        return self._pdb_fp
    @pdb_fp.setter
    def pdb_fp(self, new_pdb_fp: str):
        if not os.path.exists(new_pdb_fp):
            raise FileNotFoundError(new_pdb_fp)
        self._pdb_fp = new_pdb_fp
    @property
    def full_mutant_id(self) -> str:
        return f"{self.raw_mutant_id}_{self.mutant_score}"
    @property
    def raw_mutant_id(self) -> str:
        _raw_mutant_id = "_".join(
            [
                f"{mutant.chain_id}{mutant.wt_res}{mutant.position}{mutant.mut_res}"
                for mutant in self.mutations
            ]
        )
        return _raw_mutant_id
    @property
    def short_mutant_id(self) -> str:
        full_id = self.raw_mutant_id  
        if len(full_id) > 15:
            hashed_id = hashlib.sha256(full_id.encode()).hexdigest()
            short_id = hashed_id[:15]
        else:
            short_id = full_id
        return f"{short_id}_{self.mutant_score}"  
    @property
    def mutant_score(self) -> float:
        return self._mutant_score
    @mutant_score.setter
    def mutant_score(self, value: Union[float, str, int]):
        self._mutant_score = float(value)
    @property
    def wt_score(self) -> float:
        return self._wt_score
    @wt_score.setter
    def wt_score(self, value: Union[float, str, int]):
        self._wt_score = float(value)
    def get_mutant_sequence_single_chain(
        self, chain_id: str, ignore_missing=False
    ) -> Chain:
        if chain_id not in self.wt_protein_sequence.all_chain_ids:
            raise issues.InvalidInputError(
                f"Chain {chain_id} does not exist in wt sequence."
            )
        wt_sequence = self.wt_protein_sequence.get_sequence_by_chain(chain_id)
        if not self.mutations or not wt_sequence:
            raise issues.InvalidInputError(
                "No available mutant information or WT sequence is empty."
            )
        sequence = list(wt_sequence)
        for mutant in self.mutations:
            if mutant.chain_id != chain_id:
                continue
            pos = int(mutant.position)
            if pos > (len_seq := len(sequence)):
                raise issues.MoleculeError(
                    f"Position {pos} out of sequence range ({len_seq})."
                )
            if (wt_res_in_seq := sequence[pos - 1]) != (
                wt_res_in_mut := mutant.wt_res
            ):
                raise issues.MoleculeError(
                    f"WT residue at position {pos} does not match mutant info: {wt_res_in_seq=} - {wt_res_in_mut=}."
                )
            sequence[pos - 1] = mutant.mut_res
        if ignore_missing:
            while True:
                if "X" not in sequence:
                    break
                sequence.remove("X")
        return Chain(chain_id=chain_id, sequence="".join(sequence))
    @property
    def mutant_sequences(self) -> RosettaPyProteinSequence:
        return RosettaPyProteinSequence(
            chains=[
                self.get_mutant_sequence_single_chain(chain_id=chain)
                for chain in self.wt_protein_sequence.all_chain_ids
            ]
        )