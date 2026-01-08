"""
Shortcut functions of structure representation
"""

import warnings
from dataclasses import dataclass
from functools import cached_property

import numpy as np
import pandas as pd
from Bio.Align import substitution_matrices
from Bio.Data import IUPACData
from immutabledict import immutabledict
from pymol import cmd, util

from REvoDesign import ROOT_LOGGER, issues

from ...tools.mutant_tools import expand_range
from ...tools.pymol_utils import get_molecule_sequence
from ...tools.utils import get_cited

logging = ROOT_LOGGER.getChild(__name__)


def shortcut_real_sc(selection="(all)", representation="lines", hydrogen=False):
    """
    DESCRIPTION
        Set the representation of a molecular structure focusing on the sidechain or alpha carbon.

    USAGE
        real_sc [selection], [representation], [hydrogen]

    PARAMETERS
        selection (str, optional): Atom selection to apply the representation to. Default is '(all)'.
        representation (str, optional): Representation style ('lines', 'sticks', 'spheres', 'dots'). Default is 'lines'.
        hydrogen (bool, optional): Include hydrogens in the representation if True. Default is False.

    EXAMPLES
        real_sc      # Show sidechain or alpha carbon as lines for the entire structure
        real_sc prot # Show sidechain or alpha carbon as lines for the 'prot' selection
        real_sc sticks, hydrogen=True # Show sticks representation including hydrogens

    NOTES
        - The selection is modified to include sidechain or alpha carbon and exclude hydrogens if hydrogen is False.
        - Available representations: 'lines', 'sticks', 'spheres', 'dots'.
    """
    if representation not in ["lines", "sticks", "spheres", "dots"]:
        return
    if not selection:
        return

    cmd.show(
        representation,
        f'{selection} and (sidechain or n. CA) {"and not hydrogens" if not hydrogen else ""}',
    )


def shortcut_color_by_plddt(selection="all", align_target=0, chain_to_align="A"):
    """
    AUTHOR
            Yinying Yao

        DESCRIPTION
                        Color Predicted Protein structure by pLDDT value recorded in
                        b-factor column of PDB file.

        USAGE
                        color_by_plddt selection [, align_target [, chain_to_align]]

        ARGUMENTS
                        selection: object or selection
                        align_target: int. the rank order of target in selections
                        chain_to_align: the chain id that you want to align selection to.

        EXAMPLE
                        color_by_plddt protein_ranked_*, 1, B

    """
    # Alphafold color scheme for plddt
    cmd.set_color("high_lddt_c", [0, 0.325490196078431, 0.843137254901961])
    cmd.set_color(
        "normal_lddt_c",
        [0.341176470588235, 0.792156862745098, 0.976470588235294],
    )
    cmd.set_color("medium_lddt_c", [1, 0.858823529411765, 0.070588235294118])
    cmd.set_color("low_lddt_c", [1, 0.494117647058824, 0.270588235294118])

    # test the scale of predicted_lddt (0~1 or 0~100 ) as b-factors
    cmd.select("test_b_scale", f"b>1 and ({selection})")
    b_scale = cmd.count_atoms("test_b_scale")

    if b_scale > 0:
        cmd.select("high_lddt", f"({selection}) and (b >90 or b =90)")
        cmd.select("normal_lddt", f"({selection}) and ((b <90 and b >70) or (b =70))")
        cmd.select("medium_lddt", f"({selection}) and ((b <70 and b >50) or (b=50))")
        cmd.select("low_lddt", f"({selection}) and ((b <50 and b >0 ) or (b=0))")
    else:
        cmd.select("high_lddt", f"({selection}) and (b >.90 or b =.90)")
        cmd.select(
            "normal_lddt",
            f"({selection}) and ((b <.90 and b >.70) or (b =.70))",
        )
        cmd.select(
            "medium_lddt",
            f"({selection}) and ((b <.70 and b >.50) or (b=.50))",
        )
        cmd.select("low_lddt", f"({selection}) and ((b <.50 and b >0 ) or (b=0))")

    cmd.delete("test_b_scale")

    # set color based on plddt values
    cmd.set("cartoon_color", "high_lddt_c", "high_lddt")  # type: ignore
    cmd.set("cartoon_color", "normal_lddt_c", "normal_lddt")  # type: ignore
    cmd.set("cartoon_color", "medium_lddt_c", "medium_lddt")  # type: ignore
    cmd.set("cartoon_color", "low_lddt_c", "low_lddt")  # type: ignore

    # set background color
    cmd.bg_color("white")

    align_target = int(align_target)
    # align to top model in selections
    if align_target >= 1:
        target = cmd.get_object_list(selection=selection)[align_target - 1]
        chain_list = cmd.get_chains(selection=target)
        if chain_to_align not in chain_list:
            print(
                f"You set chain_to_align as {chain_to_align}, while this chain is not available "
                f"in object {target} chains: {chain_list}."
            )
            print(f"Trying to set target chain as {chain_list[0]}")
            chain_to_align = chain_list[0]

        # align all decoy to the very best one with only trustable regions
        cmd.select(
            "align_temp",
            f"({target}) and chain {chain_to_align} and (high_lddt or normal_lddt)",
        )

        # hide other objects if we dont align all to this align template
        cmd.select("not_aligned_but_enabled", f"(enabled) and not ({selection})")
        cmd.disable("not_aligned_but_enabled")
        # cmd.enable(selection)

        # perform an 'alignto' operation to the selection
        util.mass_align("align_temp", 1, _self=cmd)
        # cmd.cealign(target='align_temp',mobile=selection)

        # re-enable the disabled objects
        cmd.enable("not_aligned_but_enabled")
        cmd.delete("not_aligned_but_enabled")


