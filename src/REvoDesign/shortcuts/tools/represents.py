'''
Shortcut functions of structure representation
'''


from Bio.Align import substitution_matrices
from Bio.Data import IUPACData
from immutabledict import immutabledict
from pymol import cmd, util

from REvoDesign import ROOT_LOGGER

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
        cmd.select(
            "normal_lddt", f"({selection}) and ((b <90 and b >70) or (b =70))"
        )
        cmd.select(
            "medium_lddt", f"({selection}) and ((b <70 and b >50) or (b=50))"
        )
        cmd.select(
            "low_lddt", f"({selection}) and ((b <50 and b >0 ) or (b=0))"
        )
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
        cmd.select(
            "low_lddt", f"({selection}) and ((b <.50 and b >0 ) or (b=0))"
        )

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
        cmd.select(
            "not_aligned_but_enabled", f"(enabled) and not ({selection})"
        )
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
        print("%s is empty" % obj1)
        return
    if cmd.count_atoms(obj2) == 0:
        print("%s is empty" % obj2)
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

    cmd.iterate(
        obj1 + " and name CA and " + aln, "stored.chain1.append(chain)"
    )
    cmd.iterate(
        obj2 + " and name CA and " + aln, "stored.chain2.append(chain)"
    )

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
                "((%s and resi %s and chain %s) or (%s and resi %s and chain %s)) or "
                % (obj1, i1, c1, obj2, i2, c2)
            )
        else:
            mutant_selection += (
                "((%s and resi %s and chain %s) or (%s and resi %s and chain %s)) or "
                % (obj1, i1, c1, obj2, i2, c2)
            )
            # get the similarity (according to the blosum matrix) of the two residues and
            c = getBlosum90ColorName(n1, n2)
            colors.append(
                (c, f"{obj2} and resi {i2} and chain {c2} and elem C")
            )

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
    cmd.show(
        "lines",
        "(%s or %s) and ((non_mutations or not_aligned) and not name c+o+n)"
        % (obj1, obj2),
    )
    cmd.show("sticks", f"({obj1} or {obj2}) and mutations and not name c+o+n")
    cmd.color("gray", "elem C and not_aligned")
    cmd.color("white", "elem C and non_mutations")
    cmd.color("blue", "elem C and mutations and %s" % obj1)
    for col, sel in colors:
        cmd.color(col, sel)

    cmd.hide("everything", f"(hydro) and ({obj1} or {obj2})")
    cmd.center(f"{obj1} or {obj2}")
    if labels:
        cmd.label("mutations and name CA", '"(%s-%s-%s)"%(chain, resi, resn)')
    if waters:
        cmd.set("sphere_scale", "0.1")  # type: ignore
        cmd.show("spheres", f"resn HOH and ({obj1} or {obj2})")
        cmd.color("red", "resn HOH and %s" % obj1)
        cmd.color("salmon", "resn HOH and %s" % obj2)
    print(
        """
             Mutations are highlighted in blue and red.
             All mutated sidechains of %s are colored blue, the corresponding ones from %s are
             colored on a spectrum from blue to red according to how similar the two amino acids are
             (as measured by the BLOSUM90 substitution matrix).
             Aligned regions without mutations are colored white.
             Regions not used for the alignment are gray.
             NOTE: There could be mutations in the gray regions that were not detected."""
        % (obj1, obj2)
    )
    cmd.delete(aln)
    cmd.deselect()
