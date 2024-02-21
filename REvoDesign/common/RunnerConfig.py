import attrs
from attrs import define, Factory, field


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
