class REvoDesignException(Exception):
    """Base class for all exceptions in the REvoDesign application."""

    ...


# Specific error classes
class ConfigurationError(REvoDesignException):
    """Exception raised for errors in configuration."""

    ...


class PluginError(REvoDesignException):
    """Exception raised for errors related to the PyMOL plugin."""

    ...


class EnzymeDesignError(REvoDesignException):
    """Exception raised for errors during enzyme design."""

    ...


class DependencyError(REvoDesignException):
    """Exception raised for errors related to uninstalled dependency"""

    ...


class PluginNotImplementedError(NotImplementedError):
    """Exception raised when the plugin is not implemented"""

    ...


class ConfigureError(REvoDesignException):
    """Exception raised for errors related to configuration file"""

    ...


class ConfigureOutofDateError(ConfigureError):
    """Exception raised for errors related to  out-of-date configuration file"""

    ...


class UnexpectedWorkflowError(REvoDesignException):
    '''Exception raised when an analysis is not run as expected workflow'''

    ...


class NoInputError(ValueError):
    """Exception raised when an input is missing"""

    ...


class EmptySessionError(ValueError):
    """Exception raised when the current session is empty"""

    ...


class InvalidInputError(ValueError):
    """Exception raised when an input is invalid"""

    ...


class UnknownWidgetError(ValueError):
    """Exception raised when a widget is not defined"""

    ...


class NoResultsError(ValueError):
    """Exception raised for no results"""

    ...


class UnauthorizedError(REvoDesignException):
    """Exception raised when a user is not authorized"""

    ...


class MoleculeUnloadedError(NoInputError):
    """Exception raised when no molecule is loaded"""

    ...


class MoleculeError(InvalidInputError):
    """Exception raised when a molecule uses fuzzy chain id"""

    ...


class SocketError(REvoDesignException):
    """Exception raised during a socket connection"""

    ...


class UnsupportedDataTypeError(SocketError):
    """Exception raised when requiring sending unsupported data type"""

    ...


class FobbidenDataTypeError(SocketError):
    """Exception raised when requiring sending fobbiden data type"""

    ...
