# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
This module contains the icon setter class.
"""

import os
import platform

from REvoDesign.Qt import QtGui, QtWidgets


class IconSetter:
    def __init__(self, main_window: QtWidgets.QWidget):
        installed_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
        )
        icon_path = os.path.join(
            installed_dir,
            "meta",
            "images",
            "logo.svg",
        )

        icon = QtGui.QIcon(icon_path)

        if platform.system() == "Darwin":
            main_window.setWindowFilePath(icon_path)
        main_window.setWindowIcon(icon)
