# GREMLIN utils: Everything but GREMLIN function

# ------------------------------------------------------------
# "THE BEERWARE LICENSE" (Revision 42):
#  and  wrote this code.
# As long as you retain this notice, you can do whatever you want
# with this stuff. If we meet someday, and you think this stuff
# is worth it, you can buy us a beer in return.
# --Sergey Ovchinnikov and Peter Koo
# ------------------------------------------------------------

'''
https://github.com/sokrypton/GREMLIN_CPP/blob/master/GREMLIN_TF_simple.ipynb
'''

import traceback
from typing import Literal
import matplotlib


matplotlib.use('Agg')
import matplotlib.pylab as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist, squareform
import pickle
import os
from REvoDesign import ConfigBus, root_logger
from dataclasses import dataclass

logging = root_logger.getChild(__name__)


@dataclass
class CoevolvedPair:
    i: int
    j: int
    i_aa: str
    j_aa: str

    zscore: float = 0.0
    transposed: bool = False
    raw_df: pd.DataFrame = None

    png: str = ''
    csv: str = ''

    dist: float = 0.0

    dist_cutoff: float = 0

    @property
    def is_out_of_range(self):
        return self.dist > self.dist_cutoff

    @property
    def df(self) -> pd.DataFrame:
        if self.transposed:
            return self.raw_df.T

        return self.raw_df

    @df.setter
    def df(self, new_df: pd.DataFrame):
        self.raw_df = new_df.copy()

    def __str__(self):
        return f'{self.i}-{self.j} ({self.i_aa}/{self.j_aa}): {self.zscore:.5f} - {self.dist:.3f}/{self.dist_cutoff:.3f} Å'

    def wt(self, resi: Literal['i', 'j']) -> str:
        res: str = getattr(self, f'{resi}_aa')
        wt_resn = res[0]
        return wt_resn

    def pos(self, resi: Literal['i', 'j']) -> str:
        res: str = getattr(self, f'{resi}_aa')
        wt_resn = res.split('_')[-1]
        if not wt_resn.isdigit():
            raise ValueError(f'Failed to parse {wt_resn=} from {res=}')

        return int(wt_resn)

    @property
    def i_1(self) -> int:
        return self.i + 1

    @property
    def j_1(self) -> int:
        return self.j + 1


