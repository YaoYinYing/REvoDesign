'''
Module to register all parameter changes that should be reflected in the UI.
'''
from typing import Protocol
from ..basic import ParamChangeRegister as PCR
from ..basic import ParamChangeRegistryItem as PCRI
from ..common.profile_parsers import ALL_PARSER_CLASSES
from ..magician import ALL_DESIGNER_CLASSES
from ..sidechain.sidechain_solver import ALL_RUNNER_CLASSES
from ..tools.customized_widgets import refresh_widget_while_another_changed
ParamChangeSidechainSolverWeights = PCRI(
    "comboBox_sidechain_solver",
    "currentIndexChanged",
    "ui.config.sidechain_solver.use",
    "ui.config.sidechain_solver.model",
    {
        c.name: (c.weights_preset, c.default_weight_preset,)
        for c in ALL_RUNNER_CLASSES
        if c.installed
    },
)
class ParserOrDesigner(Protocol):
    """
    Protocol class to define the structure for a parser or designer type.
    This class inherits from Protocol and specifies the attributes that any instance conforming to this protocol must have.
    Attributes:
        name (str): The name of the parser or designer.
        prefer_lower (bool): A flag indicating whether the parser or designer prefers lowercase values.
    """
    name: str
    prefer_lower: bool
ALL_PROFILE_OR_DESIGNERS: tuple[type[ParserOrDesigner], ...] = ALL_PARSER_CLASSES + tuple(ALL_DESIGNER_CLASSES)
profile_or_designer_vs_is_prefer_lower_score = {
    profile_or_designer.name: (
        profile_or_designer.prefer_lower,
    ) for profile_or_designer in ALL_PROFILE_OR_DESIGNERS}
ParamChangePreferLowerScoreTabMutate = PCRI(
    "comboBox_profile_type",
    "currentIndexChanged",
    "ui.mutate.input.profile_type",
    "ui.header_panel.cmap.reverse_score",
    profile_or_designer_vs_is_prefer_lower_score
)
ParamChangePreferLowerScoreTabVisualize = PCRI(
    "comboBox_profile_type_2",
    "currentIndexChanged",
    "ui.visualize.input.profile_type",
    "ui.header_panel.cmap.reverse_score",
    profile_or_designer_vs_is_prefer_lower_score
)
ParamChangeCollections = PCR(
    register_func=refresh_widget_while_another_changed,
    registry=(
        ParamChangeSidechainSolverWeights,
        ParamChangePreferLowerScoreTabMutate,
        ParamChangePreferLowerScoreTabVisualize
    )
)