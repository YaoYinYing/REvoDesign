
import pytest
import os
from tests.conftest import TestWorker

from RosettaPy.analyser import RosettaEnergyUnitAnalyser
from REvoDesign.shortcuts.shortcuts import shortcut_rosettaligand,shortcut_pross

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
    run_dir=os.path.join('tests/outputs',f'rosettaligand_{job_id}', f'docking/6zcy_lig_rosettaligand_{job_id}')
    assert os.path.isdir(os.path.join(run_dir, 'pdb')), f"{run_dir}/pdb does not exist"
    assert os.listdir(os.path.join(run_dir, 'pdb')), f'{run_dir}/pdb should contain pdb files'
    assert [x for x in os.listdir(os.path.join(run_dir, 'scorefile')) if x.endswith('.sc')], f'{run_dir}/scorefile should contain score files ends with .sc'

    analyser=RosettaEnergyUnitAnalyser(os.path.join(run_dir, 'scorefile'))
    assert analyser.df, 'Scorefile should be loaded and analysed'


def test_pross(test_worker: TestWorker, test_node_hint):
    shortcut_pross(
        pdb="tests/data/3fap_hf3_A_short.pdb",
        pssm="tests/data/3fap_hf3_A_ascii_mtx_file_short",
        res_to_fix='1A',
        res_to_restrict='1A',
        nstruct_refine=4,
        save_dir="tests/outputs",
        job_id=f"pross",
    )

    run_dir=os.path.join('tests/outputs','pross')

