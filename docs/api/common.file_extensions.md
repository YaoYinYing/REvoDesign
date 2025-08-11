### common.file_extensions

Collections of `FileExtension` grouped as `FileExtensionCollection` for dialogs and file handling.

Available collections include:

- Session, Mutable, PDB, PDB_STRICT, MOL, SDF, PSSM, CSV, MSA, A3M, TXT, Any, Compressed, PickledObject, YAML, JSON, RosettaParams, Pictures

Example: using a collection as a PyQt file dialog filter

```python
from REvoDesign.common import file_extensions as FExt
from REvoDesign.Qt import QtWidgets

fname, flt = QtWidgets.QFileDialog.getOpenFileName(
    None,
    "Open PDB",
    ".",
    FExt.PDB.filter_string,
)
```

API helpers (from `basic.extensions`):

- FileExtension.filter_string -> str
- FileExtensionCollection.list_all, list_dot_ext, match(ext), filter_string, basename_stem(fname), squeeze(tuple[collections])
