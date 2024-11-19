from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Union


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
    group_generators: tuple[Callable[[], Union[List[str], Dict[str, Any]]], ...]
