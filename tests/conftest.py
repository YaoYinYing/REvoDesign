from __future__ import annotations

import gc
import os
import time
import warnings
from dataclasses import dataclass
from typing import Literal, Optional
from unittest.mock import MagicMock

import psutil
import pytest
from _pytest.nodes import Item
from immutabledict import immutabledict
from pymol import CmdException, cmd
from pymol.Qt import QtCore, QtWidgets  # type: ignore
from pytestqt import qtbot


from RosettaPy.utils import tmpdir_manager

from REvoDesign import ConfigBus, REvoDesignPlugin
from REvoDesign.bootstrap import EXPERIMENTS_CONFIG_DIR
from REvoDesign.citations import CitationManager
from REvoDesign.clients.QtSocketConnector import (REvoDesignWebSocketClient,
                                                  REvoDesignWebSocketServer)
from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.sidechain_solver import SidechainSolver
from REvoDesign.tools.customized_widgets import (get_widget_value,
                                                 set_widget_value)

from .data import TestData
from .data.test_data import KeyData

os.environ["PYTEST_QT_API"] = "pyqt5"

TAB_NAMES=Literal["prepare","mutate","evaluate","cluster","visualize","interact","client","socket","config"]

def pytest_collection_modifyitems(items: list[Item]):
    for item in items:
        if "spark" in item.nodeid:
            item.add_marker(pytest.mark.spark)
        elif "_int_" in item.nodeid:
            item.add_marker(pytest.mark.integration)


class Counter:
    def __init__(self):
        self.count = 0

    @property
    def i(self):
        self.count += 1
        return self.count


@pytest.fixture
def counter():
    return Counter()


@pytest.fixture(scope="function")
def app():
    # Initialize the QApplication instance required for the plugin GUI
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture(scope="function")
def plugin(qtbot: qtbot.QtBot, app):
    # Create and return an instance of the REvoDesignPlugin

    cmd.reinitialize()

    # reset singleton classes
    CitationManager.reset_instance()
    REvoDesignWebSocketClient.reset_instance()
    REvoDesignWebSocketServer.reset_instance()
    SidechainSolver.reset_instance()
    ConfigBus.reset_instance()
    gc.collect()

    plugin = REvoDesignPlugin()

    if plugin.window:
        plugin.reinitialize()
    plugin = REvoDesignPlugin()
    plugin.run_plugin_gui()

    qtbot.addWidget(
        plugin.window
    )  # Add the plugin's main window to qtbot for automatic cleanup
    return plugin


