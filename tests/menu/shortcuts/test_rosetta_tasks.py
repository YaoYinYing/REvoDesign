import os

import pytest
from RosettaPy.analyser import RosettaEnergyUnitAnalyser

from REvoDesign.shortcuts.tools.rosetta_tasks import (
    shortcut_fast_relax, shortcut_pross, shortcut_relax_w_ca_constraints,
    shortcut_rosettaligand)
from tests.conftest import TestWorker


@pytest.mark.serial
# a variant test from RosettaPy's short app tests
@pytest.mark.parametrize(
    "job_id,start_from,cst",
    [
        ['no_start_no_cst', None, None],
        # ['has_start_no_cst', (-13.218, 6.939, 6.592), None],
        # ['no_start_has_cst', None, '../tests/data/cst/6zcy_lig_disance.cst']
    ],
)
def test_rosetta_ligand(job_id, start_from, cst, test_worker: TestWorker, test_node_hint):

    test_worker.inject_rosetta_node_config(test_node_hint)

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


# time expensive test
# def test_pross(test_worker: TestWorker, test_node_hint):
#     test_worker.inject_rosetta_node_config(test_node_hint)

#     save_dir = 'rosetta_tests/outputs'
#     shortcut_pross(
#         pdb="../tests/data/3fap_hf3_A_short.pdb",
#         pssm="../tests/data/3fap_hf3_A_ascii_mtx_file_short",
#         res_to_fix='1A',
#         res_to_restrict='1A',
#         nstruct_refine=4,
#         save_dir=save_dir,
#         job_id="pross",
#     )

#     run_dir = os.path.join(save_dir, 'pross')
#     for dir in ['refinement', 'filterscan', 'design']:
#         assert os.path.isdir(os.path.join(run_dir, dir)), f"{run_dir}/{dir} does not exist"

#     refined_pdbs = [
#         x for x in os.listdir(
#             os.path.join(
#                 run_dir,
#                 'refinement',
#                 'pross_refinement',
#                 'pdb')) if x.endswith('.pdb')]
#     assert refined_pdbs, f'{run_dir}/refinement should contain pdb files'
#     assert len(refined_pdbs) == 4, f'{run_dir}/refinement should contain exact 4 pdb files'

#     filter_scan_dir = os.path.join(run_dir, 'filterscan')
#     assert os.path.isdir(os.path.join(filter_scan_dir, 'resfiles')), f"{filter_scan_dir}/resfiles does not exist"
#     assert [x for x in os.listdir(os.path.join(filter_scan_dir, 'resfiles')) if x.startswith(
#         'designable_aa_resfile')], f'{filter_scan_dir}/resfiles should contain resfiles'

#     design_dir = os.path.join(run_dir, 'design/3fap_hf3_A_short_design')
#     assert os.path.isdir(os.path.join(design_dir, 'pdb')), f"{design_dir}/pdb does not exist"
#     designed_pdbs = [x for x in os.listdir(os.path.join(design_dir, 'pdb')) if x.endswith('.pdb')]
#     assert designed_pdbs, f'{design_dir}/pdb should contain pdb files'
#     assert len(designed_pdbs) == 8, f'{design_dir}/pdb should contain exact 8 pdb files'

#     assert os.path.isdir(os.path.join(design_dir, 'scorefile')), f"{design_dir}/scorefile does not exist"
#     assert [x for x in os.listdir(os.path.join(design_dir, 'scorefile')) if x.endswith(
#         '.sc')], f'{design_dir}/scorefile should contain score files ends with .sc'

#     analyser = RosettaEnergyUnitAnalyser(os.path.join(design_dir, 'scorefile'))
#     assert not analyser.df.empty, 'Scorefile should be loaded and analysed'
#     assert analyser.df.shape[0] == 8, 'Scorefile should contain exact 8 rows'


