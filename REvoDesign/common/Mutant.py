class Mutant:
    def __init__(self, mutant_info, mutant_score):
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

    def get_mutant_score(self):
        """
        Get the mutant score.

        Returns:
        float: The mutant score.
        """
        return self.mutant_score

    def set_mutant_score(self, new_score):
        """
        Set the mutant score to a new value.

        Args:
        new_score (float): The new mutant score.
        """
        self.mutant_score = new_score
