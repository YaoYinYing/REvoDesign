
import json
from pymol import cmd
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