@pytest.mark.serial
# a variant test from RosettaPy's short app tests
@pytest.mark.parametrize(
    "job_id,pdb,dualspace,ligand",
    [
        # ['mono', '../tests/data/3fap_hf3_A_short.pdb', False, ''],
        # ['mono_dualspace', '../tests/data/3fap_hf3_A_short.pdb', True, ''],
        ['w_ligand', '../tests/data/pdb/3fap_hf3_A_short_lig.pdb', False, '../tests/data/lig/lig.fa.params'],
    ],
)
def test_fast_relax(job_id, pdb, dualspace, ligand, test_worker: TestWorker, test_node_hint):

    test_worker.inject_rosetta_node_config(test_node_hint)

    save_dir = 'rosetta_tests/outputs/fastrelax'
    relax_script = 'MonomerRelax2019'

    relax_opts = []
    if ligand:
        relax_opts.extend(['--extra_res_fa', os.path.abspath(ligand)])

    shortcut_fast_relax(
        pdb=os.path.abspath(pdb),
        relax_script=relax_script,
        dualspace=dualspace,
        job_id=job_id,
        save_dir=save_dir,
        nstruct=4,
        default_repeats=3,
        relax_opts=relax_opts,
    )
    pdb_bn = os.path.basename(pdb)[:-4]

    run_dir = os.path.join(save_dir, f'{job_id}/fastrelax_{pdb_bn}_{relax_script}')
    assert os.path.isdir(os.path.join(run_dir, 'all')), f"{run_dir}/all does not exist"
    assert [x for x in os.listdir(os.path.join(run_dir, 'all')) if x.endswith('.pdb')
            ], f'{run_dir}/all should contain pdb files'
    assert [x for x in os.listdir(os.path.join(run_dir, 'all')) if x.endswith(
        '.sc')], f'{run_dir}/all should contain score files ends with .sc'

    analyser = RosettaEnergyUnitAnalyser(os.path.join(run_dir, 'all'))
    assert not analyser.df.empty, 'Scorefile should be loaded and analysed'


@pytest.mark.serial
# a variant test from RosettaPy's short app tests
@pytest.mark.parametrize(
    "job_id,pdb,ligand",
    [
        ['mono', '../tests/data/3fap_hf3_A_short.pdb', ''],
        # ['mono_dualspace', '../tests/data/3fap_hf3_A_short.pdb', ''],
        ['w_ligand', '../tests/data/pdb/3fap_hf3_A_short_lig.pdb', '../tests/data/lig/lig.fa.params'],
    ],
)
def test_shortcut_relax_w_ca_constraints(job_id, pdb, ligand, test_worker: TestWorker, test_node_hint):

    test_worker.inject_rosetta_node_config(test_node_hint)

    save_dir = 'rosetta_tests/outputs/relax_w_ca_constraints'

    relax_opts = []
    if ligand:
        relax_opts.extend(['--extra_res_fa', os.path.abspath(ligand)])

    shortcut_relax_w_ca_constraints(
        pdb=os.path.abspath(pdb),
        job_id=job_id,
        save_dir=save_dir,
        nstructs_per_round=4,
        ncycles=3,
        relax_opts=relax_opts,
    )
    pdb_bn = os.path.basename(pdb)[:-4]
    for i in range(3):
        run_dir = os.path.join(save_dir, f'{job_id}/{job_id}_round_{i}')
        assert os.path.isdir(os.path.join(run_dir, 'all')), f"{run_dir}/all does not exist"
        all_pdbs = [x for x in os.listdir(os.path.join(run_dir, 'all')) if x.endswith('.pdb')]
        assert all_pdbs, f'{run_dir}/all should contain pdb files'
        assert len(all_pdbs) == 4, f'{run_dir}/all should contain exact 4 pdb files'
        for j in range(4):
           assert f'{pdb_bn}_R{i}_0000{j+1}.pdb' in all_pdbs, f'{run_dir}/all should contain {pdb_bn}_R{i}_0000{j}.pdb'
        analyser = RosettaEnergyUnitAnalyser(os.path.join(run_dir, 'all'))
        # bn move to the next round
        pdb_bn = analyser.best_decoy['decoy']
