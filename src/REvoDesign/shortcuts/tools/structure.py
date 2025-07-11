'''
Shortcut functions of structure manipulation
'''
import itertools

from pymol import cmd

from REvoDesign import ROOT_LOGGER
from REvoDesign.data.protein_code import rAA

logging = ROOT_LOGGER.getChild(__name__)


def shortcut_find_interface(
    selection="all",
    interact_dist=4,
):
    """
    AUTHOR
                    Yinying Yao

    DESCRIPTION
                    Find interface of specified interaction distance

    USAGE
                    find_interface selection [, interact_dist ]

    ARGUMENTS
                    selection: object or selection
                    interact_dist: int. the maximum distance of interface (angstrom).
                                default: 4 .

    EXAMPLE
                    find_interface protein_ranked_*, 4

    """
    print("Searching interface ...")
    for x in cmd.get_names(selection=f"({selection})"):
        chains_in_this_obj = cmd.get_chains(x)
        if len(chains_in_this_obj) <= 1:
            print(f"{x} may not be a multiple chain protein!")
            continue
        for ch in itertools.combinations(chains_in_this_obj, 2):
            ch_combination = "".join(ch)
            print(f"{x} has chain combination {ch_combination}")
            cmd.select(
                f"{x}_interface_{ch_combination}_{interact_dist}",
                f"({x} and chain {ch[1]} and byres /{x}//{ch[0]} around {interact_dist} ) or ({x} and chain {ch[0]} and byres /{x}//{ch[1]} around {interact_dist} )",
            )
            ifc_residues = list(
                {
                    f"{atom.chain}_{atom.resi}{rAA[atom.resn] if len(atom.resn) > 1 and atom.resn in rAA.keys() else atom.resn}"
                    for atom in cmd.get_model(
                        f"{x}_interface_{ch_combination}_{interact_dist}"
                    ).atom
                }
            )
            if len(ifc_residues) == 0:
                print(
                    f"No interact residue is found btw {x} chain {ch_combination} within {interact_dist} angstrom."
                )
                continue
            ifc_residues.sort()
            print(ifc_residues)
