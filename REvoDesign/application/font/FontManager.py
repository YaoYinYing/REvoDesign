from dataclasses import dataclass

from pymol.Qt import QtGui
from immutabledict import immutabledict

from REvoDesign.tools.system_tools import CLIENT_INFO


@dataclass(frozen=True)
class FlavoredFonts:
    OS_TYPE_FONT_TABLE: immutabledict = immutabledict(
        {
            'Windows': ('Microsoft YaHei', 'Century Gothic'),
            'Linux': ('Nimbus Sans', 'DejaVu Sans'),
            #'Darwin': ['Chalkboard']
        }
    )


class FontSetter:
    def __init__(self, main_window):
        """
        Function: set_window_font
        Usage: set_window_font(main_window)

        This function sets the font for the main window based on the operating system.

        Args:
        - main_window: Reference to the main window object

        Returns:
        - None
        """
        self.main_window = main_window

        self.font_families = QtGui.QFontDatabase().families()
        self.flavored_fonts = FlavoredFonts.OS_TYPE_FONT_TABLE

        self.set_window_font()

    def set_window_font(self):
        _OS_TYPE = CLIENT_INFO.OS_INFO.system
        if _OS_TYPE not in self.flavored_fonts:
            return

        for font_str in self.flavored_fonts.get(_OS_TYPE):
            if font_str in self.font_families:
                font = QtGui.QFont()
                font.setFamily(font_str)
                self.main_window.setFont(font)
                return
