# GREMLIN utils

import matplotlib

matplotlib.use('Agg')
import matplotlib.pylab as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist, squareform
import pickle
import os, pathlib
from absl import logging


class GREMLIN_Tools:
    def __init__(self, molecule):
        self.pwd = os.getcwd()

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
        plt.imshow(-v, cmap='bwr', vmin=-mx, vmax=mx)
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

    def plot_w(self, i, j, i_aa, j_aa, idx=0):
        transposed = True
        if i > j:
            logging.debug(f"i ({i}) > j ({j})")
            j, i = i, j
            i_aa, j_aa = j_aa, i_aa
            transposed = False

        matching_indices = np.where(
            (self.mrf["w_idx"][:, 0] == i) & (self.mrf["w_idx"][:, 1] == j)
        )[0]

        if len(matching_indices) == 0:
            # No matching pairs found, handle this case
            logging.warning(
                f"No matching co-evolutionary pairs found for positions {i} and {j}."
            )

            return None, None

        n = int(matching_indices[0])
        w = self.mrf["w"][n]

        # Extract WT residue positions
        wt_i_aa = i_aa.split('_')[0]
        wt_j_aa = j_aa.split('_')[0]

        csv_fp = f"{self.pwd}/Top.{idx:02}.W_for_positions_{str(i_aa)}_{str(j_aa)}.csv"

        # Create a dictionary where keys are from self.alphabet and values are from w
        data = {k: w[i] for i, k in enumerate(self.alphabet)}

        # Create a DataFrame from the data dictionary
        df = pd.DataFrame(
            data, index=list(self.alphabet), columns=list(self.alphabet)
        )

        if transposed:
            df = df.T

        # Write the DataFrame to a CSV file
        df.to_csv(csv_fp)

        mx = np.max((w.max(), np.abs(w.min())))
        plt.figure(figsize=(self.states / 4, self.states / 4))
        plt.imshow(-w, cmap='bwr', vmin=-mx, vmax=mx)
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
        wt_i_index = self.alphabet.index(wt_i_aa)
        wt_j_index = self.alphabet.index(wt_j_aa)
        plt.text(
            wt_j_index,
            wt_i_index,
            'WT',
            color='k',
            ha='center',
            va='center',
            fontsize=9,
        )

        plt.title(f"Top.{idx:02}: W for positions {i_aa} and {j_aa}")
        plot_fp = (
            f"{self.pwd}/Top.{idx:02}.W_for_positions_{i_aa}_and_{j_aa}.png"
        )
        plt.savefig(plot_fp)
        matplotlib.pyplot.close()
        return csv_fp, plot_fp

    def plot_w_in_batch(self):
        plot_w_fps = {}

        for n in range(self.topN):
            i = int(self.top.iloc[n]["i"])
            j = int(self.top.iloc[n]["j"])
            i_aa = self.top.iloc[n]["i_aa"]
            j_aa = self.top.iloc[n]["j_aa"]
            zscore = self.top.iloc[n]["zscore"]

            csv_fp, plot_fp = self.plot_w(i, j, i_aa, j_aa, n)

            plot_w_fps[n] = ([i, j, i_aa, j_aa, zscore], csv_fp, plot_fp)
        return plot_w_fps

    def analyze_coevolving_pairs_for_i(self, i):
        # Step 1: Find all items where i is in either column of "w_idx"
        matching_indices = np.where(
            (self.mrf["w_idx"][:, 0] == i) | (self.mrf["w_idx"][:, 1] == i)
        )[0]
        logging.info(f"Found {len(matching_indices)} matching pairs")

        # Step 2: Loop through the matching indices and filter based on sequence separation
        coevolving_pairs = []
        for idx in matching_indices:
            w_idx = self.mrf["w_idx"][idx]
            j = w_idx[1] if w_idx[0] == i else w_idx[0]

            if self.pd_mtx['j'][idx] - self.pd_mtx['i'][idx] > 5:
                coevolving_pairs.append(
                    (
                        i,
                        j,
                        self.pd_mtx['i_aa'][idx],
                        self.pd_mtx['j_aa'][idx],
                        self.pd_mtx['zscore'][idx],
                    )
                )

        # Step 3: Sort the coevolving_pairs by zscore in descending order
        coevolving_pairs.sort(key=lambda x: x[4], reverse=True)

        # logging.debug(coevolving_pairs)

        # Step 4: Select the top N items
        top_N_pairs = coevolving_pairs[: self.topN]

        logging.info(f'top {self.topN} items selected: {str(top_N_pairs)}')

        if not top_N_pairs:
            return

        # Step 5: Calculate and plot for each pair
        plot_w_fps = {}
        for n, pair in enumerate(top_N_pairs):
            (i, j, i_aa, j_aa, zscore) = pair

            csv_fp, plot_fp = self.plot_w(i, j, i_aa, j_aa, n)
            if csv_fp and plot_fp:

                plot_w_fps[n] = ([i, j, i_aa, j_aa, zscore], csv_fp, plot_fp)

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
