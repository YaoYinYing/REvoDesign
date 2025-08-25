from typing import Any
from omegaconf import DictConfig, OmegaConf
from ...basic.abc_singleton import SingletonAbstract
class ConfigStore(SingletonAbstract):
    def singleton_init(self):
        self.cfg = DictConfig({})  
    def set(self, key: str, value: Any) -> None:
        OmegaConf.update(self.cfg, key, value, merge=True)
    def get(self, key: str, default: Any = None) -> Any:
        return OmegaConf.select(self.cfg, key, default=default)
    def reset(self) -> None:
        self.cfg = DictConfig({})  # Reset the configuration to an empty DictConfig