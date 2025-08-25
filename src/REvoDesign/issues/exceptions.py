class REvoDesignException(Exception):
class InternalError(REvoDesignException):
class ConfigurationError(REvoDesignException):
class PluginError(REvoDesignException):
class EnzymeDesignError(REvoDesignException):
class DependencyError(REvoDesignException):
class PluginNotImplementedError(NotImplementedError):
class ConfigureError(REvoDesignException):
class ConfigureOutofDateError(ConfigureError):
    def __init__(self, message):
        self.message = 'You probably just updated REvoDesign from an older version that. \n' + message
        super().__init__(message)
class UnexpectedWorkflowError(REvoDesignException):
class NoInputError(ValueError):
class EmptySessionError(ValueError):
class InvalidInputError(ValueError):
class UnknownWidgetError(ValueError):
class NoResultsError(ValueError):
class UnauthorizedError(REvoDesignException):
class MoleculeUnloadedError(NoInputError):
class MoleculeError(InvalidInputError):
class SocketError(REvoDesignException):
class UnsupportedDataTypeError(SocketError):
class FobbidenDataTypeError(SocketError):
class NetworkError(ConnectionAbortedError):
class UninstalledPackageError(Exception):
class MissingExternalToolError(Exception):
    """Exception raised when a required external tool is not installed"""