# see https://pymolwiki.org/index.php/Color_By_Mutations

"""
created by Christoph Malisi.

Creates an alignment of two proteins and superimposes them.
Aligned residues that are different in the two (i.e. mutations) are highlighted and
colored according to their difference in the BLOSUM90 matrix.
Is meant to be used for similar proteins, e.g. close homologs or point mutants,
to visualize their differences.

"""


# Yinying replaced the original blosum90 matrix with biopython code.
blosum90 = substitution_matrices.load("BLOSUM90")

aa_3l = {}
for i, x in enumerate(blosum90.alphabet):  # type: ignore
    if a := IUPACData.protein_letters_1to3.get(x):
        aa_3l[a.upper()] = i
    else:
        aa_3l[x] = i

aa_3l = immutabledict(aa_3l)


def getBlosum90ColorName(aa1, aa2):
    """returns a rgb color name of a color that represents the similarity of the two residues according to
    the BLOSUM90 matrix. the color is on a spectrum from blue to red, where blue is very similar, and
    red very disimilar."""
    # return red for residues that are not part of the 20 amino acids
    if aa1 not in aa_3l or aa2 not in aa_3l:
        return "red"

    # if the two are the same, return blue
    if aa1 == aa2:
        return "blue"
    i1 = aa_3l[aa1]
    i2 = aa_3l[aa2]
    b = blosum90[i1][i2]

    # 3 is the highest score for non-identical substitutions, so substract 4 to get into range [-10, -1]
    b = abs(b - 4)

    # map to (0, 1]:
    b = 1.0 - (b / 10.0)

    # red = [1.0, 0.0, 0.0], blue = [0.0, 0.0, 1.0]
    bcolor = (1.0 - b, 0.0, b)
    col_name = "0x%02x%02x%02x" % tuple(int(b * 0xFF) for b in bcolor)
    return col_name


