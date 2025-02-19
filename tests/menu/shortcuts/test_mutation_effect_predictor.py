import pytest

from REvoDesign.shortcuts.tools.mutation_effect_predictors import \
    shortcut_thermompnn
from tests.conftest import TestWorker


@pytest.mark.serial
# a variant test from RosettaPy's short app tests
@pytest.mark.parametrize(
    "job_id,mode,threshold,long_dist,ss_penalty",
    [
        ['ssm_single', 'single', None, None, False],
        ['ssm_single_ss_penalty', 'single', None, None, True],
        ['ssm_single_higher_threshold', 'single', 10, None, False],
        ['ssm_additive', 'additive', None, None, False],
        ['ssm_epistatic', 'epistatic', None, None, False],
        # ['ssm_epistatic_longdist', 'epistatic', None, None,False]
    ],
)
def test_shortcut_thermompnn(job_id, mode, threshold, long_dist, ss_penalty, test_worker: TestWorker):
    pdb = '../tests/data/6zcy_lig.pdb'
    test_worker.test_id = test_worker.method_name()
    test_worker.load_session_and_check(customized_session=pdb)

    save_dir = 'predictors/thermompnn'

    shortcut_thermompnn(
        pdb=pdb,
        save_dir=save_dir,
        prefix=job_id,
        mode=mode,
        threshold=threshold or -0.5,
        distance=long_dist or 5.0,
        ss_penalty=ss_penalty,
        device='cpu',
        load_to_preview=True,
        top_ranked=100
    )

    test_worker.save_new_experiment(experiment_name=f'{test_worker.test_id}_{job_id}')

    test_worker.check_existed_mutant_tree()
    test_worker.save_pymol_png(basename=f'{test_worker.test_id}_{job_id}', focus=False)
