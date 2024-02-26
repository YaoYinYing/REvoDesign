from dataclasses import dataclass, field
from typing import List, Dict, Union, Optional
import hashlib


@dataclass
class Mutant:
    mutant_info: List[Dict[str, Union[str, int]]]
    _mutant_score: Optional[float] = field(
        default_factory=float
    )  # Note the underscore, indicating "private"
    _mutant_description: str = ''
    _mutant_id: str = ''
    _wt_sequences: Dict[str, str] = field(default_factory=dict)
    _wt_score: float = 0.0  # Note the underscore, indicating "private"

    def __post_init__(self):
        self.validate_mutant_info()

    def validate_mutant_info(self):
        for mutation in self.mutant_info:
            required_keys = ['chain_id', 'position', 'wt_res', 'mut_res']
            if not all(key in mutation for key in required_keys):
                raise ValueError("Missing keys in mutant_info.")

    def __str__(self):
        return f"Mutant Info: {self.mutant_info}, Mutant Score: {self.mutant_score}"

    @property
    def empty(self) -> bool:
        return not bool(self.mutant_info)

    @property
    def wt_sequences(self) -> Dict[str, str]:
        return self._wt_sequences

    @wt_sequences.setter
    def wt_sequences(self, new_wt_sequences: Dict[str, str]):
        self._wt_sequences = new_wt_sequences

    @property
    def mutant_description(self) -> str:
        return self._mutant_description

    @mutant_description.setter
    def mutant_description(self, new_description: str):
        self._mutant_description = new_description

    @property
    def full_mutant_id(self) -> str:
        self._mutant_id = '_'.join(
            [
                f'{mutant["chain_id"]}{mutant["wt_res"]}{mutant["position"]}{mutant["mut_res"]}'
                for mutant in self.mutant_info
            ]
        )
        return self._mutant_id

    @property
    def short_mutant_id(self) -> str:
        full_id = self.full_mutant_id
        if len(full_id) > 15:
            hashed_id = hashlib.sha256(full_id.encode()).hexdigest()
            short_id = hashed_id[:15]
        else:
            short_id = full_id
        return f'{short_id}_{self.mutant_score}'

    @property
    def mutant_score(self) -> float:
        """
        The mutant score property.
        """
        return self._mutant_score

    @mutant_score.setter
    def mutant_score(self, value: Union[float, str, int]):
        """
        Set the mutant score to a new value.
        """
        self._mutant_score = float(value)

    @property
    def wt_score(self) -> float:
        """
        The wild-type score property.
        """
        return self._wt_score

    @wt_score.setter
    def wt_score(self, value: Union[float, str, int]):
        """
        Set the wild-type score to a new value.
        """
        self._wt_score = value

    def get_mutant_sequence_single_chain(self, chain_id: str, ignore_missing=False) -> str:
        if chain_id not in self.wt_sequences:
            raise ValueError(
                f'Chain {chain_id} does not exist in wt sequence.'
            )

        wt_sequence = self.wt_sequences[chain_id]
        if not self.mutant_info or not wt_sequence:
            raise ValueError(
                "No available mutant information or WT sequence is empty."
            )

        sequence = list(wt_sequence)
        for mutant in self.mutant_info:
            if mutant['chain_id'] != chain_id:
                continue
            pos = int(mutant['position'])
            if pos > len(sequence):
                raise ValueError(f"Position {pos} out of sequence range.")
            if sequence[pos - 1] != mutant['wt_res']:
                raise ValueError(
                    f"WT residue at position {pos} does not match mutant info."
                )
            sequence[pos - 1] = mutant['mut_res']
        
        if ignore_missing:
            while True:
                if not 'X' in sequence:
                    break
                sequence.remove('X')

        return ''.join(sequence)

    @property
    def mutant_sequences(self) -> dict[str, str]:
        return {
            chain: self.get_mutant_sequence_single_chain(chain_id=chain)
            for chain in self.wt_sequences.keys()
        }
