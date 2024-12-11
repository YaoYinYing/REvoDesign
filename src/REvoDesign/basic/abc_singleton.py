'''
This module contains a class that implements the Singleton pattern.
'''

from abc import ABC, abstractmethod
from typing import Type, TypeVar,cast

T=TypeVar('T', bound='SingletonAbstract')

class SingletonAbstract(ABC):
    _instance = None


    @abstractmethod
    def singleton_init(self, *args, **kwargs):
        '''
        Initializes the singleton instance with the provided arguments.
        Developer should inplement this method to initialize the singleton instance.
        this method is called when the singleton instance is created.
        '''

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

    def __init__(self, *args, **kwargs):
        """
        Abstract initialization method. Must be implemented by subclasses.

        This method checks if the instance has been initialized and sets instance attributes accordingly.
        """
        # Check if the instance has already been initialized
        if not hasattr(self, "initialized"):
            self.singleton_init(*args, **kwargs)
            # If not, set the instance attributes
            self.initialized = True


    @classmethod
    def derive(cls: Type[T], name: str) -> Type[T]:
        """
        Dynamically creates a derived class with singleton behavior.

        Parameters:
        - name: The name of the derived class.

        Returns:
        - A new class that inherits from the current class.
        """
        class DerivedSingleton(cls):  # This class will inherit from `cls`.
            _instance = None  # Independent instance tracking for the derived class

            def __init__(self, *args, **kwargs):
                if not hasattr(self, 'initialized'):
                    self.singleton_init(*args, **kwargs)
                    self.initialized = True

        DerivedSingleton.__name__ = name
        # Cast to satisfy the type checker
        return cast(Type[T], DerivedSingleton)
        
