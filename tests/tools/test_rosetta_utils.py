import os
import shutil

import pytest
from RosettaPy.utils.tools import tmpdir_manager

from REvoDesign import issues
from REvoDesign.tools.rosetta_utils import (extra_res_to_opts,
                                            list_fastrelax_scripts,
                                            setup_minimal_rosetta_db)


def test_setup_minimal_rosetta_db():
    if 'ROSETTA3_DB' in os.environ:
        os.environ.pop('ROSETTA3_DB')

    db_dir = "database/sampling/relax_scripts"

    setup_minimal_rosetta_db(db_dir)
    assert 'ROSETTA3_DB' in os.environ, f"ROSETTA3_DB should be set after minimum clone"

    db_dir_env = os.environ['ROSETTA3_DB']
    assert os.path.isdir(db_dir_env), f"db directory should exist after minimum clone: {db_dir_env}"

    assert os.listdir(db_dir_env), f"db directory should not be empty after minimum clone: {db_dir_env}"

    # clean ups
    shutil.rmtree(db_dir_env)
    os.environ.pop('ROSETTA3_DB')


def test_list_fastrelax_scripts():
    scripts = list_fastrelax_scripts()
    assert scripts, f"There should be at least one fastrelax script"
    assert not any('dualspace' in s for s in scripts)


@pytest.mark.parametrize(
    'label, scripts, exists, expected',
    [
        ('no_extra_res', [], [], 0),
        ('extra_res', ['A.fa.params'], [True], 2),
        ('extra_res_multiple', ['A.fa.params', 'B.fa.params'], [True, True], 4),
        ('extra_res_multiple_missing', ['A.fa.params', 'B.fa.params'], [True, False], 2),
        ('extra_res_multiple_missing_all', ['A.fa.params', 'B.fa.params'], [False, False], 0),
        ('extra_res_cen', ['A.cen.params'], [True], 2),
        ('invalid_extra_res', ['A-fa.pdb'], [True], 0),
        ('invalid_extra_res_cen_mixed', ['A-cen.pdb', 'B.fa.params'], [True, True], 2),

    ]
)
def test_extra_res_to_opts(label, scripts, exists, expected):
    with tmpdir_manager() as tmpdir:
        scripts = [os.path.join(tmpdir, s) for s in scripts]
        for s, e in zip(scripts, exists):
            if e:
                open(s, 'w').write('')
                assert os.path.isfile(s)

        if all(e for e in exists) and all(f.endswith('.params') for f in scripts):
            opts = extra_res_to_opts(scripts)
        else:
            with pytest.warns(issues.BadDataWarning):
                opts = extra_res_to_opts(scripts)
        assert len(opts) == expected, f"{label}: {len(opts)} != {expected}"