class GREMLIN_Tools:
    def __init__(self, molecule):
        from REvoDesign.tools.utils import cmap_reverser

        self.pwd = os.getcwd()
        self.bus = ConfigBus()

        self._cmap: str = self.bus.get_value(
            'ui.header_panel.cmap.default', str
        )

        # follow the original cmap style. bwr_r -> bwr
        self.cmap = cmap_reverser(
            cmap=self._cmap,
            reverse=not self.bus.get_value(
                'ui.header_panel.cmap.reverse_score', bool
            ),
        )

        self.alphabet = "ARNDCQEGHILKMFPSTWYV-"
        self.states = len(self.alphabet)
        self.molecule = molecule
        self.sequence = ''

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
            logging.error(f"Sequence not valid: {self.sequence}")
            return None
        elif not os.path.exists(mrf_path):
            logging.error(f"Could not find GREMLIN mrf file: {mrf_path}")
            return None
        else:
            logging.info("GREMLIN mrf is loading ...")
            self.mrf = self.load_mrf(mrf_path)
            logging.info('Done')

    # Other initialization tasks can go here
    # Yinying Note here that all of these following methods are copied from the original GREMLIN with tfv1.
    # Define methods for various tasks/functions within the class, e.g., aa2num, parse_fasta, etc.

    @staticmethod
    def load_mrf(mrf_fp):
        mrf = pickle.load(open(mrf_fp, 'rb'))
        return mrf

    # ## Explore the contact map
    # ### Contact prediction:
    #
    # For contact prediction, the W matrix is reduced from LxLx21x21 to LxL matrix (by taking the L2norm for each of the 20x20). In the code below, you can access this as mtx["raw"]. Further correction (average product correction) is then performed to the mtx["raw"] to remove the effects of entropy, mtx["apc"]. The relative ranking of mtx["apc"] is used to assess importance. When there are enough effective sequences (>1000), we find that the top 1.0L contacts are ~90% accurate! When the number of effective sequences is lower, NN can help clean noise and fill in missing contacts.
    #

    # ## Functions for extracting contacts from MRF

    ###################
    @staticmethod
    def normalize(x):
        x = stats.boxcox(x - np.amin(x) + 1.0)[0]
        x_mean = np.mean(x)
        x_std = np.std(x)
        return (x - x_mean) / x_std

    def get_mtx(self):
        '''get mtx given mrf'''

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
        '''plot the mtx'''
        plt.figure(figsize=(5, 5))
        plt.imshow(
            squareform(self.mtx[key]),
            cmap='Blues',
            interpolation='none',
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
            self.pd_mtx['j'] - self.pd_mtx['i'] > 5
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
    ) -> CoevolvedPair:
        # mark if the df should be transposed
        transposed = True

        logging.warning(f"{i=} {j=}")
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
            logging.warning(
                f"No matching co-evolutionary pairs found for positions {i} and {j}."
            )

            return None

        n = int(matching_indices[0])
        w = self.mrf["w"][n]

        # Extract WT residue positions
        wt_i_aa = a_pair.wt('i')
        wt_j_aa = a_pair.wt('j')

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
        except ValueError as e:
            traceback.print_exc()
            logging.error(
                f"Error occured while processing '{wt_i_aa=}' or '{wt_j_aa=}' from {self.alphabet=}"
            )
            # early return to skip ploting
            logging.error(f'Bad pair: {str(a_pair)}')
            return None

        plt.text(
            wt_j_index,
            wt_i_index,
            'WT',
            color='k',
            ha='center',
            va='center',
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

    def plot_w_a2a(self) -> dict[int, CoevolvedPair]:
        plot_w_fps: dict[int, CoevolvedPair] = {}

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

            plot_w_fps[n] = pair
        return plot_w_fps

    def plot_w_o2a(self, resi) -> dict[int, CoevolvedPair]:
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

            if abs(self.pd_mtx['j'][idx] - self.pd_mtx['i'][idx]) > 5:
                coevolving_pairs.append(
                    (
                        int(w_idx[0]),
                        int(w_idx[1]),
                        self.pd_mtx['i_aa'][idx],
                        self.pd_mtx['j_aa'][idx],
                        self.pd_mtx['zscore'][idx],
                    )
                )

        # Step 3: Sort the coevolving_pairs by zscore in descending order
        coevolving_pairs.sort(key=lambda x: x[4], reverse=True)

        print(coevolving_pairs)

        # Step 4: Select the top N items
        top_N_pairs = coevolving_pairs[: self.topN]

        if not top_N_pairs:
            logging.warning(f'No coevolving pairs found!')
            return {}

        logging.info(f'top {self.topN} items selected: {str(top_N_pairs)}')

        # Step 5: Calculate and plot for each pair
        plot_w_fps: dict[int, CoevolvedPair] = {}

        for n, pair in enumerate(top_N_pairs):
            (i, j, i_aa, j_aa, zscore) = pair
            # if i>j, the i and j in `CoevolvedPair` will be swapped.
            pair_i: CoevolvedPair = self.plot_w(i, j, i_aa, j_aa, n)
            if not pair_i:
                continue
            pair_i.zscore = zscore
            plot_w_fps[n] = pair_i

        return plot_w_fps

    # ## Useful input features for NN (Neural Networks)
    #
    # The "apc" values are typically used as input to the NN for contact cleaning or structure prediction. Though in recent advances (aka DeepMind/Alphafold), the entire MRF was used as the input. More specificially LxLx442. The 442 channels are the 21x21 + (raw and/or apc) value.

    # w_out = np.zeros((msa["ncol_ori"], msa["ncol_ori"], 442))
    # v_out = np.zeros((msa["ncol_ori"], 21))

    # mrf_ = np.reshape(mrf["w"], (-1, 441))
    # mtx_ = np.expand_dims(mtx["apc"], -1)

    # w_out[(mtx["i"], mtx["j"])] = np.concatenate((mrf_, mtx_), -1)
    # w_out += np.transpose(w_out, (1, 0, 2))
    # v_out[mrf["v_idx"]] = mrf["v"]

    # print("w_out", w_out.shape)
    # print("v_out", v_out.shape)
