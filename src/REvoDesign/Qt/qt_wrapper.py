"""
Custom Qt Wrapper: Uses pymol.Qt when available, supports typing checks
"""

from typing import TYPE_CHECKING, Optional

# ** Type checking: Declare static types (fixes type checkers)**
if TYPE_CHECKING:
    # Type checker branch
    from PyQt5 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets  # noqa
    QtSource: str = "PyQt5"

else:
    # ** Runtime branch**
    _QtCore = _QtGui = _QtWidgets = None  # Predefine to avoid UnboundLocalError
    QtSource: Optional[str] = None  # Track the Qt backend being used

    # ** Try importing pymol.Qt first (Preferred)**
    try:
        from pymol.Qt import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets  # type: ignore
        QtSource = "pymol.Qt"
    except ImportError:
        raise ImportError("PyMOL is not installed or does not have Qt support.")

# ** Explicit Type Aliases for Static Analysis (Fixes Type Checkers)**
QtCore = _QtCore
QtGui = _QtGui
QtWidgets = _QtWidgets

# ** Define exports**
__all__ = ["QtCore", "QtGui", "QtWidgets", "QtSource"]
