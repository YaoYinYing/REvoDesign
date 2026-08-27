# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


# Original script marker: /usr/bin/env python

# # GREMLIN_TF
#
# GREMLIN implemented in tensorflow based on paper by Hetu Kamisetty and Sergey Ochinnikov.
# Need a multiple sequence alignment for it to compute couplings.

import os
import pathlib
import pickle  # nosec B403
import sys

import matplotlib
import matplotlib.pylab as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from gremlin_labels import validate_position_label
from scipy import stats
from scipy.spatial.distance import pdist, squareform
from tensorflow.python.framework import ops

matplotlib.use("Agg")


MSA_pth = pathlib.Path(sys.argv[1]).resolve()
pth = pathlib.Path(sys.argv[2]).resolve()
instance = MSA_pth.stem
gremlin_iter = int(sys.argv[3])


# for HPC multi-processors in single node
# edited by Yinying Yao

cpu_num = max(1, int(os.environ.get("GREMLIN_CALC_CPU_NUM", 1)))

config = tf.ConfigProto(
    device_count={"CPU": cpu_num},
    inter_op_parallelism_threads=cpu_num,
    intra_op_parallelism_threads=cpu_num,
    allow_soft_placement=True,
)


# ## libraries

# ## Params


################
# note: if you are modifying the alphabet
# make sure last character is "-" (gap)
################
alphabet = "ARNDCQEGHILKMFPSTWYV-"
states = len(alphabet)
a2n = {}
for amino_acid, state_index in zip(alphabet, range(states)):
    a2n[amino_acid] = state_index


################


def aa2num(aa):
    """convert aa into num"""
    if aa in a2n:
        return a2n[aa]
    return a2n["-"]


# ## Functions for prepping the MSA (Multiple sequence alignment)


# from fasta
def parse_fasta(filename, limit=-1):
    """function to parse fasta"""
    header = []
    sequence = []
    # The CLI user explicitly authorizes this local input path.
    with open(filename) as lines:  # skipcq: PTC-W6004
        for line in lines:
            line = line.rstrip()
            if line[0] == ">":
                if len(header) == limit:
                    break
                header.append(line[1:])
                sequence.append([])
            else:
                sequence[-1].append(line)
    sequence = ["".join(seq) for seq in sequence]
    return np.array(header), np.array(sequence)


def filt_gaps(msa, gap_cutoff=0.5):
    """filters alignment to remove gappy positions"""
    tmp = np.zeros_like(msa)
    tmp[np.where(msa == 20)] = 1
    non_gaps = np.where(np.sum(tmp.T, -1).T / msa.shape[0] < gap_cutoff)[0]
    return msa[:, non_gaps], non_gaps


def get_eff(msa, eff_cutoff=0.8):
    """compute effective weight for each sequence"""
    # pairwise identity
    msa_sm = 1.0 - squareform(pdist(msa, "hamming"))

    # weight for each sequence
    msa_w = np.zeros_like(msa_sm)
    msa_w[np.where(msa_sm >= eff_cutoff)] = 1
    msa_w = 1 / np.sum(msa_w, -1)

    return msa_w


def mk_msa(seqs):
    """converts list of sequences to msa"""

    msa_ori = []
    for seq in seqs:
        msa_ori.append([aa2num(aa) for aa in seq])
    msa_ori = np.array(msa_ori)

    # remove positions with more than > 50% gaps
    msa, v_idx = filt_gaps(msa_ori, 0.5)

    # compute effective weight for each sequence
    msa_weights = get_eff(msa, 0.8)

    # compute effective number of sequences
    ncol = msa.shape[1]  # length of sequence
    w_idx = v_idx[np.stack(np.triu_indices(ncol, 1), -1)]

    return {
        "msa_ori": msa_ori,
        "msa": msa,
        "weights": msa_weights,
        "neff": np.sum(msa_weights),
        "v_idx": v_idx,
        "w_idx": w_idx,
        "nrow": msa.shape[0],
        "ncol": ncol,
        "ncol_ori": msa_ori.shape[1],
    }


# ## GREMLIN

# external functions


def sym_w(w):
    """symmetrize input matrix of shape (x,y,x,y)"""
    x = w.shape[0]
    w = w * np.reshape(1 - np.eye(x), (x, 1, x, 1))
    w = w + tf.transpose(w, [2, 3, 0, 1])
    return w


