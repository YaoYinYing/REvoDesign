import os
import tempfile
from REvoDesign.tools.pymol_utils import mutate
from pymol import cmd
from REvoDesign.common.Mutant import Mutant
from REvoDesign import root_logger

logging = root_logger.getChild(__name__)


class PyMOL_mutate:
    """
    Class for performing mutations in PyMOL.

    Usage:
    pymol_mutator = PyMOL_mutate(molecule, input_session)
    mutated_pdb = pymol_mutator.run_mutate(mutant_obj)  # Perform mutation

    # Further usage for other functionalities
    """

    def __init__(self, molecule, input_session):
        """
        Initialize PyMOL_mutate with a molecule and input session.

        Args:
        - molecule: Molecule object
        - input_session: Input session information
        """
        self.molecule = molecule
        self.input_session = input_session

    def run_mutate(self, mutant_obj: Mutant, in_place=True, **kwargs) -> str:
        """
        Run mutation on the molecule using PyMOL.

        Args:
        - mutant_obj: Object containing mutation information

        Returns:
        - Path to the mutated PDB file
        """
        from Bio.Data import IUPACData

        new_obj_name = mutant_obj.short_mutant_id

        temp_dir = tempfile.mkdtemp(prefix='RD_design_')
        temp_mutant_path = os.path.join(temp_dir, f"{new_obj_name}.pdb")
        if not in_place:
            cmd.reinitialize()
            cmd.load(self.input_session)
        cmd.hide('surface')
        cmd.create(f"{new_obj_name}", self.molecule)
        if not in_place:
            cmd.delete(self.molecule)

        for mut_info in mutant_obj.mutant_info:
            chain_id = mut_info['chain_id']
            position = mut_info['position']
            new_residue = mut_info['mut_res']

            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()

            mutate(new_obj_name, chain_id, position, new_residue_3)

        cmd.save(temp_mutant_path)

        return temp_mutant_path
