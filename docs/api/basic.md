# Basic Infrastructure

This page documents the `REvoDesign.basic` module, which provides reusable infrastructure classes including plugin registries, data structures, file-extension utilities, menu items, parameter change registrations, third-party module abstractions, and mutation runners.

---

## Plugin Registry

The plugin registry system enables package-scoped, subclass-based plugin discovery. `PluginRegistry` is a frozen dataclass that discovers all non-abstract subclasses of a given base class within a Python package at initialization time. `build_plugin_registry` is a convenience factory function.

::: REvoDesign.basic.plugin_registry.PluginRegistry
::: REvoDesign.basic.plugin_registry.build_plugin_registry

---

## Data Structures

`IterableLoop` is a generic dataclass that manages an iterable with circular navigation (next/previous wrapping), tracking the current index.

::: REvoDesign.basic.data_structure.IterableLoop

---

## File Extensions

`FileExtension` represents a single file extension with a human-readable description; `FileExtensionCollection` manages a collection of extensions with support for merging, matching, and generating Qt file-filter strings.

::: REvoDesign.basic.extensions.FileExtension
::: REvoDesign.basic.extensions.FileExtensionCollection

---

## Group Registry

`GroupRegistryItem` registers a configuration item with a set of callable group generators, enabling dynamic population of UI widget values from config.

::: REvoDesign.basic.group_registries.GroupRegistryItem

---

## Parameter Change Registration

`ParamChangeRegistryItem` maps a signal on one UI widget to a config change on another via a parameter mapping dictionary. `ParamChangeRegister` registers a collection of such items.

::: REvoDesign.basic.param_toggle.ParamChangeRegistryItem
::: REvoDesign.basic.param_toggle.ParamChangeRegister

---

## Menu Items

`MenuItem` defines a single menu entry (action name, callable, arguments, display text). `MenuCollection` binds a collection of `MenuItem` instances to a UI, creating missing actions as needed.

::: REvoDesign.basic.menu_item.MenuItem
::: REvoDesign.basic.menu_item.MenuCollection

---

## Third-Party Module Abstractions

`ThirdPartyModuleAbstract` is the base class for all third-party integrations, providing `name` and `installed` attributes and inheriting from `CitableModuleAbstract` for BibTeX citation support. `TorchModuleAbstract` is a base class for PyTorch-based modules with cross-device memory management.

::: REvoDesign.basic.abc_third_party_module.ThirdPartyModuleAbstract
::: REvoDesign.basic.abc_third_party_module.TorchModuleAbstract

---

## Mutation Runner

`MutateRunnerAbstract` is the abstract base class for running protein mutation tools. It provides parallel mutation execution, PDB file mapping, and optional reconstruction support.

::: REvoDesign.basic.mutate_runner.MutateRunnerAbstract
