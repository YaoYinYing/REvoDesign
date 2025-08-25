import difflib
import importlib
import importlib.util
import io
import json
import math
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property, partial
from typing import (TYPE_CHECKING, Any, Callable, Dict, Iterable, List,
                    Mapping, NoReturn, Optional, Tuple, Type, TypeVar, Union,
                    overload)
from urllib.error import HTTPError, URLError
from pymol import cmd, get_version_message
from pymol.plugins import addmenuitemqt
from pymol.Qt.utils import loadUi
LOGGER_LEVEL = 0
if TYPE_CHECKING:
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    from pymol.Qt import QtCore, QtGui, QtWidgets
if not __file__.endswith('package_manager.py'):
    __doc__ = """Described at GitHub:
https://github.com/YaoYinYing/REvoDesign
Authors : Yinying Yao
Program : REvoDesign
Date    : Sept 2023
REvoDesign -- Makes enzyme redesign tasks easier to all."""
    class MockLogger:
        def debug(self, msg: str, *args, **kwargs):
            print(f'[DEBUG]: {msg}') if LOGGER_LEVEL < 10 else None
        def info(self, msg: str, *args, **kwargs):
            print(f'[INFO]: {msg}') if LOGGER_LEVEL < 20 else None
        def warning(self, msg: str, *args, **kwargs):
            print(f'[WARNING]: {msg}') if LOGGER_LEVEL < 30 else None
        def error(self, msg: str, *args, **kwargs):
            print(f'[ERROR]: {msg}') if LOGGER_LEVEL < 40 else None
        def critical(self, msg: str, *args, **kwargs):
            print(f'[CRITICAL]: {msg}') if LOGGER_LEVEL < 50 else None
    logging = MockLogger()
    logging.info(f'Package manager is running via PyMOL: {__file__}.')
else:
    __doc__ = '''
Module that contains key functions of constructing the REvoDesign Package Manager
This module also serves as standalone REvoDesign Package Manager,
meaning that any tools existed here is part of the manager.
To make any of them importable in certain modules, import them from here
and add to the `__all__` attributes so that they can be discoverable.
    A dataclass representing an extras item.
    Attributes:
    - name (str): The name of the extras item.
    - extras_id (str): The unique identifier for the extras item.
    - depts (list[str]): The departments associated with the extras item.
    A dataclass representing an extras group.
    Attributes:
    - name (str): The name of the extras group.
    - description (str): The description of the extras group.
    - extras (ExtrasItem): The extras item associated with this group.
self.abortbutton = QtWidgets.QPushButton('Abort')
self.abortbutton.setStyleSheet("background: 
self.abortbutton.released.connect(cmd.interrupt)
'''
@contextmanager
def hold_trigger_button(
    buttons: Union[tuple[QtWidgets.QPushButton, ...], QtWidgets.QPushButton],
    animation_duration: int = 1000  
):
    if not isinstance(buttons, (tuple, list, set)):
        buttons = (buttons,)
    timers = []
    def get_accent_color():
        color = QtGui.QColor(76, 217, 100)
        return color
    def start_breathing_animation(button: QtWidgets.QPushButton):
        accent_color = get_accent_color()
        base_color = accent_color.lighter(150)  
        darker_color = accent_color.darker(150)  
        timer = QtCore.QTimer(button)
        timer.setInterval(30)  
        elapsed = 0
        def update_stylesheet():
            nonlocal elapsed
            elapsed += timer.interval()
            t = (elapsed % animation_duration) / animation_duration  
            factor = (1 + math.sin(2 * math.pi * t)) / 2  
            r = int(base_color.red() * factor + darker_color.red() * (1 - factor))
            g = int(base_color.green() * factor + darker_color.green() * (1 - factor))
            b = int(base_color.blue() * factor + darker_color.blue() * (1 - factor))
            button.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")
        timer.timeout.connect(update_stylesheet)
        timer.start()
        timers.append(timer)
    def stop_breathing_animation(button: QtWidgets.QPushButton):
        for timer in timers:
            if timer.parent() == button:
                timer.stop()
                timers.remove(timer)
        button.setStyleSheet("")  
    try:
        for b in buttons:
            b.setEnabled(False)
            b.setProperty("held", True)  
            b.setProperty("original_style", b.styleSheet() if b.styleSheet() else "")
            start_breathing_animation(b)
            logging.debug(f"Held button: {b.text()}: ({b.objectName()})")
        yield
    finally:
        for b in buttons:
            b.setProperty("held", False)  
            stop_breathing_animation(b)
            b.setStyleSheet(b.property("original_style") if b.property("original_style") else "")
            b.setEnabled(True)  
            logging.debug(f"Released button: {b.text()}: ({b.objectName()})")
def solve_installation_config(
    source: str,
    git_url: str,
    git_tag: str,
    extras: Optional[str],
    package_name: str = 'REvoDesign',
):
    extra_string = f'[{extras}]' if extras else ''
    package_string = f"{package_name}{extra_string}"
    logging.info(f"Installing as {package_string}...")
    if source and source.startswith("https://"):
        package_string += f' @ git+{git_url}{f"@{git_tag}" if git_tag else ""}'
        return package_string
    if os.path.isdir(source):
        if source.endswith("/"):
            source = source[:-1]
        if os.path.exists(os.path.join(source, "pyproject.toml")):
            if git_tag:
                notify_box("Ignore unzipped code directory tag!")
            package_string = f"{source}{extra_string}"
            return package_string
        notify_box(f"{source} should atleast be a Git repository or a code directory!", ValueError)
    if os.path.isfile(source):
        if git_tag:
            notify_box("Ignore zipped file tag!")
        if source.endswith(".zip") or source.endswith(".tar.gz"):
            package_string = f"{source}{extra_string}"
            return package_string
        notify_box(
            f"{source} is neither a zipped file nor a tar.gz file!",
            FileNotFoundError,
        )
    notify_box(f"Unknown installation source {source}({package_name})!", ValueError)
def __init_plugin__(app=None):
    logging.info(f"REvoDesign entrypoint is located at {os.path.dirname(__file__)}")
    plugin = REvoDesignPackageManager()
    addmenuitemqt("REvoDesign Package Manager", plugin.run_plugin_gui)
    if is_package_installed('REvoDesign'):
        try:
            from REvoDesign import REvoDesignPlugin
            plugin = REvoDesignPlugin()
            addmenuitemqt("REvoDesign", plugin.run_plugin_gui)
        except Exception as e:
            logging.error(str(e))
    else:
        logging.critical("REvoDesign is not available.")