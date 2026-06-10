# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""
Universal plugin registry for package-based subclass discovery.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, TypeVar

PluginT = TypeVar("PluginT")


@dataclass(frozen=True)
class PluginRegistry(Generic[PluginT]):
    """
    Package-scoped plugin registry.

    Discovery is performed during initialization by importing all modules
    under `package` and collecting subclasses of `base_class`.
    """

    base_class: type[PluginT]
    package: str
    installed_attr: str = "installed"
    include_package_module: bool = True
    include_predicate: Callable[[type[PluginT]], bool] | None = None

    def __post_init__(self):
        all_classes = self._discover_classes()
        implemented_map = MappingProxyType({cls.name: cls for cls in all_classes})  # type: ignore[attr-defined]

        object.__setattr__(self, "_all_classes", tuple(all_classes))
        object.__setattr__(self, "_implemented_map", implemented_map)

    @property
    def all_classes(self) -> tuple[type[PluginT], ...]:
        return self._all_classes  # type: ignore[attr-defined]

    @property
    def implemented_map(self) -> Mapping[str, type[PluginT]]:
        return self._implemented_map  # type: ignore[attr-defined]

    @property
    def installed_names(self) -> list[str]:
        return [
            cls.name  # type: ignore[attr-defined]
            for cls in self.all_classes
            if bool(getattr(cls, self.installed_attr, False))
        ]

    def get(self, name: str, **kwargs) -> PluginT:
        plugin_class = self.implemented_map[name]
        return plugin_class(**kwargs)

    def _iter_module_names(self) -> list[str]:
        package_module = importlib.import_module(self.package)
        module_names = []

        if self.include_package_module:
            module_names.append(package_module.__name__)

        package_paths = getattr(package_module, "__path__", None)
        if package_paths is None:
            return module_names

        for module_info in pkgutil.iter_modules(package_paths, f"{package_module.__name__}."):
            module_names.append(module_info.name)

        return module_names

    def _discover_classes(self) -> list[type[PluginT]]:
        by_name: dict[str, type[PluginT]] = {}

        for module_name in self._iter_module_names():
            module = importlib.import_module(module_name)
            for _, candidate in inspect.getmembers(module, inspect.isclass):
                if candidate is self.base_class:
                    continue
                if not issubclass(candidate, self.base_class):
                    continue
                if inspect.isabstract(candidate):
                    continue
                if self.include_predicate and not self.include_predicate(candidate):
                    continue

                plugin_name = str(getattr(candidate, "name", "")).strip()
                if not plugin_name:
                    raise ValueError(
                        f"Plugin class must define a non-empty 'name': "
                        f"{candidate.__module__}.{candidate.__qualname__}"
                    )

                if plugin_name in by_name and by_name[plugin_name] is not candidate:
                    other = by_name[plugin_name]
                    raise ValueError(
                        f"Duplicate plugin name '{plugin_name}': "
                        f"{other.__module__}.{other.__qualname__} "
                        f"vs {candidate.__module__}.{candidate.__qualname__}"
                    )

                by_name[plugin_name] = candidate

        return sorted(by_name.values(), key=lambda cls: cls.name)  # type: ignore[attr-defined]


def build_plugin_registry(
    base_class: type[PluginT],
    package: str,
    installed_attr: str = "installed",
    include_package_module: bool = True,
    include_predicate: Callable[[type[PluginT]], bool] | None = None,
) -> PluginRegistry[PluginT]:
    return PluginRegistry(
        base_class=base_class,
        package=package,
        installed_attr=installed_attr,
        include_package_module=include_package_module,
        include_predicate=include_predicate,
    )

