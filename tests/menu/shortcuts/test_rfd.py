import os

import pytest
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.shortcuts.tools.rfdiffusion_tasks import RfDiffusion
from REvoDesign.shortcuts.wrappers.rfdiffusion_tasks import _run_general_rfdiffusion_task
from tests.conftest import MEMORY_AVAILABLE_GB


@pytest.mark.serial
@pytest.mark.skipif(MEMORY_AVAILABLE_GB < 3, reason="Not enough memory available for this test")
@pytest.mark.skipif(not RfDiffusion.installed, reason="RfDiffusion not installed")
def test_rfdiffusion_general():
    kwargs = {
        "config_preset": "base",
        "config_file": "../tests/data/rfdiffusion/partial.yaml",
        "model_name": "Base_ckpt.pt",
        "overrides": "",
    }
    _run_general_rfdiffusion_task(**kwargs)

    save_dir = "rfdiffusion/partial_diffusion"

    assert os.path.isdir(save_dir), f"{save_dir=} does not exist"
    files = os.listdir(save_dir)
    assert files, f"{save_dir=} is empty"

    pdb_path = os.path.join(save_dir, "3fap_hf3_0.pdb")

    assert os.path.isfile(pdb_path)
    assert os.path.isfile(os.path.join(save_dir, "3fap_hf3_0.trb"))

    sequence_original = RosettaPyProteinSequence.from_pdb("../tests/data/3fap_hf3_A_short.pdb")

    sequence_designed = RosettaPyProteinSequence.from_pdb(pdb_path)
    assert sequence_designed.all_chain_ids == ["A"]
    assert (
        sequence_designed.chains[0].sequence != sequence_original.chains[0].sequence
    ), f"Expected different sequences: {sequence_designed.chains[0].sequence=} != {sequence_original.chains[0].sequence=}"

    assert sequence_designed.chains[0].sequence.startswith(
        "GGGGGG"
    ), f"Expected sequence to start with GGGGGG: {sequence_designed.chains[0].sequence=}"
