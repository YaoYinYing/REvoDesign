"""
pytest configuration
"""

from __future__ import annotations

import gc
import json
import os
import platform
import platformdirs
import shutil
import time
import warnings
from dataclasses import dataclass
from typing import Callable, Literal
from unittest.mock import MagicMock, patch

import psutil
import pytest
from _pytest.nodes import Item
from immutabledict import immutabledict

from pytestqt import qtbot
from RosettaPy.node import NodeHintT
from RosettaPy.utils import tmpdir_manager

# mostly mock on data and cache to isolated from user's production system
test_root = os.path.abspath('.')
data_dirname = os.path.join(test_root, "mock", "data", "dir")
cache_dirname = os.path.join(test_root, "tests", "downloaded", "cache")
os.makedirs(data_dirname, exist_ok=True)
os.makedirs(cache_dirname, exist_ok=True)


def _static_platform_dir(dirname: str):
    def _impl(*args, **kwargs):
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        return dirname

    return _impl


platformdirs.user_data_dir = _static_platform_dir(data_dirname)
platformdirs.user_cache_dir = _static_platform_dir(cache_dirname)

with (
    patch("REvoDesign.bootstrap.set_config.user_data_dir", return_value=data_dirname) as mock_user_data_dir,
    patch("REvoDesign.bootstrap.set_config.user_cache_dir", return_value=cache_dirname) as mock_user_cache_dir
    ):
    from pymol import CmdException, cmd
    
    from REvoDesign import REvoDesignPlugin
    from REvoDesign.basic.abc_singleton import SingletonAbstract, reset_singletons
    from REvoDesign.bootstrap import EXPERIMENTS_CONFIG_DIR
    from REvoDesign.bootstrap.set_config import ConfigConverter, reload_config_file, set_REvoDesign_config_file
    from REvoDesign.common import MutantTree
    from REvoDesign.driver.ui_driver import ConfigBus
    from REvoDesign.Qt import QtCore, QtWidgets
    from REvoDesign.tools.customized_widgets import get_widget_value, set_widget_value
    from REvoDesign.tools.package_manager import LiveProcessResult, REvoDesignPackageManager, refresh_window

    from .data import TestData
    from .data.test_data import KeyData

os.environ["PYTEST_QT_API"] = "pyqt5"

TAB_NAMES = Literal["prepare", "mutate", "evaluate", "cluster", "visualize", "interact", "socket", "config"]

repo_dir = os.path.join(os.path.dirname(__file__), "..")


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

# def check_real_config_dir():
#     '''
#     A checkpoint to check whether the test suite has created the real config dir.
#     '''
#     the_dir='/Users/yyy/Library/Application Support/REvoDesign/config'
#     if os.path.exists(the_dir):
#         raise RuntimeError(f'The test suite has created this dir! {the_dir}')


@pytest.fixture(scope="function")
def plugin(qtbot: qtbot.QtBot, app,patch_config_user_data, patch_config_user_cache):
    # Create and return an instance of the REvoDesignPlugin

    # check_real_config_dir() # failed

    cmd.reinitialize()

    reset_singletons()

    # reset all singleton classes

    gc.collect()
    # check_real_config_dir() # passed

    plugin = REvoDesignPlugin()

    if plugin.window:
        plugin.reinitialize()
    
    # check_real_config_dir() # passed
    plugin = REvoDesignPlugin()

    # check_real_config_dir() # passed

    plugin.run_plugin_gui()

    # check_real_config_dir()

    qtbot.addWidget(plugin.window)  # Add the plugin's main window to qtbot for automatic cleanup
    return plugin


def mock_fetch_json(url):
    d = json.load(open(os.path.join(repo_dir, "jsons", "REvoDesignExtrasTableRich.json")))
    if "notification" in d:
        warnings.warn(UserWarning(f'These notification lines will be removed: {d["notification"]}'))
        del d["notification"]
    return d


@pytest.fixture(scope="function")
def pm_plugin(qtbot: qtbot.QtBot) -> REvoDesignPackageManager:

    with (
        patch(
            "REvoDesign.tools.package_manager.notify_box", side_effect=lambda *args, **kargs: None
        ) as mock_notify_box,
        patch("REvoDesign.tools.package_manager.fetch_gist_json", side_effect=mock_fetch_json) as mock_fetch_gist_json,
        patch(
            "REvoDesign.tools.package_manager.get_github_repo_tags",
            side_effect=lambda repo_url: ["1.0.0", "1.0.1", "1.0.2"],
        ) as mock_notify_box,
    ):

        plugin = REvoDesignPackageManager()
        plugin.run_plugin_gui()
        plugin.dialog.lineEdit_local.setText(repo_dir)

        qtbot.addWidget(plugin.dialog)
        return plugin


