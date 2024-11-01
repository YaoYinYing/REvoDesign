'''
Utils to manage fonts in Plugin windows
'''
from dataclasses import dataclass

from pymol.Qt import QtGui
from immutabledict import immutabledict

from REvoDesign.tools.system_tools import CLIENT_INFO


@dataclass(frozen=True)
class FlavoredFonts:
    """
    A frozen dataclass representing a collection of fonts associated with different operating system types.
    
    This class uses the `dataclass` decorator to automatically generate special methods like `__init__`, `__repr__`, 
    and `__eq__`.

    Attributes:
        OS_TYPE_FONT_TABLE (immutabledict): A dictionary containing font recommendations for different operating 
        system types.
            - The dictionary uses operating system names as keys (e.g., 'Windows', 'Linux') and tuples of font 
            names as values.
            - The use of `immutabledict` ensures that the dictionary is immutable, aligning with the immutable 
            nature of the class instances.
            - Note: The font recommendations for 'Darwin' (macOS) are currently commented out, indicating that 
            this part of the data may still be under consideration or not yet finalized.
    """
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
        """
        Set the window font based on the operating system type.

        This method retrieves the current client operating system type and checks if it exists in the predefined font dictionary.
        If the OS type is not found, the method returns without making any changes. If the OS type is found, it iterates through
        the list of fonts associated with that OS type and sets the window font to the first available font family found in the
        `self.font_families` list.

        Parameters:
        - None

        Returns:
        - None
        """
        os_type = CLIENT_INFO.OS_INFO.system
        if os_type not in self.flavored_fonts:
            return

        for font_str in self.flavored_fonts.get(os_type):
            if font_str in self.font_families:
                # Create a QFont object and set its family to the found font string
                font = QtGui.QFont()
                font.setFamily(font_str)
                # Set the main window's font to the created font
                self.main_window.setFont(font)
                return
