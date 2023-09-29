
import json
from Bio.Data import IUPACData
from pymol import cmd, util
import matplotlib
matplotlib.use('Agg')
from matplotlib.cm import get_cmap

from tools.utils import suppress_print



# http://www.pymolwiki.org/index.php/rotkit
@suppress_print
def mutate(molecule, chain, resi, target="CYS", mutframe="1"):
    target = target.upper()
    cmd.wizard("mutagenesis")
    #cmd.do("refresh_wizard")
    cmd.refresh_wizard()
    cmd.get_wizard().set_mode("%s" % target)
    selection = "/%s//%s/%s" % (molecule, chain, resi)
    cmd.get_wizard().do_select(selection)
    cmd.frame(str(mutframe))
    cmd.get_wizard().apply()
    # cmd.set_wizard("done")
    cmd.set_wizard()
    #cmd.refresh()
    
cmd.extend("mutate", mutate)

def read_json_file(filename):
    with open(filename) as file:
        data = json.load(file)
    return data

def process_mutations(data):
    positions = data['indices']
    mutations = data['mutations']
    result = []
    for position in positions:
        if str(position) in mutations:
            mutation = mutations[str(position)]
            wt_residue = mutation['wt']
            wt_pssm_score = mutation['wt_pssm']
            candidates = mutation['candidates']
            result.append((position, wt_residue, wt_pssm_score, candidates))
    return result

def process_pssm_mutations(filename):
    data = read_json_file(filename)
    return process_mutations(data)

@suppress_print
def create_pymol_objects(molecule, chain_id, position,  new_residue, color,is_reduced=False,wt_residue='A',wt_pssm_score=0, score=0):
    new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()
    new_obj_name = f'{position}{new_residue}_{score}'
    cmd.create(new_obj_name, f'{molecule} and c. {chain_id}')
    mutate(new_obj_name, chain_id, position, new_residue_3)
    cmd.hide('lines', f'{new_obj_name}')
    cmd.show("sticks", f" {new_obj_name} and resi {position} and (sidechain or n. CA)")
    # record score to b factor of mutated residues.
    cmd.alter(f" {new_obj_name} and resi {position} and (sidechain or n. CA)", f'b={score}')

    if is_reduced:
        cmd.remove(f" {new_obj_name} and not ( resi {position} and (sidechain or n. CA))")

    # set backbone color
    cmd.set_color(f'color_{new_obj_name}', color)
    cmd.color(f'color_{new_obj_name}', f'( {new_obj_name} and resi {position} )')
    util.cnc(f'({new_obj_name} and resi {position})', _self=cmd)

    #cmd.set("stick_color", str(color), f"{new_obj_name} and resi {position} and (sidechain or n. CA)")
    cmd.group(f"mt_{wt_residue}{position}_{str(wt_pssm_score)}", f"{new_obj_name}")



def load_pssm_mutations(obj, chain_id, filename):
    mutations = process_pssm_mutations(filename)

    # Collect the new_residue_scores for color determination
    new_residue_scores = []
    for position, wt_residue, wt_pssm_score, candidates in mutations:
        for new_residue, new_residue_score in candidates.items():
            new_residue_scores.append(new_residue_score)

    # Determine the color bar range
    max_abs_pssm = max(abs(min(new_residue_scores)), abs(max(new_residue_scores)))
    cmap = get_cmap('bwr_r')

    for (position, wt_residue, wt_pssm_score, candidates) in mutations:
        for new_residue, new_residue_score in candidates.items():
            color = get_color(cmap, new_residue_score, max_abs_pssm)
            create_pymol_objects(obj, chain_id, position, new_residue, color)

    cmd.hide('everything', 'hydrogens and polymer.protein')


def get_color(cmap, data, max_abs_value):
    num_color = cmap.N
    scaled_value = (data + max_abs_value) / (2 * max_abs_value)
    color = cmap(int(num_color * scaled_value))[:3]
    return color

# Register the key functions to be used in PyMOL command line
#cmd.extend("load_pssm_mutations", load_pssm_mutations)