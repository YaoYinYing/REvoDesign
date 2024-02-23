from attrs import define, field


@define(kw_only=True)
class REvoDesignRunnerConfig:
    molecule: str = field(converter=str)
    chain_id: str = field(converter=str)
    input_pse: str = field(converter=str)
    output_pse: str = field(converter=str)