class PmTestWorker:
    def __init__(self, qtbot: qtbot.QtBot, plugin: REvoDesignPackageManager):
        ...
        self.qtbot = qtbot
        self.plugin = plugin

        self.SCREENSHOT_DIR = os.path.join(os.path.abspath("."), "screenshots", "package_manager")
        os.makedirs(self.SCREENSHOT_DIR, exist_ok=True)

    def save_screenshot(
        self,
        widget: QtWidgets.QWidget,  # type: ignore
        basename: str = "default",
    ):
        png_file = self.qtbot.screenshot(widget=widget)
        moved_file = os.rename(png_file, os.path.join(self.SCREENSHOT_DIR, f"{basename}.png"))
        return moved_file

    def _click(
        self,
        widget: QtWidgets.QWidget,
        cursor,
        times: int = 1,
    ):  # type: ignore
        if isinstance(widget, QtWidgets.QAction):
            for t in range(times):
                widget.trigger()
                self.sleep(100)
            return self

        for t in range(times):
            self.qtbot.mouseClick(widget, cursor)
            self.sleep(100)
        return self

    def click(
        self,
        widget: QtWidgets.QWidget,
        times: int = 1,
    ):
        return self._click(widget, QtCore.Qt.MouseButton.LeftButton, times)

    def rclick(self, widget: QtWidgets.QWidget, times: int = 1):
        return self._click(widget, QtCore.Qt.MouseButton.RightButton, times)

    def sleep(self, time=1000):
        for i in range(int(time / 10)):
            self.qtbot.wait(i * 10)
            refresh_window()

    def do_typing(self, widget: QtWidgets.QWidget, text: str, strict_mode: bool = False):  # type: ignore
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

    @property
    def method_name(self):
        import sys

        return sys._getframe(1).f_code.co_name


