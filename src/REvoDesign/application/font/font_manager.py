import platform
from dataclasses import dataclass
from immutabledict import immutabledict
from REvoDesign.Qt import QtGui
@dataclass(frozen=True)
class FlavoredFonts:
    OS_TYPE_FONT_TABLE: immutabledict[str, tuple[str, ...]] = immutabledict(
        {
            "Windows": ("Microsoft YaHei", "Century Gothic"),
            "Linux": ("Nimbus Sans", "DejaVu Sans"),
        }
    )
class FontSetter:
    def __init__(self, main_window):
        self.main_window = main_window
        self.font_families = QtGui.QFontDatabase().families()
        self.flavored_fonts = FlavoredFonts.OS_TYPE_FONT_TABLE
        self.set_window_font()
    def set_window_font(self):
        os_type: str = platform.system()
        if os_type not in self.flavored_fonts:
            return
        for font_str in self.flavored_fonts[os_type]:
            if font_str in self.font_families:
                font = QtGui.QFont()
                font.setFamily(font_str)
                self.main_window.setFont(font)
                return