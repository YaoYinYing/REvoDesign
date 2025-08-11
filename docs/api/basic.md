### basic

- SingletonAbstract: base for singletons; use ClassName() to get instance; supports reset_instance and derive.
- ThirdPartyModuleAbstract: base for third-party module wrappers; track `name`, `installed`.
- TorchModuleAbstract: device-aware helper with cleanup().
- MutateRunnerAbstract: base class for sidechain mutation runners with run_mutate/run_mutate_parallel.
- ExternalDesignerAbstract: base for external design/scoring modules with initialize/designer/scorer.
- FileExtension, FileExtensionCollection: see `common.file_extensions` examples.
- MenuItem, MenuCollection: bind Qt actions to functions.
- ParamChangeRegister/Item, GroupRegistryItem: configuration helpers used by UI.
- MenuActionServerMonitor, ServerControlAbstract: helper interfaces for server control.

Example (singleton):

```python
from REvoDesign.basic import SingletonAbstract

class MySingle(SingletonAbstract):
    def singleton_init(self):
        self.value = 1

s1 = MySingle()
s2 = MySingle()
assert s1 is s2
```