class TestWorker:
    def __init__(self, qtbot: qtbot.QtBot, plugin: REvoDesignPlugin):
        from REvoDesign.tools.system_tools import CLIENT_INFO

        self.test_id = "default"
        self.qtbot = qtbot
        self.plugin = plugin
        self.qtbot.addWidget(
            self.plugin.window
        )  # Add the plugin's main window to qtbot for automatic cleanup

        self.tab_widget_mapping: immutabledict[
            TAB_NAMES, QtWidgets.QWidget  # type: ignore
        ] = immutabledict(
            {
                "prepare": self.plugin.ui.tab_prepare,
                "mutate": self.plugin.ui.tab_mutate,
                "evaluate": self.plugin.ui.tab_evaluate,
                "cluster": self.plugin.ui.tab_cluster,
                "visualize": self.plugin.ui.tab_visualize,
                "interact": self.plugin.ui.tab_interact,
                "client": self.plugin.ui.tab_client,
                "socket": self.plugin.ui.tab_socket,
                "config": self.plugin.ui.tab_config,
            }
        )

        self.client_info = CLIENT_INFO()
        self.run_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        self.CURSOR = QtCore.Qt.MouseButton.LeftButton

        # determine which runner carries this test
        self.in_which_runner: dict[str, bool] = {
            "CIRCLECI": bool(os.environ.get("CIRCLE_OIDC_TOKEN")),
            "GITHUB": bool(os.environ.get("GITHUB_ACTION")),
            "MACBOOKPRO": bool(os.environ.get("PROTEIN_DESIGN_KIT")),
        }

        self.is_in_ci_runner = self.in_which_runner.get(
            "CIRCLECI"
        ) or self.in_which_runner.get("GITHUB")

        self.SKIP_PYMOL_PNG = bool(
            int(os.environ.get("RD_TEST_SKIP_PYMOL_PNG", 0))
        )

        self.c = Counter()

        TEST_DIR = os.path.abspath(".")

        @dataclass
        class AUTO_TEST_DATA(TestData):
            test_data_repo: str = TEST_DIR

        # test data
        self.test_data = AUTO_TEST_DATA()

        # test data directories.
        self.DOWNLOAD_DIR = os.path.abspath("../tests/downloaded")
        self.EXPANDED_DIR = os.path.abspath(
            "../tests/expanded_compressed_files"
        )

        # test results directories
        self.SCREENSHOT_DIR = os.path.join(os.path.abspath("."), "screenshots")
        self.PYMOL_PNG_DIR = os.path.join(
            os.path.abspath("."), "pymol_screenshots"
        )

        self.EXPERIMENT_DIR = os.path.join(os.path.abspath("."), "experiments")

        self.ANALYSIS_DIR = os.path.join(os.path.abspath("."), "analysis")
        self.POCKET_DIR = os.path.join(os.path.abspath("."), "pockets")
        self.SURFACE_DIR = os.path.join(
            os.path.abspath("."), "surface_residue_records"
        )
        self.MUTAGENESIS_DIR = os.path.join(os.path.abspath("."), "mutagenese")

        # performance checks
        self.PERFORMANCE_DIR = os.path.join(
            os.path.abspath("."), "performance"
        )

        dirs = {
            self.DOWNLOAD_DIR,
            self.EXPANDED_DIR,
            self.SCREENSHOT_DIR,
            self.PYMOL_PNG_DIR,
            self.EXPERIMENT_DIR,
            self.POCKET_DIR,
            self.SURFACE_DIR,
            self.ANALYSIS_DIR,
            self.MUTAGENESIS_DIR,
            self.PERFORMANCE_DIR,
        }
        [os.makedirs(dir, exist_ok=True) for dir in dirs]

    def pse_snapshot(self, custom_name: str = 'none') -> str:
        time_stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        os.makedirs(os.path.join(self.ANALYSIS_DIR, 'snap'), exist_ok=True)
        snapshot_pze = os.path.join(self.ANALYSIS_DIR, 'snap', f'{self.test_id}_{time_stamp}_{custom_name}.pze')
        cmd.save(snapshot_pze)
        return snapshot_pze

    def _fetch_pdb(
        self, pdb_code: Optional[str] = None, spell: Optional[str] = None
    ):
        if not pdb_code:
            pdb_code = self.test_data.molecule
        if not spell:
            spell = self.test_data.post_fetch_spell

        try:
            molecules = cmd.get_names()
            print(f"Before fetch: {molecules}")
            cmd.fetch(pdb_code)
            cmd.do(spell)

            molecules = cmd.get_names()
            print(f"After fetch: {molecules}")
        except CmdException:
            pass

    def _load_pocket_pse(self, pse_file):
        try:
            assert os.path.exists(pse_file)
            print(f"loading {pse_file}")
            cmd.reinitialize()
            cmd.load(pse_file)
        except CmdException:
            pass

    def load_session_and_check(
        self,
        pdb_code: Optional[str] = None,
        spell: Optional[str] = None,
        from_rcsb: bool = False,
        customized_session: Optional[str] = None,
    ):
        self.sleep(100)
        nproc = get_widget_value(self.plugin.ui.spinBox_nproc)
        print(f"nproc: {nproc}")
        if (
            self.in_which_runner.get("CIRCLECI")
            and nproc > self.test_data.nproc_circleci
        ):
            print(
                f"Fix nproc to reduce performance for CircleCI: {nproc} {os.cpu_count()}-> {self.test_data.nproc_circleci}"
            )
            set_widget_value(
                self.plugin.ui.spinBox_nproc,
                self.test_data.nproc_circleci,
            )

        cmd.reinitialize()

        if from_rcsb:
            self._fetch_pdb(pdb_code, spell)

        else:
            if not customized_session:
                customized_session = self.test_data.pocket_pse
            self._load_pocket_pse(customized_session)

        self.plugin.reload_molecule_info()
        self.check_molecule_after_loaded()

    def save_new_experiment(self, experiment_name: Optional[str] = None):
        import shutil

        if not experiment_name:
            experiment_name = self.test_id

        new_cfg_file = os.path.join(
            self.EXPERIMENT_DIR, f"{experiment_name}.yaml"
        )
        new_cfg_base_name: str = os.path.basename(new_cfg_file)
        new_cfg_prefix = experiment_name
        experiment_file = os.path.join(
            EXPERIMENTS_CONFIG_DIR, new_cfg_base_name
        )

        self.plugin.save_configuration_from_ui(
            experiment=f"experiments/{new_cfg_prefix}"
        )
        # hydra has already saved config into EXPERIMENTS_CONFIG_DIR, copy to user defined config file path
        shutil.copy(experiment_file, new_cfg_file)
        print(f"saved config at {new_cfg_file}, backup at {experiment_file}")

    def click(self, widget: QtWidgets.QWidget, times: int = 1):  # type: ignore
        if isinstance(widget, QtWidgets.QAction):
            for t in range(times):
                widget.trigger()
                self.sleep(100)
            return self

        for t in range(times):
            self.qtbot.mouseClick(widget, self.CURSOR)
            self.sleep(100)
        return self

    def sleep(self, time=1000):
        self.qtbot.wait(time)

    def do_typing(
        self, widget: QtWidgets.QWidget, text: str, strict_mode: bool = False  # type: ignore
    ):
        set_widget_value(widget=widget, value="")
        # if text is short enough or in strict mode
        # type one after another
        if (len(text) < 10) or strict_mode:
            self.qtbot.keyClicks(widget, text)
            return
        # otherwise,
        # only type the last character to trigger hook connected to this widget
        _tex, _t = text[:-1], text[-1]
        set_widget_value(widget=widget, value=_tex)

        self.qtbot.keyClicks(widget, _t)
        self.sleep(100)

    def _navigate_to_tab(
        self, tab: QtWidgets.QWidget, page: QtWidgets.QWidget  # type: ignore
    ):
        tab.setCurrentWidget(page)

    def go_to_tab(self, tab_name: TAB_NAMES):
        self._navigate_to_tab(
            tab=self.plugin.ui.tabWidget,
            page=self.tab_widget_mapping.get(tab_name),
        )
        self.sleep(5)

    def check_molecule_after_loaded(self, molecule: Optional[str] = None):
        if molecule and isinstance(molecule, str):
            assert (
                self.plugin.bus.get_value("ui.header_panel.input.molecule")
                == molecule
            )
            assert (
                get_widget_value(self.plugin.ui.comboBox_design_molecule)
                == molecule
            )
            return

        assert (
            self.plugin.bus.get_value("ui.header_panel.input.molecule")
            in self.test_data.used_molecules
        )

        assert (
            get_widget_value(self.plugin.ui.comboBox_design_molecule)
            in self.test_data.used_molecules
        )

    @property
    def existed_mutant_tree(self) -> MutantTree:
        from REvoDesign.tools.mutant_tools import existed_mutant_tree

        self.mutant_tree: MutantTree = existed_mutant_tree(
            sequences=self.plugin.designable_sequences, enabled_only=0
        )
        print(self.mutant_tree)

        return self.mutant_tree

    def check_existed_mutant_tree(self):
        assert not self.existed_mutant_tree.empty

    def focus_on_tree(self, method="orient"):
        objs = self.existed_mutant_tree.all_mutant_ids
        sele = " or ".join(objs)

        if method == "orient":
            cmd.orient(sele)
            return
        if method == "center":
            cmd.center(sele)
            return
        if method == "zoom":
            cmd.zoom(sele)
            return

    def method_name(self):
        import sys

        return sys._getframe(1).f_code.co_name

    @staticmethod
    def non_emtpy_list(input_list: list) -> list:
        while True:
            if "" in input_list:
                input_list.remove("")
            else:
                return input_list

    def save_screenshot(
        self,
        widget: QtWidgets.QWidget,  # type: ignore
        basename: str = "default",
    ):
        if self.is_in_ci_runner:
            return
        png_file = self.qtbot.screenshot(widget=widget)
        moved_file = os.rename(
            png_file, os.path.join(self.SCREENSHOT_DIR, f"{basename}.png")
        )
        return moved_file

    def save_pymol_png(
        self,
        basename: str = "default",
        dpi: int = 300,
        use_ray: int = 0,
        spells: Optional[str] = None,
        focus=True,
        focus_method="orient",
    ):
        if self.is_in_ci_runner:
            warnings.warn("Skip PyMOL png because CI runner is detected")
            return
        if self.SKIP_PYMOL_PNG:
            warnings.warn(
                f"Skip PyMOL png because an environment variable is set: {self.SKIP_PYMOL_PNG=}"
            )
            return

        if spells:
            cmd.do(spells)
        png_file = os.path.join(self.PYMOL_PNG_DIR, f"{basename}.png")
        if focus and not self.existed_mutant_tree.empty:
            try:
                self.focus_on_tree(method=focus_method)
            except CmdException as e:
                print(e)

        cmd.png(png_file, dpi=dpi, ray=use_ray)

    def wait_for_file(
        self, file: str, interval: int = 100, timeout: float = 61.0
    ) -> bool:
        started_moment = time.perf_counter()
        while True:
            self.qtbot.wait(interval)
            if os.path.exists(file):
                return True
            check_moment = time.perf_counter()
            if check_moment - started_moment > timeout:
                raise TimeoutError(
                    f"File {file} is not available within timeout limit ({timeout} sec)."
                )

    def performace_report(self):
        # print("Performance report...")
        self.print_all_mem()
        # gc.collect()

    def print_mem(self, p):
        rss = p.memory_info().rss
        return f"[{p.pid}] memory usage: {rss / 1e6:0.3} MB"

    def print_all_mem(self):
        p = psutil.Process()
        procs = [p] + p.children(recursive=True)
        mem_count_file = os.path.join(
            "performance", f"ram_usage_{self.run_time}.log"
        )
        with open(mem_count_file, "w") as mc:
            mc.write("\n".join([self.print_mem(p) for p in procs]))

    def teardown(self):
        self.performace_report()
        self.plugin.reinitialize()
        cmd.reinitialize()

        # reset singleton classes
        CitationManager.reset_instance()
        REvoDesignWebSocketClient.reset_instance()
        REvoDesignWebSocketServer.reset_instance()
        SidechainSolver.reset_instance()
        ConfigBus.reset_instance()

        gc.collect()


