### Qt wrapper

Import Qt modules via `REvoDesign.Qt` which uses `pymol.Qt` at runtime and provides correct types for tooling.

```python
from REvoDesign.Qt import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication([])
label = QtWidgets.QLabel("Hello")
label.show()
app.exec_()
```
