import os

import traceback

import biolib

from REvoDesign import root_logger
from REvoDesign.citations import CitableModules

logging = root_logger.getChild(__name__)


class PythiaBiolib(CitableModules):
    def __init__(self, molecule, chain_id):
        logging.info("Creating Pythia Instance ...")
        self.molecule = molecule
        self.chain_id = chain_id

        self.work_dir = os.path.abspath('.')

    def predict(self):
        from REvoDesign.tools.pymol_utils import make_temperal_input_pdb

        input_pdb = make_temperal_input_pdb(
            molecule=self.molecule,
            chain_id=self.chain_id,
            wd=self.work_dir,
            reload=False,
        )
        logging.info('Predict ddG effect using pythia from biolib ...')
        pythia_wubianlab = biolib.load('YaoYinYing/pythia_wubianlab')
        logging.info('Remote image loaded.')
        try:
            logging.info(f'Processing `{input_pdb}`... ')
            res = pythia_wubianlab.cli(args=f'--pdb_filename {input_pdb}')

            expected_output = os.path.join(
                self.work_dir,
                f'{self.molecule}_pred_mask.csv',
            )
            res.save_files(os.path.dirname(expected_output))
            logging.info(
                f'Result is saved at `{os.path.dirname(expected_output)}`'
            )
            assert os.path.exists(expected_output)
            return expected_output
        except AssertionError:
            logging.error('Failed to run Pythia via biolib remote command!')
        except:
            traceback.print_exc()

    def __bibtex__(self):
        return {
            'pythia-ddg': """@article {Sun2023.08.09.552725,
	author = {Jinyuan Sun and Tong Zhu and Yinglu Cui and Bian Wu},
	title = {Structure-based self-supervised learning enables ultrafast prediction of stability changes upon mutation at the protein universe scale},
	elocation-id = {2023.08.09.552725},
	year = {2023},
	doi = {10.1101/2023.08.09.552725},
	publisher = {Cold Spring Harbor Laboratory},
	abstract = {Predicting free energy changes (ΔΔG) is of paramount significance in advancing our comprehension of protein evolution and holds profound implications for protein engineering and pharmaceutical development. Traditional methods, however, often suffer from limitations such as sluggish computational speed or heavy reliance on biased training datasets. These challenges are magnified when aiming for accurate ΔΔG prediction across the vast universe of protein sequences. In this study, we present Pythia, a self-supervised graph neural network tailored for zero-shot ΔΔG predictions. In comparative benchmarks with other self-supervised pre-training models and force field-based methods, Pythia outshines its contenders with superior correlations while operating with the fewest parameters, and exhibits a remarkable acceleration in computational speed, up to 105-fold. The efficacy of Pythia is corroborated through its application in predicting thermostable mutations of limonene epoxide hydrolase (LEH) with significant higher experimental success rates. This efficiency propels the exploration of 26 million high-quality protein structures. Such a grand-scale application signifies a leap forward in our capacity to traverse the protein sequence space and potentially enrich our insights into the intricacies of protein genotype-phenotype relationships. We provided a web app at https://pythia.wulab.xyz for users to conveniently execute predictions. Keywords: self-supervised learning, protein mutation prediction, protein thermostabilityCompeting Interest StatementThe authors have declared no competing interest.},
	URL = {https://www.biorxiv.org/content/early/2023/08/14/2023.08.09.552725},
	eprint = {https://www.biorxiv.org/content/early/2023/08/14/2023.08.09.552725.full.pdf},
	journal = {bioRxiv}
}
"""
        }