@pytest.fixture
def test_worker(
    qtbot: qtbot.QtBot,
    plugin,
    request,
):
    w = TestWorker(qtbot, plugin)

    def final_action():
        w.teardown()

    yield w
    request.addfinalizer(final_action)


@pytest.fixture(scope="session")
def KeyDataDuringTests():
    return KeyData()

# mocks on qt widgets


@pytest.fixture
def mock_push_button():
    def _mock_push_button(text=""):
        mock_button = MagicMock(spec=QtWidgets.QPushButton)
        mock_button.text.return_value = text
        mock_button.setText = MagicMock()
        mock_button.clicked = MagicMock()
        return mock_button

    return _mock_push_button


@pytest.fixture
def mock_line_edit():
    def _mock_line_edit(initial_text=""):
        mock_line_edit = MagicMock(spec=QtWidgets.QLineEdit)
        # Internal state
        _text = initial_text

        def _setText(value):
            nonlocal _text
            _text = str(value)

        def _text_method():
            return _text

        def _clear():
            nonlocal _text
            _text = ""

        mock_line_edit.setText.side_effect = _setText
        mock_line_edit.text.side_effect = _text_method
        mock_line_edit.clear.side_effect = _clear

        return mock_line_edit

    return _mock_line_edit


@pytest.fixture
def mock_combo_box():
    def _mock_combo_box(items=None, current_index=0):
        if items is None:
            items = []
        mock_combo = MagicMock(spec=QtWidgets.QComboBox)
        # Internal state
        _items = items.copy()
        _current_index = current_index

        def _clear():
            nonlocal _items, _current_index
            _items.clear()
            _current_index = -1

        def _addItems(new_items):
            nonlocal _items
            _items.extend(map(str, new_items))

        def _addItem(item_text, user_data=None):
            nonlocal _items
            _items.append(str(item_text))

        def _setCurrentText(text):
            nonlocal _current_index
            text = str(text)
            if text in _items:
                _current_index = _items.index(text)
            else:
                _current_index = -1

        def _currentText():
            if 0 <= _current_index < len(_items):
                return _items[_current_index]
            return ""

        mock_combo.clear.side_effect = _clear
        mock_combo.addItems.side_effect = _addItems
        mock_combo.addItem.side_effect = _addItem
        mock_combo.setCurrentText.side_effect = _setCurrentText
        mock_combo.currentText.side_effect = _currentText

        # Mock properties
        mock_combo.count.side_effect = lambda: len(_items)
        mock_combo.currentIndex.side_effect = lambda: _current_index

        return mock_combo

    return _mock_combo_box


