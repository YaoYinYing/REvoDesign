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
    QtUiTools,
    QtWebSockets,
    QtWidgets,
    has_qt_module,
    install_qt6_aliases,
    install_qt5_aliases,
    qexec,
)

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtNetwork",
    "QtWebSockets",
    "QtSvg",
    "QtUiTools",
    "QtCompat",
    "QT_BACKEND",
    "QT_MAJOR",
    "QtSource",
    "has_qt_module",
    "install_qt6_aliases",
    "install_qt5_aliases",
    "qexec",
]
