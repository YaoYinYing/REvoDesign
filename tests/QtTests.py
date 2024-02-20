from dataclasses import dataclass
import os
import glob
from typing import Union

os.environ['PYTEST_QT_API'] = 'pyqt5'
import time
from pymol import cmd, util, CmdException
import pytest
from pytestqt import qtbot

from pymol.Qt import QtWidgets, QtCore, QtGui
from tests.TestData import TestData

from REvoDesign import REvoDesignPlugin

from REvoDesign.tools.customized_widgets import (
    get_widget_value,
    set_widget_value,
)

TEST_DIR = os.path.abspath('.')
os.makedirs(TEST_DIR, exist_ok=True)


@dataclass
class AUTO_TEST_DATA(TestData):
    test_data_repo: str = TEST_DIR


for sub_dirs in [
    'analysis',
    'surface_residue_records',
    'mutagenese',
]:
    os.makedirs(sub_dirs, exist_ok=True)


class TestWorker:
    def __init__(
        self, revo_design_plugin: REvoDesignPlugin, qtbot: qtbot.QtBot
    ):
        from REvoDesign.tools.system_tools import CLIENT_INFO

        self.revo_design_plugin = revo_design_plugin
        self.qtbot = qtbot
        self.tab_widget_mapping: dict[str, QtWidgets.QWidget] = {
            'prepare': self.revo_design_plugin.ui.tab_prepare,
            'mutate': self.revo_design_plugin.ui.tab_mutate,
            'evaluate': self.revo_design_plugin.ui.tab_evaluate,
            'cluster': self.revo_design_plugin.ui.tab_cluster,
            'visualize': self.revo_design_plugin.ui.tab_visualize,
            'interact': self.revo_design_plugin.ui.tab_interact,
            'client': self.revo_design_plugin.ui.tab_client,
            'socket': self.revo_design_plugin.ui.tab_socket,
            'config': self.revo_design_plugin.ui.tab_config,
        }
        self.test_data = AUTO_TEST_DATA()

        self.DOWNLOAD_DIR = os.path.abspath('../tests/downloaded')
        os.makedirs(self.DOWNLOAD_DIR, exist_ok=True)
        self.EXPANDED_DIR = os.path.abspath(
            '../tests/expanded_compressed_files'
        )
        os.makedirs(self.EXPANDED_DIR, exist_ok=True)

        self.client_info = CLIENT_INFO()
        self.CURSOR = QtCore.Qt.MouseButton.LeftButton

        self.SCREENSHOT_DIR = os.path.join(os.path.abspath('.'), 'screenshots')
        os.makedirs(self.SCREENSHOT_DIR, exist_ok=True)

        self.PYMOL_PNG_DIR = os.path.join(
            os.path.abspath('.'), 'pymol_screenshots'
        )
        os.makedirs(self.PYMOL_PNG_DIR, exist_ok=True)

        # determine which runner carries this test
        self.in_which_runner: dict[str, bool] = {
            'CIRCLECI': bool(os.environ.get('CIRCLE_OIDC_TOKEN')),
            'GITHUB': bool(os.environ.get('GITHUB_ACTION')),
            'MACBOOKPRO': bool(os.environ.get('PROTEIN_DESIGN_KIT')),
        }

        self.in_ci_runner= (self.in_which_runner.get('CIRCLECI') or self.in_which_runner.get('GITHUB'))

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
        nproc = get_widget_value(self.revo_design_plugin.ui.spinBox_nproc)
        print(f'nproc: {nproc}')
        if (
            self.in_which_runner.get('CIRCLECI')
            and nproc > self.test_data.nproc_circleci
        ):
            print(
                f'Fix nproc to reduce performance for CircleCI: {nproc} {os.cpu_count()}-> {self.test_data.nproc_circleci}'
            )
            set_widget_value(
                self.revo_design_plugin.ui.spinBox_nproc,
                self.test_data.nproc_circleci,
            )
        if from_rcsb:
            self._fetch_pdb()
        else:
            if not customized_session:
                customized_session = self.test_data.pocket_pse
            self._load_pocket_pse(customized_session)

        self.qtbot.wait(100)

        self.revo_design_plugin.reload_molecule_info(
        )
        self.check_molecule_after_loaded()

    def click(self, widget: QtWidgets.QWidget, times: int = 1):
        for t in range(times):
            self.qtbot.mouseClick(widget, self.CURSOR)

    def _navigate_to_tab(
        self, tab: QtWidgets.QWidget, page: QtWidgets.QWidget
    ):
        tab.setCurrentWidget(page)

    def go_to_tab(self, tab_name: str):
        self._navigate_to_tab(
            tab=self.revo_design_plugin.ui.tabWidget,
            page=self.tab_widget_mapping.get(tab_name),
        )

    def check_molecule_after_loaded(self):
        assert (
            self.revo_design_plugin.design_molecule == self.test_data.molecule
        )
        assert (
            self.revo_design_plugin.design_chain_id == self.test_data.chain_id
        )
        assert (
            get_widget_value(
                self.revo_design_plugin.ui.comboBox_design_molecule
            )
            == self.test_data.molecule
        )
        assert (
            get_widget_value(self.revo_design_plugin.ui.comboBox_chain_id)
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

        mutant_tree: MutantTree = existed_mutant_tree(
            sequences=self.revo_design_plugin.designable_sequences
        )

        assert not mutant_tree.empty

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
        if self.in_ci_runner:
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
        if self.in_ci_runner:
            return 
        if spells:
            cmd.do(spells)
        png_file = os.path.join(self.PYMOL_PNG_DIR, f'{basename}.png')
        cmd.png(png_file, dpi=dpi, ray=use_ray)


def wait_for_file(
    qtbot: qtbot.QtBot, file: str, interval: str = 100, timeout: float = 61.0
) -> Union[bool, None]:
    started_moment = time.perf_counter()
    while True:
        qtbot.wait(interval)
        if os.path.exists(file):
            return True
        check_moment = time.perf_counter()
        if check_moment - started_moment > timeout:
            raise TimeoutError(
                f'File {file} is not available within timeout limit ({timeout} sec).'
            )


@pytest.fixture(scope="session")
def app():
    # Initialize the QApplication instance required for the plugin GUI
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def revo_design_plugin(qtbot, app):
    # Create and return an instance of the REvoDesignPlugin
    plugin = REvoDesignPlugin()
    if not plugin.window:
        plugin.run_plugin_gui()
    qtbot.addWidget(
        plugin.window
    )  # Add the plugin's main window to qtbot for automatic cleanup
    return plugin


@dataclass
class KeyDataDuringTests:
    pocket_files: list[str] = None
    hetatm_pocket_sele: str = None
    design_shell_file: str = None
    surface_file: str = None
    pssm_file: str = None


class TestREvoDesignPlugin:
    def test_plugin_gui_visibility(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        # Check if the main window of the plugin is visible
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        assert revo_design_plugin.window.isVisible()
        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        for tab in WORKER.tab_widget_mapping.keys():
            WORKER.go_to_tab(tab_name=tab)
            WORKER.save_screenshot(
                widget=revo_design_plugin.window,
                basename=f'test_tab_{tab}',
            )


@pytest.mark.usefixtures("qtbot")
class TestREvoDesignPlugin_TabPrepare:
    def test_load_molecule(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check(from_rcsb=True)
        WORKER.go_to_tab(tab_name='prepare')

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

    def test_pocket(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check(from_rcsb=True)
        WORKER.go_to_tab(tab_name='prepare')

        set_widget_value(
            revo_design_plugin.ui.comboBox_ligand_sel,
            WORKER.test_data.substrate,
        )
        set_widget_value(
            revo_design_plugin.ui.comboBox_cofactor_sel,
            WORKER.test_data.cofactor,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_pocket,
            WORKER.test_data.pocket_pse,
        )

        qtbot.wait(100)
        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_run_pocket_detection,
        )
        qtbot.wait(100)

        pocket_file_dir = os.path.abspath('./pockets/')
        assert os.path.exists(WORKER.test_data.pocket_pse)
        assert os.path.exists(pocket_file_dir)
        pocket_files = glob.glob(os.path.join(pocket_file_dir, '*.txt'))
        assert len(pocket_files) == 4

        pocket_file_design_shell = [
            fn for fn in pocket_files if 'design_shell' in fn
        ][0]

        KeyDataDuringTests.design_shell_file = os.path.join(
            pocket_file_dir, os.path.basename(pocket_file_design_shell)
        )

        assert pocket_file_design_shell is not None

        with open(pocket_file_design_shell, 'r') as ds_fr:
            design_shell_residue_ids = ds_fr.read().strip()
            assert design_shell_residue_ids

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

    def test_surface(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='prepare')

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_run_surface_refresh
        )

        hetatm_residues = [
            sel
            for sel in cmd.get_names(type='selections')
            if 'pkt_hetatm_' in sel
        ][0]
        assert hetatm_residues

        KeyDataDuringTests.hetatm_pocket_sele = hetatm_residues

        set_widget_value(
            revo_design_plugin.ui.comboBox_surface_exclusion, hetatm_residues
        )

        set_widget_value(
            revo_design_plugin.ui.doubleSpinBox_surface_cutoff,
            WORKER.test_data.suface_probe,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_surface,
            WORKER.test_data.surface_pse,
        )

        qtbot.wait(100)
        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_run_surface_detection,
        )
        qtbot.wait(100)

        surface_dir = os.path.abspath('./surface_residue_records/')
        assert os.path.exists(WORKER.test_data.surface_pse)
        assert os.path.exists(surface_dir)
        surface_files = glob.glob(
            os.path.join(
                surface_dir,
                f'{WORKER.test_data.molecule}_residues_cutoff_{WORKER.test_data.suface_probe:.1f}.txt',
            )
        )
        assert len(surface_files) == 1

        surface_file_design_shell = [
            fn for fn in surface_files if 'residues_cutoff' in fn
        ][0]

        assert surface_file_design_shell is not None

        KeyDataDuringTests.surface_file = os.path.join(
            surface_dir, os.path.basename(surface_file_design_shell)
        )

        with open(surface_file_design_shell, 'r') as ss_fr:
            surface_residue_ids = ss_fr.read().strip()
            assert surface_residue_ids

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())


