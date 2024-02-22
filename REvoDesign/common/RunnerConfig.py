import attrs
from attrs import define, field


@define(kw_only=True)
class REvoDesignRunnerConfig:
    molecule: str = field(converter=str)
    chain_id: str = field(converter=str)
    input_pse: str = field(converter=str)
    output_pse: str = field(converter=str)


@define(kw_only=True)
class SurfaceFinderConfig(REvoDesignRunnerConfig):
    exclude_residue_selection: str = field(converter=str, default='')
    cutoff: float = field(converter=float, default=15)
    do_show_surf_CA: bool = field(converter=bool, default=True)


@define(kw_only=True)
class PocketSearcherConfig(REvoDesignRunnerConfig):
    save_dir: str = field(converter=str, default='.')
    ligand: str = field(converter=str, default='UNK')
    ligand_radius: float = field(converter=float, default=6)
    cofactor: str = field(converter=str, default='')
    cofactor_radius: float = field(converter=float, default=7)
