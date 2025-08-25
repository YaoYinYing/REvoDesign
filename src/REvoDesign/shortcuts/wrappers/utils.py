'''
Shortcut wrappers of other utility functions
'''
from REvoDesign.logger.logger import logger_level_setter
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from ...logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
registry = DialogWrapperRegistry("logger")
wrapped_logger_level_setter = registry.register("logger_level_setter", logger_level_setter)