# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Module for sidechain solvers manipulation and management.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field

from RosettaPy.utils.escape import print_diff

from REvoDesign import ConfigBus, SingletonAbstract, issues
from REvoDesign.basic import build_plugin_registry
from REvoDesign.basic.mutate_runner import MutateRunnerAbstract
from REvoDesign.logger import ROOT_LOGGER

# Trigger subpackage imports so the registry can discover all runner subclasses.
from REvoDesign.sidechain import mutate_runner as _mutate_runner  # noqa: F401
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb
from REvoDesign.tools.utils import timing

logging = ROOT_LOGGER.getChild(__name__)

RUNNER_REGISTRY = build_plugin_registry(
    base_class=MutateRunnerAbstract,
    package="REvoDesign.sidechain.mutate_runner",
)
ALL_RUNNER_CLASSES: list[type[MutateRunnerAbstract]] = list(RUNNER_REGISTRY.all_classes)
IMPLEMENTED_RUNNER: Mapping[str, type[MutateRunnerAbstract]] = RUNNER_REGISTRY.implemented_map

# Re-export discovered classes so ``from REvoDesign.sidechain import <Name>`` still works.
for _cls in ALL_RUNNER_CLASSES:
    globals()[_cls.__name__] = _cls

__all__ = [
    "MutateRunnerAbstract",
    "SidechainSolver",
    "ALL_RUNNER_CLASSES",
    "IMPLEMENTED_RUNNER",
]


@dataclass(frozen=True)
class MutateRunnerManager:
    installed_worker: list[str] = field(default_factory=lambda: RUNNER_REGISTRY.installed_names)

    @staticmethod
    def get(sidechain_solver_name: str, **kwargs) -> MutateRunnerAbstract:
        return RUNNER_REGISTRY.get(sidechain_solver_name, **kwargs)


@dataclass(frozen=True)
class SidechainSolverConfig:
    sidechain_solver_name: str
    sidechain_solver_radius: float | None
    sidechain_solver_model: str | None

    def reconfigured(self, new_config: "SidechainSolverConfig") -> bool:
        reconfigured = False
        if new_config != self:
            for (k1, v1), (_k2, v2) in zip(asdict(self).items(), asdict(new_config).items()):
                if v1 == v2:
                    continue
                print_diff(k1, {"Before": v1, "After": v2})
            reconfigured = True
        return reconfigured


class SidechainSolver(SingletonAbstract):
    def singleton_init(self):
        # If not, set the instance attributes
        self.bus: ConfigBus = ConfigBus()
        self.mutate_runner: MutateRunnerAbstract = None  # type: ignore
        self.runner_manager = MutateRunnerManager()
        self.cfg: SidechainSolverConfig = self.get_config()

    def setup(self):
        logging.info(f"Using {self.cfg.sidechain_solver_name} as sidechain solver.")

        molecule = self.bus.get_value("ui.header_panel.input.molecule", str, reject_none=True)
        input_pdb = make_temperal_input_pdb(molecule=molecule, reload=False)

        with timing("Setting up sidechain solver"):
            try:
                self.mutate_runner = self.runner_manager.get(
                    self.cfg.sidechain_solver_name,
                    pdb_file=input_pdb,
                    use_model=self.cfg.sidechain_solver_model,
                    radius=self.cfg.sidechain_solver_radius,
                )
                return self
            except Exception as e:
                raise issues.DependencyError(f"Error occurs while trying to get a mutate runner: {e}") from e

    def get_config(self) -> SidechainSolverConfig:
        cfg = SidechainSolverConfig(
            sidechain_solver_name=self.bus.get_widget_value("ui.config.sidechain_solver.use", str),
            sidechain_solver_radius=self.bus.get_widget_value("ui.config.sidechain_solver.repack_radius", float),
            sidechain_solver_model=self.bus.get_widget_value("ui.config.sidechain_solver.model", str),
        )

        return cfg

    def refresh(self) -> "SidechainSolver":
        latest_cfg = self.get_config()
        if not (reconfigured := self.cfg.reconfigured(new_config=latest_cfg)):
            logging.warning(f"SC solver stays unchanged: {self.cfg=}, {latest_cfg=}.")

        if reconfigured or not self.mutate_runner:
            logging.warning(f"Reconfiguring SC solver with {latest_cfg=}...")
            # return a updated
            self.cfg = latest_cfg
            self.setup()

        return self
