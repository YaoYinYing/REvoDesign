'''
This module contains the icon setter class.
'''
import os
import platform

from REvoDesign.Qt import QtGui


class IconSetter:
    def __init__(self, main_window):
        installed_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
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
