# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""Public Qt compatibility exports for REvoDesign."""

from .qt_wrapper import (
    QT_BACKEND,
    QT_MAJOR,
    QtCompat,
    QtCore,
    QtGui,
    QtNetwork,
    QtSource,
    QtSvg,
    QtWebSockets,
    QtWidgets,
    has_qt_module,
    qexec,
)

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtNetwork",
    "QtWebSockets",
    "QtSvg",
    "QtCompat",
    "QT_BACKEND",
    "QT_MAJOR",
    "QtSource",
    "has_qt_module",
    "qexec",
]
