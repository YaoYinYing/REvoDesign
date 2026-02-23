# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Import Path for REvoDesign.Qt
Ensures type checkers recognize QtCore, QtGui, and QtWidgets correctly.
"""

from .qt_wrapper import QtCore, QtGui, QtSource, QtWidgets

__all__ = ["QtCore", "QtGui", "QtWidgets", "QtSource"]
