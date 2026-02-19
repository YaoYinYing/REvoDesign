# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Shortcut functions of third-party mutant effect predictors
"""

import os
from typing import Literal

import pandas as pd
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign import ROOT_LOGGER
from REvoDesign.basic.abc_third_party_module import ThirdPartyModuleAbstract, TorchModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.common.mutant import Mutant
from REvoDesign.common.mutant_tree import MutantTree
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id, quick_mutagenesis
from REvoDesign.tools.utils import get_cited, require_installed, timing

logging = ROOT_LOGGER.getChild(__name__)

RUN_MODE_T = Literal["single", "additive", "epistatic"]


@require_installed
class ThermoMpnnPredictor(ThirdPartyModuleAbstract, TorchModuleAbstract):
    """
    ThermoMpnnPredictor class for predicting the thermodynamic stability effects of protein mutations.
    It utilizes the ThermoMPNN model to analyze protein structure and sequence to predict stability changes due to mutations.

    Attributes:
        name (str): Name of the predictor, set to 'ThermoMPNN'.
        installed (bool): Indicates if the 'thermompnn' package is installed.
    """

    name: str = "ThermoMPNN"
    installed: bool = is_package_installed("thermompnn")

    def __init__(
        self,
        pdb: str,
        save_dir: str | None = None,
        prefix: str = "thermompnn_ssm",
        chains: list[str] | None = None,
        mode: RUN_MODE_T = "single",
        batch_size: int = 256,
        threshold: float = -0.5,
        distance: float = 5.0,
        ss_penalty: bool = False,
        device: str = "cpu",
    ):
        """
        Initializes the ThermoMpnnPredictor with the given parameters.

        Parameters:
            pdb (str): Path to the PDB file of the protein.
            save_dir (Optional[str]): Directory to save the output files. Defaults to None.
            prefix (str): Prefix for the output files. Defaults to 'thermompnn_ssm'.
            chains (Optional[List[str]]): List of chains to consider. Defaults to None.
            mode (RUN_MODE_T): Mode of operation, either 'single' or 'batch'. Defaults to 'single'.
            batch_size (int): Batch size for processing. Defaults to 256.
            threshold (float): Threshold for some processing criteria. Defaults to -0.5.
            distance (float): Distance threshold for some calculations. Defaults to 5.0.
            ss_penalty (bool): Whether to apply secondary structure penalty. Defaults to False.
            device (str): Device to run the model on, either 'cpu' or 'gpu'. Defaults to 'cpu'.
        """
        self.prefix = prefix
        self.mode = mode
        self.device = device

        from thermompnn import ThermoMPNN

        if save_dir and prefix:
            # Construct the save prefix and create the directory if it doesn't exist
            self.save_prefix = os.path.join(save_dir, prefix)
            os.makedirs(os.path.dirname(self.save_prefix), exist_ok=True)
        else:
            self.save_prefix = ""

        # Load the protein sequence from the PDB file
        self.sequence = RosettaPyProteinSequence.from_pdb(pdb)
        # Initialize the ThermoMPNN application with the provided parameters
        self.app = ThermoMPNN(
            pdb, self.save_prefix, chains, mode, batch_size, threshold, distance, ss_penalty, self.device
        )

    @get_cited
    def run(self) -> pd.DataFrame:
        """
        Runs the ThermoMPNN prediction and returns the results as a DataFrame.

        Returns:
            pd.DataFrame: DataFrame containing the prediction results with columns 'ddG' and 'Mutation',
                          or 'ddG', 'Mutation', and 'dist' depending on the mode.
        """
        # Process the protein and get the results as a DataFrame
        df = self.app.process(save_csv=bool(self.save_prefix))
        # Rename the DataFrame columns based on the mode
        if self.mode == "single":
            df.columns = ["ddG", "Mutation"]
        else:
            df.columns = ["ddG", "Mutation", "dist"]
        return df

    @staticmethod
    def mutant_name2mutant(mutant_id: str, sequences: RosettaPyProteinSequence) -> Mutant:
        """
        Converts a mutant ID string into a Mutant object.

        Parameters:
            mutant_id (str): String representation of the mutant.
            sequences (RosettaPyProteinSequence): Protein sequence object.

        Returns:
            Mutant: Mutant object created from the mutant ID.
        """
        return extract_mutants_from_mutant_id(mutant_string=mutant_id, sequences=sequences, wt_before_chain=True)

    def df2mutant_tree(self, df: pd.DataFrame, sorted_by: Literal["prefix", "positions"] = "prefix") -> MutantTree:
        """
        Converts a DataFrame of mutation predictions into a MutantTree object.

        Parameters:
            df (pd.DataFrame): DataFrame containing mutation predictions.
            sorted_by (Literal['prefix', 'positions']): Sorting criterion for the mutant tree. Defaults to 'prefix'.

        Returns:
            MutantTree: MutantTree object containing the mutation predictions.
        """
        mutant_tree = MutantTree()
        # Iterate over each row in the DataFrame to create Mutant objects and add them to the MutantTree
        for _, row in df.iterrows():
            score: float = row["ddG"]
            mutation: str = row["Mutation"]
            logging.debug(f"{mutation=}, {score=}")
            mutant = self.mutant_name2mutant(mutant_id=f'{mutation.replace(":", "_")}_{score}', sequences=self.sequence)
            mutant.mutant_score = score
            mutant.wt_score = 0

            # Add the mutant to the appropriate branch in the MutantTree
            mutant_tree.add_mutant_to_branch(
                (
                    self.prefix
                    if sorted_by == "prefix"
                    else "TMPNN_" + "_vs_".join(str(m.position) for m in mutant.mutations)
                ),
                mutant.full_mutant_id,
                mutant,
            )

        return mutant_tree

    __bibtex__ = {
        "ThermoMPNN": """@article{
doi:10.1073/pnas.2314853121,
author = {Henry Dieckhaus  and Michael Brocidiacono  and Nicholas Z. Randolph  and Brian Kuhlman },
title = {Transfer learning to leverage larger datasets for improved prediction of protein stability changes},
journal = {Proceedings of the National Academy of Sciences},
volume = {121},
number = {6},
pages = {e2314853121},
year = {2024},
doi = {10.1073/pnas.2314853121},
URL = {https://www.pnas.org/doi/abs/10.1073/pnas.2314853121},
eprint = {https://www.pnas.org/doi/pdf/10.1073/pnas.2314853121},
}""",
        "ThermoMPNN-D": """@article{https://doi.org/10.1002/pro.70003,
author = {Dieckhaus, Henry and Kuhlman, Brian},
title = {Protein stability models fail to capture epistatic interactions of double point mutations},
journal = {Protein Science},
volume = {34},
number = {1},
pages = {e70003},
doi = {https://doi.org/10.1002/pro.70003},
url = {https://onlinelibrary.wiley.com/doi/abs/10.1002/pro.70003},
eprint = {https://onlinelibrary.wiley.com/doi/pdf/10.1002/pro.70003},
year = {2025}
}""",
    }


def shortcut_thermompnn(
    pdb: str,
    save_dir: str | None = "./thermompnn/predicts",
    prefix: str = "ssm",
    chains: list[str] | None = None,
    mode: RUN_MODE_T = "single",
    batch_size: int = 256,
    threshold: float = -0.5,
    distance: float = 5.0,
    ss_penalty: bool = False,
    device: str = "cpu",
    load_to_preview: bool = False,
    top_ranked: int | None = 100,
):
    app = ThermoMpnnPredictor(pdb, save_dir, prefix, chains, mode, batch_size, threshold, distance, ss_penalty, device)

    df = app.run()

    # TODO: add resource usage warnings if top_ranked is not set (<=0 for unlimited)
    if top_ranked and top_ranked > 1:
        df.sort_values(by=["ddG"], inplace=True)
        logging.info(f"Selecting top {top_ranked} mutants...")
        df = df.head(top_ranked)

    with timing("parsing dataframe from ThermoMPNN"):
        mutant_tree = app.df2mutant_tree(df, sorted_by="positions")

    logging.info(f"ThermoMPNN produced {len(mutant_tree.all_mutant_objects)} Mutants.")
    logging.debug(f"{mutant_tree=}")

    if load_to_preview:
        logging.info("Perform visualising...")
        quick_mutagenesis(mutant_tree)

    app.cleanup()

    import gc

    gc.collect()
