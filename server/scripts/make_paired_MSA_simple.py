# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


# a copy from RosettaFold2

import gzip
import string
import sys
from pathlib import Path

import numpy as np

TABLE = str.maketrans(dict.fromkeys(string.ascii_lowercase))
ALPHABET = np.array(list("ARNDCQEGHILKMFPSTWYV-"), dtype="|S1").view(np.uint8)


def seq2number(seq):
    seq_no_ins = seq.translate(TABLE)
    seq_no_ins = np.array(list(seq_no_ins), dtype="|S1").view(np.uint8)
    for i in range(ALPHABET.shape[0]):
        seq_no_ins[seq_no_ins == ALPHABET[i]] = i
    seq_no_ins[seq_no_ins > 20] = 20

    return seq_no_ins


def calc_seqID(query, cand):
    same = (query == cand).sum()
    return same / float(len(query))


def read_a3m(fn):
    # read sequences in a3m file
    # only take one (having the highest seqID to query) per each taxID
    if fn.split(".")[-1] == "gz":
        with gzip.open(fn, "rt") as fp:
            query, tmp = _read_a3m_taxa(fp)
    else:
        with open(fn) as fp:
            query, tmp = _read_a3m_taxa(fp)

    query_in_num = seq2number(query)
    a3m = {}
    for TaxID in tmp:
        if len(tmp[TaxID]) < 1:
            continue
        if len(tmp[TaxID]) < 2:
            a3m[TaxID] = tmp[TaxID][0]
            continue
        # Get the best sequence only
        score_s = []
        for _seqID, seq in tmp[TaxID]:
            seq_in_num = seq2number(seq)
            score = calc_seqID(query_in_num, seq_in_num)
            score_s.append(score)
        #
        idx = np.argmax(score_s)
        a3m[TaxID] = tmp[TaxID][idx]

    return query, a3m


def _read_a3m_taxa(fp):
    is_first = True
    is_ignore = False
    tmp = {}

    for line in fp:
        if line[0] == ">":
            if is_first:
                continue
            x = line.split()
            seqID = x[0][1:]
            try:
                idx = line.index("OX")
                is_ignore = False
            except ValueError:
                is_ignore = True
                continue
            TaxID = line[idx:].split()[0].split("=")[-1]
            if TaxID not in tmp:
                tmp[TaxID] = []
        else:
            if is_first:
                query = line.strip()
                is_first = False
            elif is_ignore:
                continue
            else:
                tmp[TaxID].append((seqID, line.strip()))

    return query, tmp


if len(sys.argv) == 1:
    print("USAGE: python make_paired_MSA_simple.py [a3m*]")
    sys.exit()

tags = [f"{Path(input_path).stem}_{index}" for index, input_path in enumerate(sys.argv[1:])]
queries = {}
alignments = {}
for tag, input_path in zip(tags, sys.argv[1:]):
    queries[tag], alignments[tag] = read_a3m(input_path)

paired_data = [(9999, "query", "/".join(queries[tag] for tag in tags))]


marked = {}
for tag_index, fn1 in enumerate(tags):

    preseq = ""
    for pre in range(tag_index):
        if pre > 0:
            preseq += "/"
        preseq += "-" * len(queries[tags[pre]])

    for tax in alignments[fn1]:
        name = alignments[fn1][tax][0]
        if tag_index > 0:
            paired_sequence = preseq + "/" + alignments[fn1][tax][1]
        else:
            paired_sequence = alignments[fn1][tax][1]
        ct = 1

        if fn1 + "." + tax in marked:
            continue

        for j in range(tag_index + 1, len(tags)):
            fn2 = tags[j]
            if tax in alignments[fn2]:
                name += " " + alignments[fn2][tax][0]
                paired_sequence += "/"
                paired_sequence += alignments[fn2][tax][1]
                marked[fn2 + "." + tax] = 1
                ct += 1
            else:
                paired_sequence += "/"
                paired_sequence += "-" * len(queries[fn2])

        marked[fn1 + "." + tax] = 1
        paired_data.append((ct, name, paired_sequence))

paired_data = sorted(paired_data, key=lambda x: x[0], reverse=True)
for p in paired_data:
    print(">", p[1])
    print(p[2])