def shortcut_color_by_mutation(obj1, obj2, waters=0, labels=0):
    """
    DESCRIPTION

                    Creates an alignment of two proteins and superimposes them.
                    Aligned residues that are different in the two (i.e. mutations) are highlighted and
                    colored according to their difference in the BLOSUM90 matrix.
                    Is meant to be used for similar proteins, e.g. close homologs or point mutants,
                    to visualize their differences.

    USAGE

                    color_by_mutation selection1, selection2 [,waters [,labels ]]

    ARGUMENTS

                    obj1: object or selection

                    obj2: object or selection

                    waters: bool (0 or 1). If 1, waters are included in the view, colored
                                                    differently for the both input structures.
                                                    default = 0

                    labels: bool (0 or 1). If 1, the possibly mutated sidechains are
                                                    labeled by their chain, name and id
                                                    default = 0

    EXAMPLE

                    color_by_mutation protein1, protein2

    SEE ALSO

                    super
    """
    # TODO: deprecating the usage of pymol's internal stored variable
    from pymol import CmdException, stored  # type: ignore

    if cmd.count_atoms(obj1) == 0:
        print(f"{obj1} is empty")
        return
    if cmd.count_atoms(obj2) == 0:
        print(f"{obj2} is empty")
        return
    waters = int(waters)
    labels = int(labels)

    # align the two proteins
    aln = "__aln"

    # first, an alignment with 0 cycles (no atoms are rejected, which maximized the number of aligned residues)
    # for some mutations in the same protein this works fine). This is essentially done to get a
    # sequence alignment
    cmd.super(obj1, obj2, object=aln, cycles=0)

    # superimpose the the object using the default parameters to get a slightly better superimposition,
    # i.e. get the best structural alignment
    cmd.super(obj1, obj2)

    stored.resn1, stored.resn2 = [], []
    stored.resi1, stored.resi2 = [], []
    stored.chain1, stored.chain2 = [], []

    # store residue ids, residue names and chains of aligned residues
    cmd.iterate(obj1 + " and name CA and " + aln, "stored.resn1.append(resn)")
    cmd.iterate(obj2 + " and name CA and " + aln, "stored.resn2.append(resn)")

    cmd.iterate(obj1 + " and name CA and " + aln, "stored.resi1.append(resi)")
    cmd.iterate(obj2 + " and name CA and " + aln, "stored.resi2.append(resi)")

    cmd.iterate(obj1 + " and name CA and " + aln, "stored.chain1.append(chain)")
    cmd.iterate(obj2 + " and name CA and " + aln, "stored.chain2.append(chain)")

    mutant_selection = ""
    non_mutant_selection = "none or "
    colors = []

    # loop over the aligned residues
    for n1, n2, i1, i2, c1, c2 in zip(
        stored.resn1,
        stored.resn2,
        stored.resi1,
        stored.resi2,
        stored.chain1,
        stored.chain2,
    ):
        # take care of 'empty' chain names
        if c1 == "":
            c1 = '""'
        if c2 == "":
            c2 = '""'
        if n1 == n2:
            non_mutant_selection += (
                f"(({obj1} and resi {i1} and chain {c1}) or ({obj2} and resi {i2} and chain {c2})) or "
            )
        else:
            mutant_selection += f"(({obj1} and resi {i1} and chain {c1}) or ({obj2} and resi {i2} and chain {c2})) or "
            # get the similarity (according to the blosum matrix) of the two residues and
            c = getBlosum90ColorName(n1, n2)
            colors.append((c, f"{obj2} and resi {i2} and chain {c2} and elem C"))

    if mutant_selection == "":
        raise CmdException("No mutations found")

    # create selections
    cmd.select("mutations", mutant_selection[:-4])
    cmd.select("non_mutations", non_mutant_selection[:-4])
    cmd.select(
        "not_aligned",
        f"({obj1} or {obj2}) and not mutations and not non_mutations",
    )

    # create the view and coloring
    cmd.hide("everything", f"{obj1} or {obj2}")
    cmd.show("cartoon", f"{obj1} or {obj2}")
    cmd.show("lines", f"({obj1} or {obj2}) and ((non_mutations or not_aligned) and not name c+o+n)")
    cmd.show("sticks", f"({obj1} or {obj2}) and mutations and not name c+o+n")
    cmd.color("gray", "elem C and not_aligned")
    cmd.color("white", "elem C and non_mutations")
    cmd.color("blue", f"elem C and mutations and {obj1}")
    for col, sel in colors:
        cmd.color(col, sel)

    cmd.hide("everything", f"(hydro) and ({obj1} or {obj2})")
    cmd.center(f"{obj1} or {obj2}")
    if labels:
        cmd.label("mutations and name CA", '"(%s-%s-%s)"%(chain, resi, resn)')
    if waters:
        cmd.set("sphere_scale", "0.1")  # type: ignore
        cmd.show("spheres", f"resn HOH and ({obj1} or {obj2})")
        cmd.color("red", f"resn HOH and {obj1}")
        cmd.color("salmon", f"resn HOH and {obj2}")
    print(
        f"""
             Mutations are highlighted in blue and red.
             All mutated sidechains of {obj1} are colored blue, the corresponding ones from {obj2} are
             colored on a spectrum from blue to red according to how similar the two amino acids are
             (as measured by the BLOSUM90 substitution matrix).
             Aligned regions without mutations are colored white.
             Regions not used for the alignment are gray.
             NOTE: There could be mutations in the gray regions that were not detected."""
    )
    cmd.delete(aln)
    cmd.deselect()


