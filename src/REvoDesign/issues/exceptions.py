'''
REvoDesign Exceptions
'''


class REvoDesignException(Exception):
    """Base class for all exceptions in the REvoDesign application."""


class InternalError(REvoDesignException):
    """Exception raised for internal errors that develops during the execution of the program."""

# Specific error classes


class ConfigurationError(REvoDesignException):
    """Exception raised for errors in configuration."""


class PluginError(REvoDesignException):
    """Exception raised for errors related to the PyMOL plugin."""


class EnzymeDesignError(REvoDesignException):
    """Exception raised for errors during enzyme design."""


class DependencyError(REvoDesignException):
    """Exception raised for errors related to uninstalled dependency"""


class PluginNotImplementedError(NotImplementedError):
    """Exception raised when the plugin is not implemented"""


class ConfigureError(REvoDesignException):
    """Exception raised for errors related to configuration file"""


class ConfigureOutofDateError(ConfigureError):
    """Exception raised for errors related to  out-of-date configuration file"""
    def __init__(self, message):
        self.message = 'You probably just updated REvoDesign from an older version that. \n'+ message
        super().__init__(message)
        


class UnexpectedWorkflowError(REvoDesignException):
    """Exception raised when an analysis is not run as expected workflow"""


class NoInputError(ValueError):
    """Exception raised when an input is missing"""


class EmptySessionError(ValueError):
    """Exception raised when the current session is empty"""


class InvalidInputError(ValueError):
    """Exception raised when an input is invalid"""


class UnknownWidgetError(ValueError):
    """Exception raised when a widget is not defined"""


class NoResultsError(ValueError):
    """Exception raised for no results"""


class UnauthorizedError(REvoDesignException):
    """Exception raised when a user is not authorized"""


class MoleculeUnloadedError(NoInputError):
    """Exception raised when no molecule is loaded"""


class MoleculeError(InvalidInputError):
    """Exception raised when a molecule uses fuzzy chain id"""


class SocketError(REvoDesignException):
    """Exception raised during a socket connection"""


class UnsupportedDataTypeError(SocketError):
    """Exception raised when requiring sending unsupported data type"""


class FobbidenDataTypeError(SocketError):
    """Exception raised when requiring sending fobbiden data type"""


class NetworkError(ConnectionAbortedError):
    """Exception raised when a network error occurs"""


class UninstalledPackageError(Exception):
    """Exception raised when a package is not installed"""


class MissingExternalToolError(Exception):
    """Exception raised when a required external tool is not installed"""
