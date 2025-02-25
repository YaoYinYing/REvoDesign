# import os
# import random

# import pytest
# from unittest.mock import patch
# from pymol import cmd

# from REvoDesign.sidechain.mutate_runner.PIPPack import PIPPack_worker
# from REvoDesign.tools.customized_widgets import (get_widget_value,
#                                                  set_widget_value)

# from REvoDesign.tools.package_manager import decide

# from ...conftest import TestWorker
# from ...data.test_data import KeyData

# os.environ["PYTEST_QT_API"] = "pyqt5"


# @pytest.mark.serial
# @pytest.mark.order(-1)
# class TestREvoDesignPlugin_TabVisualize_MultiDesign:
#     def test_multiple_design(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
#         test_worker.test_id = test_worker.method_name()

#         test_worker.load_session_and_check(
#             customized_session=KeyDataDuringTests.evaluate_pse_path
#         )
#         test_worker.go_to_tab(tab_name="visualize")

#         set_widget_value(
#             test_worker.plugin.ui.checkBox_multi_design_use_external_scorer,
#             False,
#         )
#         set_widget_value(
#             test_worker.plugin.ui.checkBox_multi_design_color_by_scores, False
#         )

#         test_worker.do_typing(
#             widget=test_worker.plugin.ui.lineEdit_multi_design_mutant_table,
#             text=test_worker.test_data.multi_mut_txt,
#             strict_mode=True,
#         )

#         test_worker.save_screenshot(
#             widget=test_worker.plugin.window,
#             basename=f"{test_worker.test_id}_{test_worker.c.i}",
#         )
#         test_worker.save_pymol_png(
#                 basename=f"{test_worker.test_id}_init"
#             )

#         md_init = test_worker.plugin.bus.button("multi_design_initialize")
#         md_new = test_worker.plugin.bus.button("multi_design_start_new_design")
#         md_next = test_worker.plugin.bus.button("multi_design_right")
#         md_prev = test_worker.plugin.bus.button("multi_design_left")
#         test_worker.plugin.bus.button("multi_design_end_this_design")
#         md_save = test_worker.plugin.bus.button(
#             "multi_design_export_mutants_from_table"
#         )

#         test_worker.click(md_init).click(md_new)

#         for i in random.sample(
#             test_worker.test_data.multi_design_steps,
#             3,
#         ):
#             j = test_worker.c.i
#             test_worker.click(md_next, times=i)
#             test_worker.save_pymol_png(
#                 basename=f"{test_worker.test_id}_{j}_{i}"
#             )

#             test_worker.sleep(30)

#         test_worker.click(md_prev, 1)

#         test_worker.click(md_save)

#         test_worker.sleep(30)

#         assert os.path.exists(test_worker.test_data.multi_mut_txt)

#     def test_multiple_design_mpnn_score(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
#         test_worker.test_id = test_worker.method_name()

#         test_worker.load_session_and_check(
#             customized_session=KeyDataDuringTests.evaluate_pse_path
#         )
#         test_worker.go_to_tab(tab_name="visualize")

#         test_worker.do_typing(
#             widget=test_worker.plugin.ui.lineEdit_multi_design_mutant_table,
#             text=test_worker.test_data.multi_mut_txt_mpnn,
#             strict_mode=True,
#         )

#         set_widget_value(
#             test_worker.plugin.ui.comboBox_profile_type_2,
#             test_worker.test_data.multi_design_scorer,
#         )

#         test_worker.save_screenshot(
#             widget=test_worker.plugin.window,
#             basename=f"{test_worker.test_id}_{test_worker.c.i}",
#         )

#         md_init = test_worker.plugin.bus.button("multi_design_initialize")
#         md_new = test_worker.plugin.bus.button("multi_design_start_new_design")
#         md_next = test_worker.plugin.bus.button("multi_design_right")
#         test_worker.plugin.bus.button("multi_design_left")
#         test_worker.plugin.bus.button("multi_design_end_this_design")
#         md_save = test_worker.plugin.bus.button(
#             "multi_design_export_mutants_from_table"
#         )

#         test_worker.click(md_init).click(md_new)

#         for i in random.sample(
#             test_worker.test_data.multi_design_steps,
#             3,
#         ):
#             j = test_worker.c.i
#             test_worker.click(md_next, times=i)
#             test_worker.save_pymol_png(
#                 basename=f"{test_worker.test_id}_{j}_{i}"
#             )

#             test_worker.sleep(30)

#         test_worker.click(md_save)

#         test_worker.sleep(30)

#         assert (
#             test_worker.plugin.multi_designer.all_design_multi_design_mutant_object
#         )

#         assert os.path.exists(test_worker.test_data.multi_mut_txt_mpnn)
