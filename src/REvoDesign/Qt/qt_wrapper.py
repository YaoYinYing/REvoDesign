"""
Custom Qt Wrapper: Uses pymol.Qt when available, supports typing checks
"""
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    
    from PyQt5 import QtCore as _QtCore
    from PyQt5 import QtGui as _QtGui
    from PyQt5 import QtWidgets as _QtWidgets
    QtSource: str = "PyQt5"
else:
    
    _QtCore = _QtGui = _QtWidgets = None  
    QtSource: Optional[str] = None  
    
    try:
        from pymol.Qt import QtCore as _QtCore
        from pymol.Qt import QtGui as _QtGui
        from pymol.Qt import QtWidgets as _QtWidgets
        QtSource = "pymol.Qt"
    except ImportError as e:
        raise ImportError(f"PyMOL is not installed or does not have Qt support: {e}") from e
QtCore = _QtCore
QtGui = _QtGui
QtWidgets = _QtWidgets
__all__ = ["QtCore", "QtGui", "QtWidgets", "QtSource"]