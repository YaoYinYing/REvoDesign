# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Utils to manage fonts in Plugin windows
"""

import platform
from dataclasses import dataclass

from immutabledict import immutabledict

from REvoDesign.Qt import QtGui, QtWidgets

DEFAULT_FONT: QtGui.QFont = None  # type: ignore
CURRENT_FONT: QtGui.QFont = None  # type: ignore


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

    OS_TYPE_FONT_TABLE: immutabledict[str, tuple[str, ...]] = immutabledict(
        {
            "Windows": ("Microsoft YaHei", "Century Gothic"),
            "Linux": ("Nimbus Sans", "DejaVu Sans"),
            # 'Darwin': ['Chalkboard']
        }
    )


class FontSetter:
    def __init__(self, main_window: QtWidgets.QWidget):
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
        global DEFAULT_FONT
        global CURRENT_FONT

        DEFAULT_FONT = self.main_window.font()

        self.set_window_font()
        CURRENT_FONT = self.main_window.font()

    def set_window_font(self, custom_font: QtGui.QFont | str | None = None):
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
        if custom_font:
            if isinstance(custom_font, str):
                custom_font = QtGui.QFont(custom_font)
            self.main_window.setFont(custom_font)
            return

        os_type: str = platform.system()

        if os_type not in self.flavored_fonts:
            return

        for font_str in self.flavored_fonts[os_type]:
            if font_str in self.font_families:
                # Create a QFont object and set its family to the found font string
                font = QtGui.QFont(font_str)
                # Set the main window's font to the created font
                self.main_window.setFont(font)
                return


def set_font(font: QtGui.QFont | str | None = None):
    """
    Sets the font for the application interface

    Args:
        font (QtGui.QFont | str | None): The font object, font name string or None to use.
                                       If None, the default font (DEFAULT_FONT) will be used.

    Returns:
        None
    """
    if not font:
        font = DEFAULT_FONT
    if isinstance(font, str):
        font = QtGui.QFont(font)

    # Get configuration bus and UI instance
    from REvoDesign.driver.ui_driver import ConfigBus
    from REvoDesign.UI.Ui_REvoDesign import Ui_REvoDesignPyMOL_UI as UI

    bus = ConfigBus()
    ui: UI = bus.ui
    window = bus.ui.centralwidget
    window.setFont(font)

    # Iterate through and set font for all open windows
    if hasattr(ui, "open_windows"):
        open_windows: list[QtWidgets.QWidget] = getattr(ui, "open_windows")
        for window in open_windows:
            window.setFont(font)


def set_font_dialog():
    fq = QtWidgets.QFontDialog()
    if fq.exec():
        set_font(fq.currentFont())
        global CURRENT_FONT

        CURRENT_FONT = fq.currentFont()