def opt_adam(loss, name, var_list=None, lr=1.0, b1=0.9, b2=0.999, b_fix=False):
    # adam optimizer
    # Note: this is a modified version of adam optimizer. More specifically, we replace "vt"
    # with sum(g*g) instead of (g*g). Furthmore, we find that disabling the bias correction
    # (b_fix=False) speeds up convergence for our case.

    if var_list is None:
        var_list = tf.trainable_variables()
    gradients = tf.gradients(loss, var_list)
    if b_fix:
        t = tf.Variable(1.0, "t")
    opt = []
    for n, (x, g) in enumerate(zip(var_list, gradients)):
        if g is not None:
            ini = dict(initializer=tf.zeros_initializer, trainable=False)
            mt = tf.get_variable(name + "_mt_" + str(n), shape=x.shape, **ini)
            vt = tf.get_variable(name + "_vt_" + str(n), shape=(1,), **ini)

            mt_tmp = b1 * mt + (1 - b1) * g
            vt_tmp = b2 * vt + (1 - b2) * tf.reduce_sum(tf.square(g))
            lr_tmp = lr / tf.sqrt(vt_tmp)

            if b_fix:
                lr_tmp = lr_tmp * tf.sqrt(1 - tf.pow(b2, t)) / (1 - tf.pow(b1, t))

            opt.append(x.assign_add(-lr_tmp * mt_tmp))
            opt.append(vt.assign(vt_tmp))
            opt.append(mt.assign(mt_tmp))

    if b_fix:
        t.assign_add(1.0)
    return tf.group(opt)


def GREMLIN(msa, opt_type="adam", opt_iter=100, opt_rate=1.0, batch_size=None):
    ##############################################################
    # SETUP COMPUTE GRAPH
    ##############################################################
    # kill any existing tensorflow graph
    # PG added 2020-01-30
    # tf.reset_default_graph()
    ops.reset_default_graph()

    ncol = msa["ncol"]  # length of sequence

    # msa (multiple sequence alignment)
    MSA = tf.placeholder(tf.int32, shape=(None, ncol), name="msa")

    # one-hot encode msa
    OH_MSA = tf.one_hot(MSA, states)

    # msa weights
    MSA_weights = tf.placeholder(tf.float32, shape=(None,), name="msa_weights")

    # 1-body-term of the MRF
    V = tf.get_variable(name="V", shape=[ncol, states], initializer=tf.zeros_initializer)

    # 2-body-term of the MRF
    W = tf.get_variable(name="W", shape=[ncol, states, ncol, states], initializer=tf.zeros_initializer)

    # symmetrize W
    W = sym_w(W)

    def L2(x):
        return tf.reduce_sum(tf.square(x))

    ########################################
    # V + W
    ########################################
    VW = V + tf.tensordot(OH_MSA, W, 2)

    # hamiltonian
    H = tf.reduce_sum(tf.multiply(OH_MSA, VW), axis=2)
    # local Z (parition function)
    Z = tf.reduce_logsumexp(VW, axis=2)

    # Psuedo-Log-Likelihood
    PLL = tf.reduce_sum(H - Z, axis=1)

    # Regularization
    L2_V = 0.01 * L2(V)
    L2_W = 0.01 * L2(W) * 0.5 * (ncol - 1) * (states - 1)

    # loss function to minimize
    loss = -tf.reduce_sum(PLL * MSA_weights) / tf.reduce_sum(MSA_weights)
    loss = loss + (L2_V + L2_W) / msa["neff"]

    ##############################################################
    # MINIMIZE LOSS FUNCTION
    ##############################################################
    if opt_type == "adam":
        opt = opt_adam(loss, "adam", lr=opt_rate)

    # generate input/feed
    def feed(feed_all=False):
        if batch_size is None or feed_all:
            return {MSA: msa["msa"], MSA_weights: msa["weights"]}
        idx = np.random.randint(0, msa["nrow"], size=batch_size)
        return {MSA: msa["msa"][idx], MSA_weights: msa["weights"][idx]}

    # optimize!
    # edited by Yinying Yao
    with tf.Session(config=config) as sess:
        # initialize variables V and W
        sess.run(tf.global_variables_initializer())

        # initialize V
        msa_cat = tf.keras.utils.to_categorical(msa["msa"], states)
        pseudo_count = 0.01 * np.log(msa["neff"])
        V_ini = np.log(np.sum(msa_cat.T * msa["weights"], -1).T + pseudo_count)
        V_ini = V_ini - np.mean(V_ini, -1, keepdims=True)
        sess.run(V.assign(V_ini))

        # compute loss across all data
        def get_loss():
            return round(sess.run(loss, feed(feed_all=True)) * msa["neff"], 2)

        print("starting", get_loss())

        if opt_type == "lbfgs":
            lbfgs = tf.contrib.opt.ScipyOptimizerInterface
            opt = lbfgs(loss, method="L-BFGS-B", options={"maxiter": opt_iter})
            opt.minimize(sess, feed(feed_all=True))

        if opt_type == "adam":
            for i in range(opt_iter):
                sess.run(opt, feed())
                if (i + 1) % max(1, int(opt_iter / 10)) == 0:
                    print("iter", (i + 1), get_loss())

        # save the V and W parameters of the MRF
        V_ = sess.run(V)
        W_ = sess.run(W)

    # only return upper-right triangle of matrix (since it's symmetric)
    tri = np.triu_indices(ncol, 1)
    W_ = W_[tri[0], :, tri[1], :]

    mrf = {"v": V_, "w": W_, "v_idx": msa["v_idx"], "w_idx": msa["w_idx"]}

    return mrf


