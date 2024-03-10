# revo_design_issues.py


class REvoDesignException(Exception):
    """Base class for all exceptions in the REvoDesign application."""

    pass


# Specific error classes
class ConfigurationError(REvoDesignException):
    """Exception raised for errors in configuration."""

    pass


class PluginError(REvoDesignException):
    """Exception raised for errors related to the PyMOL plugin."""

    pass


class EnzymeDesignError(REvoDesignException):
    """Exception raised for errors during enzyme design."""

    pass
