from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Union
@dataclass(frozen=True)
class GroupRegistryItem:
    cfg_item: str
    group_generators: tuple[Callable[[], Union[List[str], Dict[str, Any]]], ...]