class TestWorker:
    def __init__(self, qtbot: qtbot.QtBot, plugin: REvoDesignPlugin):
        from REvoDesign.tools.system_tools import CLIENT_INFO

        self.test_id = "default"
        self.qtbot = qtbot
        self.plugin = plugin
        self.qtbot.addWidget(self.plugin.window)  # Add the plugin's main window to qtbot for automatic cleanup
        # self.workspace_data="./mock/data/dir"
        # os.makedirs(self.workspace_data, exist_ok=True)

        # a deep reset is necessary to avoid any side effect
        self.main_config = set_REvoDesign_config_file(True)


        self.tab_widget_mapping: immutabledict[TAB_NAMES, QtWidgets.QWidget] = immutabledict(  # type: ignore
            {
                "prepare": self.plugin.ui.tab_prepare,
                "mutate": self.plugin.ui.tab_mutate,
                "evaluate": self.plugin.ui.tab_evaluate,
                "cluster": self.plugin.ui.tab_cluster,
                "visualize": self.plugin.ui.tab_visualize,
                "interact": self.plugin.ui.tab_interact,
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

        self.is_in_ci_runner = self.in_which_runner.get("CIRCLECI") or self.in_which_runner.get("GITHUB")

        self.SKIP_PYMOL_PNG = bool(int(os.environ.get("RD_TEST_SKIP_PYMOL_PNG", 0)))

        self.c = Counter()

        TEST_DIR = os.path.abspath(".")

        @dataclass
        class AUTO_TEST_DATA(TestData):
            test_data_repo: str = TEST_DIR

        # test data
        self.test_data = AUTO_TEST_DATA()

        # test data directories.
        self.DOWNLOAD_DIR = os.path.abspath("../tests/downloaded")
        self.EXPANDED_DIR = os.path.abspath("../tests/expanded_compressed_files")

        # test results directories
        self.SCREENSHOT_DIR = os.path.join(os.path.abspath("."), "screenshots")
        self.PYMOL_PNG_DIR = os.path.join(os.path.abspath("."), "pymol_screenshots")

        self.EXPERIMENT_DIR = os.path.join(os.path.abspath("."), "experiments")

        self.ANALYSIS_DIR = os.path.join(os.path.abspath("."), "analysis")
        self.POCKET_DIR = os.path.join(os.path.abspath("."), "pockets")
        self.SURFACE_DIR = os.path.join(os.path.abspath("."), "surface_residue_records")
        self.MUTAGENESIS_DIR = os.path.join(os.path.abspath("."), "mutagenese")

        # performance checks
        self.PERFORMANCE_DIR = os.path.join(os.path.abspath("."), "performance")

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


    def pse_snapshot(self, custom_name: str = "none") -> str:
        time_stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        os.makedirs(os.path.join(self.ANALYSIS_DIR, "snap"), exist_ok=True)
        snapshot_pze = os.path.join(self.ANALYSIS_DIR, "snap", f"{self.test_id}_{time_stamp}_{custom_name}.pze")
        cmd.save(snapshot_pze)
        return snapshot_pze

    def _fetch_pdb(self, pdb_code: str | None = None, spell: str | None = None):
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
        pdb_code: str | None = None,
        spell: str | None = None,
        from_rcsb: bool = False,
        customized_session: str | None = None,
    ):
        self.sleep(100)
        nproc = get_widget_value(self.plugin.ui.spinBox_nproc)
        print(f"nproc: {nproc}")
        if self.in_which_runner.get("CIRCLECI") and nproc > self.test_data.nproc_circleci:
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
        self.check_designable_sequences()

    def save_new_experiment(self, experiment_name: str | None = None):
        import shutil

        if not experiment_name:
            experiment_name = self.test_id

        new_cfg_file = os.path.join(self.EXPERIMENT_DIR, f"{experiment_name}.yaml")
        new_cfg_base_name: str = os.path.basename(new_cfg_file)
        new_cfg_prefix = experiment_name
        experiment_file = os.path.join(EXPERIMENTS_CONFIG_DIR, new_cfg_base_name)
        self.plugin.bus.cfg_group["main"].save_as(experiment_file)

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

    def do_typing(self, widget: QtWidgets.QWidget, text: str, strict_mode: bool = False):  # type: ignore
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

    def _navigate_to_tab(self, tab: QtWidgets.QWidget, page: QtWidgets.QWidget):  # type: ignore
        tab.setCurrentWidget(page)

    def go_to_tab(self, tab_name: TAB_NAMES):
        self._navigate_to_tab(
            tab=self.plugin.ui.tabWidget,
            page=self.tab_widget_mapping.get(tab_name),
        )
        self.sleep(5)

    def check_designable_sequences(self):
        assert self.plugin.designable_sequences is not None, "Designable sequences are not loaded to the plugin."
        assert self.plugin.bus.get_value(
            "designable_sequences", dict, reject_none=True, cfg="runtime"
        ), "Designable sequences are not in Configuration."

    def check_molecule_after_loaded(self, molecule: str | None = None):
        if molecule and isinstance(molecule, str):
            assert self.plugin.bus.get_value("ui.header_panel.input.molecule", str) == molecule
            assert get_widget_value(self.plugin.ui.comboBox_design_molecule) == molecule
            return

    @property
    def existed_mutant_tree(self) -> MutantTree:
        from REvoDesign.tools.mutant_tools import existed_mutant_tree

        self.mutant_tree: MutantTree = existed_mutant_tree(sequences=self.plugin.designable_sequences, enabled_only=0)
        print(self.mutant_tree)

        return self.mutant_tree

    def check_existed_mutant_tree(self):
        mt = self.existed_mutant_tree
        assert not mt.empty, f"No mutant tree found in test {self.test_id}"
        return mt

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
        dist_file = os.path.join(self.SCREENSHOT_DIR, f"{basename}.png")
        dist_dir = os.path.dirname(dist_file)
        if not os.path.isdir(dist_dir):
            os.makedirs(dist_dir)
        moved_file = os.rename(png_file, dist_file)
        return moved_file

    def save_pymol_png(
        self,
        basename: str = "default",
        dpi: int = 300,
        use_ray: int = 0,
        spells: str | None = None,
        focus=True,
        focus_method="orient",
    ):
        if self.is_in_ci_runner:
            warnings.warn("Skip PyMOL png because CI runner is detected")
            return
        if self.SKIP_PYMOL_PNG:
            warnings.warn(f"Skip PyMOL png because an environment variable is set: {self.SKIP_PYMOL_PNG=}")
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

    def wait_for_file(self, file: str, interval: int = 100, timeout: float = 61.0) -> bool:
        started_moment = time.perf_counter()
        while True:
            self.qtbot.wait(interval)
            if os.path.exists(file):
                return True
            check_moment = time.perf_counter()
            if check_moment - started_moment > timeout:
                raise TimeoutError(f"File {file} is not available within timeout limit ({timeout} sec).")

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
        mem_count_file = os.path.join("performance", f"ram_usage_{self.run_time}.log")
        with open(mem_count_file, "w") as mc:
            mc.write("\n".join([self.print_mem(p) for p in procs]))

    def inject_rosetta_node_config(self, node_hint: NodeHintT):
        self.plugin.bus.set_value("rosetta.node_hint", node_hint or "native")

    def teardown(self):
        # check_real_config_dir()
        self.performace_report()
        self.plugin.reinitialize()

        # deep reset again to avoild downstream side effects
        set_REvoDesign_config_file(True)
        cmd.reinitialize()

        reset_singletons()

        gc.collect()

# fixtures to patch user cache/data dir are still required
@pytest.fixture
def patch_config_user_cache():
    os.makedirs(cache_dirname, exist_ok=True)

    with patch("REvoDesign.bootstrap.set_config.user_cache_dir", return_value=cache_dirname) as mock_user_cache_dir:
        yield mock_user_cache_dir

@pytest.fixture
def patch_config_user_data():
    os.makedirs(data_dirname, exist_ok=True)
    with patch("REvoDesign.bootstrap.set_config.user_data_dir", return_value=data_dirname) as mock_user_cache_dir:
        yield mock_user_cache_dir


@pytest.fixture
def test_worker(
    qtbot: qtbot.QtBot,
    plugin,
    request,
    patch_config_user_data,
    patch_config_user_cache,
):
    # move test worker config to another place so it won't pollute the production

    workspace_data=patch_config_user_data()

    os.makedirs(workspace_data, exist_ok=True)
    
    w = TestWorker(qtbot, plugin)

    def final_action():
        w.teardown()

    yield w
    request.addfinalizer(final_action)


@pytest.fixture
def pm_test_worker(
    qtbot: qtbot.QtBot,
    pm_plugin,
    request,
):
    w = PmTestWorker(qtbot, pm_plugin)

    def final_action():
        gc.collect()

    yield w
    request.addfinalizer(final_action)


@pytest.fixture(scope="session")
def KeyDataDuringTests():
    return KeyData()


@pytest.fixture
def test_tmp_dir():
    with tmpdir_manager() as tmpdir:
        yield tmpdir


# rosetta test configuration from RosettaPy


def has_native_rosetta():
    import subprocess

    result = subprocess.run(["whichrosetta", "rosetta_scripts"], capture_output=True, text=True)
    # Check that the command was successful
    has_rosetta_installed = "rosetta_scripts" in result.stdout
    warnings.warn(UserWarning(f"Rosetta Installed: {has_rosetta_installed} - {result.stdout}"))
    return has_rosetta_installed


HAS_NATIVE_ROSETTA = has_native_rosetta()


def github_rosetta_test():
    return os.environ.get("GITHUB_ROSETTA_TEST", "NO") == "YES"


# Determine if running in GitHub Actions
is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"

has_docker = shutil.which("docker") is not None

# Github Actions, Ubuntu-latest with Rosetta Docker container enabled
ENABLE_ROSETTA_CONTAINER_NODE_TEST = os.environ.get("ENABLE_ROSETTA_CONTAINER_NODE_TEST", "NO") == "YES"

WINDOWS_WITH_WSL = platform.system() == "Windows" and shutil.which("wsl") is not None


@pytest.fixture(
    params=[
        pytest.param(
            "docker_mpi",
            marks=pytest.mark.skipif(
                not ENABLE_ROSETTA_CONTAINER_NODE_TEST, reason="Skipping docker tests in GitHub Actions"
            ),
        ),
        pytest.param(
            "native",
            marks=pytest.mark.skipif(not HAS_NATIVE_ROSETTA, reason="No Rosetta Installed."),
        ),
    ]
)
def test_node_hint(request):
    return request.param


def chech_memory_available():
    return psutil.virtual_memory().available / (1024**3)


MEMORY_AVAILABLE_GB = chech_memory_available()


def fetch_node_config_from_hint(node_hint: NodeHintT):
    # fetch node config according to node_hint
    node_config = ConfigConverter.convert(
        reload_config_file(f"rosetta-node/{node_hint}")["rosetta-node"]["node_config"]
    )

    warnings.warn(RuntimeWarning(f"Using rosetta-node/{test_node_hint} as node config: {node_config}"))
    return node_config


@pytest.fixture
def mock_rosetta_node_config(test_node_hint):
    """
    Fixture to mock rosetta node configuration for tests

    This fixture sets up the rosetta node hint in ConfigBus and patches the
    read_rosetta_node_config function to return the node configuration
    corresponding to the test_node_hint.

    Parameters:
        test_node_hint: The node hint to use for fetching node configuration

    Yields:
        node_config: The mocked node configuration dictionary
    """
    # real test node inject
    ConfigBus().set_value("rosetta.node_hint", test_node_hint)

    with patch("REvoDesign.tools.rosetta_utils.read_rosetta_node_config") as mock_read_rosetta_node_config:

        node_config = fetch_node_config_from_hint(test_node_hint)
        mock_read_rosetta_node_config.return_value = node_config
        yield node_config
