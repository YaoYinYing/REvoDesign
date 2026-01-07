import os

import pytest

from REvoDesign.shortcuts.tools.evolution import run_gremlin


@pytest.mark.serial
def test_run_gremlin():
    msa = f"../tests/data/msa/4FAZA.i90c75_aln.fas"
    save_to = f"./evol/gremlin/4FAZA.i90c75_aln.mrf.pkl"
    os.makedirs(os.path.dirname(save_to), exist_ok=True)
    assert os.path.isfile(msa)
    # clean up
    if os.path.isfile(save_to):
        os.remove(save_to)
        
    assert not os.path.isfile(save_to)
    run_gremlin(msa, save_to, gremlin_iter=100)
    assert os.path.isfile(save_to)
