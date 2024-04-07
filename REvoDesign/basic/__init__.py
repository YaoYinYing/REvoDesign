from abc import ABC, abstractmethod, abstractclassmethod


class SingletonAbstract(ABC):
    _instance = None

    @classmethod
    def __new__(cls, *args, **kwargs):
        # Check if an instance of SingletonAbstract already exists
        if not cls._instance:
            # If not, create a new instance and assign it to the _instance class variable
            cls._instance = super(SingletonAbstract, cls).__new__(cls)
        # Return the existing instance
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    @abstractclassmethod
    def initialize(cls):
        if not cls._instance:
            cls()
        else:
            ...

    @abstractmethod
    def __init__(self):
        # Check if the instance has already been initialized
        if not hasattr(self, 'initialized'):
            # If not, set the instance attributes
            ...
            self.initialized = True
