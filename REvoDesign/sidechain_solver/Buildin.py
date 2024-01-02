import os
import tempfile
from REvoDesign.tools.pymol_utils import mutate
from pymol import cmd
from REvoDesign.common.Mutant import Mutant
from Bio.Data import IUPACData


class PyMOL_mutate:
    def __init__(self, molecule, input_session):
        self.molecule = molecule
        self.input_session = input_session

    def run_mutate(self, mutant_obj: Mutant,**kwargs) -> str:
        new_obj_name = mutant_obj.get_short_mutant_id()

        temp_dir = tempfile.mkdtemp(prefix='RD_design_')
        temp_mutant_path = os.path.join(
            temp_dir, f"{new_obj_name}.pdb"
        )
        cmd.load(self.input_session)
        cmd.hide('surface')
        cmd.create(f"{new_obj_name}", self.molecule)
        cmd.delete(self.molecule)

        for mut_info in mutant_obj.get_mutant_info():
            chain_id = mut_info['chain_id']
            position = mut_info['position']
            new_residue = mut_info['mut_res']

            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()

            mutate(new_obj_name, chain_id, position, new_residue_3)

        cmd.save(temp_mutant_path)

        return temp_mutant_path
