from dataclasses import dataclass
from typing import Generic, Tuple, TypeVar
T = TypeVar("T")
@dataclass
class IterableLoop(Generic[T]):
    iterable: Tuple[T]
    current_idx: int = -1
    @property
    def empty(self):
        return not bool(self.iterable)
    @property
    def initialized(self):
        return self.current_idx >= 0
    def pick_next(self) -> int:
        if self.current_idx == len(self.iterable) - 1:
            self.current_idx = 0
        else:
            self.current_idx += 1
        return self.current_idx
    def pick_previous(self) -> int:
        if self.current_idx == 0:
            self.current_idx = len(self.iterable) - 1
        else:
            self.current_idx -= 1
        return self.current_idx
    def walker(self, direction: bool) -> int:
        if not self.initialized:
            self.current_idx = 0
            if direction:
                return self.current_idx
            self.pick_previous()
            return self.current_idx
        if direction:
            return self.pick_next()
        return self.pick_previous()
    @property
    def current_item(self) -> T:
        return self.iterable[self.current_idx]
    def reset(self) -> int:
        self.current_idx = -1
        return self.current_idx