@pytest.mark.usefixtures("qtbot")
class TestREvoDesignPlugin_TabMutate:
    def test_pssm_ent_surf(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='mutate')

        expected_downloaded_file = WORKER.download_file(
            url=WORKER.test_data.PSSM_GREMLIN_DATA_URL,
            md5=WORKER.test_data.PSSM_GREMLIN_DATA_MD5,
        )

        dist_dir, expanded_files = WORKER.expand_zip(
            compressed_file=expected_downloaded_file
        )

        assert expanded_files
        pssm_file = os.path.join(
            dist_dir,
            'pssm_msa',
            f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}_ascii_mtx_file',
        )
        assert os.path.exists(pssm_file)

        KeyDataDuringTests.pssm_file = pssm_file

        set_widget_value(revo_design_plugin.ui.lineEdit_input_csv, pssm_file)
        set_widget_value(
            revo_design_plugin.ui.lineEdit_input_customized_indices,
            KeyDataDuringTests.surface_file,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.entro_design_pse,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_score_minima,
            WORKER.test_data.entropy_min_score,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.entropy_max_score,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.entropy_reject,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.entropy_accept,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_design_case,
            WORKER.test_data.entropy_design_case,
        )

        if os.path.exists(WORKER.test_data.entro_design_pse):
            os.remove(WORKER.test_data.entro_design_pse)

        WORKER.click(widget=revo_design_plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.check_existed_mutant_tree()

    def test_mpnn_surf(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='mutate')

        set_widget_value(
            revo_design_plugin.ui.comboBox_profile_type,
            WORKER.test_data.mpnn_profile_type,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.mpnn_surface_residues,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.mpnn_design_pse,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.mpnn_reject,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.mpnn_accept,
        )

        set_widget_value(
            revo_design_plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.mpnn_score_reversed,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_design_case,
            WORKER.test_data.mpnn_design_case,
        )

        set_widget_value(
            revo_design_plugin.ui.doubleSpinBox_designer_temperature,
            WORKER.test_data.mpnn_temperature,
        )

        set_widget_value(
            revo_design_plugin.ui.spinBox_designer_batch,
            WORKER.test_data.mpnn_batch_designs,
        )
        set_widget_value(
            revo_design_plugin.ui.spinBox_designer_num_samples,
            WORKER.test_data.mpnn_num_designs,
        )
        set_widget_value(
            revo_design_plugin.ui.checkBox_deduplicate_designs,
            WORKER.test_data.mpnn_deduplicated,
        )

        if os.path.exists(WORKER.test_data.mpnn_design_pse):
            os.remove(WORKER.test_data.mpnn_design_pse)

        WORKER.click(widget=revo_design_plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.check_existed_mutant_tree()

    def test_ddg_surf_non_biolib_calling(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='mutate')

        local_ddg_file = WORKER.download_file(
            url=WORKER.test_data.PYTHIA_DDG_CSV_URL,
            md5=WORKER.test_data.PYTHIA_DDG_CSV_MD5,
        )

        set_widget_value(
            revo_design_plugin.ui.comboBox_profile_type,
            WORKER.test_data.ddg_profile_type_local,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_input_csv, local_ddg_file
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.ddg_surface_residues,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.ddg_design_non_biolib_pse,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_score_minima,
            WORKER.test_data.ddg_min_score,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.ddg_max_score,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.pocket_pssm_reject,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_preffer_substitution,
            '',
        )

        set_widget_value(
            revo_design_plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.ddg_score_reversed,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_design_case,
            WORKER.test_data.ddg_design_case,
        )

        if os.path.exists(WORKER.test_data.ddg_design_pse):
            os.remove(WORKER.test_data.ddg_design_case)

        WORKER.click(widget=revo_design_plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.check_existed_mutant_tree()

    # def test_ddg_surf_biolib_calling(
    #     self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    # ):
    #     WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
    #     WORKER.load_session_and_check()
    #     WORKER.go_to_tab(tab_name='mutate')

    #     set_widget_value(
    #         revo_design_plugin.ui.comboBox_profile_type,
    #         WORKER.test_data.ddg_profile_type_biolib,
    #     )

    #     set_widget_value(
    #         revo_design_plugin.ui.lineEdit_input_customized_indices,
    #         WORKER.test_data.ddg_surface_residues,
    #     )
    #     set_widget_value(
    #         revo_design_plugin.ui.lineEdit_output_pse_mutate,
    #         WORKER.test_data.ddg_design_pse,
    #     )

    #     set_widget_value(
    #         revo_design_plugin.ui.lineEdit_score_minima,
    #         WORKER.test_data.ddg_min_score,
    #     )
    #     set_widget_value(
    #         revo_design_plugin.ui.lineEdit_score_maxima,
    #         WORKER.test_data.ddg_max_score,
    #     )

    #     set_widget_value(
    #         revo_design_plugin.ui.lineEdit_reject_substitution,
    #         WORKER.test_data.pocket_pssm_reject,
    #     )
    #     set_widget_value(
    #         revo_design_plugin.ui.lineEdit_preffer_substitution,
    #         '',
    #     )

    #     set_widget_value(
    #         revo_design_plugin.ui.checkBox_reverse_mutant_effect,
    #         WORKER.test_data.ddg_score_reversed,
    #     )

    #     set_widget_value(
    #         revo_design_plugin.ui.lineEdit_design_case,
    #         WORKER.test_data.ddg_design_case,
    #     )

    #     if os.path.exists(WORKER.test_data.ddg_design_pse):
    #         os.remove(WORKER.test_data.ddg_design_case)

    #     WORKER.click(widget=revo_design_plugin.ui.pushButton_run_PSSM_to_pse)

    #     WORKER.save_screenshot(
    #         widget=revo_design_plugin.window,
    #         basename=WORKER.method_name(),
    #     )

    #     pythia_results = [
    #         f for f in os.listdir('pythia') if f.endswith('.csv')
    #     ]
    #     if pythia_results:
    #         WORKER.check_existed_mutant_tree()
    #         WORKER.save_pymol_png(basename=WORKER.method_name())

    def test_pssm_pocket_design(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='mutate')

        expected_downloaded_file = WORKER.download_file(
            url=WORKER.test_data.PSSM_GREMLIN_DATA_URL,
            md5=WORKER.test_data.PSSM_GREMLIN_DATA_MD5,
        )

        dist_dir, expanded_files = WORKER.expand_zip(
            compressed_file=expected_downloaded_file
        )

        assert expanded_files
        pssm_file = os.path.join(
            dist_dir,
            'pssm_msa',
            f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}_ascii_mtx_file',
        )
        assert os.path.exists(pssm_file)

        KeyDataDuringTests.pssm_file = pssm_file

        set_widget_value(revo_design_plugin.ui.lineEdit_input_csv, pssm_file)
        set_widget_value(
            revo_design_plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.pocket_pssm_residues,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.pocket_design_pse,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_score_minima,
            WORKER.test_data.pocket_pssm_min_score,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.pocket_pssm_max_score,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.pocket_pssm_reject,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.pocket_pssm_accept,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_design_case,
            WORKER.test_data.pocket_pssm_design_case,
        )

        if os.path.exists(WORKER.test_data.pocket_design_pse):
            os.remove(WORKER.test_data.pocket_design_pse)

        WORKER.click(widget=revo_design_plugin.ui.pushButton_run_PSSM_to_pse)
        WORKER.check_existed_mutant_tree()

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())


@pytest.mark.usefixtures("qtbot")
class TestREvoDesignPlugin_TabEvaluate:
    def test_evaluate_pssm_ent_surf_best_hits(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check(
            customized_session=WORKER.test_data.entro_design_pse
        )
        WORKER.go_to_tab(tab_name='evaluate')

        mutagenesis_dir = os.path.abspath('mutagenese')
        mutant_file = os.path.join(
            mutagenesis_dir, 'evaluate_pssm_ent_surf.besthits.mut.txt'
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_mut_table, mutant_file
        )
        set_widget_value(revo_design_plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            revo_design_plugin.ui.checkBox_reverse_mutant_effect_2,
            WORKER.test_data.entropy_score_reversed,
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_reinitialize_mutant_choosing
        )
        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_choose_lucky_mutant
        )

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        assert not revo_design_plugin.mutant_tree_pssm_selected.empty
        with open(mutant_file, 'r') as mr:
            picked_mutants = mr.read().strip().split('\n')

        picked_mutants = WORKER.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            revo_design_plugin.mutant_tree_pssm_selected.all_mutant_objects
        )

    def test_evaluate_pssm_ent_surf_mannual_pick(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check(
            customized_session=WORKER.test_data.entro_design_pse
        )
        WORKER.go_to_tab(tab_name='evaluate')

        mutagenesis_dir = os.path.abspath('mutagenese')
        mutant_file = os.path.join(
            mutagenesis_dir, 'evaluate_pssm_ent_surf.mannual.mut.txt'
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_mut_table, mutant_file
        )
        set_widget_value(revo_design_plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            revo_design_plugin.ui.checkBox_reverse_mutant_effect_2,
            WORKER.test_data.entropy_score_reversed,
        )
        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_reinitialize_mutant_choosing
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_next_mutant, times=2
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_accept_this_mutant
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_next_mutant, times=3
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_accept_this_mutant
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_next_mutant, times=2
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_accept_this_mutant
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_next_mutant, times=5
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_goto_best_hit_in_group
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_accept_this_mutant
        )

        WORKER.click(
            widget=revo_design_plugin.ui.pushButton_next_mutant, times=2
        )

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        assert not revo_design_plugin.mutant_tree_pssm_selected.empty
        with open(mutant_file, 'r') as mr:
            picked_mutants = mr.read().strip().split('\n')

        picked_mutants = WORKER.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            revo_design_plugin.mutant_tree_pssm_selected.all_mutant_objects
        )


