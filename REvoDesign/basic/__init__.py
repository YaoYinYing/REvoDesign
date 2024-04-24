from abc import ABC, abstractmethod
from typing import Tuple, TypeVar, Generic
from dataclasses import dataclass

T = TypeVar('T')


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

    @classmethod
    def initialize(cls, *args, **kwargs):
        if not cls._instance:
            cls(*args, **kwargs)
        else:
            ...

    @abstractmethod
    def __init__(self):
        # Check if the instance has already been initialized
        if not hasattr(self, 'initialized'):
            # If not, set the instance attributes
            ...
            self.initialized = True


@dataclass
class IterableLoop(Generic[T]):
    """
    A class for managing an iterable with looping behavior.
    """

    iterable: Tuple[T]
    current_idx: int = -1

    @property
    def empty(self):
        return not bool(self.iterable)

    @property
    def initialized(self):
        return self.current_idx >= 0

    def pick_next(self) -> int:
        """
        Moves to the next item in the iterable, wrapping around to the beginning if necessary.
        """
        if self.current_idx == len(self.iterable) - 1:
            self.current_idx = 0
        else:
            self.current_idx += 1

        return self.current_idx

    def pick_previous(self) -> int:
        """
        Moves to the previous item in the iterable, wrapping around to the end if necessary.
        """
        if self.current_idx == 0:
            self.current_idx = len(self.iterable) - 1
        else:
            self.current_idx -= 1

        return self.current_idx

    def walker(self, direction: bool) -> int:
        """
        Moves to the next or previous item in the iterable based on the given direction.

        Args:
            direction: A boolean value indicating the direction of movement.
                       True for next, False for previous.
        """
        if not self.initialized:
            self.current_idx = 0
            # [-1] -> 0
            if direction:
                return self.current_idx
            # [-1] -> 0 -> -1
            self.pick_previous()

            return self.current_idx

        if direction:
            return self.pick_next()
        else:
            return self.pick_previous()

    @property
    def current_item(self) -> T:
        """
        Returns the current item in the iterable.
        """
        return self.iterable[self.current_idx]

    def reset(self) -> int:
        """
        Resets the current index to -1, indicating an uninitialized state.
        """
        self.current_idx = -1
        return self.current_idx
