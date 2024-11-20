import os

from pymol.Qt import QtGui  # type: ignore

from REvoDesign.tools.system_tools import CLIENT_INFO


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
        
        if CLIENT_INFO().os == "Darwin":
            main_window.setWindowFilePath(icon_path)
        main_window.setWindowIcon(icon)
