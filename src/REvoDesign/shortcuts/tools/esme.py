from typing import Literal

import pandas as pd
from esme import variant

from REvoDesign.basic import ThirdPartyModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.tools.utils import get_cited, require_installed

from .esm2 import Esm1v

ESME_MODELS = Literal['esmc', 'esm1b', 'esm1v', 'esm2', 'esm2_8m']


@require_installed
class ESM1vEfficient(ThirdPartyModuleAbstract):
    installed: bool = is_package_installed('esme')
    name: str = "esm1v-efficient"

    def __init__(
        self,
        model_name: ESME_MODELS,
        sequence: str,
        dms_output: str,
    ):

        self.model_name = model_name
        self.sequence = sequence

        self.dms_output = dms_output

    @get_cited
    def predict(self) -> pd.DataFrame:
        from esme import ESM2

        model = ESM2.from_pretrained(self.model_name)
        return variant.predict_mask_margin(model=model, seq=self.sequence)

    __bibtex_esme__ = {
        'ESM-Efficient': """@article {Celik2024.10.22.619563,
    author = {Celik, Muhammed Hasan and Xie, Xiaohui},
    title = {Efficient Inference, Training, and Fine-tuning of Protein Language Models},
    elocation-id = {2024.10.22.619563},
    year = {2024},
    doi = {10.1101/2024.10.22.619563},
    publisher = {Cold Spring Harbor Laboratory},
    URL = {https://www.biorxiv.org/content/early/2024/10/25/2024.10.22.619563},
    eprint = {https://www.biorxiv.org/content/early/2024/10/25/2024.10.22.619563.full.pdf},
    journal = {bioRxiv}
}"""
    }

    __bibtex__ = {**Esm1v.__bibtex__, **__bibtex_esme__}
