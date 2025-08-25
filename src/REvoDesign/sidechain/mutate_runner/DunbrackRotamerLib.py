import os
from typing import List
from Bio.Data import IUPACData
from joblib import Parallel, delayed
from REvoDesign.basic import MutateRunnerAbstract
from REvoDesign.common.mutant import Mutant
from REvoDesign.logger import ROOT_LOGGER
logging = ROOT_LOGGER.getChild(__name__)
class PyMOL_mutate(MutateRunnerAbstract):
    name: str = "Dunbrack Rotamer Library"
    installed: bool = True
    def __init__(self, pdb_file, molecule="", **kwargs):
        super().__init__(pdb_file)
        self.input_session = pdb_file
        self.molecule = molecule
        self.temp_dir = self.new_cache_dir
    def run_mutate(self, mutant: Mutant) -> str:
        import pymol2
        new_obj_name = mutant.short_mutant_id
        logging.debug(f"Mutating {mutant=}")
        temp_mutant_path = os.path.join(self.temp_dir, f"{new_obj_name}.pdb")
        with pymol2.PyMOL() as p:
            p.cmd.reinitialize()
            p.cmd.load(self.input_session, object=self.molecule)
            p.cmd.hide("surface")
            logging.debug(
                f"creating {new_obj_name=} copyed from  {self.molecule=}: {p.cmd.get_names()=}"
            )
            p.cmd.create(new_obj_name, self.molecule, quiet=0)
            p.cmd.delete(self.molecule)
            for mut_info in mutant.mutations:
                new_residue_3 = IUPACData.protein_letters_1to3[
                    mut_info.mut_res
                ].upper()
                target = new_residue_3.upper()
                p.cmd.wizard("mutagenesis")
                p.cmd.refresh_wizard()
                p.cmd.get_wizard().set_mode(f"{target}")
                p.selection = f"/{new_obj_name}//{mut_info.chain_id}/{mut_info.position}"  
                p.cmd.get_wizard().do_select(p.selection)
                p.cmd.frame("1")
                p.cmd.get_wizard().apply()
                p.cmd.set_wizard()
            p.cmd.save(temp_mutant_path, new_obj_name)
        return temp_mutant_path
    def run_mutate_parallel(
        self, mutants: List[Mutant], nproc: int = 2
    ) -> List[str]:
        results = Parallel(n_jobs=nproc, return_as="list")(
            delayed(self.run_mutate)(mutant) for mutant in mutants
        )
        return list(results)  
    __bibtex__ = {
        "Dunbrack Rotamer Library": """@Article{Shapovalov2011,
author={Shapovalov, Maxim V.
and Dunbrack Jr., Roland L.,},
title={A Smoothed Backbone-Dependent Rotamer Library for Proteins Derived from Adaptive Kernel Density Estimates and Regressions},
journal={Structure},
year={2011},
month={Jun},
day={08},
publisher={Elsevier},
volume={19},
number={6},
pages={844-858},
abstract={Rotamer libraries are used in protein structure determination, prediction, and design. The backbone-dependent rotamer library consists of rotamer frequencies, mean dihedral angles, and variances as a function of the backbone dihedral angles. Structure prediction and design methods that employ backbone flexibility would strongly benefit from smoothly varying probabilities and angles. A new version of the backbone-dependent rotamer library has been developed using adaptive kernel density estimates for the rotamer frequencies and adaptive kernel regression for the mean dihedral angles and variances. This formulation allows for evaluation of the rotamer probabilities, mean angles, and variances as a smooth and continuous function of phi and psi. Continuous probability density estimates for the nonrotameric degrees of freedom of amides, carboxylates, and aromatic side chains have been modeled as a function of the backbone dihedrals and rotamers of the remaining degrees of freedom. New backbone-dependent rotamer libraries at varying levels of smoothing are available from http://dunbrack.fccc.edu.},
issn={0969-2126},
doi={10.1016/j.str.2011.03.019},
url={https://doi.org/10.1016/j.str.2011.03.019}
}
"""
    }