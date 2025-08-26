'''
This module contains functions and classes related to generating unique identifiers (UUIDs).
'''

import uuid


class UUIDGenerator:
    """
    This class implements a UUID generator using Python's built-in 'uuid' module.
    """

    @staticmethod
    def generate_uuid():
        """
        Generates a UUID using the uuid4 method.

        Returns:
        - str: A string representation of the generated UUID.
        """
        return str(uuid.uuid4())
