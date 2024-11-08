from abc import ABC


class SingletonAbstract(ABC):
    _instance = None

    @classmethod
    def __new__(cls, *args, **kwargs):
        """
        Ensures a single instance of the class is created.

        Parameters:
        - cls: The current class
        - *args: Positional arguments
        - **kwargs: Keyword arguments

        Returns:
        - Returns the singleton instance of the current class.
        """
        # Check if an instance of the class already exists
        if not cls._instance:
            # If not, create a new instance and assign it to the _instance class variable
            cls._instance = super().__new__(cls)
        # Return the existing instance
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """
        Resets the class instance to None.
        """
        cls._instance = None

    @classmethod
    def initialize(cls, *args, **kwargs):
        """
        Initializes the class instance if it doesn't exist yet.

        Parameters:
        - *args: Positional arguments
        - **kwargs: Keyword arguments
        """
        if not cls._instance:
            cls(*args, **kwargs)  # Instantiate the class if no instance exists
        else:
            ...  # ... (additional logic if needed)

    def __init__(self):
        """
        Abstract initialization method. Must be implemented by subclasses.

        This method checks if the instance has been initialized and sets instance attributes accordingly.
        """
        # Check if the instance has already been initialized
        if not hasattr(self, 'initialized'):
            # If not, set the instance attributes
            self.initialized = True