def _read_b_factors(
    file_path: str,
    label_x: str | int | None = 0,
    label_y: str | int | None = 1,
) -> pd.DataFrame:
    """Reads B-factor values from a text file.

    Args:
        file_path (str): Path to the text file containing B-factor values. CSV, TSV, TXT, XVG,
        label_x (Optional[str]): Optional label for positioning purposes.
        label_y (Optional[str]): Optional label for bfactor purposes.
        index_x (Optional[int]): Optional index for positioning purposes. Default is 0 for the first column.
        index_y (Optional[int]): Optional index for bfactor purposes. Default is 1 for the second column.
    Returns:
        pd.DataFrame: A 2D array of postion: B-factor values.
    """
    from REvoDesign.tools.utils import xvg2df

    df_bfactors = None
    if file_path.endswith(".csv"):
        # read floats from csv file, in col `label` if provided, else first column
        df = pd.read_csv(file_path)

    elif file_path.endswith((".xlsx", ".xls")):
        # read floats from excel file, in col `label` if provided, else first column
        df = pd.read_excel(file_path)
    elif file_path.endswith(".tsv"):
        df = pd.read_csv(file_path, sep="\t")

    elif file_path.endswith(".xvg"):
        df = xvg2df(file_path)

    elif file_path.endswith(".pdb"):
        logging.warning(
            "PDB file detected. Assuming positions are in the ATOM lines and B-factors are in the B-factor column"
        )

        logging.warning("A dataframe with the following columns will be created: position, bfactor")
        # create empty dataframe
        df = pd.DataFrame()
        # read floats from PDB file
        with open(file_path) as inFile:
            # read lines and find the ATOM lines with atom name as 'CA'
            # collect the residue index and bfactor columns, respectively.
            # convert resi to int and bfactor to float and add them to the dataframe

            logging.debug(f"Reading PDB file {file_path}")

            for line in inFile.readlines():
                if line.startswith("ATOM"):
                    # skip non-CA lines
                    if "CA" not in line[13:16]:
                        continue
                    resi = int(line[22:26])
                    # if befactor is missing, set it to 0
                    try:
                        bfactor = float(line[54:60])
                    except ValueError:
                        logging.warning(f"B-factor missing for residue {resi}")
                        bfactor = 0
                    df.loc[resi, "position"] = resi
                    df.loc[resi, "bfactor"] = bfactor
                    logging.debug(f"Read B-factor {bfactor} for residue {resi}")

    elif file_path.endswith(".txt"):
        logging.warning(
            "Plain text file detected. Assuming positions are 1,2,3,... and B-factors are in the first column"
        )
        logging.warning("A dataframe with the following columns will be created: position, bfactor")
        df = pd.DataFrame()
        # read floats from plain text file
        with open(file_path) as inFile:

            # support plain text file by read lines
            bfactor_data = [float(line.strip()) for line in inFile.readlines()]
            logging.debug(f"Read {len(bfactor_data)} B-factors from file {file_path}")
            logging.debug(f"B-factors: {bfactor_data}")
            # reconstruct positions according to the number of lines, a guessed value
            pos_data = [x for x in range(1, len(bfactor_data) + 1)]
            logging.debug(f"Positions: {pos_data}")

            # 2 * N
            df = pd.DataFrame([pos_data, bfactor_data], index=["position", "bfactor"])

            # transpose to N * 2
            df = df.T

            logging.debug(f"Dataframe: {df}")

    else:
        raise issues.FileFormatError(f"Failed to read B-factors from file {file_path}")

    # select columns by label if provided
    if (
        label_x
        and label_x in df.columns
        and isinstance(label_x, str)
        and label_y
        and label_y in df.columns
        and isinstance(label_y, str)
    ):
        logging.debug(f"Selected columns: {label_x}, {label_y}")
        df_bfactors = df[[label_x, label_y]]
    # otherwise, select columns by index
    elif isinstance(label_x, int) and isinstance(label_y, int) and label_x != label_y:
        logging.debug(f"Selected columns by index: {df.columns[label_x]}, {df.columns[label_y]}")
        df_bfactors = df[[df.columns[label_x], df.columns[label_y]]]
    else:
        raise issues.FileFormatError(f"Failed to read B-factors from file {file_path}")
    return df_bfactors


