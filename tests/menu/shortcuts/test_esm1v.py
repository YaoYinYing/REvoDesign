import os

from RosettaPy.common.mutation import RosettaPyProteinSequence
import pytest

from REvoDesign.shortcuts.tools.esm2 import shortcut_esm1v
from tests.conftest import TestWorker


def test_esm1v(test_worker: TestWorker):
    pdb="../tests/data/3fap_hf3_A_short.pdb"
    test_worker.test_id = test_worker.method_name()
    test_worker.load_session_and_check(customized_session=pdb)

    bus=test_worker.plugin.bus

    chain_id = bus.get_value("ui.header_panel.input.chain_id")
    designable_sequences: RosettaPyProteinSequence = bus.get_value(
        "designable_sequences", RosettaPyProteinSequence.from_dict)
    sequence: str = designable_sequences.get_sequence_by_chain(chain_id)


    save_dir = 'predictors/esm1v'

    shortcut_esm1v(
        model_names=['esm1v_t33_650M_UR90S_1'],
        sequence=sequence,
        dms_output=os.path.join(save_dir, 'esm1v_t33_650M_UR90S_1.csv'),
        checkpoint_dir='',
        skip_wt=False,
        mutation_col='mutation',
        offset_idx=1,
        scoring_strategy='wt-marginals',
        msa_path='',
        msa_samples=400,
        device='cpu',

    )