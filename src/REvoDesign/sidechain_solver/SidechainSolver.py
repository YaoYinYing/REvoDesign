from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from typing import List, Mapping, Optional

from RosettaPy.utils.escape import print_diff

from REvoDesign import ConfigBus, SingletonAbstract, issues
from REvoDesign.basic import MutateRunnerAbstract
from REvoDesign.logger import root_logger
from REvoDesign.sidechain_solver.mutate_runner import (DLPacker_worker,
                                                       PIPPack_worker,
                                                       PyMOL_mutate)
from REvoDesign.tools.pymol_utils import make_temperal_input_pdb
from REvoDesign.tools.utils import timing

logging = root_logger.getChild(__name__)
all_runner_c: List[type[MutateRunnerAbstract]] = [
    PyMOL_mutate,
    DLPacker_worker,
    PIPPack_worker,
]


# create table of implemented runners
implemented_runner: Mapping[str, type[MutateRunnerAbstract]] = MappingProxyType(
    {
        c.name: c
        for c in all_runner_c
    }
)

__all__ = [
    'MutateRunnerAbstract',
    'SidechainSolver',
    'PyMOL_mutate',
    'DLPacker_worker',
    'PIPPack_worker',
    'all_runner_c',
    'implemented_runner'
]


@dataclass(frozen=True)
class MutateRunnerManager:
    # create list of installed runners here
    installed_worker: List[str] = field(
        default_factory=lambda: [c.name
                                 for c in all_runner_c if c.installed]
    )

    def get(
        self, sidechain_solver_name: str, **kwargs
    ) -> MutateRunnerAbstract:
        runner_class = implemented_runner[sidechain_solver_name]
        return runner_class(**kwargs)

@dataclass(frozen=True)
class SidechainSolverConfig:
    molecule: str
    sidechain_solver_name: str
    sidechain_solver_radius: Optional[float]
    sidechain_solver_model: Optional[str]

    def reconfigured(self, new_config: 'SidechainSolverConfig') -> bool:
        reconfigured = False
        if new_config != self:
            for (k1, v1), (k2, v2) in zip(asdict(self).items(), asdict(new_config).items()):
                if v1 == v2:
                    continue
                print_diff(k1, {'Before': v1, 'After': v2})
            reconfigured = True
        return reconfigured


class SidechainSolver(SingletonAbstract):
    def __init__(self):
        # Check if the instance has already been initialized
        if not hasattr(self, 'initialized'):
            # If not, set the instance attributes
            self.bus: ConfigBus = ConfigBus()
            self.mutate_runner: MutateRunnerAbstract = None  # type: ignore
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
                self.mutate_runner = self.runner_manager.get(
                    self.cfg.sidechain_solver_name,
                    pdb_file=input_pdb,
                    use_model=self.cfg.sidechain_solver_model,
                    radius=self.cfg.sidechain_solver_radius,
                    molecule=self.cfg.molecule,
                )
                return self
            except Exception as e:
                raise issues.DependencyError(f'Error occurs while trying to get a mutate runner: {e}') from e

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
