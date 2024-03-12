from typing import Union
from REvoDesign.sidechain_solver.DLPacker import DLPacker_worker
from REvoDesign.sidechain_solver.DunbrackRotamerLib import PyMOL_mutate
from REvoDesign.sidechain_solver.PIPPack import PIPPack_worker
from REvoDesign import WITH_DEPENDENCIES, ConfigBus
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

from REvoDesign import root_logger

from REvoDesign.issues.exceptions import (
    DependencyError,
    PluginNotImplementedError,
)


logging = root_logger.getChild(__name__)

__all__ = [
    'SidechainSolver',
    'PyMOL_mutate',
    'DLPacker_worker',
    'PIPPack_worker',
]


class SidechainSolver:
    def __init__(self):
        self.bus: ConfigBus = ConfigBus()
        self.mutate_runner: Union[
            PyMOL_mutate, DLPacker_worker, PIPPack_worker, None
        ] = None
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
        self.available_sidechain_solvers = list(
            self.bus.get_value('ui.config.sidechain_solver.group')
        )

    def setup(self):
        if not (
            self.sidechain_solver_name
            and self.sidechain_solver_name
            in list(self.available_sidechain_solvers)
        ):
            raise PluginNotImplementedError(
                f'sidechain_solver is not available: {self.sidechain_solver_name=}: {self.available_sidechain_solvers=}'
            )

        logging.info(
            f'Using {self.sidechain_solver_name} as sidechain solver.'
        )

        input_pdb = make_temperal_input_pdb(
            molecule=self.molecule, chain_id=self.chain_id, reload=False
        )
        if self.sidechain_solver_name == 'Dunbrack Rotamer Library':
            self.mutate_runner = PyMOL_mutate(
                molecule=self.molecule, input_session=input_pdb
            )
            return self

        if self.sidechain_solver_name == 'DLPacker':
            if not WITH_DEPENDENCIES.DLPACKER:
                raise DependencyError(
                    f'{self.sidechain_solver_name} is not available in your installation. Aborded..'
                )

            self.mutate_runner = DLPacker_worker(pdb_file=input_pdb)
            self.mutate_runner.reconstruct_area_radius = (
                self.sidechain_solver_radius
            )
            return self
        if self.sidechain_solver_name == 'PIPPack':
            if not WITH_DEPENDENCIES.PIPPACK:
                raise DependencyError(
                    f'{self.sidechain_solver_name} is not available in your installation. Aborded..'
                )
            self.mutate_runner = PIPPack_worker(
                pdb_file=input_pdb, use_model=self.sidechain_solver_model
            )
            return self

        # setup more sidechain solvers here ...

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
