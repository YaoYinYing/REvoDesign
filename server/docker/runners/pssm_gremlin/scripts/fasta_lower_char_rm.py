# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


# Original script marker: python
# created by Yao Yin Ying
# for hhblits a3m alignment file treatment


import pathlib
import string
import sys

LOWERCASE_TRANSLATION = str.maketrans(dict.fromkeys(string.ascii_lowercase))


# remove lowercase in sequence but not its title
def char_filter(text):
    if text.startswith(">"):
        return text
    return text.translate(LOWERCASE_TRANSLATION)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fasta_lower_char_rm.py hhblits.a3m")
    else:
        input_fn = pathlib.Path(sys.argv[1]).resolve()

        output_fn = input_fn.parent.joinpath(f"{input_fn.stem}_aln.fas")

        with open(output_fn, "w") as out_fn, open(input_fn) as in_fn:
            for line in in_fn:
                out_fn.write(char_filter(line))

        print(output_fn)
