import os

import pytest
from RosettaPy.analyser import RosettaEnergyUnitAnalyser

from REvoDesign.shortcuts.shortcuts import (shortcut_pross,
                                            shortcut_rosettaligand)
from tests.conftest import TestWorker


# a variant test from RosettaPy's short app tests
@pytest.mark.parametrize(
    "job_id,start_from,cst",
    [
        ['no_start_no_cst', None, None],
        ['has_start_no_cst', (-13.218, 6.939, 6.592), None],
        ['no_start_has_cst', None, '../tests/data/cst/6zcy_lig_disance.cst']
    ],
)
def test_rosetta_ligand(job_id, start_from, cst, test_worker: TestWorker, test_node_hint):

    save_dir = 'rosetta_tests/outputs'

    shortcut_rosettaligand(
        pdb='../tests/data/6zcy_lig.pdb',
        ligands=['../tests/data/lig/lig.fa.params'],
        nstruct=4,
        save_dir=save_dir,
        job_id=f'rosettaligand_{job_id}',
        cst=cst,
        box_size=30,
        move_distance=0.5,
        gridwidth=45,
        chain_id_for_dock='B',
        start_from_xyz=start_from,
    )
    run_dir = os.path.join(save_dir, f'rosettaligand_{job_id}', f'docking/6zcy_lig_rosettaligand_{job_id}')
    assert os.path.isdir(os.path.join(run_dir, 'pdb')), f"{run_dir}/pdb does not exist"
    assert os.listdir(os.path.join(run_dir, 'pdb')), f'{run_dir}/pdb should contain pdb files'
    assert [x for x in os.listdir(os.path.join(run_dir, 'scorefile')) if x.endswith(
        '.sc')], f'{run_dir}/scorefile should contain score files ends with .sc'

    analyser = RosettaEnergyUnitAnalyser(os.path.join(run_dir, 'scorefile'))
    assert not analyser.df.empty, 'Scorefile should be loaded and analysed'


def test_pross(test_worker: TestWorker, test_node_hint):
    save_dir = 'rosetta_tests/outputs'
    shortcut_pross(
        pdb="../tests/data/3fap_hf3_A_short.pdb",
        pssm="../tests/data/3fap_hf3_A_ascii_mtx_file_short",
        res_to_fix='1A',
        res_to_restrict='1A',
        nstruct_refine=4,
        save_dir=save_dir,
        job_id="pross",
    )

    run_dir = os.path.join(save_dir, 'pross')
    for dir in ['refinement', 'filterscan', 'design']:
        assert os.path.isdir(os.path.join(run_dir, dir)), f"{run_dir}/{dir} does not exist"

    refined_pdbs = [
        x for x in os.listdir(
            os.path.join(
                run_dir,
                'refinement',
                'pross_refinement',
                'pdb')) if x.endswith('.pdb')]
    assert refined_pdbs, f'{run_dir}/refinement should contain pdb files'
    assert len(refined_pdbs) == 4, f'{run_dir}/refinement should contain exact 4 pdb files'

    filter_scan_dir = os.path.join(run_dir, 'filterscan')
    assert os.path.isdir(os.path.join(filter_scan_dir, 'resfiles')), f"{filter_scan_dir}/resfiles does not exist"
    assert [x for x in os.listdir(os.path.join(filter_scan_dir, 'resfiles')) if x.startswith(
        'designable_aa_resfile')], f'{filter_scan_dir}/resfiles should contain resfiles'

    design_dir = os.path.join(run_dir, 'design/3fap_hf3_A_short_design')
    assert os.path.isdir(os.path.join(design_dir, 'pdb')), f"{design_dir}/pdb does not exist"
    designed_pdbs = [x for x in os.listdir(os.path.join(design_dir, 'pdb')) if x.endswith('.pdb')]
    assert designed_pdbs, f'{design_dir}/pdb should contain pdb files'
    assert len(designed_pdbs) == 8, f'{design_dir}/pdb should contain exact 8 pdb files'

    assert os.path.isdir(os.path.join(design_dir, 'scorefile')), f"{design_dir}/scorefile does not exist"
    assert [x for x in os.listdir(os.path.join(design_dir, 'scorefile')) if x.endswith(
        '.sc')], f'{design_dir}/scorefile should contain score files ends with .sc'

    analyser = RosettaEnergyUnitAnalyser(os.path.join(design_dir, 'scorefile'))
    assert not analyser.df.empty, 'Scorefile should be loaded and analysed'
    assert analyser.df.shape[0] == 8, 'Scorefile should contain exact 8 rows'
