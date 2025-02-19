'''
Shortcut functions of third-party mutant effect predictors
'''


import os
from typing import List, Literal, Optional

from RosettaPy.common.mutation import RosettaPyProteinSequence

import pandas as pd
from REvoDesign.citations import CitableModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.common.mutant import Mutant
from REvoDesign.common.mutant_tree import MutantTree
from REvoDesign.sidechain.sidechain_solver import SidechainSolver
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id


RUN_MODE_T=Literal["single", "additive", "epistatic"]

class ThermoMpnnPredictor(CitableModuleAbstract):
    installed: bool= is_package_installed('thermompnn')

    def __init__(self, pdb: str, save_dir: Optional[str]=None, prefix: str='thermompnn_ssm', chains: Optional[List[str]] = None,
            mode: RUN_MODE_T  = 'single',
            batch_size: int = 256,
            threshold: float = -0.5,
            distance: float = 5.0,
            ss_penalty: bool = False,
            device: str = 'cpu') :
        
        self.prefix=prefix
        
        from thermompnn import ThermoMPNN
        if save_dir and prefix:
            self.save_prefix=os.path.join(save_dir, prefix)
            os.makedirs(os.path.dirname(save_dir), exist_ok=True)
        else:
            self.save_prefix=''

        self.sequence=RosettaPyProteinSequence.from_pdb(pdb)
        self.app = ThermoMPNN(pdb, self.save_prefix, chains, mode, batch_size, threshold, distance, ss_penalty, device)

    def run(self) -> pd.DataFrame:
        df=self.app.process(save_csv=bool(self.save_prefix))
        # only when the application is passed successfully can the citation be prompted.
        self.cite()
        return df
    
    @staticmethod
    def mutant_name2mutant(mutant_id: str, sequences: RosettaPyProteinSequence) -> Mutant:
        return extract_mutants_from_mutant_id(
            mutant_string=mutant_id,
            sequences=sequences,
            wt_before_chain=True
        )
    


    def df2mutant_tree(self, df: pd.DataFrame) -> MutantTree:
        mutant_tree=MutantTree()
        for i, row in df.iterrows():
            score: float=row['ddG (kcal/mol)']
            mutation: str=row['Mutation']
            mutant=self.mutant_name2mutant(mutant_id=f'{mutation.replace(":", "_")}_{score}', sequences=self.sequence)
            mutant.mutant_score=score
            mutant.wt_score=0

            mutant_tree.add_mutant_to_branch(self.prefix, mutant.full_mutant_id, mutant)


        return mutant_tree
        
    __bibtex__ = {
        'ThermoMPNN': """@article{
doi:10.1073/pnas.2314853121,
author = {Henry Dieckhaus  and Michael Brocidiacono  and Nicholas Z. Randolph  and Brian Kuhlman },
title = {Transfer learning to leverage larger datasets for improved prediction of protein stability changes},
journal = {Proceedings of the National Academy of Sciences},
volume = {121},
number = {6},
pages = {e2314853121},
year = {2024},
doi = {10.1073/pnas.2314853121},
URL = {https://www.pnas.org/doi/abs/10.1073/pnas.2314853121},
eprint = {https://www.pnas.org/doi/pdf/10.1073/pnas.2314853121},
}""",
        'ThermoMPNN-D': """@article{https://doi.org/10.1002/pro.70003,
author = {Dieckhaus, Henry and Kuhlman, Brian},
title = {Protein stability models fail to capture epistatic interactions of double point mutations},
journal = {Protein Science},
volume = {34},
number = {1},
pages = {e70003},
doi = {https://doi.org/10.1002/pro.70003},
url = {https://onlinelibrary.wiley.com/doi/abs/10.1002/pro.70003},
eprint = {https://onlinelibrary.wiley.com/doi/pdf/10.1002/pro.70003},
year = {2025}
}"""}
        



def shortcut_thermompnn(
    pdb: str, 
    save_dir: Optional[str]='./thermompnn/predicts', 
    prefix: str='ssm', 
    chains: Optional[List[str]] = None,
    mode: RUN_MODE_T  = 'single',
    batch_size: int = 256,
    threshold: float = -0.5,
    distance: float = 5.0,
    ss_penalty: bool = False,
    device: str = 'cpu',
    load_to_preview: bool = False
):
    app=ThermoMpnnPredictor(pdb, save_dir, prefix, chains, mode, batch_size, threshold, distance, ss_penalty, device)

    df=app.run()

    mutant_tree=app.df2mutant_tree(df)

    if load_to_preview:
        sidechain_solver=SidechainSolver()
        mutant_tree.run_mutate_parallel(sidechain_solver.mutate_runner)
        
