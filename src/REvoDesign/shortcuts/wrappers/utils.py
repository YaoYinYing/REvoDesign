from REvoDesign.logger.logger import logger_level_setter


from REvoDesign.shortcuts.utils import DialogWrapperRegistry

from ...logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)

registry = DialogWrapperRegistry("logger")

registry.register("logger_level_setter", logger_level_setter)


def wrapped_logger_level_setter():
    """
    Runs the logger_level_setter function with parameters collected from the dialog.
    Args:
        **kwargs: Parameters collected from the dialog.
    """

    registry.call("logger_level_setter")