import pytest

from REvoDesign.tools.customized_widgets import QButtonBrick, QButtonMatrix
from REvoDesign.tools.mutant_tools import pick_design_from_profile
from tests.conftest import KeyData, TestWorker


@pytest.mark.serial
def test_pick_design_from_profile(test_worker: TestWorker, KeyDataDuringTests: KeyData):
    test_worker.test_id = test_worker.method_name()
    test_worker.load_session_and_check()

    profile = KeyDataDuringTests.pssm_file
    profile_type = 'PSSM'
    prefer_lower_score = False
    keep_missing = True
    residue_range = KeyDataDuringTests.surface_file
    view_highlight = 'orient'
    view_highlight_nbr = 6

    assert not hasattr(test_worker.plugin.bus.ui, 'open_windows'), 'Open windows detected'

    pick_design_from_profile(
        profile,
        profile_type,
        prefer_lower_score,
        keep_missing,
        residue_range,
        view_highlight,
        view_highlight_nbr
    )

    assert hasattr(test_worker.plugin.bus.ui, 'open_windows'), 'No dialog opened'
    assert len(test_worker.plugin.bus.ui.open_windows) == 1, 'More than one dialog opened'

    subwindow = test_worker.plugin.ui.open_windows[0]  # type: ignore
    test_worker.save_screenshot(
        widget=subwindow,
        basename=f"{test_worker.test_id}_opened_dialog"
    )

    bm = subwindow.findChild(QButtonMatrix, 'ProfileDesignButtonMatrix')

    test_worker.save_pymol_png(
        basename=f"{test_worker.test_id}_start_clicking",
        focus=False,
    )
    for row, col in [(1, 2), (3, 4)]:
        test_worker.click(
            bm.findChild(QButtonBrick,
                         f"matrixButton_{row}_vs_{col}"
                         )
        )
        test_worker.sleep(200)

        test_worker.save_pymol_png(
            basename=f"{test_worker.test_id}_pick_{row}_{col}",
            focus=False,
        )

        test_worker.check_existed_mutant_tree()
