# Exceptions and Warnings

The `REvoDesign.issues` module defines the application's exception and warning
hierarchy. All custom exceptions inherit from `REvoDesignException` and all
custom warnings inherit from `REvoDesignWarning`.

## Exception Hierarchy

::: REvoDesign.issues.exceptions.REvoDesignException
    options:
      show_submodules: false

### Direct subclasses of REvoDesignException

::: REvoDesign.issues.exceptions.InternalError

::: REvoDesign.issues.exceptions.ConfigurationError

::: REvoDesign.issues.exceptions.PluginError

::: REvoDesign.issues.exceptions.EnzymeDesignError

::: REvoDesign.issues.exceptions.DependencyError

::: REvoDesign.issues.exceptions.ConfigureError

::: REvoDesign.issues.exceptions.ConfigureOutofDateError

::: REvoDesign.issues.exceptions.UnexpectedWorkflowError

::: REvoDesign.issues.exceptions.UnauthorizedError

::: REvoDesign.issues.exceptions.SocketError

::: REvoDesign.issues.exceptions.UnsupportedDataTypeError

::: REvoDesign.issues.exceptions.FobbidenDataTypeError

::: REvoDesign.issues.exceptions.FileFormatError

::: REvoDesign.issues.exceptions.BadDataError

### Subclasses of ValueError

::: REvoDesign.issues.exceptions.NoInputError

::: REvoDesign.issues.exceptions.EmptySessionError

::: REvoDesign.issues.exceptions.InvalidInputError

::: REvoDesign.issues.exceptions.MoleculeError

::: REvoDesign.issues.exceptions.UnknownWidgetError

::: REvoDesign.issues.exceptions.NoResultsError

::: REvoDesign.issues.exceptions.MoleculeUnloadedError

### Other exceptions

::: REvoDesign.issues.exceptions.PluginNotImplementedError

::: REvoDesign.issues.exceptions.NetworkError

::: REvoDesign.issues.exceptions.UninstalledPackageError

::: REvoDesign.issues.exceptions.MissingExternalToolError

## Warning Hierarchy

::: REvoDesign.issues.warnings.REvoDesignWarning
    options:
      show_submodules: false

### Direct subclasses of REvoDesignWarning

::: REvoDesign.issues.warnings.PerformanceWarning

::: REvoDesign.issues.warnings.REvoDesignSessionsWarning

::: REvoDesign.issues.warnings.CoevolveAnalysisWarning

::: REvoDesign.issues.warnings.BadDataWarning

::: REvoDesign.issues.warnings.NoResultsWarning

::: REvoDesign.issues.warnings.REvoDesignWidgetWarning

::: REvoDesign.issues.warnings.AlreadyDisconnectedWarning

::: REvoDesign.issues.warnings.DisabledFunctionWarning

::: REvoDesign.issues.warnings.NoInputWarning

::: REvoDesign.issues.warnings.EmptySessionWarning

::: REvoDesign.issues.warnings.InvalidSessionWarning

::: REvoDesign.issues.warnings.FallingBackWarning

::: REvoDesign.issues.warnings.CrystalStructureWarning

::: REvoDesign.issues.warnings.ResidueMissingWarning

::: REvoDesign.issues.warnings.OverridesWarning

::: REvoDesign.issues.warnings.SocketWarning

::: REvoDesign.issues.warnings.SocketUserAlreadyExists

::: REvoDesign.issues.warnings.SocketMessageOverflow

::: REvoDesign.issues.warnings.SocketMeetingRoomIsEmpty

::: REvoDesign.issues.warnings.MissingExternalTool

::: REvoDesign.issues.warnings.MoleculeWarning

### Subclasses of RuntimeWarning (not REvoDesignWarning)

::: REvoDesign.issues.warnings.ConflictWarning

::: REvoDesign.issues.warnings.PlatformNotSupportedWarning

::: REvoDesign.issues.warnings.AppleSiliconRosetta2Warning

::: REvoDesign.issues.warnings.CIRunnerWarning
