from typing import Protocol, Tuple

from ..tools.customized_widgets import refresh_widget_while_another_changed
from ..sidechain_solver.SidechainSolver import all_runner_c
from ..common.ProfileParsers import all_parser_classes
from ..external_designer import all_designer_classes
from ..basic import ParamChangeRegistryItem as PCRI, ParamChangeRegister as PCR


# write all connected cases
ParamChangeSidechainSolverWeights=PCRI(
    "comboBox_sidechain_solver",
    "currentIndexChanged",
    "ui.config.sidechain_solver.use",
    "ui.config.sidechain_solver.model",
    {
        c.name: (c.weights_preset, c.default_weight_preset,)
        for c in all_runner_c
        if c.installed
    },
)


class ParserOrDesigner(Protocol):
    name: str
    prefer_lower: bool

all_profile_or_designers: Tuple[type[ParserOrDesigner]]=all_parser_classes + tuple(all_designer_classes) # type: ignore


profile_or_designer_vs_is_prefer_lower_score={profile_or_designer.name: (profile_or_designer.prefer_lower,) for profile_or_designer in all_profile_or_designers}

ParamChangePreferLowerScoreTabMutate=PCRI(
    "comboBox_profile_type",
    "currentIndexChanged",
    "ui.mutate.input.profile_type",
    "ui.header_panel.cmap.reverse_score",
    profile_or_designer_vs_is_prefer_lower_score

)

ParamChangePreferLowerScoreTabVisualize=PCRI(
    "comboBox_profile_type_2",
    "currentIndexChanged",
    "ui.visualize.input.profile_type",
    "ui.header_panel.cmap.reverse_score",
    profile_or_designer_vs_is_prefer_lower_score

)


# collect all of these cases

ParamChangeCollections=PCR(
    register_func=refresh_widget_while_another_changed,
    registry=(
        ParamChangeSidechainSolverWeights,
        ParamChangePreferLowerScoreTabMutate,
        ParamChangePreferLowerScoreTabVisualize
        )
    )



