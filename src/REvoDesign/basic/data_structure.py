# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
This module contains the definition of the IterableLoop class, which manages an iterable with looping behavior.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class IterableLoop(Generic[T]):
    """
    A class for managing an iterable with looping behavior.
    """

    iterable: tuple[T]
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


@dataclass(frozen=True)
class FloatRange:
    start: float
    stop: float
    step: float = 0.1

    @classmethod
    def from_str(cls, input_str: str) -> "FloatRange":
        """
        Resolve a FloatRange object from a string.
        """
        return cls(*map(float, input_str.split(",")))
