from dataclasses import dataclass
import gc
import os
import time
from typing import Union

import pytest

os.environ['PYTEST_QT_API'] = 'pyqt5'

from immutabledict import immutabledict
import psutil
from pytestqt import qtbot

from pymol import cmd, CmdException
from pymol.Qt import QtWidgets, QtCore, QtGui

from REvoDesign import ConfigBus, REvoDesignPlugin, EXPERIMENTS_CONFIG_DIR

from REvoDesign.tools.customized_widgets import (
    get_widget_value,
    set_widget_value,
)

from REvoDesign.tests import *


@pytest.fixture
def app():
    # Initialize the QApplication instance required for the plugin GUI
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def plugin(qtbot: qtbot.QtBot, app):
    # Create and return an instance of the REvoDesignPlugin
    plugin = REvoDesignPlugin()
    ConfigBus.reset_instance()
    if not plugin.window:
        plugin.run_plugin_gui()
    qtbot.addWidget(
        plugin.window
    )  # Add the plugin's main window to qtbot for automatic cleanup
    return plugin


class TestWorker:
    def __init__(self, qtbot: qtbot.QtBot, plugin: REvoDesignPlugin):
        from REvoDesign.tools.system_tools import CLIENT_INFO

        self.test_id = 'default'
        self.qtbot = qtbot
        self.plugin = plugin
        self.qtbot.addWidget(
            self.plugin.window
        )  # Add the plugin's main window to qtbot for automatic cleanup

        self.tab_widget_mapping: immutabledict[
            str, QtWidgets.QWidget
        ] = immutabledict(
            {
                'prepare': self.plugin.ui.tab_prepare,
                'mutate': self.plugin.ui.tab_mutate,
                'evaluate': self.plugin.ui.tab_evaluate,
                'cluster': self.plugin.ui.tab_cluster,
                'visualize': self.plugin.ui.tab_visualize,
                'interact': self.plugin.ui.tab_interact,
                'client': self.plugin.ui.tab_client,
                'socket': self.plugin.ui.tab_socket,
                'config': self.plugin.ui.tab_config,
            }
        )

        self.client_info = CLIENT_INFO()
        self.run_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        self.CURSOR = QtCore.Qt.MouseButton.LeftButton

        # determine which runner carries this test
        self.in_which_runner: dict[str, bool] = {
            'CIRCLECI': bool(os.environ.get('CIRCLE_OIDC_TOKEN')),
            'GITHUB': bool(os.environ.get('GITHUB_ACTION')),
            'MACBOOKPRO': bool(os.environ.get('PROTEIN_DESIGN_KIT')),
        }

        self.is_in_ci_runner = self.in_which_runner.get(
            'CIRCLECI'
        ) or self.in_which_runner.get('GITHUB')

        TEST_DIR = os.path.abspath('.')

        @dataclass
        class AUTO_TEST_DATA(TestData):
            test_data_repo: str = TEST_DIR

        # test data
        self.test_data = AUTO_TEST_DATA()

        # test data directories.
        self.DOWNLOAD_DIR = os.path.abspath('../tests/downloaded')
        self.EXPANDED_DIR = os.path.abspath(
            '../tests/expanded_compressed_files'
        )

        # test results directories
        self.SCREENSHOT_DIR = os.path.join(os.path.abspath('.'), 'screenshots')
        self.PYMOL_PNG_DIR = os.path.join(
            os.path.abspath('.'), 'pymol_screenshots'
        )

        self.EXPERIMENT_DIR = os.path.join(os.path.abspath('.'), 'experiments')

        self.ANALYSIS_DIR = os.path.join(os.path.abspath('.'), 'analysis')
        self.POCKET_DIR = os.path.join(os.path.abspath('.'), 'pocket')
        self.SURFACE_DIR = os.path.join(
            os.path.abspath('.'), 'surface_residue_records'
        )
        self.MUTAGENESIS_DIR = os.path.join(os.path.abspath('.'), 'mutagenese')

        # performance checks
        self.PERFORMANCE_DIR = os.path.join(
            os.path.abspath('.'), 'performance'
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

    def _fetch_pdb(self):
        try:
            molecules = cmd.get_names()
            print(f'Before fetch: {molecules}')
            cmd.fetch(self.test_data.molecule)
            cmd.do(self.test_data.post_fetch_spell)

            molecules = cmd.get_names()
            print(f'After fetch: {molecules}')
        except CmdException:
            pass

    def _load_pocket_pse(self, pse_file):
        try:
            assert os.path.exists(pse_file)
            print(f'loading {pse_file}')
            cmd.reinitialize()
            cmd.load(pse_file)
        except CmdException:
            pass

    def load_session_and_check(
        self, from_rcsb=False, customized_session: str = None
    ):
        nproc = get_widget_value(self.plugin.ui.spinBox_nproc)
        print(f'nproc: {nproc}')
        if (
            self.in_which_runner.get('CIRCLECI')
            and nproc > self.test_data.nproc_circleci
        ):
            print(
                f'Fix nproc to reduce performance for CircleCI: {nproc} {os.cpu_count()}-> {self.test_data.nproc_circleci}'
            )
            set_widget_value(
                self.plugin.ui.spinBox_nproc,
                self.test_data.nproc_circleci,
            )
        if from_rcsb:
            self._fetch_pdb()
        else:
            if not customized_session:
                customized_session = self.test_data.pocket_pse
            self._load_pocket_pse(customized_session)

        self.qtbot.wait(100)

        self.plugin.reload_molecule_info()
        self.check_molecule_after_loaded()

    def save_new_experiment(self, experiment_name: str = None):
        import shutil

        if not experiment_name:
            experiment_name = self.test_id

        new_cfg_file = os.path.join(
            self.EXPERIMENT_DIR, f'{experiment_name}.yaml'
        )
        new_cfg_base_name: str = os.path.basename(new_cfg_file)
        new_cfg_prefix = experiment_name
        experiment_file = os.path.join(
            EXPERIMENTS_CONFIG_DIR, new_cfg_base_name
        )

        self.plugin.save_configuration_from_ui(
            experiment=f'experiments/{new_cfg_prefix}'
        )
        # hydra has already saved config into EXPERIMENTS_CONFIG_DIR, copy to user defined config file path
        shutil.copy(experiment_file, new_cfg_file)
        print(f'saved config at {new_cfg_file}, backup at {experiment_file}')

    def click(self, widget: QtWidgets.QWidget, times: int = 1):
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
        self, widget: QtWidgets.QWidget, text: str, strict_mode: bool = False
    ):
        set_widget_value(widget=widget, value='')
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

    def _navigate_to_tab(
        self, tab: QtWidgets.QWidget, page: QtWidgets.QWidget
    ):
        tab.setCurrentWidget(page)

    def go_to_tab(self, tab_name: str):
        self._navigate_to_tab(
            tab=self.plugin.ui.tabWidget,
            page=self.tab_widget_mapping.get(tab_name),
        )

    def check_molecule_after_loaded(self):
        assert (
            self.plugin.bus.get_value('ui.header_panel.input.molecule')
            == self.test_data.molecule
        )
        assert (
            self.plugin.bus.get_value('ui.header_panel.input.chain_id')
            == self.test_data.chain_id
        )
        assert (
            get_widget_value(self.plugin.ui.comboBox_design_molecule)
            == self.test_data.molecule
        )
        assert (
            get_widget_value(self.plugin.ui.comboBox_chain_id)
            == self.test_data.chain_id
        )

    def download_file(self, url, md5):
        expected_downloaded_file = os.path.join(
            self.DOWNLOAD_DIR, os.path.basename(url)
        )
        import pooch

        if not os.path.exists(expected_downloaded_file):
            pooch.retrieve(
                url=url,
                known_hash=md5,
                progressbar=True,
                path=self.DOWNLOAD_DIR,
                fname=os.path.basename(url),
            )

            assert os.path.exists(expected_downloaded_file)
        return expected_downloaded_file

    def expand_zip(self, compressed_file):
        sub_dirname = os.path.basename(compressed_file).split('.')[0]
        dist_dir = os.path.join(self.EXPANDED_DIR, sub_dirname)
        os.makedirs(dist_dir, exist_ok=True)

        expanded_dirs = os.listdir(dist_dir)
        if not expanded_dirs:
            import zipfile

            with zipfile.ZipFile(compressed_file, mode='r') as z:
                z.extractall(path=dist_dir)

        extracted_files = os.listdir(dist_dir)
        return dist_dir, extracted_files

    def check_existed_mutant_tree(self):
        from REvoDesign.common.MutantTree import MutantTree
        from REvoDesign.tools.mutant_tools import existed_mutant_tree

        self.mutant_tree: MutantTree = existed_mutant_tree(
            sequences=self.plugin.designable_sequences
        )

        assert not self.mutant_tree.empty

    def method_name(self):
        import sys

        return sys._getframe(1).f_code.co_name

    @staticmethod
    def non_emtpy_list(input_list: list) -> list:
        while True:
            if '' in input_list:
                input_list.remove('')
            else:
                return input_list

    def save_screenshot(
        self,
        widget: QtWidgets.QWidget,
        basename: str = 'default',
    ):
        if self.is_in_ci_runner:
            return
        png_file = self.qtbot.screenshot(widget=widget)
        moved_file = os.rename(
            png_file, os.path.join(self.SCREENSHOT_DIR, f'{basename}.png')
        )
        return moved_file

    def save_pymol_png(
        self,
        basename: str = 'default',
        dpi: int = 300,
        use_ray: bool = False,
        spells: str = None,
    ):
        if self.is_in_ci_runner:
            return
        if spells:
            cmd.do(spells)
        png_file = os.path.join(self.PYMOL_PNG_DIR, f'{basename}.png')
        cmd.png(png_file, dpi=dpi, ray=use_ray)

    def wait_for_file(
        self, file: str, interval: str = 100, timeout: float = 61.0
    ) -> Union[bool, None]:
        started_moment = time.perf_counter()
        while True:
            self.qtbot.wait(interval)
            if os.path.exists(file):
                return True
            check_moment = time.perf_counter()
            if check_moment - started_moment > timeout:
                raise TimeoutError(
                    f'File {file} is not available within timeout limit ({timeout} sec).'
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
            'performance', f'ram_usage_{self.run_time}.log'
        )
        with open(mem_count_file, 'w') as mc:
            mc.write('\n'.join([self.print_mem(p) for p in procs]))


@pytest.fixture
def WORKER(
    qtbot: qtbot.QtBot,
    plugin,
    request,
):
    w = TestWorker(qtbot, plugin)

    def final_action():
        w.performace_report()
        w.plugin.reinitialize()
        gc.collect()

    yield w
    request.addfinalizer(final_action)