# adapted from pymol script loadBfacts.py
# https://wiki.pymol.org/index.php/Load_new_B-factors
# Gatti-Lafranconi, Pietro (2014). Pymol script: loadBfacts.py. figshare.
# Software. https://doi.org/10.6084/m9.figshare.1176991.v1


load_b_factors_citation: dict[str, str | tuple] = {
    "loadBfacts.py": """@article{Gatti-Lafranconi2014,
author = "Pietro Gatti-Lafranconi",
title = "{Pymol script: loadBfacts.py}",
year = "2014",
month = "9",
url = "https://figshare.com/articles/software/Pymol_script_loadBfacts_py/1176991",
doi = "10.6084/m9.figshare.1176991.v1"
}""",
    "PyMOL - putty": """
@misc{mura2014developmentimplementationpymol,
      title={Development & Implementation of a PyMOL 'putty' Representation},
      author={Cameron Mura},
      year={2014},
      eprint={1407.5211},
      archivePrefix={arXiv},
      primaryClass={q-bio.BM},
      url={https://arxiv.org/abs/1407.5211},
}""",
}


@dataclass(frozen=True)
class BFactor:
    """
    B-factor dataclass

    Attributes:
        mol (str): PyMOL object name
        chain_id (str): Chain ID
        sequence (str): Sequence string
        bfactor_data (pd.DataFrame): B-factor dataframe (N * 2)
            where col 0 is the position column and col 1 is the bfactor colum
            (one-indexed)

        offset (int): Offset to add to the position column.
            If the position column in `bfactor_data` is not zero-indexed,
            set this to the offset to add to the position column so that it can align to the one-indexed.
            Default is 0.


    Normal usage:

        | position | bfactor |
        | -------- | ------- |
        |     1    |   0.1   |
        |     2    |   0.1   |
        |     N    |   0.2   |

        The position column is one-indexed. If not so, a non-zero offset must be set to fix the position column.

        e.g.:

        In original dataframe:

        | position | bfactor |
        | -------- | ------- |
        |     0    |   0.1   |
        |     1    |   0.1   |
        |    N-1   |   0.2   |

        In this case, set `offset` to 1.

        Adjusted dataframe:

        | position | bfactor |
        | -------- | ------- |
        |     1    |   0.1   |
        |     2    |   0.1   |
        |     N    |   0.2   |
    """

    mol: str
    chain_id: str
    sequence: str

    bfactor_data: pd.DataFrame
    offset: int = 0

    @cached_property
    def obj_sel_pymol(self) -> str:
        """
        Return the PyMOL selection string for the object
        """
        return f"{self.mol} and c. {self.chain_id}"

    def get(self, pos_one_idx: int) -> float:
        """
        Get the bfactor value at the given position
        (zero-indexed)

        Args:
            pos_one_idx (int): Position (one-indexed)

        Returns:
            float: Bfactor value
        """
        # retrieve the bfactor value at col 1 where [0] == pos_zero_idx+1
        val = self.bfactor_data[self.bfactor_data.iloc[:, 0] == pos_one_idx + self.offset].iloc[0, 1]
        if not isinstance(val, float):
            logging.warning(
                f"Failed to retrieve B-factor value for position {pos_one_idx} (zero-indexed {pos_one_idx-1})"
            )
            raise issues.InvalidInputError(
                f"Failed to retrieve B-factor value for position {pos_one_idx} (zero-indexed {pos_one_idx-1})"
            )

        return float(val)

    __getitem__ = get

    # this method assumes that the bfactor_data[pos_zero_idx] is the
    # the bfactor value for resi pos_zero_idx+1

    def assign_to_res_pymol(self, pos_one_idx: int, state: int = 0) -> float:
        """
        Assigns the bfactor value to the residue at pos_zero_idx+1
        Returns the bfactor value

        Parameters
        pos_one_idx : int
            The index of the residue to assign the bfactor value to (one-indexed)

        Returns
        float
            The bfactor value
        """
        bfact = self.get(pos_one_idx)
        logging.debug(f"Setting B-factor for position {pos_one_idx} (zero-indexed {pos_one_idx-1}) to {bfact}")
        try:
            cmd.alter_state(
                state=state, selection=f"{self.obj_sel_pymol} and i. {pos_one_idx}", expression=f"b={bfact}"
            )
        except Exception as e:
            logging.error(f"Failed to set B-factor for position {pos_one_idx} (zero-indexed {pos_one_idx-1}): {e}")
            warnings.warn(
                issues.BadDataWarning(
                    f"Failed to set B-factor for position {pos_one_idx} (zero-indexed {pos_one_idx-1})"
                )
            )
        return bfact

    def _rescaled_bfactor_data(self, scale_from: tuple[float, float], scale_dst: tuple[float, float]) -> pd.DataFrame:
        """
        Rescale the B-factor data to a new range.
        Args:
            scale_from (tuple[float, float]): The original range of the B-factor data.
            scale_dst (tuple[float, float]): The new range to which the B-factor data should be scaled.

        Returns:
            np.ndarray: The rescaled B-factor data.
        """
        # retrieve the bfactor data in column 1
        bfact_data = self.bfactor_data.iloc[:, 1]

        # convert the colum to numpy array and interpolate it to the new range
        scaled_bdata = np.interp(bfact_data, scale_from, scale_dst)

        # create a new dataframe by copying the original dataframe and replacing the bfactor data with the scaled data
        df_scaled = self.bfactor_data.copy()
        df_scaled.iloc[:, 1] = scaled_bdata
        return df_scaled

    def rescaled(self, scale_from: tuple[float, float], scale_dst: tuple[float, float]) -> "BFactor":
        """
        Returns a new BFactor object with the B-factor data scaled to a new range.
        Parameters:
            scale_from (tuple[float, float]): The current range of the B-factor data.
            scale_dst (tuple[float, float]): The new range to which the B-factor data should be scaled.

        Returns:
            BFactor: A new BFactor object with the rescaled B-factor data.
        """
        return self.__class__(
            mol=self.mol,
            chain_id=self.chain_id,
            sequence=self.sequence,
            bfactor_data=self._rescaled_bfactor_data(scale_from, scale_dst),
        )

    _read_b_factors = staticmethod(_read_b_factors)


