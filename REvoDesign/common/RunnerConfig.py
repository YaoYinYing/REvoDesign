from dataclasses import dataclass


@dataclass
class REvoDesignRunnerConfig:
    molecule: str
    chain_id: str
    input_pse: str
    output_pse: str
