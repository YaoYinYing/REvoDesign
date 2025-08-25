from Bio.Align import substitution_matrices
from Bio.Data import IUPACData
from immutabledict import immutabledict
from pymol import cmd, util
from REvoDesign import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
def shortcut_real_sc(selection="(all)", representation="lines", hydrogen=False):
    if representation not in ["lines", "sticks", "spheres", "dots"]:
        return
    if not selection:
        return
    cmd.show(
        representation,
        f'{selection} and (sidechain or n. CA) {"and not hydrogens" if not hydrogen else ""}',
    )
def shortcut_color_by_plddt(selection="all", align_target=0, chain_to_align="A"):
    cmd.set_color("high_lddt_c", [0, 0.325490196078431, 0.843137254901961])
    cmd.set_color(
        "normal_lddt_c",
        [0.341176470588235, 0.792156862745098, 0.976470588235294],
    )
    cmd.set_color("medium_lddt_c", [1, 0.858823529411765, 0.070588235294118])
    cmd.set_color("low_lddt_c", [1, 0.494117647058824, 0.270588235294118])
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
    cmd.set("cartoon_color", "high_lddt_c", "high_lddt")  
    cmd.set("cartoon_color", "normal_lddt_c", "normal_lddt")  
    cmd.set("cartoon_color", "medium_lddt_c", "medium_lddt")  
    cmd.set("cartoon_color", "low_lddt_c", "low_lddt")  
    cmd.bg_color("white")
    align_target = int(align_target)
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
        cmd.select(
            "align_temp",
            f"({target}) and chain {chain_to_align} and (high_lddt or normal_lddt)",
        )
        cmd.select(
            "not_aligned_but_enabled", f"(enabled) and not ({selection})"
        )
        cmd.disable("not_aligned_but_enabled")
        util.mass_align("align_temp", 1, _self=cmd)
        cmd.enable("not_aligned_but_enabled")
        cmd.delete("not_aligned_but_enabled")
blosum90 = substitution_matrices.load("BLOSUM90")
aa_3l = {}
for i, x in enumerate(blosum90.alphabet):  
    if a := IUPACData.protein_letters_1to3.get(x):
        aa_3l[a.upper()] = i
    else:
        aa_3l[x] = i
aa_3l = immutabledict(aa_3l)
def getBlosum90ColorName(aa1, aa2):
    if aa1 not in aa_3l or aa2 not in aa_3l:
        return "red"
    if aa1 == aa2:
        return "blue"
    i1 = aa_3l[aa1]
    i2 = aa_3l[aa2]
    b = blosum90[i1][i2]
    b = abs(b - 4)
    b = 1.0 - (b / 10.0)
    bcolor = (1.0 - b, 0.0, b)
    col_name = "0x%02x%02x%02x" % tuple(int(b * 0xFF) for b in bcolor)
    return col_name
def shortcut_color_by_mutation(obj1, obj2, waters=0, labels=0):
    from pymol import CmdException, stored  
    if cmd.count_atoms(obj1) == 0:
        print(f"{obj1} is empty")
        return
    if cmd.count_atoms(obj2) == 0:
        print(f"{obj2} is empty")
        return
    waters = int(waters)
    labels = int(labels)
    aln = "__aln"
    cmd.super(obj1, obj2, object=aln, cycles=0)
    cmd.super(obj1, obj2)
    stored.resn1, stored.resn2 = [], []
    stored.resi1, stored.resi2 = [], []
    stored.chain1, stored.chain2 = [], []
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
    for n1, n2, i1, i2, c1, c2 in zip(
        stored.resn1,
        stored.resn2,
        stored.resi1,
        stored.resi2,
        stored.chain1,
        stored.chain2,
    ):
        if c1 == "":
            c1 = '""'
        if c2 == "":
            c2 = '""'
        if n1 == n2:
            non_mutant_selection += (
                f"(({obj1} and resi {i1} and chain {c1}) or ({obj2} and resi {i2} and chain {c2})) or "
            )
        else:
            mutant_selection += (
                f"(({obj1} and resi {i1} and chain {c1}) or ({obj2} and resi {i2} and chain {c2})) or "
            )
            c = getBlosum90ColorName(n1, n2)
            colors.append(
                (c, f"{obj2} and resi {i2} and chain {c2} and elem C")
            )
    if mutant_selection == "":
        raise CmdException("No mutations found")
    cmd.select("mutations", mutant_selection[:-4])
    cmd.select("non_mutations", non_mutant_selection[:-4])
    cmd.select(
        "not_aligned",
        f"({obj1} or {obj2}) and not mutations and not non_mutations",
    )
    cmd.hide("everything", f"{obj1} or {obj2}")
    cmd.show("cartoon", f"{obj1} or {obj2}")
    cmd.show(
        "lines",
        f"({obj1} or {obj2}) and ((non_mutations or not_aligned) and not name c+o+n)"
    )
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
        cmd.set("sphere_scale", "0.1")  
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