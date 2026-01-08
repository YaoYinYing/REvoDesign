"""
Basic module that contains some basic classes and functions.
"""

from .abc_singleton import SingletonAbstract, reset_singletons
from .data_structure import IterableLoop
from .extensions import FileExtension, FileExtensionCollection
from .group_registries import GroupRegistryItem
from .menu_item import MenuCollection, MenuItem
from .param_toggle import ParamChangeRegister, ParamChangeRegistryItem

__all__ = [
    "SingletonAbstract",
    "reset_singletons",
    "IterableLoop",
    "FileExtension",
    "FileExtensionCollection",
    "GroupRegistryItem",
    "ParamChangeRegistryItem",
    "ParamChangeRegister",
    "MenuItem",
    "MenuCollection",
]
