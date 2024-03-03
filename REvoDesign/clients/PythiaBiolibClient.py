import os
import biolib
import traceback
from REvoDesign import root_logger

logging = root_logger.getChild(__name__)


class PythiaBiolib:
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
