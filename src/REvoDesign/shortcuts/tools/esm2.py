# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
ESM-1v variant predict
"""

# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import itertools
import os
import string
from typing import Literal

import pandas as pd
from Bio import SeqIO
from immutabledict import immutabledict
from tqdm import tqdm

from REvoDesign import issues
from REvoDesign.basic.abc_third_party_module import ThirdPartyModuleAbstract, TorchModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.tools.download_registry import FileDownloadRegistry
from REvoDesign.tools.utils import get_cited, require_installed

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)


ESM1V_SCORING_STRATEGY_T = Literal["wt-marginals", "pseudo-ppl", "masked-marginals"]

ESM_MODEL_BASE_URL = "https://dl.fbaipublicfiles.com/fair-esm/models"

ESM1V_MODEL_DICT: immutabledict[str, str] = immutabledict(
    {
        "esm-1v_1": "esm1v_t33_650M_UR90S_1",
        "esm-1v_2": "esm1v_t33_650M_UR90S_2",
        "esm-1v_3": "esm1v_t33_650M_UR90S_3",
        "esm-1v_4": "esm1v_t33_650M_UR90S_4",
        "esm-1v_5": "esm1v_t33_650M_UR90S_5",
        "msa-1b": "esm_msa1b_t12_100M_UR50S",
        "esm-2": "esm2_t36_3B_UR50D",
    }
)

ESM1V_WEIGHTS = FileDownloadRegistry(
    name="ESM2", base_url=ESM_MODEL_BASE_URL, registry={f"{v}.pt": None for v in ESM1V_MODEL_DICT.values()}
)


def list_all_esm_variant_predict_model_names() -> list[str]:
    """
    List all ESM-1v variant predict model names.

    Returns:
        list[str]: List of ESM-1v variant predict model names
    """
    return ESM1V_WEIGHTS.list_all_files


def remove_insertions(sequence: str) -> str:
    """Removes any insertions into the sequence. Needed to load aligned sequences in an MSA."""
    # This is an efficient way to delete lowercase characters and insertion characters from a string
    deletekeys = dict.fromkeys(string.ascii_lowercase)
    deletekeys["."] = None
    deletekeys["*"] = None

    translation = str.maketrans(deletekeys)
    return sequence.translate(translation)


def read_msa(filename: str, nseq: int) -> list[tuple[str, str]]:
    """Reads the first nseq sequences from an MSA file, automatically removes insertions.

    The input file must be in a3m format (although we use the SeqIO fasta parser)
    for remove_insertions to work properly."""

    msa = [
        (record.description, remove_insertions(str(record.seq)))
        for record in itertools.islice(SeqIO.parse(filename, "fasta"), nseq)
    ]
    return msa


def label_row(row, sequence, token_probs, alphabet, offset_idx):
    wt, idx, mt = row[0], int(row[1:-1]) - offset_idx, row[-1]
    if sequence[idx] != wt:
        raise ValueError("The listed wildtype does not match the provided sequence")

    wt_encoded, mt_encoded = alphabet.get_idx(wt), alphabet.get_idx(mt)

    # add 1 for BOS
    score = token_probs[0, 1 + idx, mt_encoded] - token_probs[0, 1 + idx, wt_encoded]
    return score.item()


@require_installed
class Esm1v(ThirdPartyModuleAbstract, TorchModuleAbstract):
    name: str = "esm1v"
    installed: bool = is_package_installed("esm2")

    # skipcq: PYL-W0231
    def __init__(
        self,
        model_names: list[str],
        sequence: str,
        dms_output: str,
        checkpoint_dir: str | None = None,
        skip_wt: bool = True,
        mutation_col: str = "mutation",
        offset_idx: int = 0,
        scoring_strategy: ESM1V_SCORING_STRATEGY_T = "wt-marginals",
        msa_path: str | None = None,
        msa_samples: int = 400,
        device: str = "cpu",
    ):
        """
        Initialize Deep Mutation Scan for ESM-1v
        Args:
            model_location: PyTorch model file OR name of pretrained model to download (see README for models)
            sequence: Base sequence to which mutations were applied
            dms_output: CSV file containing the deep mutational scan
            skip_wt: Skip the wild type sequence in the deep mutational scan
            mutation_col: column in the deep mutational scan labeling the mutation as 'AiB'
            offset_idx: Offset of the mutation positions in `--mutation-col`
            scoring_strategy: Scoring strategy for the deep mutational scan
            msa_path: path to MSA in a3m format (required for MSA Transformer)
            msa_samples: number of sequences to select from the start of the MSA

        """
        self.model_names = model_names
        self.checkpoint_dir = checkpoint_dir
        self.sequence = sequence
        self.dms_output = dms_output
        self.skip_wt = skip_wt
        self.mutation_col = mutation_col
        self.offset_idx = offset_idx
        self.scoring_strategy = scoring_strategy
        self.msa_path = msa_path
        self.msa_samples = msa_samples
        self.device = device

        os.makedirs(os.path.dirname(self.dms_output), exist_ok=True)

    def generate_dms_list(self) -> pd.DataFrame:
        """
        Generate Deep Mutation Scan list for ESM-1v.

        Returns:
            pd.DataFrame: Deep Mutation Scan list for ESM-1v
        """

        alphabet = "ARNDCQEGHILKMFPSTWYV"
        if self.skip_wt:
            df_dms = pd.DataFrame(
                [
                    f"{self.sequence[idx]}{idx + 1}{mut}"
                    for idx, mut in itertools.product(range(0, len(self.sequence)), alphabet)
                    if self.sequence[idx] != mut
                ],
                columns=[self.mutation_col],
            )
        else:
            df_dms = pd.DataFrame(
                [
                    f"{self.sequence[idx]}{idx + 1}{mut}"
                    for idx, mut in itertools.product(range(0, len(self.sequence)), alphabet)
                ],
                columns=[self.mutation_col],
            )
        return df_dms

    def _resolve_model_weight(self, model_name: str):
        """
        Resolve and get the model weight file path

        This function decides whether to load the model from a local checkpoint directory or download
        it from a remote server based on the configuration. If a checkpoint directory is configured,
        it will load from local first; otherwise it downloads from the default ESM1V weight server.

        Args:
            model_name (str): Model name used to construct the model file path

        Returns:
            str: Full path to the model weight file

        Raises:
            issues.ConfigureError: When the checkpoint directory is misconfigured or the model file does not exist
        """
        # Load model from local checkpoint directory
        if self.checkpoint_dir:
            expected_model_path = os.path.join(self.checkpoint_dir, model_name)
            # Verify that the checkpoint directory exists and contains the specified model file
            if not (os.path.isdir(self.checkpoint_dir) and os.path.isfile(expected_model_path)):
                raise issues.ConfigureError(
                    "Checkpoint directory is expected to be existing and containing model checkpoint file."
                    "If you dont have model checkpoint file, please keep it as blank."
                )

            logging.info(f"Loading model from {expected_model_path=}")
            return expected_model_path

        # Download model from remote server
        logging.info(f"Fetching model {model_name=} from {ESM1V_WEIGHTS.base_url}")
        return ESM1V_WEIGHTS.setup(model_name).downloaded

    @get_cited
    def predict(self):
        import torch
        from esm2 import MSATransformer, pretrained  # type: ignore

        # Load the deep mutational scan
        df = self.generate_dms_list()

        # inference for each model
        for model_name in self.model_names:
            model_path = self._resolve_model_weight(model_name)
            model, alphabet = pretrained.load_model_and_alphabet(model_path)
            model.eval()
            if self.device != "cpu":
                model = model.to(self.device)
                logging.info(f"Transferred model to {self.device}")

            batch_converter = alphabet.get_batch_converter()

            if isinstance(model, MSATransformer):
                if self.msa_path is None:
                    raise ValueError("MSA Transformer requires an MSA file")
                data = [read_msa(self.msa_path, self.msa_samples)]
                if self.scoring_strategy != "masked-marginals":
                    raise NotImplementedError("MSA Transformer only supports masked marginal strategy")

                _unused_batch_labels, _unused_batch_strs, batch_tokens = batch_converter(data)

                all_token_probs = []
                for i in tqdm(range(batch_tokens.size(2))):
                    batch_tokens_masked = batch_tokens.clone()
                    batch_tokens_masked[0, 0, i] = alphabet.mask_idx  # mask out first sequence
                    with torch.no_grad():
                        token_probs = torch.log_softmax(model(batch_tokens_masked.to(self.device))["logits"], dim=-1)
                    all_token_probs.append(token_probs[:, 0, i])  # vocab size
                token_probs = torch.cat(all_token_probs, dim=0).unsqueeze(0)
                df[model_name] = df.apply(
                    lambda row, token_probs=token_probs, alphabet=alphabet: label_row(
                        row[self.mutation_col], self.sequence, token_probs, alphabet, self.offset_idx
                    ),
                    axis=1,
                )

            else:
                data = [
                    ("protein1", self.sequence),
                ]
                _unused_batch_labels, _unused_batch_strs, batch_tokens = batch_converter(data)

                if self.scoring_strategy == "wt-marginals":
                    with torch.no_grad():
                        token_probs = torch.log_softmax(model(batch_tokens.to(self.device))["logits"], dim=-1)
                    df[model_name] = df.apply(
                        lambda row, token_probs=token_probs, alphabet=alphabet: label_row(
                            row[self.mutation_col],
                            self.sequence,
                            token_probs,
                            alphabet,
                            self.offset_idx,
                        ),
                        axis=1,
                    )
                elif self.scoring_strategy == "masked-marginals":
                    all_token_probs = []
                    for i in tqdm(range(batch_tokens.size(1))):
                        batch_tokens_masked = batch_tokens.clone()
                        batch_tokens_masked[0, i] = alphabet.mask_idx
                        with torch.no_grad():
                            token_probs = torch.log_softmax(
                                model(batch_tokens_masked.to(self.device))["logits"], dim=-1
                            )
                        all_token_probs.append(token_probs[:, i])  # vocab size
                    token_probs = torch.cat(all_token_probs, dim=0).unsqueeze(0)
                    df[model_name] = df.apply(
                        lambda row, token_probs=token_probs, alphabet=alphabet: label_row(
                            row[self.mutation_col],
                            self.sequence,
                            token_probs,
                            alphabet,
                            self.offset_idx,
                        ),
                        axis=1,
                    )
                elif self.scoring_strategy == "pseudo-ppl":
                    tqdm.pandas()
                    df[model_name] = df.progress_apply(
                        lambda row, model=model, alphabet=alphabet: self.compute_pppl(
                            row[self.mutation_col], self.sequence, model, alphabet, self.offset_idx
                        ),
                        axis=1,
                    )  # type: ignore

        df.to_csv(self.dms_output)

    def compute_pppl(self, row, sequence, model, alphabet, offset_idx):
        import torch

        wt, idx, mt = row[0], int(row[1:-1]) - offset_idx, row[-1]
        if sequence[idx] != wt:
            raise ValueError("The listed wildtype does not match the provided sequence")

        # modify the sequence
        sequence = sequence[:idx] + mt + sequence[(idx + 1) :]

        # encode the sequence
        data = [
            ("protein1", sequence),
        ]

        batch_converter = alphabet.get_batch_converter()

        _unused_batch_labels, _unused_batch_strs, batch_tokens = batch_converter(data)

        _unused_wt_encoded, _unused_mt_encoded = alphabet.get_idx(wt), alphabet.get_idx(mt)

        # compute probabilities at each position
        log_probs = []
        for i in range(1, len(sequence) - 1):
            batch_tokens_masked = batch_tokens.clone()
            batch_tokens_masked[0, i] = alphabet.mask_idx
            with torch.no_grad():
                token_probs = torch.log_softmax(model(batch_tokens_masked.to(self.device))["logits"], dim=-1)
            log_probs.append(token_probs[0, i, alphabet.get_idx(sequence[i])].item())  # vocab size
        return sum(log_probs)

    __bibtex__ = {
        "ESM": """@article{rives2019biological,
  author={Rives, Alexander and Meier, Joshua and Sercu, Tom and Goyal, Siddharth and Lin, Zeming and Liu, Jason and Guo, Demi and Ott, Myle and Zitnick, C. Lawrence and Ma, Jerry and Fergus, Rob},
  title={Biological Structure and Function Emerge from Scaling Unsupervised Learning to 250 Million Protein Sequences},
  year={2019},
  doi={10.1101/622803},
  url={https://www.biorxiv.org/content/10.1101/622803v4},
  journal={PNAS}
}""",
        "ESM-1v": """@article{meier2021language,
  author = {Meier, Joshua and Rao, Roshan and Verkuil, Robert and Liu, Jason and Sercu, Tom and Rives, Alexander},
  title = {Language models enable zero-shot prediction of the effects of mutations on protein function},
  year={2021},
  doi={10.1101/2021.07.09.450648},
  url={https://www.biorxiv.org/content/10.1101/2021.07.09.450648v1},
  journal={bioRxiv}
}""",
        "MSA Transformer": """@article{rao2021msa,
  author = {Rao, Roshan and Liu, Jason and Verkuil, Robert and Meier, Joshua and Canny, John F. and Abbeel, Pieter and Sercu, Tom and Rives, Alexander},
  title={MSA Transformer},
  year={2021},
  doi={10.1101/2021.02.12.430858},
  url={https://www.biorxiv.org/content/10.1101/2021.02.12.430858v1},
  journal={bioRxiv}
}""",
        "ESM-2": """@article{lin2022language,
  title={Language models of protein sequences at the scale of evolution enable accurate structure prediction},
  author={Lin, Zeming and Akin, Halil and Rao, Roshan and Hie, Brian and Zhu, Zhongkai and Lu, Wenting and Smetanin, Nikita and dos Santos Costa, Allan and Fazel-Zarandi, Maryam and Sercu, Tom and Candido, Sal and others},
  journal={bioRxiv},
  year={2022},
  publisher={Cold Spring Harbor Laboratory}
}""",
    }


def shortcut_esm1v(
    model_names: list[str],
    sequence: str,
    dms_output: str,
    checkpoint_dir: str | None = None,
    skip_wt: bool = True,
    mutation_col: str = "mutation",
    offset_idx: int = 0,
    scoring_strategy: ESM1V_SCORING_STRATEGY_T = "wt-marginals",
    msa_path: str | None = None,
    msa_samples: int = 400,
    device: str = "cpu",
):
    predictor = Esm1v(
        model_names=model_names,
        sequence=sequence,
        dms_output=dms_output,
        checkpoint_dir=checkpoint_dir,
        skip_wt=skip_wt,
        mutation_col=mutation_col,
        offset_idx=offset_idx,
        scoring_strategy=scoring_strategy,
        msa_path=msa_path,
        msa_samples=msa_samples,
        device=device,
    )
    predictor.predict()
    predictor.cleanup()
