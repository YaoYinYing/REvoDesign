from typing import Any, Callable, Dict, Union
from types import MappingProxyType
from dataclasses import dataclass

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

from REvoDesign.issues.exceptions import (
    DependencyError,
    PluginNotImplementedError,
)


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
    installed_worker: MappingProxyType[str, bool] = MappingProxyType(
        {
            'Dunbrack Rotamer Library': True,
            'DLPacker': WITH_DEPENDENCIES.DLPACKER,
            'PIPPack': WITH_DEPENDENCIES.PIPPACK,
        }
    )

    # Append implemented runner here
    implemented_runner: MappingProxyType[str, Callable] = MappingProxyType(
        {
            'Dunbrack Rotamer Library': PyMOL_mutate,
            'DLPacker': DLPacker_worker,
            'PIPPack': PIPPack_worker,
        }
    )

    def _runner_is_implemented(self, sidechain_solver_name: str) -> bool:
        if sidechain_solver_name in self.implemented_runner:
            return True
        raise PluginNotImplementedError(
            f'sidechain_solver is not available: {sidechain_solver_name=}: {self.implemented_runner=}'
        )

    def _runner_installed(self, sidechain_solver_name: str) -> bool:
        if sidechain_solver_name not in self.installed_worker:
            raise DependencyError(
                f'{sidechain_solver_name} is not available in your installation. Aborted..'
            )
        return self.installed_worker.get(sidechain_solver_name)

    def get_runner(
        self, sidechain_solver_name: str, **kwargs
    ) -> MutateRunnerAbstract:
        if self._runner_installed(
            sidechain_solver_name
        ) and self._runner_is_implemented(sidechain_solver_name):
            runner_class = self.implemented_runner[sidechain_solver_name]
            return runner_class(**kwargs)
        raise RuntimeError(f'Failed to get runner for {sidechain_solver_name}')


class SidechainSolver:
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()
        self.mutate_runner: MutateRunnerAbstract = None

        self.molecule: str = self.bus.get_value(
            'ui.header_panel.input.molecule'
        )
        self.chain_id: str = self.bus.get_value(
            'ui.header_panel.input.chain_id'
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
            molecule=self.molecule, chain_id=self.chain_id, reload=False
        )

        self.mutate_runner = self.runner_manager.get_runner(
            self.sidechain_solver_name,
            pdb_file=input_pdb,
            use_model=self.sidechain_solver_model,
            radius=self.sidechain_solver_radius,
            molecule=self.molecule,
        )
        return self

    @property
    def cfg_updated(self) -> bool:
        molecule: str = self.bus.get_value('ui.header_panel.input.molecule')
        chain_id: str = self.bus.get_value('ui.header_panel.input.chain_id')

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
            chain_id,
            sidechain_solver_name,
            sidechain_solver_radius,
            sidechain_solver_model,
        ]
        old_cfgs = [
            self.molecule,
            self.chain_id,
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
            return SidechainSolver().setup()
        else:
            logging.warning(f'SC solver stays unchanged.')
            return self