@pytest.fixture
def mock_spin_box():
    def _mock_spin_box(initial_value=0):
        mock_spin = MagicMock(spec=QtWidgets.QSpinBox)
        # Internal state
        _value = initial_value
        _min = 0
        _max = 100

        def _setValue(value):
            nonlocal _value
            if _min <= int(value) <= _max:
                _value = int(value)
            else:
                raise ValueError("Value out of range")

        def _value_method():
            return _value

        def _setRange(min_value, max_value):
            nonlocal _min, _max
            _min = int(min_value)
            _max = int(max_value)

        mock_spin.setValue.side_effect = _setValue
        mock_spin.value.side_effect = _value_method
        mock_spin.setRange.side_effect = _setRange

        return mock_spin

    return _mock_spin_box


@pytest.fixture
def mock_double_spin_box():
    def _mock_double_spin_box(initial_value=0.0):
        mock_double_spin = MagicMock(spec=QtWidgets.QDoubleSpinBox)
        # Internal state
        _value = initial_value
        _min = 0.0
        _max = 100.0

        def _setValue(value):
            nonlocal _value
            if _min <= float(value) <= _max:
                _value = float(value)
            else:
                raise ValueError("Value out of range")

        def _value_method():
            return _value

        def _setRange(min_value, max_value):
            nonlocal _min, _max
            _min = float(min_value)
            _max = float(max_value)

        mock_double_spin.setValue.side_effect = _setValue
        mock_double_spin.value.side_effect = _value_method
        mock_double_spin.setRange.side_effect = _setRange

        return mock_double_spin

    return _mock_double_spin_box


