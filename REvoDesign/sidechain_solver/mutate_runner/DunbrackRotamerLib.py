import os
from joblib import Parallel, delayed
from REvoDesign.common.Mutant import Mutant
from REvoDesign import root_logger
from REvoDesign.tools.utils import suppress_print

logging = root_logger.getChild(__name__)

from REvoDesign.sidechain_solver.mutate_runner import MutateRunnerAbstract


class PyMOL_mutate(MutateRunnerAbstract):
    """
    Class for performing mutations in PyMOL.

    Usage:
    pymol_mutator = PyMOL_mutate(molecule, input_session)
    mutated_pdb = pymol_mutator.run_mutate(mutant_obj)  # Perform mutation

    # Further usage for other functionalities
    """

    def __init__(self, pdb_file, molecule='', **kwargs):
        """
        Initialize PyMOL_mutate with a molecule and input session.

        Args:
        - molecule: Molecule object
        - input_session: Input session information
        """
        super().__init__(pdb_file)
        self.input_session = pdb_file
        self.molecule = molecule

        self.temp_dir = self.new_cache_dir

    def run_mutate(self, mutant_obj: Mutant, **kwargs) -> str:
        """
        Run mutation on the molecule using PyMOL.

        Args:
        - mutant_obj: Object containing mutation information
        - in_place: Whether to in-place mutation.
            + If False, PyMOL will perform a series of work:
                1. reinitialize workspace (session)
                2. load the input PDB
                3. create a new object in the name of mutant.short_mutant_id
                4. delete original object naming as input molecule
                5. run mutate against this object.
                6. save the mutated object as a new PDB file.
                7. return the PDB file path

        Returns:
        - Path to the mutated PDB file
        """
        from Bio.Data import IUPACData
        import pymol2

        new_obj_name = mutant_obj.short_mutant_id
        logging.debug(f'Mutating {mutant_obj=}')

        temp_mutant_path = os.path.join(self.temp_dir, f"{new_obj_name}.pdb")

        with pymol2.PyMOL() as p:
            p.cmd.reinitialize()
            p.cmd.load(self.input_session, object=self.molecule)
            p.cmd.hide('surface')
            logging.debug(
                f'creating {new_obj_name=} copyed from  {self.molecule=}: {p.cmd.get_names()=}'
            )

            p.cmd.create(new_obj_name, self.molecule, quiet=0)

            p.cmd.delete(self.molecule)

            for mut_info in mutant_obj.mutant_info:
                chain_id = mut_info['chain_id']
                position = mut_info['position']
                new_residue = mut_info['mut_res']

                new_residue_3 = IUPACData.protein_letters_1to3[
                    new_residue
                ].upper()

                # a variant from rotkit mutate function that uses pymol2 context manager
                # http://www.pymolwiki.org/index.php/rotkit 
                target = new_residue_3.upper()
                p.cmd.wizard("mutagenesis")
                # cmd.do("refresh_wizard")
                p.cmd.refresh_wizard()
                p.cmd.get_wizard().set_mode("%s" % target)
                p.selection = "/%s//%s/%s" % (
                    new_obj_name,
                    chain_id,
                    position,
                )
                p.cmd.get_wizard().do_select(p.selection)
                p.cmd.frame(str("1"))
                p.cmd.get_wizard().apply()
                p.cmd.set_wizard()

            p.cmd.save(temp_mutant_path, new_obj_name)

        return temp_mutant_path

    def run_mutate_parallel(
        self, mutants: list[Mutant], n_jobs: int = 2, **kwargs
    ):
        """
        Perform mutation on the protein in parallel.

        Args:
        - mutants: List of Mutant objects containing mutation information
        - n_jobs: Number of parallel jobs to run (default: -1, which means using all available cores)
        - **kwargs: Additional keyword arguments to pass to the run_mutate method

        Returns:
        - List of paths to the mutated PDB files
        """

        results = Parallel(n_jobs=n_jobs)(
            delayed(self.run_mutate)(mutant) for mutant in mutants
        )
        return results
