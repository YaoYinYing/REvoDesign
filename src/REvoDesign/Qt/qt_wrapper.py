"""
Custom Qt Wrapper: Uses pymol.Qt when available, supports typing checks
"""

from typing import TYPE_CHECKING

# ** Type checking: Declare static types (fixes type checkers)**
if TYPE_CHECKING:
    # Type checker branch
    from PyQt5 import QtCore as _QtCore
    from PyQt5 import QtGui as _QtGui
    from PyQt5 import QtWidgets as _QtWidgets
    QtSource: str = "PyQt5"

else:
    # ** Runtime branch**
    _QtCore = _QtGui = _QtWidgets = None  # Predefine to avoid UnboundLocalError
    QtSource: str | None = None  # Track the Qt backend being used

    # ** Try importing pymol.Qt first (Preferred)**
    try:
        from pymol.Qt import QtCore as _QtCore
        from pymol.Qt import QtGui as _QtGui
        from pymol.Qt import QtWidgets as _QtWidgets
        QtSource = "pymol.Qt"
    except ImportError as e:
        raise ImportError(f"PyMOL is not installed or does not have Qt support: {e}") from e

# ** Explicit Type Aliases for Static Analysis (Fixes Type Checkers)**
QtCore = _QtCore
QtGui = _QtGui
QtWidgets = _QtWidgets
# ** Define exports**
__all__ = ["QtCore", "QtGui", "QtWidgets", "QtSource"]
