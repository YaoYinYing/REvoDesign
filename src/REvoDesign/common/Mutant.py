import os
from typing import List, Dict, Mapping, Union, Optional
from dataclasses import dataclass, field
import hashlib
import warnings

from REvoDesign import issues


@dataclass
class Mutant:
    mutant_info: List[Dict[str, Union[str, int]]]
    _mutant_score: Optional[float] = field(
        default_factory=float
    )  # Note the underscore, indicating "private"
    _mutant_description: str = ''
    _pdb_fp: str = ''
    _mutant_id: str = ''
    _wt_sequences: Dict[str, str] = field(default_factory=dict)
    _wt_score: float = 0.0  # Note the underscore, indicating "private"

    def __post_init__(self):
        """
        This method is automatically called after the initialization of the instance.
        It validates the mutant information stored within the instance to ensure its correctness and consistency.

        The `__post_init__` method is a special method in Python data classes that allows for additional
        initialization steps after the regular `__init__` method has executed. In this case, it calls
        the `validate_mutant_info` method which should contain the logic to validate the state of the
        object based on the provided mutant information.

        Note: No parameters are taken besides `self`, and there is no return value as it operates by modifying
        the instance's state directly or raising exceptions if validation fails.
        """
        self.validate_mutant_info()

    def validate_mutant_info(self):
        """
        Validates the structure of the mutant information.

        Iterate through each mutation in the `mutant_info` list and ensure that all
        the required keys ('chain_id', 'position', 'wt_res', 'mut_res') are present.
        Raises a MoleculeError if any key is missing.

        Args:
            self: An instance of the class containing the `mutant_info` attribute, which is a list of dictionaries representing mutations.

        Raises:
            issues.MoleculeError: If any dictionary in `mutant_info` is missing one or more of the required keys.
        """
        for mutation in self.mutant_info:
            required_keys = ['chain_id', 'position', 'wt_res', 'mut_res']
            if not all(key in mutation for key in required_keys):
                raise issues.MoleculeError("Missing keys in mutant_info.")

    def __str__(self):
        return f"Mutant Info: {self.mutant_info}, Mutant Score: {self.mutant_score}"

    @property
    def empty(self) -> bool:
        """
        Checks whether the current object is empty.

        This method examines the `mutant_info` attribute of the object to determine if it is empty.
        If `mutant_info` is empty or non-existent, the object is considered empty.

        Returns:
            bool: Returns True if the object is empty; False otherwise.
        """
        # Evaluates if `mutant_info` is empty, returning True if so, and False otherwise.
        return not bool(self.mutant_info)

    @property
    def wt_sequences(self) -> Dict[str, str]:
        """
        Retrieves a dictionary of wild-type sequences.

        This method takes no parameters and returns a dictionary where keys are sample IDs and values are the corresponding wild-type sequences.

        :return: A dictionary with string keys representing sample IDs and string values representing the wild-type sequences.
        """
        return self._wt_sequences

    @wt_sequences.setter
    def wt_sequences(self, new_wt_sequences: Mapping[str, str]):
        """
        Updates or sets the object's wild-type sequences.

        This method allows users to provide a mapping (dictionary) of sequence identifiers to their corresponding wild-type sequences.

        Args:
            new_wt_sequences (Mapping[str, str]): A dictionary where keys are sequence identifiers and values are the wild-type sequences.

        Raises:
            InvalidInputError: If `new_wt_sequences` is not a `dict`.
            OverridesWarning: If `new_wt_sequences` is not a `dict`, it will be converted to one.

        """
        if not isinstance(new_wt_sequences, Mapping):
            raise issues.InvalidInputError(
                f'new_wt_sequences must be a Dict, not {type(new_wt_sequences)=}!'
            )
        if not isinstance(new_wt_sequences, Dict):
            warnings.warn(
                issues.OverridesWarning(
                    f'{type(new_wt_sequences)=} is converted as a Dict'
                )
            )
            new_wt_sequences = dict(new_wt_sequences)
        self._wt_sequences = new_wt_sequences

    @property
    def mutant_description(self) -> str:
        """
        Retrieves the description of the mutant.

        This method is an instance method that doesn't require any explicit parameters (besides the implicit 'self',
        used to access instance attributes and methods), and returns a string representing the mutant's description.

        Return:
            str: The description of the mutant as a string.
        """

    @mutant_description.setter
    def mutant_description(self, new_description: str):
        """
        Updates the object's "mutant description".

        This method is used to set a new description that characterizes a mutant's traits or state.

        Parameters:
        new_description (str): A new description string to replace the current mutant description.
        """
        self._mutant_description = new_description

    @property
    def pdb_fp(self) -> str:
        """
        Retrieves the path to the PDB file.

        This method checks if the internally stored PDB file path is valid (exists) and
        if not, sets it to an empty string. This could happen if the Mutant object has been
        transferred to another user or the PDB file has been deleted.

        Returns:
            str: The path to the PDB file, or an empty string if the file doesn't exist.
        """
        if not (self._pdb_fp and os.path.exists(self._pdb_fp)):
            self._pdb_fp = ''
        return self._pdb_fp

    @pdb_fp.setter
    def pdb_fp(self, new_pdb_fp: str):
        """
        Sets the new path for the PDB file.

        Parameters:
        new_pdb_fp (str): The specified new path for the PDB file.

        Returns:
        None
        """
        # Check if the new path exists, and raise an exception if it doesn't
        if not os.path.exists(new_pdb_fp):
            raise FileNotFoundError(new_pdb_fp)

        self._pdb_fp = new_pdb_fp

    @property
    def full_mutant_id(self) -> str:
        return f'{self.raw_mutant_id}_{self.mutant_score}'

    @property
    def raw_mutant_id(self) -> str:
        """
        Generates and returns a raw mutant identifier string by concatenating
        chain ID, wild-type residue, position, and mutated residue for each
        mutant in the mutant_info list.

        Args:
            self: An instance of the class containing the `mutant_info` attribute,
                which is a list of dictionaries representing mutant information.

        Returns:
            _raw_mutant_id (str): A concatenated string of all mutant identifiers,
                                separated by underscores.
        """
        _raw_mutant_id = '_'.join(
            [
                f'{mutant["chain_id"]}{mutant["wt_res"]}{mutant["position"]}{mutant["mut_res"]}'
                for mutant in self.mutant_info
            ]
        )
        return _raw_mutant_id

    @property
    def short_mutant_id(self) -> str:
        """
        Generates a shortened mutant ID.

        This method creates a short ID by taking the first 15 characters of the original mutant ID or its SHA-256 hash,
        followed by the mutant score. If the original ID is 15 characters or fewer, it uses the original ID directly.

        Returns:
            str: Shortened mutant ID in the format "<short_id>_<mutant_score>".
        """
        full_id = self.raw_mutant_id  # Get the raw mutant ID

        # If the original ID length is greater than 15 characters,
        if len(full_id) > 15:
            hashed_id = hashlib.sha256(full_id.encode()).hexdigest()
            short_id = hashed_id[:15]
        else:
            short_id = full_id

        return f'{short_id}_{self.mutant_score}'  # Combine the short ID with the mutant score

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

    def get_mutant_sequence_single_chain(
        self, chain_id: str, ignore_missing=False
    ) -> str:
        """
        Generates a mutated sequence for a single chain based on the provided chain ID and mutation information.

        Parameters:
        - chain_id: str, The ID of the chain.
        - ignore_missing: bool, If True, ignores 'X' residues in the sequence.

        Returns:
        - str, The mutated sequence for the specified chain.

        Raises:
        - issues.InvalidInputError: If the chain ID doesn't exist in the wild-type sequences,
          or there's no available mutant information or the wild-type sequence is empty.
        - issues.MoleculeError: If the position is out of sequence range or the wild-type residue
          at the position doesn't match the mutant information.

        Note: If `ignore_missing` is True, any 'X' residues in the sequence will be removed.
        """
        if chain_id not in self.wt_sequences:
            raise issues.InvalidInputError(
                f'Chain {chain_id} does not exist in wt sequence.'
            )

        wt_sequence = self.wt_sequences[chain_id]
        if not self.mutant_info or not wt_sequence:
            raise issues.InvalidInputError(
                "No available mutant information or WT sequence is empty."
            )

        sequence = list(wt_sequence)
        for mutant in self.mutant_info:
            if mutant['chain_id'] != chain_id:
                continue
            pos = int(mutant['position'])
            if pos > (len_seq := len(sequence)):
                raise issues.MoleculeError(
                    f"Position {pos} out of sequence range ({len_seq})."
                )
            if (wt_res_in_seq := sequence[pos - 1]) != (
                wt_res_in_mut := mutant['wt_res']
            ):
                raise issues.MoleculeError(
                    f"WT residue at position {pos} does not match mutant info: {wt_res_in_seq=} - {wt_res_in_mut=}."
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
        """
        Generates a dictionary of mutant sequences for each chain.

        Iterates through each chain in the original wt_sequences dictionary and retrieves the mutant sequence for that specific chain.

        Returns:
            dict[str, str]: A dictionary where keys are chain IDs and values are the corresponding mutated sequences.
        """
        return {
            chain: self.get_mutant_sequence_single_chain(chain_id=chain)
            for chain in self.wt_sequences.keys()
        }
