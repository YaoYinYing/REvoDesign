class IconSetter:
    def __init__(self, main_window):
        import os
        from pymol.Qt import QtGui

        installed_dir = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
        )
        icon_path = os.path.join(
            installed_dir,
            'meta',
            'images',
            'logo.svg',
        )

        icon = QtGui.QIcon(icon_path)
        from REvoDesign.tools.system_tools import CLIENT_INFO

        if CLIENT_INFO().os == 'Darwin':
            main_window.setWindowFilePath(icon_path)
        main_window.setWindowIcon(icon)
