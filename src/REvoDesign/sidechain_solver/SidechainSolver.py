import warnings
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from REvoDesign import WITH_DEPENDENCIES, ConfigBus, SingletonAbstract, issues
from REvoDesign.logger import root_logger
from REvoDesign.sidechain_solver.mutate_runner import (DLPacker_worker,
                                                       MutateRunnerAbstract,
                                                       PIPPack_worker,
                                                       PyMOL_mutate)
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb
from REvoDesign.tools.utils import timing

logging = root_logger.getChild(__name__)

__all__ = [
    'MutateRunnerAbstract',
    'SidechainSolver',
    'PyMOL_mutate',
    'DLPacker_worker',
    'PIPPack_worker',
]


@dataclass(frozen=True)
class MutateRunnerManager:
    # Append installed runner here
    installed_worker: Mapping = field(
        default_factory=lambda: MappingProxyType(
            {
                'Dunbrack Rotamer Library': True,
                'DLPacker': WITH_DEPENDENCIES.DLPACKER,
                'PIPPack': WITH_DEPENDENCIES.PIPPACK,
            }
        )
    )

    # Append implemented runner here
    implemented_runner: Mapping = field(
        default_factory=lambda: MappingProxyType(
            {
                'Dunbrack Rotamer Library': PyMOL_mutate,
                'DLPacker': DLPacker_worker,
                'PIPPack': PIPPack_worker,
            }
        )
    )

    def _runner_is_implemented(self, sidechain_solver_name: str) -> bool:
        if sidechain_solver_name not in self.implemented_runner:
            raise issues.PluginNotImplementedError(
                f'sidechain_solver is not available: {sidechain_solver_name=}: {self.implemented_runner=}'
            )
        return True

    def _runner_installed(self, sidechain_solver_name: str) -> bool:
        if not (
            sidechain_solver_name in self.installed_worker
            and self.installed_worker.get(sidechain_solver_name)
        ):
            raise issues.DependencyError(
                f'{sidechain_solver_name} is not available in your installation. Aborted..'
            )
        return True

    def avaliable(self, sidechain_solver_name: str) -> bool:
        return self._runner_installed(
            sidechain_solver_name
        ) and self._runner_is_implemented(sidechain_solver_name)

    def get_runner(
        self, sidechain_solver_name: str, **kwargs
    ) -> MutateRunnerAbstract:
        if self.avaliable(sidechain_solver_name):
            runner_class = self.implemented_runner[sidechain_solver_name]
            return runner_class(**kwargs)


@dataclass(frozen=True)
class SidechainSolverConfig:
    molecule: str
    sidechain_solver_name: str
    sidechain_solver_radius: float
    sidechain_solver_model: str

    def dump(self) -> tuple[str, float]:
        return (
            self.molecule,
            self.sidechain_solver_name,
            self.sidechain_solver_radius,
            self.sidechain_solver_model,
        )

    def reconfigured(self, new_config: 'SidechainSolverConfig') -> bool:
        reconfigured = False
        for _new_cfg, _old_cfg in zip(new_config.dump(), self.dump()):
            if _new_cfg != _old_cfg:
                logging.warning(
                    f'SC solver changed: {_old_cfg=} -> {_new_cfg=}'
                )
                reconfigured = True
        return reconfigured


class SidechainSolver(SingletonAbstract):
    def __init__(self):
        # Check if the instance has already been initialized
        if not hasattr(self, 'initialized'):
            # If not, set the instance attributes
            self.bus: ConfigBus = ConfigBus()
            self.mutate_runner: MutateRunnerAbstract = None
            self.runner_manager = MutateRunnerManager()
            self.cfg: SidechainSolverConfig = self.get_config()
            # Mark the instance as initialized to prevent reinitialization
            self.initialized = True

    def setup(self):
        logging.info(
            f'Using {self.cfg.sidechain_solver_name} as sidechain solver.'
        )

        input_pdb = make_temperal_input_pdb(
            molecule=self.cfg.molecule, reload=False
        )

        with timing('Setting up sidechain solver'):
            try:
                self.mutate_runner = self.runner_manager.get_runner(
                    self.cfg.sidechain_solver_name,
                    pdb_file=input_pdb,
                    use_model=self.cfg.sidechain_solver_model,
                    radius=self.cfg.sidechain_solver_radius,
                    molecule=self.cfg.molecule,
                )
                return self
            except issues.DependencyError:
                self.fallback().setup()
                return self

    def fallback(self) -> 'SidechainSolver':
        warnings.warn(
            issues.FallingBackWarning(
                f'{self.cfg.sidechain_solver_name=} can not be accessed, fallback to `Dunbrack Rotamer Library`'
            )
        )
        self.bus.set_widget_value(
            'ui.config.sidechain_solver.default',
            'Dunbrack Rotamer Library',
            hard=True,
        )
        self.cfg = self.get_config()
        return self

    def get_config(self) -> SidechainSolverConfig:
        cfg = SidechainSolverConfig(
            molecule=self.bus.get_value('ui.header_panel.input.molecule'),
            sidechain_solver_name=self.bus.get_widget_value(
                'ui.config.sidechain_solver.default'
            ),
            sidechain_solver_radius=self.bus.get_widget_value(
                'ui.config.sidechain_solver.repack_radius', float
            ),
            sidechain_solver_model=self.bus.get_widget_value(
                'ui.config.sidechain_solver.model'
            ),
        )

        return cfg

    def refresh(self) -> 'SidechainSolver':
        latest_cfg = self.get_config()
        if not (reconfigured := self.cfg.reconfigured(new_config=latest_cfg)):
            logging.warning(
                f'SC solver stays unchanged: {self.cfg=}, {latest_cfg=}.'
            )

        if reconfigured or not self.mutate_runner:
            logging.warning(f'Reconfiguring SC solver with {latest_cfg=}...')
            # return a updated
            self.cfg = latest_cfg
            self.setup()

        return self
