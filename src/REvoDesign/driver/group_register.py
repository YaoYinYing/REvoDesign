'''
This module contains all grouped values from widgets for the GUI.
'''

import os
from typing import Dict, List, Tuple

import matplotlib
from Bio.Align import substitution_matrices
from pymol.Qt import QtGui  # type: ignore
from RosettaPy.node import NodeHintT

from ..basic import GroupRegistryItem as GR
from ..tools.customized_widgets import create_cmap_icon


# define actions
class CallableGroupValues:

    @staticmethod
    def list_some_blanks(n=1) -> List[str]:
        return [''] * n

    @staticmethod
    def list_score_matrix() -> List:
        score_matrix = [
            mtx
            for mtx in os.listdir(
                os.path.join(substitution_matrices.__path__[0], "data")  # type: ignore
            )
        ]
        return score_matrix

    @staticmethod
    def list_color_map() -> Dict:
        cmap_group = {
            _cmap: QtGui.QIcon(create_cmap_icon(cmap=_cmap))
            for _cmap in matplotlib.colormaps()
        }
        return cmap_group

    @staticmethod
    def list_installed_mutate_runners() -> List[str]:
        from REvoDesign.sidechain_solver.SidechainSolver import all_runner_c

        return [c.name for c in all_runner_c if c.installed]

    @staticmethod
    def list_all_profile_parsers() -> List[str]:
        from REvoDesign.common.ProfileParsers import all_parser_classes

        return [p.name for p in all_parser_classes]

    @staticmethod
    def list_all_designers() -> List[str]:
        from REvoDesign.magician import all_designer_classes

        return [
            dc.name
            for dc in all_designer_classes
            if dc.installed and not dc.scorer_only
        ]

    @staticmethod
    def list_all_scorers() -> List[str]:
        from REvoDesign.magician import all_designer_classes

        return [dc.name for dc in all_designer_classes if dc.installed]

    @staticmethod
    def list_all_rosetta_node_hints() -> List[str]:

        from REvoDesign.magician.designers.cart_ddg import \
            is_run_node_available

        node_hints: List[NodeHintT] = [
            "native",
            "docker",
            "docker_mpi",
            "mpi",
            "wsl",
            "wsl_mpi",
        ]

        available_run_node_hints = [
            n for n in node_hints if is_run_node_available(n)
        ]

        return available_run_node_hints


# define all group mappers
# Header
GroupCmap = GR("comboBox_cmap", (CallableGroupValues.list_color_map,),)

# Tab Cluster
GroupScoreMatrix = GR("comboBox_cluster_matrix", (CallableGroupValues.list_score_matrix,),)

# Tab Mutate
GroupProfileTypeTabMutate = GR("comboBox_profile_type", (
    CallableGroupValues.list_all_profile_parsers,
    CallableGroupValues.list_all_designers,
),)

# Tab Visualize
GroupProfileTypeTabVisualize = GR("comboBox_profile_type_2", (
    CallableGroupValues.list_some_blanks,  # blank for reading scores from table directly
    CallableGroupValues.list_all_profile_parsers,
    CallableGroupValues.list_all_scorers,
),)

# Tab Interact
GroupScorerTabInteract = GR("comboBox_external_scorer", (CallableGroupValues.list_some_blanks,
                                                         CallableGroupValues.list_all_scorers,))

# Tab Config
GroupSidechainSolver = GR("comboBox_sidechain_solver", (CallableGroupValues.list_installed_mutate_runners,))
GroupRosettaNodeHint = GR("comboBox_rosetta_node_hint", (CallableGroupValues.list_all_rosetta_node_hints,))


# collect all together
GroupRegistryCollection: Tuple[GR, ...] = (
    GroupCmap,
    GroupScoreMatrix,
    GroupProfileTypeTabMutate,
    GroupProfileTypeTabVisualize,
    GroupScorerTabInteract,
    GroupSidechainSolver,
    GroupRosettaNodeHint,
)
