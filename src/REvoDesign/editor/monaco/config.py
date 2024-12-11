from typing import Any

from omegaconf import DictConfig, OmegaConf

from ...basic.abc_singleton import SingletonAbstract


class ConfigStore(SingletonAbstract):
    """
    A centralized configuration store using SingletonAbstract and DictConfig for thread-safe configuration management.
    """

    def singleton_init(self):
        super().__init__()
        self.cfg = DictConfig({})  # Initialize the configuration store with an empty DictConfig

    def set(self, key: str, value: Any) -> None:
        """
        Sets a configuration value.

        Args:
            key (str): The configuration key.
            value (Any): The value to store.
        """
        OmegaConf.update(self.cfg, key, value, merge=True)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value.

        Args:
            key (str): The configuration key.
            default (Any): The default value to return if the key is not found.

        Returns:
            Any: The value associated with the key, or the default value.
        """
        return OmegaConf.select(self.cfg, key, default=default)

    def reset(self) -> None:
        """
        Resets the configuration store to an empty state.
        """
        self.cfg = DictConfig({})  # Reset the configuration to an empty DictConfig
