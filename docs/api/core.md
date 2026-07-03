# Core Abstractions

This page documents the three foundational abstractions of REvoDesign: the Borg-like singleton pattern, the base class for all third-party designer/scorer modules, and the central configuration-to-UI bridge.

---

## SingletonAbstract

`SingletonAbstract` is the Borg-like singleton base class. It enforces that only one instance of a class is created, supports dynamic derivation of independent singleton subclasses, provides instance re-initialization, and allows explicit instance reset. Subclasses must implement the `singleton_init` method for custom initialization logic.

::: REvoDesign.basic.abc_singleton.SingletonAbstract

---

## ExternalDesignerAbstract

`ExternalDesignerAbstract` is the abstract base class for all third-party designer and scorer modules in REvoDesign. It inherits from `ThirdPartyModuleAbstract` and provides a framework for designing molecules, including serial and parallel scoring of mutants.

::: REvoDesign.basic.designer.ExternalDesignerAbstract

---

## ConfigBus

`ConfigBus` is the central configuration-to-UI bridge singleton. It inherits from both `SingletonAbstract` and `CitableModuleAbstract`, managing the bidirectional mapping between OmegaConf/Hydra YAML configuration and UI widget state. In headless mode only `get_value`/`set_value` are available; GUI methods are guarded by the `@require_non_headless` decorator.

See the [Driver API](driver.md#configbus-detailed-methods) for the full method reference.