# ## EXAMPLE


# ===============================================================================
# PREP MSA
# ===============================================================================
# parse fasta
names, input_sequences = parse_fasta(MSA_pth)
print("Alignment has been parsed!")
# process input sequences
msa_data = mk_msa(input_sequences)

mrf_data = GREMLIN(msa_data, opt_iter=gremlin_iter)


# ## Explore the contact map
# ### Contact prediction:
#
# For contact prediction, the W matrix is reduced from LxLx21x21 to LxL matrix
# by taking the L2 norm for each of the 20x20 slices. In the code below, you can
# access this as mtx["raw"]. Further correction (average product correction) is
# then performed to remove entropy effects, producing mtx["apc"]. The relative
# ranking of mtx["apc"] is used to assess importance. When there are enough
# effective sequences (>1000), we find that the top 1.0L contacts are ~90%
# accurate. When the number of effective sequences is lower, NN can help clean
# noise and fill in missing contacts.
#

# ## Functions for extracting contacts from MRF


###################
def normalize(x):
    x = stats.boxcox(x - np.amin(x) + 1.0)[0]
    x_mean = np.mean(x)
    x_std = np.std(x)
    return (x - x_mean) / x_std


def get_mtx(mrf):
    """get mtx given mrf"""

    # l2norm of 20x20 matrices (note: we ignore gaps)
    raw = np.sqrt(np.sum(np.square(mrf["w"][:, :-1, :-1]), (1, 2)))
    raw_sq = squareform(raw)

    # apc (average product correction)
    ap_sq = np.sum(raw_sq, 0, keepdims=True) * np.sum(raw_sq, 1, keepdims=True) / np.sum(raw_sq)
    apc = squareform(raw_sq - ap_sq, checks=False)

    mtx = {"i": mrf["w_idx"][:, 0], "j": mrf["w_idx"][:, 1], "raw": raw, "apc": apc, "zscore": normalize(apc)}
    return mtx


def plot_mtx(mtx, key="zscore", vmin=1, vmax=3):
    """plot the mtx"""
    plt.figure(figsize=(5, 5))
    plt.imshow(squareform(mtx[key]), cmap="Blues", interpolation="none", vmin=vmin, vmax=vmax)
    plt.grid(False)
    plt.show()
    plt.savefig(f"{pth}/{instance}_GREMLIN_mtx.png")


# save mtx file
with open(f"{pth}/{instance}.GREMLIN.mrf.pkl", "wb") as mrf_file:
    pickle.dump(mrf_data, mrf_file)

mtx_data = get_mtx(mrf_data)
plot_mtx(mtx_data)

# ## Look at top co-evolving residue pairs


######################################################################################
# WARNING - WARNING - WARNING
######################################################################################
# - the i,j index starts at 0 (zero)
# - the "first" position = 0
# - often in biology first position of a sequence is 1
#   for this index use i_aa and j_aa!

