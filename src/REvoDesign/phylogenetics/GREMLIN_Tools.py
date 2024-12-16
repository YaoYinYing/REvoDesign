'''
GREMLIN utils: Everything but GREMLIN function

Original License:
------------------------------------------------------------
"THE BEERWARE LICENSE" (Revision 42):
 and  wrote this code.
As long as you retain this notice, you can do whatever you want
with this stuff. If we meet someday, and you think this stuff
is worth it, you can buy us a beer in return.
--Sergey Ovchinnikov and Peter Koo
------------------------------------------------------------

from:
    https://github.com/sokrypton/GREMLIN_CPP/blob/master/GREMLIN_TF_simple.ipynb
'''


import os
import pickle
import traceback
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

import matplotlib
import matplotlib.pylab as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist, squareform

from REvoDesign import ConfigBus, issues
from REvoDesign.citations import CitableModuleAbstract
from REvoDesign.logger import root_logger

logging = root_logger.getChild(__name__)
matplotlib.use("Agg")


@dataclass
class CoevolvedPair:
    """A data class that represents a coevolved pair of amino acids.

    """
    # zero-indexed positions
    i: int
    j: int
    i_aa: str
    j_aa: str

    homochains_dist: Dict[str, float] = field(default_factory=dict)

    zscore: float = 0.0
    transposed: bool = False
    raw_df: pd.DataFrame = None

    png: str = ""
    csv: str = ""

    selection_string: str = ""

    dist_cutoff: float = 0

    @property
    def homochain_mode(self) -> bool:
        return len(self.homochains_dist) > 1

    @property
    def empty(self) -> bool:
        return not bool(self.homochains_dist)

    @property
    def homochains(self) -> tuple[str]:
        return tuple(self.homochains_dist.keys())

    def is_out_of_range(self, chain_pair: str) -> bool:
        return self.dist(chain_pair=chain_pair) > self.dist_cutoff

    @property
    def min_dist(self):
        if self.empty:
            warnings.warn(
                issues.NoInputWarning(f"Pair {repr(self)} is empty! ")
            )
            return -1
        return min(d for d in self.homochains_dist.values() if d > 0)

    def dist(self, chain_pair: str) -> float:
        dist = self.homochains_dist.get(chain_pair)
        if not dist:
            raise issues.NoResultsError(
                f"{chain_pair=} not in {self.homochains_dist=}"
            )
        return float(dist)

    @property
    def all_out_of_range(self) -> bool:
        return all(self.is_out_of_range(c) for c in self.homochains)

    @property
    def df(self) -> pd.DataFrame:
        if self.transposed:
            return self.raw_df.T

        return self.raw_df

    @df.setter
    def df(self, new_df: pd.DataFrame):
        self.raw_df = new_df.copy()

    def __repr__(self):
        return f'{"homo" if self.homochain_mode else "mono"}.{self.i_1}{self.wt("i")}_{self.j_1}{self.wt("j")}'

    def __str__(self):
        dist = {c: f"{float(d):.2f}" for c, d in self.homochains_dist.items()}
        return f"{self.i}-{self.j} ({self.i_aa}/{self.j_aa}): {self.zscore:.5f} - {dist}/{self.dist_cutoff:.2f} Å"

    def wt(self, resi: Literal["i", "j"]) -> str:
        res: str = getattr(self, f"{resi}_aa")
        wt_resn = res[0]
        return wt_resn

    def pos(self, resi: Literal["i", "j"]) -> str:
        res: str = getattr(self, f"{resi}_aa")
        wt_resn = res.split("_")[-1]
        if not wt_resn.isdigit():
            raise ValueError(f"Failed to parse {wt_resn=} from {res=}")

        return int(wt_resn)

    def res_pair(
        self,
        chain_pair: str,
    ) -> tuple[str]:
        if chain_pair not in self.homochains_dist:
            raise ValueError(
                f"No such {chain_pair=} in {self.homochains_dist=}"
            )

        assert len(chain_pair) == 2, f"{len(chain_pair)=} != 2"
        res_pair = (
            f"(c. {chain_pair[0]} and i. {self.i_1})",
            f"(c. {chain_pair[1]} and i. {self.j_1})",
        )

        # logging.debug(f'{res_pair=}')

        return res_pair

    def res_pair_selection(
        self,
        chain_pair: str,
    ) -> str:
        res_1, res_2 = self.res_pair(chain_pair)
        return f"({res_1} or {res_2})"

    @property
    def all_res_pairs(self) -> dict[str, tuple[str]]:
        all_res_pairs = {
            cc: self.res_pair(chain_pair=cc) for cc in self.homochains_dist
        }
        # logging.debug(f'{all_res_pairs=}')
        return all_res_pairs

    @property
    def all_res_pairs_selections(self) -> dict[str, str]:
        all_res_pairs_selections = {
            cc: self.res_pair_selection(chain_pair=cc)
            for cc in self.homochains_dist
        }
        # logging.debug(f'{all_res_pairs_selections}')
        return all_res_pairs_selections

    @property
    def i_1(self) -> int:
        return self.i + 1

    @property
    def j_1(self) -> int:
        return self.j + 1


