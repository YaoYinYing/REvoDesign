from ..tools.customized_widgets import refresh_widget_while_another_changed
from ..sidechain_solver.SidechainSolver import all_runner_c
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


# collect all of these cases

ParamChangeCollections=PCR(
    register_func=refresh_widget_while_another_changed,
    registry=(ParamChangeSidechainSolverWeights,)
    )



