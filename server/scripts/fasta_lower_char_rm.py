#! python
# created by Yao Yin Ying
# for hhblits a3m alignment file treatment


import pathlib
import re
import sys


# remove lowercase in sequence but not its title
def char_filter(input):
    if re.match(r"^>", input):
        return input
    else:
        for item in "abcdefghijklmnopqrstuvwxyz":
            input = "".join(input.split(item))
        return input


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fasta_lower_char_rm.py hhblits.a3m")
    else:
        input_fn = pathlib.Path(sys.argv[1]).resolve()

        output_fn = input_fn.parent.joinpath(f"{input_fn.stem}_aln.fas")

        with open(output_fn, "w") as out_fn:
            treated = ""
            with open(input_fn) as in_fn:
                in_rd = in_fn.readlines()
                for line in in_rd:
                    treated += char_filter(line)
            out_fn.write(treated)

        print(output_fn)
