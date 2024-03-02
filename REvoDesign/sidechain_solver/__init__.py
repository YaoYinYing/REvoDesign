from dataclasses import dataclass
from typing import Union
from attrs import define, field
from REvoDesign.sidechain_solver.DLPacker import DLPacker_worker
from REvoDesign.sidechain_solver.DunbrackRotamerLib import PyMOL_mutate
from REvoDesign.sidechain_solver.PIPPack import PIPPack_worker
from REvoDesign.tools.post_installed import WITH_DEPENDENCIES
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

from REvoDesign.REvoDesign import logging as logger


logging = logger.getChild(__name__)

__all__ = [
    'SidechainSolver',
    'PyMOL_mutate',
    'DLPacker_worker',
    'PIPPack_worker',
]


@dataclass
class SidechainSolverConfig:
    molecule: str = field(converter=str)
    chain_id: str = field(converter=str)
    sidechain_solver_name: str = field(converter=str)
    sidechain_solver_model: str = field(converter=str)
    sidechain_solver_radius: float = field(converter=float, default=0)
    available_sidechain_solvers: list = field(converter=list)
    mutate_runner: Union[
        PyMOL_mutate, DLPacker_worker, PIPPack_worker, None
    ] = None


class SidechainSolver(SidechainSolverConfig):
    def setup(self):
        if not (
            self.sidechain_solver_name
            and self.sidechain_solver_name
            in list(self.available_sidechain_solvers)
        ):
            logging.error(
                f'Sidechain solver is not available: {self.sidechain_solver}'
            )
            return self

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

        elif self.sidechain_solver_name == 'DLPacker':
            if not WITH_DEPENDENCIES.DLPACKER:
                logging.error(
                    'DLPacker is not available in your installation. Aborded..'
                )
                return self

            self.mutate_runner = DLPacker_worker(pdb_file=input_pdb)
            self.mutate_runner.reconstruct_area_radius = (
                self.sidechain_solver_radius
            )
            return self
        elif self.sidechain_solver_name == 'PIPPack':
            if not WITH_DEPENDENCIES.PIPPACK:
                logging.error(
                    'PIPPack is not available in your installation. Aborded..'
                )
                return self
            self.mutate_runner = PIPPack_worker(
                pdb_file=input_pdb, use_model=self.sidechain_solver_model
            )
        else:
            raise NotImplementedError

        # setup more sidechain solvers here ...

    def refresh(
        self,
        molecule,
        chain_id,
        sidechain_solver_name,
        sidechain_solver_radius,
        sidechain_solver_model,
    ):
        if not (
            self.molecule == molecule
            and chain_id == chain_id
            and self.sidechain_solver_name == sidechain_solver_name
            and self.sidechain_solver_radius == sidechain_solver_radius
            and self.sidechain_solver_model == sidechain_solver_model
        ):
            self.sidechain_solver_name == sidechain_solver_name
            self.sidechain_solver_radius == sidechain_solver_radius
            self.sidechain_solver_model == sidechain_solver_model
            return self.setup()
