"""
Life of a Singleton Class

+---------------------------------------------+
|         Client Code Calls SingletonAbstract |
+---------------------------------------------+
                     |
                     v
         +---------------------------+
         | Calls __new__             |
         +---------------------------+
                     |
         +---------------------------+
         | Does _instance Exist?     |
         +---------------------------+
          |                      |
          | No                   | Yes
          v                      v
+---------------------------+   +---------------------------+
| Create New Instance       |   | Return Existing Instance  |
| with super().__new__      |   +---------------------------+
+---------------------------+
          |
          v
+---------------------------+
| Assign New Instance       |
| to _instance              |
+---------------------------+
          |
          v
+---------------------------+
| Call __init__ for         |
| Initialization            |
+---------------------------+
          |
          v
+---------------------------+
| Check if 'initialized'    |
| Attribute Exists          |
+---------------------------+
          |                      |
          | No                   | Yes
          v                      v
+---------------------------+   +---------------------------+
| Call singleton_init       |   | Skip Initialization Logic |
| for Custom Initialization |   +---------------------------+
+---------------------------+
          |
          v
+---------------------------+
| Set 'initialized'         |
| Attribute to True         |
+---------------------------+
          |
          v
+---------------------------+
| Return Singleton Instance |
+---------------------------+

Dynamic Derivation
+---------------------------------------------+
| Client Calls derive(name)                   |
+---------------------------------------------+
                     |
                     v
+---------------------------+
| Create New Derived Class  |
| Dynamically               |
+---------------------------+
                     |
                     v
+---------------------------+
| Set Derived Class _instance|
| to None                    |
+---------------------------+
                     |
                     v
+---------------------------+
| Return New Derived Class  |
+---------------------------+

Initialize or Update Instance
+---------------------------------------------+
| Client Calls initialize(*args, **kwargs)    |
+---------------------------------------------+
                     |
                     v
+---------------------------+
| Does _instance Exist?     |
+---------------------------+
          |                      |
          | No                   | Yes
          v                      v
+---------------------------+   +---------------------------+
| Call __new__ to Create    |   | Update _instance          |
| Instance                  |   | Attributes with kwargs    |
+---------------------------+   +---------------------------+
          |
          v
+---------------------------+
| Initialize New Instance   |
| with args and kwargs      |
+---------------------------+
          |
          v
+---------------------------+
| Return Singleton Instance |
+---------------------------+

Resetting Instance
+---------------------------------------------+
| Client Calls reset_instance                 |
+---------------------------------------------+
                     |
                     v
+---------------------------+
| Set _instance to None     |
+---------------------------+


"""

from abc import ABC, abstractmethod
from typing import TypeVar, cast

T = TypeVar("T", bound="SingletonAbstract")


class SingletonAbstract(ABC):
    """
    A base class that enforces the Singleton design pattern.
    Ensures that only one instance of the class is created, with support
    for dynamic derivation of new singleton classes.

    Attributes:
        _instance: The singleton instance of the class.
    """

    _instance = None

    @classmethod
    def __new__(cls, *args, **kwargs):
        """
        Creates or returns the singleton instance of the class.

        This method ensures that only one instance of the class is created,
        regardless of how many times the class is instantiated.

        Args:
            cls: The current class.
            *args: Positional arguments for the instance.
            **kwargs: Keyword arguments for the instance.

        Returns:
            The singleton instance of the class.
        """
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, *args, **kwargs):
        """
        Initializes the singleton instance.

        Ensures that the instance is only initialized once. Subclasses must implement
        the `singleton_init` method for custom initialization logic.

        Args:
            *args: Positional arguments for initialization.
            **kwargs: Keyword arguments for initialization.
        """
        if not hasattr(self, "initialized"):
            self.singleton_init(*args, **kwargs)
            self.initialized = True

    @abstractmethod
    def singleton_init(self, *args, **kwargs):
        """
        Abstract method to initialize the singleton instance with custom logic.

        Subclasses must implement this method to initialize their specific attributes.

        Args:
            *args: Positional arguments for initialization.
            **kwargs: Keyword arguments for initialization.
        """

    @classmethod
    def initialize(cls, *args, **kwargs):
        """
        Initializes the singleton instance if it doesn't exist yet.
        Updates the singleton instance with new variables if it already exists.

        Args:
            *args: Positional arguments for initialization.
            **kwargs: Keyword arguments for initialization or updating.
        """
        if not cls._instance:
            # Create the instance using __new__ and initialize it
            cls(*args, **kwargs)
        else:
            # Update existing instance with new variables
            for key, value in kwargs.items():
                setattr(cls._instance, key, value)

    @classmethod
    def derive(cls: type[T], name: str) -> type[T]:
        """
        Dynamically creates a derived class with independent singleton behavior.

        This method allows for the creation of new singleton classes that inherit from
        the current class. Each derived class has its own independent singleton instance.

        Args:
            name: The name of the derived class.

        Returns:
            A dynamically created subclass with singleton behavior.
        """

        class DerivedSingleton(cls):
            """
            A dynamically created derived singleton class.
            """

            _instance = None  # Independent instance tracking for the derived class

            def __init__(self, *args, **kwargs):
                """
                Initializes the derived singleton instance.

                Ensures that the instance is only initialized once, using the
                `singleton_init` method for custom logic.

                Args:
                    *args: Positional arguments for initialization.
                    **kwargs: Keyword arguments for initialization.
                """
                if not hasattr(self, "initialized"):
                    self.singleton_init(*args, **kwargs)
                    self.initialized = True

        DerivedSingleton.__name__ = name
        return cast(type[T], DerivedSingleton)

    @classmethod
    def reset_instance(cls):
        """
        Resets the singleton instance for the class.

        After calling this method, the next instantiation will create a new singleton instance.
        """
        cls._instance = None


def reset_singletons():
    """
    Reset singleton classes.

    This function is used to gracefully reset all singleton classes. It iterates through all subclasses of SingletonAbstract,
    and if the subclass has an '_instance' attribute and it is not None, it calls the reset_instance method of that class.

    Note: This function does not accept parameters and does not return any value.
    """
    # gracefully reset all singleton classes
    for cls in SingletonAbstract.__subclasses__():
        # check if the singleton class instance exists
        if hasattr(cls, "_instance") and cls._instance is not None:
            # reset the instance of the singleton class
            cls.reset_instance()
