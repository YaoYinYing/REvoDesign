
import pytest
from tests.conftest import TestWorker
from REvoDesign.shortcuts.shortcuts import shortcut_rosettaligand

# a variant test from RosettaPy's short app tests
@pytest.mark.parametrize(
    "job_id,start_from,cst",
    [
        ['no_start_no_cst',None, None], 
        ['has_start_no_cst',(-13.218, 6.939, 6.592), None],
        ['no_start_has_cst',None, 'tests/data/cst/6zcy_lig_disance.cst']
    ],
)
def test_rosetta_ligand(job_id, start_from,cst, test_worker: TestWorker, test_node_hint):
    shortcut_rosettaligand(
        pdb='tests/data/6zcy_lig.pdb',
        ligands=['tests/data/lig/lig.fa.params'],
        nstruct=4,
        save_dir='tests/outputs',
        job_id=f'rosettaligand_{job_id}',
        cst=cst,
        box_size=30,
        move_distance=0.5,
        gridwidth=45,
        chain_id_for_dock='B',
        start_from_xyz=start_from,
    )