@pytest.mark.usefixtures("qtbot")
class TestREvoDesignPlugin_TabConfig:
    def test_use_pippack_mpnn_design(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        WORKER = TestWorker(revo_design_plugin=revo_design_plugin, qtbot=qtbot)
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            revo_design_plugin.ui.comboBox_sidechain_solver, 'PIPPack'
        )
        assert (
            get_widget_value(
                revo_design_plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'ensemble'
        )

        set_widget_value(
            revo_design_plugin.ui.comboBox_sidechain_solver_model,
            'pippack_model_1',
        )
        assert (
            get_widget_value(
                revo_design_plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'pippack_model_1'
        )

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=f'{WORKER.method_name()}_use_PIPPack_model_1',
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        # back to tab mutate and run mpnn redesign, saved as another file
        WORKER.go_to_tab(tab_name='mutate')

        set_widget_value(
            revo_design_plugin.ui.comboBox_profile_type,
            WORKER.test_data.mpnn_profile_type,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.mpnn_surface_residues,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.pippack_pse,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.mpnn_reject,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.mpnn_accept,
        )

        set_widget_value(
            revo_design_plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.mpnn_score_reversed,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_design_case,
            WORKER.test_data.mpnn_design_case,
        )

        set_widget_value(
            revo_design_plugin.ui.doubleSpinBox_designer_temperature,
            WORKER.test_data.mpnn_temperature,
        )

        set_widget_value(
            revo_design_plugin.ui.spinBox_designer_batch,
            WORKER.test_data.mpnn_batch_designs,
        )
        set_widget_value(
            revo_design_plugin.ui.spinBox_designer_num_samples,
            WORKER.test_data.mpnn_num_designs,
        )
        set_widget_value(
            revo_design_plugin.ui.checkBox_deduplicate_designs,
            WORKER.test_data.mpnn_deduplicated,
        )

        if os.path.exists(WORKER.test_data.pippack_pse):
            os.remove(WORKER.test_data.pippack_pse)

        WORKER.click(widget=revo_design_plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=revo_design_plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.check_existed_mutant_tree()


if __name__ == '__main__' or __name__ == 'pymol':
    pytest.main()
