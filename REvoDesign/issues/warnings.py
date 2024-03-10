class REvoDesignWarning(Warning):
    """Base class for all warnings in the REvoDesign application."""

    pass


# Specific warning classes
class DeprecationWarning(REvoDesignWarning):
    """Warning raised for deprecated features."""

    pass


class PerformanceWarning(REvoDesignWarning):
    """Warning raised for potential performance issues."""

    pass