@pytest.fixture
def mock_check_box():
    def _mock_check_box(initial_checked=False):
        mock_check = MagicMock(spec=QtWidgets.QCheckBox)
        # Internal state
        _checked = initial_checked

        def _setChecked(value):
            nonlocal _checked
            _checked = bool(value)

        def _isChecked():
            return _checked

        mock_check.setChecked.side_effect = _setChecked
        mock_check.isChecked.side_effect = _isChecked

        return mock_check

    return _mock_check_box


@pytest.fixture
def mock_progress_bar():
    def _mock_progress_bar(initial_value=0):
        mock_progress = MagicMock(spec=QtWidgets.QProgressBar)
        # Internal state
        _value = initial_value
        _min = 0
        _max = 100

        def _setValue(value):
            nonlocal _value
            if _min <= int(value) <= _max:
                _value = int(value)
            else:
                raise ValueError("Value out of range")

        def _value_method():
            return _value

        def _setRange(min_value, max_value):
            nonlocal _min, _max
            _min = int(min_value)
            _max = int(max_value)

        mock_progress.setValue.side_effect = _setValue
        mock_progress.value.side_effect = _value_method
        mock_progress.setRange.side_effect = _setRange

        return mock_progress

    return _mock_progress_bar


@pytest.fixture
def mock_lcd_number():
    def _mock_lcd_number(initial_value=0):
        mock_lcd = MagicMock(spec=QtWidgets.QLCDNumber)
        # Internal state
        _value = initial_value

        def _display(value):
            nonlocal _value
            _value = float(value)

        def _value_method():
            return _value

        mock_lcd.display.side_effect = _display
        mock_lcd.value.side_effect = (
            _value_method  # Assuming value() returns the displayed value
        )

        return mock_lcd

    return _mock_lcd_number


@pytest.fixture
def test_tmp_dir():
    with tmpdir_manager() as tmpdir:
        yield tmpdir