# adding amino acid to index
mtx_data["i_aa"] = np.array(
    [alphabet[msa_data["msa_ori"][0][position_i]] + "_" + str(position_i + 1) for position_i in mtx_data["i"]]
)
mtx_data["j_aa"] = np.array(
    [alphabet[msa_data["msa_ori"][0][position_j]] + "_" + str(position_j + 1) for position_j in mtx_data["j"]]
)


# load mtx into pandas dataframe
pd_mtx = pd.DataFrame(mtx_data, columns=["i", "j", "apc", "zscore", "i_aa", "j_aa"])

# get contacts with sequence seperation > 5
# sort by zscore, show top 10
top = pd_mtx.loc[pd_mtx["j"] - pd_mtx["i"] > 5].sort_values("zscore", ascending=False)
top.head(5)


# ## Explore the MRF


def plot_v(mrf):
    al_a = list(alphabet)
    v = mrf["v"].T
    mx = np.max((v.max(), np.abs(v.min())))
    plt.figure(figsize=(v.shape[1] / 4, states / 4))
    plt.imshow(-v, cmap="bwr", vmin=-mx, vmax=mx)
    plt.xticks(np.arange(v.shape[1]))
    plt.yticks(np.arange(0, 21))
    plt.grid(False)
    ax = plt.gca()
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, y: mrf["v_idx"][x]))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, y: al_a[x]))


plot_v(mrf_data)


def plot_w(mrf, i, j, i_aa, j_aa):
    i_aa = validate_position_label(i_aa, alphabet)
    j_aa = validate_position_label(j_aa, alphabet)
    n = int(np.where((mrf["w_idx"][:, 0] == i) & (mrf["w_idx"][:, 1] == j))[0])
    w = mrf["w"][n]

    csv_path = pth / f"W_for_positions_{i_aa}_{j_aa}.csv"
    with csv_path.open("w") as f:  # skipcq: PTC-W6004
        f.write(",")
        for k in alphabet:
            f.write(k + ",")
        f.write("\n")
        dummy = 0
        for pos1 in w:
            f.write(alphabet[dummy] + ",")
            for pos2 in pos1:
                f.write(str(round(pos2, 2)) + ",")
            f.write("\n")
            dummy += 1
    mx = np.max((w.max(), np.abs(w.min())))
    plt.figure(figsize=(states / 4, states / 4))
    plt.imshow(-w, cmap="bwr", vmin=-mx, vmax=mx)
    plt.xticks(np.arange(0, states))
    plt.yticks(np.arange(0, states))
    plt.grid(False)

    ax = plt.gca()
    al_a = list(alphabet)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, y: al_a[x]))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, y: al_a[x]))
    plt.title(f"W for positions {i_aa} and {j_aa}")
    plt.savefig(pth / f"W_for_positions_{i_aa}_and_{j_aa}.png")


for contact_rank in range(50):
    contact_i = int(top.iloc[contact_rank]["i"])
    contact_j = int(top.iloc[contact_rank]["j"])
    contact_i_aa = top.iloc[contact_rank]["i_aa"]
    contact_j_aa = top.iloc[contact_rank]["j_aa"]
    plot_w(mrf_data, contact_i, contact_j, contact_i_aa, contact_j_aa)

# ## Useful input features for NN (Neural Networks)
#
# The "apc" values are typically used as input to the NN for contact
# cleaning or structure prediction. Though in recent advances (aka
# DeepMind/Alphafold), the entire MRF was used as the input. More
# specificially LxLx442. The 442 channels are the 21x21 + (raw and/or apc)
# value.


w_out = np.zeros((msa_data["ncol_ori"], msa_data["ncol_ori"], 442))
v_out = np.zeros((msa_data["ncol_ori"], 21))

mrf_ = np.reshape(mrf_data["w"], (-1, 441))
mtx_ = np.expand_dims(mtx_data["apc"], -1)

w_out[(mtx_data["i"], mtx_data["j"])] = np.concatenate((mrf_, mtx_), -1)
w_out += np.transpose(w_out, (1, 0, 2))
v_out[mrf_data["v_idx"]] = mrf_data["v"]

print("w_out", w_out.shape)
print("v_out", v_out.shape)
