# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Data classes for Group Registry.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GroupRegistryItem:
    """
    A data class representing an item in a group registry.

    Attributes:
        cfg_item (str): The configuration item associated with this registry entry.
        group_generators (tuple[Callable[[], Union[List[str], Dict[str, Any]]], ...]):
            A tuple of callables that generate groups. Each callable returns either a list of strings or a dictionary.
    """

    cfg_item: str
    group_generators: tuple[Callable[[], list[str] | dict[str, Any]], ...]
