import os
from unittest.mock import patch

import pytest
from pymol import cmd

# simply import the wrappers you want to test
from REvoDesign.shortcuts.wrappers.designs import (wrapped_profile_pick_design,
                                                   wrapped_pssm2csv)
from REvoDesign.shortcuts.wrappers.esm2 import wrapped_esm1v
from REvoDesign.shortcuts.wrappers.exports import (
    wrapped_dump_fasta_from_struct, wrapped_menu_dump_sidechains)
from REvoDesign.shortcuts.wrappers.ligand_converters import (
    wrapped_smiles_conformer_batch, wrapped_smiles_conformer_single,
    wrapper_sdf2rosetta_params)
from REvoDesign.shortcuts.wrappers.mutation_effect_predictors import \
    wrapped_thermompnn
from REvoDesign.shortcuts.wrappers.represents import (
    wrapped_color_by_mutation, wrapped_color_by_plddt, wrapped_load_b_factors,
    wrapped_real_sc)
from REvoDesign.shortcuts.wrappers.rfdiffusion_tasks import (
    wrapped_general_rfdiffusion_task, wrapped_visualize_substrate_potentials)
from REvoDesign.shortcuts.wrappers.rosetta_tasks import (
    wrapped_fast_relax, wrapped_pross, wrapped_relax_w_ca_constraints,
    wrapped_rosettaligand)
from REvoDesign.shortcuts.wrappers.structure import wrapped_resi_renumber
from REvoDesign.shortcuts.wrappers.utils import wrapped_logger_level_setter,wrapped_convert_residue_ranges
from REvoDesign.shortcuts.wrappers.vina_tools import (wrapped_alter_box,
                                                      wrapped_get_pca_box,
                                                      wrapped_getbox)
from REvoDesign.tools.customized_widgets import ValueDialog
from tests.conftest import TestWorker

### YOUR JOBS ARE DONE HERE

# fetch a local snapshot to find these wrappers
local_snapshot = locals().items()
imported_wrappers = [(k, v) for k, v in local_snapshot if k.startswith(("wrapper", "wrapped"))]


@pytest.mark.parametrize("test_window_wrapper, test_window_wrapper_func", (
    # collect all imported wrappers here in an automatic way
    imported_wrappers
))
def test_menu_window_pops(test_window_wrapper, test_window_wrapper_func, test_worker: TestWorker):
    test_worker.test_id = test_worker.method_name()
    test_worker.load_session_and_check(customized_session='../tests/data/3fap_hf3_A_short.pdb')

    # pre-select a residue that required by some functions
    cmd.select('sele', 'resi 1')

    assert not test_worker.plugin.bus.headless, "Runs Headless mode"

    assert not hasattr(test_worker.plugin.bus.ui,
                       'open_windows'), f"There are open windows stored in the bus: {getattr(test_worker.plugin.bus.ui, 'open_windows')}"
    test_window_wrapper_func()

    # the window is opened and stored with the UI.
    assert hasattr(test_worker.plugin.bus.ui, 'open_windows'), "There are no open windows stored in the bus"
    all_opened_windows: list[ValueDialog] = getattr(test_worker.plugin.bus.ui, 'open_windows')
    assert len(all_opened_windows) == 1, f"There are more than one window opened: {len(all_opened_windows)}"
    # get that window
    that_window = all_opened_windows[0]
    # take a screenshot
    test_worker.save_screenshot(that_window, basename=f'window_pops/{test_worker.method_name()}-{test_window_wrapper}')

    # save the recipe
    os.makedirs('shortcut_recipes', exist_ok=True)
    expected_recipe_json = f'shortcut_recipes/{test_window_wrapper}.json'
    with patch('REvoDesign.driver.file_dialog.FileDialog.browse_filename', return_value=expected_recipe_json):
        that_window._on_save_clicked()
        assert os.path.isfile(expected_recipe_json), f"Expected recipe json file not found: {expected_recipe_json}"

    # the window must be closed to prevent AttributeError of Qt raised from qtbot
    that_window.close()

    # make sure the window is closed
    assert not hasattr(test_worker.plugin.bus.ui,
                       'open_windows'), f"There are remaining window opened: {getattr(test_worker.plugin.bus.ui, 'open_windows')}"
