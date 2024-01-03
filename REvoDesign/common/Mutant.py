from typing import Union


class Mutant:
    def __init__(
        self, mutant_info: list[dict], mutant_score: Union[float, None]
    ):
        """
        Initialize a Mutant object with mutant information and score.

        Args:
        mutant_info (list of dict): List of dictionaries containing mutant information.
            Each dictionary should have the following keys: 'molecule', 'chain_id',
            'position', 'wt_res', 'mut_res'.
        mutant_score (float): The mutant score.

        Example:
        mutant_info = [{'chain_id': 'A', 'position': 10, 'wt_res': 'P', 'mut_res': 'L'},
                       {'chain_id': 'B', 'position': 20, 'wt_res': 'S', 'mut_res': 'T'}]
        mutant_score = 0.95
        mutant_obj = Mutant(mutant_info, mutant_score)
        """
        self.mutant_info = mutant_info
        self.mutant_score = mutant_score
        self.mutant_description = ''
        self.mutant_id = ''
        self.wt_sequence = ''
        self.wt_score = 0

    def __str__(self):
        """
        Return a string representation of the Mutant object.
        """
        return f"Mutant Info: {self.mutant_info}, Mutant Score: {self.mutant_score}"

    def get_mutant_info(self):
        """
        Get the mutant information.

        Returns:
        list of dict: List of dictionaries containing mutant information.
        """
        return self.mutant_info

    def get_mutant_id(self):
        """
        Get the mutant identifier.

        Returns:
        string: The mutant identifier with score
        """

        self.mutant_id = '_'.join(
            [
                f'{_mutant_info["chain_id"]}{_mutant_info["wt_res"]}{_mutant_info["position"]}{_mutant_info["mut_res"]}'
                for _mutant_info in self.mutant_info
            ]
        )

        return f'{self.mutant_id}_{self.mutant_score}'

    def get_short_mutant_id(self):
        """
        Get the short mutant identifier.

        Returns:
        string: The short mutant identifier with score
        """
        self.mutant_id = '_'.join(
            [
                f'{_mutant_info["chain_id"]}{_mutant_info["wt_res"]}{_mutant_info["position"]}{_mutant_info["mut_res"]}'
                for _mutant_info in self.mutant_info
            ]
        )

        if len(self.mutant_id) > 15:
            import hashlib

            hashed_mutant_id = hashlib.sha256(
                bytes(self.mutant_id.encode())
            ).hexdigest()
            mutant_id = hashed_mutant_id[:15]
        else:
            mutant_id = self.mutant_id

        return f'{mutant_id}_{self.mutant_score}'

    def get_mutant_score(self) -> float:
        """
        Get the mutant score.

        Returns:
        float: The mutant score.
        """
        return self.mutant_score

    def set_mutant_score(self, new_score: float):
        """
        Set the mutant score to a new value.

        Args:
        new_score (float): The new mutant score.
        """
        self.mutant_score = new_score

    def set_mutant_description(self, new_description: str):
        """
        Set the mutant description to a new value.

        Args:
        new_description (str): The new mutant description.
        """
        self.mutant_description = new_description

    def get_mutant_description(self) -> str:
        """
        Get the mutant description.

        Returns:
        str: The mutant description.
        """
        return self.mutant_description

    def get_mutant_sequence(self) -> str:
        """
        Get the mutant sequence.

        Returns:
        string: The mutant sequence
        """
        if not self.mutant_info:
            raise ValueError("No available mutant!")
        if not self.wt_sequence:
            raise ValueError('WT sequence is empty!')

        _sequence = list(self.wt_sequence)

        for _mut in self.mutant_info:
            _pos = int(_mut['position'])
            if _pos > len(_sequence):
                raise ValueError(
                    f"Mutant sequence is too short! {_pos} >{len(_sequence)}"
                )

            _wt_res_mut = _mut['wt_res']
            _wt_res_seq = _sequence[_pos - 1]

            if _wt_res_mut != _wt_res_seq:
                raise ValueError(
                    f'Mutant WT residue {_wt_res_mut} does not match sequence {_wt_res_seq}!'
                )
            _sequence[_pos - 1] = _mut['mut_res']

        return ''.join(_sequence)

    def get_wt_score(self) -> float:
        """
        Get the wt score.

        Returns:
        float: The wt score.
        """
        return self.wt_score

    def set_wt_score(self, new_score: str):
        """
        Set the wt score to a new value.

        Args:
        new_score (float): The new wt score.
        """
        self.wt_score = new_score
