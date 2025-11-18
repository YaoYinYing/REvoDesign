'''
Shortcut wrappers of other utility functions
'''
from REvoDesign.logger.logger import logger_level_setter
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.tools.utils import convert_residue_ranges

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)

logger_registry = DialogWrapperRegistry("logger")

wrapped_logger_level_setter = logger_registry.register("logger_level_setter", logger_level_setter)


utils_registry = DialogWrapperRegistry("utils")
wrapped_convert_residue_ranges = utils_registry.register("convert_residue_ranges", convert_residue_ranges)