def _load_b_factors(
    mol: str,
    chain_ids: str,
    keep_missing: bool,
    source: str,
    offset: int = 0,
    label_x: str | None = None,
    label_y: str | None = None,
    index_x: int = 0,
    index_y: int = 1,
    pos_slice: str | None = None,
    palette_code: str = "rainbow",
    do_rescale: bool = False,
    scale_min: float = 0.0,
    scale_max: float = 10.0,
    rescale_min: float = 0.0,
    rescale_max: float = 100.0,
    visual: bool = True,
    putty_transform_mode: int = 3,
) -> None:
    """
    Replaces B-factors with a list of values contained in a plain txt file

    Parameters:
        mol (str): Object selection.
        chain_id (str): Chain ID.
        keep_missing (bool): Whether to keep missing residues in sequence.
        source (str): Path to the file containing new B-factor values.
        pos_slice (Optional[str]): Range of one-index positions to apply B-factors to (e.g. "1-100,150-200").
        label_x (Optional[str]): Label for resi column. Will not be used if None.
        label_y (Optional[str]): Label for bfactor column. Will not be used if None.
        index_x (int): Index of resi column. Default is 0 for the first column.
        index_y (int): Index of bfactor column. Default is 1 for the second column.
        offset (int): Offset to apply to positions (default is 0).
        palette (str): Color palette to use for coloring residues.
        do_rescale (bool): Whether to rescale B-factors to a custom range.
        scale_min (float): Minimum original value for rescaling B-factors.
        scale_max (float): Maximum original value for rescaling B-factors.
        rescale_min (float): Minimum target value for rescaling B-factors.
        rescale_max (float): Maximum target value for rescaling B-factors.
        visual (bool): Whether to update visual representation (default is True).
        putty_transform_code (str): Code for Putty transformation (default is 3, absolute nonlinear scaling).

    Returns:
        None

    Raises:
        MoleculeError: If no object is found for the given selection.


    Note:
        spectrum uses space-separated color names.
            - `red yellow blue violet`
        ramp_new uses list-like strings:
            - `['red', 'yellow','blue','violet']`

        Color name definition example:
        ```pymol

        # define custom colors
        set_color c1, [0,0,0]
        set_color c2, [1,0,0]
        set_color c3, [1,1,0]
        set_color c4, [1,1,1]

        # set a ramp using a list of colors
        ramp_new count_start_A_ori, start, [0.0472, 0.353], ['c1', 'c2','c3','c4']

        # show spectrum using custom colors
        spectrum b, c1 c2 c3 c4
        ```

        This provide a possible way to use custom colors in both the spectrum and the ramp.

        How about the cmap from matplotlib?
    """
    from pymol.creating import ramp_spectrum_dict

    logging.debug(f"Loading B-factors from {source} for {mol}, chain {chain_ids}")
    objs = cmd.get_object_list(mol)
    logging.debug(f"Found {len(objs)} objects: {objs}")

    if not objs:
        raise issues.MoleculeError(f"No found object: {mol}")
    obj = objs[0]

    _chain_ids = chain_ids.strip().split(",")

    bfactor_df = _read_b_factors(
        file_path=source,
        label_x=label_x or index_x,
        label_y=label_y or index_y,
    )

    logging.info(f"B-factor dataframe: \n{bfactor_df.head()}")
    logging.debug(f"B-factor dataframe: \n{bfactor_df}")

    def _load_to_one_chain(chain_id: str, state: int = 0):
        bf_chain = BFactor(
            mol=mol,
            chain_id=chain_id,
            sequence=get_molecule_sequence(obj, chain_id=chain_id, keep_missing=keep_missing),
            bfactor_data=bfactor_df,
            offset=offset,
        )
        logging.debug(f"B-factor chain: {bf_chain}")

        logging.debug(f"Using object {obj} for selection {mol}")

        # fetch sequence info
        seq = get_molecule_sequence(obj, chain_id=chain_id, keep_missing=keep_missing)
        logging.debug(f"Sequence: {seq}")

        # set all b-factors to -1.0 before loading new ones
        cmd.alter_state(state=state, selection=bf_chain.obj_sel_pymol, expression="b=-1.0")

        # read new b factor data from csv file or excel file or txt file

        logging.debug(f"Read {len(bf_chain.bfactor_data)} B-factor values from {source}")

        bf_rescale: BFactor | None = None

        if do_rescale:
            bf_rescale = bf_chain.rescaled((scale_min, scale_max), (rescale_min, rescale_max))
            logging.debug(
                f"Rescaling B-factor values from [{scale_min}, {scale_max}] to [{rescale_min}, {rescale_max}]"
            )

            logging.warning(f"B-factor values rescaled: ({scale_min}, {scale_max}) -> ({rescale_min}, {rescale_max}).")

        bfact_assign: BFactor = bf_rescale or bf_chain

        positions = expand_range(pos_slice if pos_slice else f"1-{len(seq)}")
        # correct positions from one-based to zero-based indexing

        bfacts_orignal = []
        bfacts_rescaled = []

        for pos in positions:
            try:
                bfact = bfact_assign.get(pos)
                bfact_ori = bf_chain.get(pos)
            except (IndexError, KeyError, issues.InvalidInputError):
                logging.warning(
                    f"Position {pos} (zero-indexed {pos-1}) exceeds the length of new B-factor data ({len(bf_chain.bfactor_data)}); setting B-factor to -1.0"
                )
                continue
            bfacts_orignal.append(bfact_ori)
            bfacts_rescaled.append(bfact)
            # fix pos to one-based indexing for pymol
            logging.debug(f"Setting B-factor for position {pos} (zero-indexed {pos-1}) to {bfact}")
            bfact_assign.assign_to_res_pymol(pos, state=0)

        if not visual:
            logging.debug(f"Not updating visual representation for {mol} (chain {chain_id})")
            return

        ramp_color: str | list[str] = palette_code

        if palette_code.startswith("rainbow"):
            logging.debug(f"Using rainbow palette {palette_code}")

        elif palette_code not in ramp_spectrum_dict:
            logging.warning(f"Palette {palette_code} not found in ramp_spectrum_dict, try to create it.")
            ramp_color: str | list[str] = palette_code.split("_")
            logging.debug(f"Ramp color: {ramp_color}")
        else:
            logging.warning(f"Palette {palette_code} found in ramp_spectrum_dict, .")

        logging.debug(f"Setting visual representation for {mol} (chain {chain_id}) based on B-factors")
        cmd.show_as("cartoon", bfact_assign.obj_sel_pymol)
        cmd.cartoon("putty", bfact_assign.obj_sel_pymol)
        cmd.set("cartoon_putty_scale_min", min(bfacts_rescaled), obj, state=state)
        cmd.set("cartoon_putty_scale_max", max(bfacts_rescaled), obj, state=state)
        cmd.set("cartoon_putty_transform", putty_transform_mode, obj, state=state)
        cmd.set("cartoon_putty_radius", 0.2, obj, state=state)  # type: ignore
        cmd.spectrum("b", palette=palette_code, selection=f"{bfact_assign.obj_sel_pymol} and n. CA ")
        _ramp_name = f"count_{mol}_{chain_id}_{'rescaled' if bf_rescale else 'ori'}"
        logging.debug(
            f'ramp_new {f"{_ramp_name}, {obj}, [{min(bfacts_rescaled)}, {max(bfacts_rescaled)}], {ramp_color}"}'
        )

        cmd.ramp_new(f"{_ramp_name}", obj, [min(bfacts_rescaled), max(bfacts_rescaled)], color=ramp_color)

        if do_rescale:
            logging.debug(
                f'ramp_new {f"count_{mol}_{chain_id}_ori, {obj}, [{min(bfacts_orignal)}, {max(bfacts_orignal)}], {ramp_color}"}'
            )
            cmd.ramp_new(
                f"count_{mol}_{chain_id}_ori", obj, [min(bfacts_orignal), max(bfacts_orignal)], color=ramp_color
            )
        cmd.recolor()

    for chain_id in _chain_ids:
        _load_to_one_chain(chain_id)


setattr(_load_b_factors, "__bibtex__", load_b_factors_citation)
load_b_factors = get_cited(_load_b_factors)
