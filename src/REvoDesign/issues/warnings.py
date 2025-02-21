'''
Warnings for REvoDesign
'''


class REvoDesignWarning(Warning):
    """Base class for all warnings in the REvoDesign application."""


class PerformanceWarning(REvoDesignWarning):
    """Warning raised for potential performance issues."""


class REvoDesignSessionsWarning(REvoDesignWarning):
    """Warning raised for PyMOL sessions used by REvoDesign"""


class CoevolveAnalysisWarning(REvoDesignWarning):
    """Warning raised for GREMLIN Tools"""


class BadDataWarning(REvoDesignWarning):
    """Warning raised for discarding bad data"""


class NoResultsWarning(REvoDesignWarning):
    """Warning raised for no results"""


class REvoDesignWidgetWarning(REvoDesignWarning):
    """Warning raised for Qt Widgets"""


class AlreadyDisconnectedWarning(REvoDesignWidgetWarning):
    """Warning raised for disconnect trials from QtWidget signals"""


class DisabledFunctionWarning(REvoDesignWarning):
    """Warning raised for disabled functions"""


class ConflictWarning(RuntimeWarning):
    """Warning raised for existed configuration conflicts against runtime program"""


class NoInputWarning(REvoDesignWarning):
    """Warning raised when an input is missing"""


class EmptySessionWarning(REvoDesignWarning):
    """Warning raised when the current session is empty"""


class InvalidSessionWarning(REvoDesignWarning):
    """Warning raised when the current session is invalid"""


class FallingBackWarning(REvoDesignWarning):
    """Warning raised when failing back to default behavior from failed imports"""


class CrystalStructureWarning(REvoDesignWarning):
    """Warning raised when a crystal structure is detected"""


class ResidueMissingWarning(CrystalStructureWarning):
    """Warning raised when reading molecule sequence from a crystal structure"""


class OverridesWarning(REvoDesignWarning):
    """Warning raised when overriding something"""


class PlatformNotSupportedWarning(RuntimeWarning):
    """Warning raised when a platform is not supported"""


class AppleSiliconRosetta2Warning(PlatformNotSupportedWarning):
    """Warning raised if PyMOL is run under Rosetta2 translation"""


class CIRunnerWarning(PlatformNotSupportedWarning):
    """Warning raised when a CI Runner is detected by unexpected platform behaviours are catched"""


class MoleculeWarning(NoInputWarning):
    """Warning raised when a molecule uses fuzzy chain id"""


class SocketWarning(REvoDesignWarning):
    """Warning about a socket event"""


class SocketUserAlreadyExists(SocketWarning):
    """Warning raised when socket user exists in the meething room"""


class SocketMessageOverflow(SocketWarning):
    """Warning raised when a socket message overflows"""


class SocketMeetingRoomIsEmpty(SocketWarning):
    """Warning raised when a socket has no client"""

class MissingExternalTool(REvoDesignWarning):
    """Warning raised when a external tool is missing"""