class GREMLIN_Tools(CitableModuleAbstract):
    def __init__(self, molecule):
        from REvoDesign.tools.utils import cmap_reverser

        self.pwd = os.getcwd()
        self.bus = ConfigBus()

        self._cmap: str = self.bus.get_value(
            "ui.header_panel.cmap.default", str
        )

        # follow the original cmap style. bwr_r -> bwr
        self.cmap = cmap_reverser(
            cmap=self._cmap,
            reverse=not self.bus.get_value(
                "ui.header_panel.cmap.reverse_score", bool
            ),
        )

        self.alphabet = "ARNDCQEGHILKMFPSTWYV-"
        self.states = len(self.alphabet)
        self.molecule = molecule
        self.sequence = ""

        self.a2n = {}
        for a, n in zip(self.alphabet, range(self.states)):
            self.a2n[a] = n

        self.topN = 50

        # ===============================================================================
        # PREP MSA
        # ===============================================================================
        # parse fasta

    def load_msa_and_mrf(self, mrf_path):
        if not self.sequence:
            raise issues.NoInputError(f"Sequence not valid: {self.sequence}")

        elif not os.path.exists(mrf_path):
            raise issues.InvalidInputError(
                f"Could not find GREMLIN mrf file: {mrf_path}"
            )

        else:
            logging.info("GREMLIN mrf is loading ...")
            self.mrf = self.load_mrf(mrf_path)
            logging.info("Done")

    # Other initialization tasks can go here
    # Yinying Note here that all of these following methods are copied from the original GREMLIN with tfv1.
    # Define methods for various tasks/functions within the class, e.g., aa2num, parse_fasta, etc.

    @staticmethod
    def load_mrf(mrf_fp):
        mrf = pickle.load(open(mrf_fp, "rb"))
        return mrf

    ###################

    @staticmethod
    def normalize(x):
        x = stats.boxcox(x - np.amin(x) + 1.0)[0]
        x_mean = np.mean(x)
        x_std = np.std(x)
        return (x - x_mean) / x_std

    def get_mtx(self):
        """get mtx given mrf"""

        # l2norm of 20x20 matrices (note: we ignore gaps)
        raw = np.sqrt(np.sum(np.square(self.mrf["w"][:, :-1, :-1]), (1, 2)))
        raw_sq = squareform(raw)

        # apc (average product correction)
        ap_sq = (
            np.sum(raw_sq, 0, keepdims=True)
            * np.sum(raw_sq, 1, keepdims=True)
            / np.sum(raw_sq)
        )
        apc = squareform(raw_sq - ap_sq, checks=False)

        mtx = {
            "i": self.mrf["w_idx"][:, 0],
            "j": self.mrf["w_idx"][:, 1],
            "raw": raw,
            "apc": apc,
            "zscore": self.normalize(apc),
        }
        return mtx

    def plot_mtx(self, key="zscore", vmin=1, vmax=3):
        """plot the mtx"""
        plt.figure(figsize=(5, 5))
        plt.imshow(
            squareform(self.mtx[key]),
            cmap="Blues",
            interpolation="none",
            vmin=vmin,
            vmax=vmax,
        )
        plt.grid(False)
        # plt.show()

        plot_gremlin_mtx_fp = (
            f"{self.pwd}/{self.molecule}_GREMLIN_mtx_{key}.png"
        )

        plt.savefig(plot_gremlin_mtx_fp)
        return plot_gremlin_mtx_fp

    def get_to_coevolving_pairs(self):
        self.mtx = self.get_mtx()

        # ## Look at top co-evolving residue pairs

        ######################################################################################
        # WARNING - WARNING - WARNING
        ######################################################################################
        # - the i,j index starts at 0 (zero)
        # - the "first" position = 0
        # - often in biology first position of a sequence is 1
        #   for this index use i_aa and j_aa!

        # adding amino acid to index
        self.mtx["i_aa"] = np.array(
            [self.sequence[i] + "_" + str(i + 1) for i in self.mtx["i"]]
        )
        self.mtx["j_aa"] = np.array(
            [self.sequence[j] + "_" + str(j + 1) for j in self.mtx["j"]]
        )

        # load mtx into pandas dataframe
        self.pd_mtx = pd.DataFrame(
            self.mtx, columns=["i", "j", "apc", "zscore", "i_aa", "j_aa"]
        )

        # get contacts with sequence seperation > 5
        # sort by zscore, show top 10
        self.top = self.pd_mtx.loc[
            self.pd_mtx["j"] - self.pd_mtx["i"] > 5
        ].sort_values("zscore", ascending=False)
        self.top.head(5)

    # ## Explore the MRF

    def plot_v(self):
        al_a = list(self.alphabet)
        v = self.mrf["v"].T
        mx = np.max((v.max(), np.abs(v.min())))
        plt.figure(figsize=(v.shape[1] / 4, self.states / 4))
        plt.imshow(-v, cmap=self.cmap, vmin=-mx, vmax=mx)
        plt.xticks(np.arange(v.shape[1]), rotation=45)
        plt.yticks(np.arange(0, 21))
        plt.grid(False)
        ax = plt.gca()
        ax.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, y: self.mrf["v_idx"][x])
        )
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, y: al_a[x]))

        plot_mrf_fp = f"{self.pwd}/{self.molecule}_GREMLIN_MRF.png"

        plt.savefig(plot_mrf_fp)
        return plot_mrf_fp

    def plot_w(
        self, i: int, j: int, i_aa: str, j_aa: str, idx: int = 0
    ) -> Optional[CoevolvedPair]:
        # mark if the df should be transposed
        transposed = True

        logging.debug(f"{i=} {j=}")
        if i > j:
            j, i = i, j
            i_aa, j_aa = j_aa, i_aa
            transposed = False

        a_pair = CoevolvedPair(
            i=i, j=j, i_aa=i_aa, j_aa=j_aa, transposed=transposed
        )

        matching_indices = np.where(
            (self.mrf["w_idx"][:, 0] == i) & (self.mrf["w_idx"][:, 1] == j)
        )[0]

        if not matching_indices:
            # No matching pairs found, handle this case
            warnings.warn(
                issues.NoResultsWarning(
                    f"No matching co-evolutionary pairs found for positions {i} and {j}."
                )
            )

            return None

        n = int(matching_indices[0])
        w = self.mrf["w"][n]

        # Extract WT residue positions
        wt_i_aa = a_pair.wt("i")
        wt_j_aa = a_pair.wt("j")

        csv_fp = f"{self.pwd}/Top.{idx:02}.W_for_positions_{a_pair.i_aa}_{a_pair.j_aa}.csv"

        # Create a dictionary where keys are from self.alphabet and values are from w
        data = {k: w[i] for i, k in enumerate(self.alphabet)}

        # Create a DataFrame from the data dictionary
        df = pd.DataFrame(
            data, index=list(self.alphabet), columns=list(self.alphabet)
        )

        a_pair.df = df

        # Write the DataFrame to a CSV file
        a_pair.df.to_csv(csv_fp)

        mx = np.max((w.max(), np.abs(w.min())))
        plt.figure(figsize=(self.states / 4, self.states / 4))
        plt.imshow(-w, cmap=self.cmap, vmin=-mx, vmax=mx)
        plt.xticks(np.arange(0, self.states))
        plt.yticks(np.arange(0, self.states))
        plt.grid(False)

        ax = plt.gca()
        al_a = list(self.alphabet)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, y: al_a[x]))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, y: al_a[x]))

        # Add axis titles
        plt.xlabel(f"Position: {j_aa}")
        plt.ylabel(f"Position: {i_aa}")

        # Highlight WT residue pair
        try:
            wt_i_index = self.alphabet.index(wt_i_aa)
            wt_j_index = self.alphabet.index(wt_j_aa)
        except ValueError:
            traceback.print_exc()
            logging.error(
                f"Error occured while processing '{wt_i_aa=}' or '{wt_j_aa=}' from {self.alphabet=}"
            )
            # early return to skip ploting
            warnings.warn(issues.BadDataWarning(f"Bad pair: {str(a_pair)}"))
            return None

        plt.text(
            wt_j_index,
            wt_i_index,
            "WT",
            color="k",
            ha="center",
            va="center",
            fontsize=6,
        )

        plt.title(
            f"Top.{idx:02}: W for positions {a_pair.i_aa} and {a_pair.j_aa}"
        )
        plot_fp = f"{self.pwd}/Top.{idx:02}.W_for_positions_{a_pair.i_aa}_and_{a_pair.j_aa}.png"
        plt.savefig(plot_fp)
        matplotlib.pyplot.close()

        a_pair.csv = csv_fp
        a_pair.png = plot_fp
        return a_pair

    def plot_w_a2a(self) -> tuple[CoevolvedPair, ...]:
        plot_w_fps: List[CoevolvedPair] = []

        for n in range(self.topN):
            i = int(self.top.iloc[n]["i"])
            j = int(self.top.iloc[n]["j"])
            i_aa = self.top.iloc[n]["i_aa"]
            j_aa = self.top.iloc[n]["j_aa"]
            zscore = self.top.iloc[n]["zscore"]

            pair: CoevolvedPair = self.plot_w(i, j, i_aa, j_aa, n)
            if not pair:
                continue
            pair.zscore = zscore

            plot_w_fps.append(pair)
        return tuple(plot_w_fps)

    def plot_w_o2a(self, resi) -> tuple[CoevolvedPair]:
        # Step 1: Find all items where i is in either column of "w_idx"
        matching_indices = np.where(
            (self.mrf["w_idx"][:, 0] == resi)
            | (self.mrf["w_idx"][:, 1] == resi)
        )[0]
        logging.info(f"Found {len(matching_indices)} matching pairs")

        # Step 2: Loop through the matching indices and filter based on sequence separation
        coevolving_pairs = []
        for idx in matching_indices:
            w_idx = self.mrf["w_idx"][idx]

            if abs(self.pd_mtx["j"][idx] - self.pd_mtx["i"][idx]) > 5:
                coevolving_pairs.append(
                    (
                        int(w_idx[0]),
                        int(w_idx[1]),
                        self.pd_mtx["i_aa"][idx],
                        self.pd_mtx["j_aa"][idx],
                        self.pd_mtx["zscore"][idx],
                    )
                )

        # Step 3: Sort the coevolving_pairs by zscore in descending order
        coevolving_pairs.sort(key=lambda x: x[4], reverse=True)

        print(coevolving_pairs)

        # Step 4: Select the top N items
        top_N_pairs = coevolving_pairs[: self.topN]

        if not top_N_pairs:
            warnings.warn(
                issues.NoResultsWarning("No coevolving pairs found!")
            )
            return {}

        logging.info(f"top {self.topN} items selected: {str(top_N_pairs)}")

        # Step 5: Calculate and plot for each pair
        plot_w_fps: List[CoevolvedPair] = []

        for n, pair in enumerate(top_N_pairs):
            (i, j, i_aa, j_aa, zscore) = pair
            # if i>j, the i and j in `CoevolvedPair` will be swapped.
            pair_i: CoevolvedPair = self.plot_w(i, j, i_aa, j_aa, n)
            if not pair_i:
                continue
            pair_i.zscore = zscore
            plot_w_fps.append(pair_i)

        return tuple(plot_w_fps)

    __bibtex__ = {
        matplotlib.__name__: matplotlib.__bibtex__,
        "GREMLIN": r"""@article{
doi:10.1073/pnas.1314045110,
author = {Hetunandan Kamisetty  and Sergey Ovchinnikov  and David Baker },
title = {Assessing the utility of coevolution-based residue–residue contact predictions in a sequence- and structure-rich era},
journal = {Proceedings of the National Academy of Sciences},
volume = {110},
number = {39},
pages = {15674-15679},
year = {2013},
doi = {10.1073/pnas.1314045110},
URL = {https://www.pnas.org/doi/abs/10.1073/pnas.1314045110},
eprint = {https://www.pnas.org/doi/pdf/10.1073/pnas.1314045110},
abstract = {Recently developed methods have shown considerable promise in predicting residue–residue contacts in protein 3D structures using evolutionary covariance information. However, these methods require large numbers of evolutionarily related sequences to robustly assess the extent of residue covariation, and the larger the protein family, the more likely that contact information is unnecessary because a reasonable model can be built based on the structure of a homolog. Here we describe a method that integrates sequence coevolution and structural context information using a pseudolikelihood approach, allowing more accurate contact predictions from fewer homologous sequences. We rigorously assess the utility of predicted contacts for protein structure prediction using large and representative sequence and structure databases from recent structure prediction experiments. We find that contact predictions are likely to be accurate when the number of aligned sequences (with sequence redundancy reduced to 90\%) is greater than five times the length of the protein, and that accurate predictions are likely to be useful for structure modeling if the aligned sequences are more similar to the protein of interest than to the closest homolog of known structure. These conditions are currently met by 422 of the protein families collected in the Pfam database.}}""",
    }
