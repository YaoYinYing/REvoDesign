from typing import Any, Callable, Dict, Union, Mapping
from types import MappingProxyType
from dataclasses import dataclass, field

from immutabledict import immutabledict
from REvoDesign.sidechain_solver.mutate_runner import (
    MutateRunnerAbstract,
    PyMOL_mutate,
    DLPacker_worker,
    PIPPack_worker,
)

from REvoDesign import WITH_DEPENDENCIES, ConfigBus
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

from REvoDesign import root_logger

from REvoDesign import issues
import warnings

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
        if sidechain_solver_name in self.implemented_runner:
            return True
        raise issues.PluginNotImplementedError(
            f'sidechain_solver is not available: {sidechain_solver_name=}: {self.implemented_runner=}'
        )

    def _runner_installed(self, sidechain_solver_name: str) -> bool:
        if (
            sidechain_solver_name in self.installed_worker
            and self.installed_worker.get(sidechain_solver_name)
        ):
            return self.installed_worker.get(sidechain_solver_name)

        raise issues.DependencyError(
            f'{sidechain_solver_name} is not available in your installation. Aborted..'
        )

    def get_runner(
        self, sidechain_solver_name: str, **kwargs
    ) -> MutateRunnerAbstract:
        if self._runner_installed(
            sidechain_solver_name
        ) and self._runner_is_implemented(sidechain_solver_name):
            runner_class = self.implemented_runner[sidechain_solver_name]
            return runner_class(**kwargs)
        raise


class SidechainSolver:
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()
        self.mutate_runner: MutateRunnerAbstract = None

        self.molecule: str = self.bus.get_value(
            'ui.header_panel.input.molecule'
        )

        self.sidechain_solver_name = self.bus.get_value(
            'ui.config.sidechain_solver.default'
        )

        self.sidechain_solver_radius = self.bus.get_value(
            'ui.config.sidechain_solver.repack_radius', float
        )
        self.sidechain_solver_model = self.bus.get_value(
            'ui.config.sidechain_solver.model'
        )

        self.runner_manager = MutateRunnerManager()

    def setup(self):
        logging.info(
            f'Using {self.sidechain_solver_name} as sidechain solver.'
        )

        input_pdb = make_temperal_input_pdb(
            molecule=self.molecule, reload=False
        )

        try:
            self.mutate_runner = self.runner_manager.get_runner(
                self.sidechain_solver_name,
                pdb_file=input_pdb,
                use_model=self.sidechain_solver_model,
                radius=self.sidechain_solver_radius,
                molecule=self.molecule,
            )
            return self
        except issues.DependencyError:
            fallback_sidechain_solver = self.fallback()
            fallback_sidechain_solver.mutate_runner = (
                fallback_sidechain_solver.runner_manager.get_runner(
                    fallback_sidechain_solver.sidechain_solver_name,
                    pdb_file=input_pdb,
                    use_model=fallback_sidechain_solver.sidechain_solver_model,
                    radius=fallback_sidechain_solver.sidechain_solver_radius,
                    molecule=fallback_sidechain_solver.molecule,
                )
            )
            return fallback_sidechain_solver

    def fallback(self) -> 'SidechainSolver':
        warnings.warn(
            issues.FallingBackWarning(
                f'{self.sidechain_solver_name=} can not be accessed, fallback to `Dunbrack Rotamer Library`'
            )
        )
        self.bus.set_widget_value(
            'ui.config.sidechain_solver.default',
            'Dunbrack Rotamer Library',
            hard=True,
        )
        return self.refresh()

    @property
    def cfg_updated(self) -> bool:
        molecule: str = self.bus.get_value('ui.header_panel.input.molecule')

        sidechain_solver_name = self.bus.get_value(
            'ui.config.sidechain_solver.default'
        )

        sidechain_solver_radius = self.bus.get_value(
            'ui.config.sidechain_solver.repack_radius', float
        )
        sidechain_solver_model = self.bus.get_value(
            'ui.config.sidechain_solver.model'
        )

        new_cfgs = [
            molecule,
            sidechain_solver_name,
            sidechain_solver_radius,
            sidechain_solver_model,
        ]
        old_cfgs = [
            self.molecule,
            self.sidechain_solver_name,
            self.sidechain_solver_radius,
            self.sidechain_solver_model,
        ]
        reconfigured = False
        for _new_cfg, _old_cfg in zip(new_cfgs, old_cfgs):
            if _new_cfg != _old_cfg:
                logging.warning(
                    f'SC solver changed: {_old_cfg=} -> {_new_cfg=}'
                )
                reconfigured = True

        return reconfigured

    def refresh(self) -> 'SidechainSolver':
        if self.cfg_updated:
            logging.warning(f'Reconfiguring SC solver...')
            # return a updated
            self = SidechainSolver().setup()
        else:
            logging.warning(f'SC solver stays unchanged.')

        return self
