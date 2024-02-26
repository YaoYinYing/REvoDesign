from dataclasses import dataclass
import gc
import os
import glob
from typing import Union
from immutabledict import immutabledict
import psutil
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

@dataclass
class KeyDataDuringTests:
    pocket_files: list[str] = None
    hetatm_pocket_sele: str = None
    design_shell_file: str = None
    surface_file: str = None
    pssm_file: str = None
    gremlin_pkl_fp:str =None
    mutant_file: str =None
    minimum_mutant_file: str=None
    ddg_file: str = None



for sub_dirs in [
    'analysis',
    'surface_residue_records',
    'mutagenese',
    'performance'
]:
    os.makedirs(sub_dirs, exist_ok=True)

@pytest.fixture
def app():
    # Initialize the QApplication instance required for the plugin GUI
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def plugin(qtbot, app):
    # Create and return an instance of the REvoDesignPlugin
    plugin = REvoDesignPlugin()
    if not plugin.window:
        plugin.run_plugin_gui()
    qtbot.addWidget(
        plugin.window
    )  # Add the plugin's main window to qtbot for automatic cleanup
    return plugin



class TestWorker:
    def __init__(
        self, qtbot: qtbot.QtBot, plugin:REvoDesignPlugin
    ):
        from REvoDesign.tools.system_tools import CLIENT_INFO
        self.qtbot = qtbot
        self.plugin = plugin
        self.qtbot.addWidget(
            self.plugin.window
        )  # Add the plugin's main window to qtbot for automatic cleanup
        
        self.tab_widget_mapping: immutabledict[str, QtWidgets.QWidget] = immutabledict({
            'prepare': self.plugin.ui.tab_prepare,
            'mutate': self.plugin.ui.tab_mutate,
            'evaluate': self.plugin.ui.tab_evaluate,
            'cluster': self.plugin.ui.tab_cluster,
            'visualize': self.plugin.ui.tab_visualize,
            'interact': self.plugin.ui.tab_interact,
            'client': self.plugin.ui.tab_client,
            'socket': self.plugin.ui.tab_socket,
            'config': self.plugin.ui.tab_config,
        })
        self.test_data = AUTO_TEST_DATA()
        self.run_time=time.strftime("%Y%m%d_%H%M%S", time.localtime())

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

        self.in_ci_runner = self.in_which_runner.get(
            'CIRCLECI'
        ) or self.in_which_runner.get('GITHUB')

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

    def click(self, widget: QtWidgets.QWidget, times: int = 1):
        for t in range(times):
            self.qtbot.mouseClick(widget, self.CURSOR)
            self.sleep(100)
        return self
    
    def sleep(self,time=1000):
        self.qtbot.wait(time)

    def do_typing(self, widget: QtWidgets.QWidget, text: str, strict_mode:bool=False):
        set_widget_value(widget=widget, value='')
        # if text is short enough or in strict mode
        # type one after another
        if (len(text) < 10) or strict_mode:
            self.qtbot.keyClicks(widget, text)
            return
        # otherwise,
        # only type the last character to trigger hook connected to this widget
        _tex, _t=text[:-1], text[-1]
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
            self.plugin.design_molecule == self.test_data.molecule
        )
        assert (
            self.plugin.design_chain_id == self.test_data.chain_id
        )
        assert (
            get_widget_value(
                self.plugin.ui.comboBox_design_molecule
            )
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


    def wait_for_file( self, file: str, interval: str = 100, timeout: float = 61.0
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
        #print("Performance report...")
        self.print_all_mem()
        #gc.collect()
    

    def print_mem(self,p):
        rss = p.memory_info().rss
        return (f"[{p.pid}] memory usage: {rss / 1e6:0.3} MB")


    def print_all_mem(self):
        p = psutil.Process()
        procs = [p] + p.children(recursive=True)
        mem_count_file=os.path.join('performance', f'ram_usage_{self.run_time}.log')
        with open(mem_count_file,'w') as mc:
            mc.write('\n'.join([self.print_mem(p) for p in procs]))


        

@pytest.fixture
def WORKER(qtbot:qtbot.QtBot,plugin,request,):
    w=TestWorker(qtbot,plugin)
    def final_action():
        w.performace_report()
        w.plugin.reinitialize()
        gc.collect()
    yield w
    request.addfinalizer(final_action)
    


class TestREvoDesignPlugin:
    def test_plugin_gui_visibility(
        self, WORKER: TestWorker
    ):
        # Check if the main window of the plugin is visible
        assert WORKER.plugin.window.isVisible()
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        for tab in WORKER.tab_widget_mapping.keys():
            WORKER.go_to_tab(tab_name=tab)
            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'test_tab_{tab}',
            )


class TestREvoDesignPlugin_TabPrepare:
    def test_load_molecule(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check(from_rcsb=True)
        WORKER.go_to_tab(tab_name='prepare')

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

    def test_pocket(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check(from_rcsb=True)
        WORKER.go_to_tab(tab_name='prepare')

        WORKER.do_typing(
            WORKER.plugin.ui.comboBox_ligand_sel,
            WORKER.test_data.substrate,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.comboBox_cofactor_sel,
            WORKER.test_data.cofactor,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_pocket,
            WORKER.test_data.pocket_pse,
        )

        WORKER.qtbot.wait(100)
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.click(
            widget=WORKER.plugin.ui.pushButton_run_pocket_detection,
        )
        WORKER.qtbot.wait(100)

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

        WORKER.save_pymol_png(basename=WORKER.method_name())
        

    def test_surface(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='prepare')

        WORKER.click(
            widget=WORKER.plugin.ui.pushButton_run_surface_refresh
        )

        hetatm_residues = [
            sel
            for sel in cmd.get_names(type='selections')
            if 'pkt_hetatm_' in sel
        ][0]
        assert hetatm_residues

        KeyDataDuringTests.hetatm_pocket_sele = hetatm_residues

        WORKER.do_typing(
            WORKER.plugin.ui.comboBox_surface_exclusion, hetatm_residues
        )

        set_widget_value(
            WORKER.plugin.ui.doubleSpinBox_surface_cutoff,
            WORKER.test_data.suface_probe,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_surface,
            WORKER.test_data.surface_pse,
        )

        WORKER.qtbot.wait(100)
        WORKER.click(
            widget=WORKER.plugin.ui.pushButton_run_surface_detection,
        )
        WORKER.qtbot.wait(100)

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
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())
        



class TestREvoDesignPlugin_TabMutate:
    def test_pssm_ent_surf(
        self, WORKER: TestWorker
    ):
        
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

        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_csv, pssm_file)
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            KeyDataDuringTests.surface_file,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.entro_design_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_minima,
            WORKER.test_data.entropy_min_score,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.entropy_max_score,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.entropy_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.entropy_accept,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.entropy_design_case,
        )

        if os.path.exists(WORKER.test_data.entro_design_pse):
            os.remove(WORKER.test_data.entro_design_pse)

        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.check_existed_mutant_tree()
        

    def test_mpnn_surf(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='mutate')

        set_widget_value(
            WORKER.plugin.ui.comboBox_profile_type,
            WORKER.test_data.mpnn_profile_type,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.mpnn_surface_residues,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.mpnn_design_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.mpnn_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.mpnn_accept,
        )

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.mpnn_score_reversed,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.mpnn_design_case,
        )

        set_widget_value(
            WORKER.plugin.ui.doubleSpinBox_designer_temperature,
            WORKER.test_data.mpnn_temperature,
        )

        set_widget_value(
            WORKER.plugin.ui.spinBox_designer_batch,
            WORKER.test_data.mpnn_batch_designs,
        )
        set_widget_value(
            WORKER.plugin.ui.spinBox_designer_num_samples,
            WORKER.test_data.mpnn_num_designs,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_deduplicate_designs,
            WORKER.test_data.mpnn_deduplicated,
        )

        if os.path.exists(WORKER.test_data.mpnn_design_pse):
            os.remove(WORKER.test_data.mpnn_design_pse)

        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.check_existed_mutant_tree()
        

    def test_ddg_surf_non_biolib_calling(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='mutate')

        local_ddg_file = WORKER.download_file(
            url=WORKER.test_data.PYTHIA_DDG_CSV_URL,
            md5=WORKER.test_data.PYTHIA_DDG_CSV_MD5,
        )

        KeyDataDuringTests.ddg_file=local_ddg_file

        WORKER.do_typing(
            WORKER.plugin.ui.comboBox_profile_type,
            WORKER.test_data.ddg_profile_type_local,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_csv, local_ddg_file
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.ddg_surface_residues,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.ddg_design_non_biolib_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_minima,
            WORKER.test_data.ddg_min_score,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.ddg_max_score,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.pocket_pssm_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            '',
        )

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.ddg_score_reversed,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.ddg_design_case,
        )

        if os.path.exists(WORKER.test_data.ddg_design_pse):
            os.remove(WORKER.test_data.ddg_design_case)

        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.check_existed_mutant_tree()
        

    # def test_ddg_surf_biolib_calling(
    #     self, WORKER: TestWorker
    # ):
    #     
    #     WORKER.load_session_and_check()
    #     WORKER.go_to_tab(tab_name='mutate')

    #     set_widget_value(
    #         WORKER.plugin.ui.comboBox_profile_type,
    #         WORKER.test_data.ddg_profile_type_biolib,
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_input_customized_indices,
    #         WORKER.test_data.ddg_surface_residues,
    #     )
    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_output_pse_mutate,
    #         WORKER.test_data.ddg_design_pse,
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_score_minima,
    #         WORKER.test_data.ddg_min_score,
    #     )
    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_score_maxima,
    #         WORKER.test_data.ddg_max_score,
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_reject_substitution,
    #         WORKER.test_data.pocket_pssm_reject,
    #     )
    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_preffer_substitution,
    #         '',
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.checkBox_reverse_mutant_effect,
    #         WORKER.test_data.ddg_score_reversed,
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_design_case,
    #         WORKER.test_data.ddg_design_case,
    #     )

    #     if os.path.exists(WORKER.test_data.ddg_design_pse):
    #         os.remove(WORKER.test_data.ddg_design_case)

    #     WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

    #     WORKER.save_screenshot(
    #         widget=WORKER.plugin.window,
    #         basename=WORKER.method_name(),
    #     )

    #     pythia_results = [
    #         f for f in os.listdir('pythia') if f.endswith('.csv')
    #     ]
    #     if pythia_results:
    #         WORKER.check_existed_mutant_tree()
    #         WORKER.save_pymol_png(basename=WORKER.method_name())

    def test_pssm_pocket_design_dunbrack(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver, 'Dunbrack Rotamer Library'
        )
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

        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_csv, pssm_file)
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.pocket_pssm_residues,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.pocket_design_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_minima,
            WORKER.test_data.pocket_pssm_min_score,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.pocket_pssm_max_score,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.pocket_pssm_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.pocket_pssm_accept,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.pocket_pssm_design_case,
        )

        if os.path.exists(WORKER.test_data.pocket_design_pse):
            os.remove(WORKER.test_data.pocket_design_pse)

        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)
        WORKER.check_existed_mutant_tree()

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())
        



class TestREvoDesignPlugin_TabEvaluate:
    def test_evaluate_pssm_ent_surf_best_hits(
        self, WORKER: TestWorker
    ):
        
        pse_path = WORKER.download_file(
            url=WORKER.test_data.EVALUATION_PSE_URL,
            md5=WORKER.test_data.EVALUATION_PSE_MD5,
        )
        WORKER.load_session_and_check(customized_session=pse_path)
        WORKER.go_to_tab(tab_name='evaluate')

        mutagenesis_dir = os.path.abspath('mutagenese')
        mutant_file = os.path.join(
            mutagenesis_dir, 'evaluate_pssm_ent_surf.besthits.mut.txt'
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_mut_table, mutant_file
        )
        set_widget_value(WORKER.plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect_2,
            WORKER.test_data.entropy_score_reversed,
        )

        WORKER.click(
            widget=WORKER.plugin.ui.pushButton_reinitialize_mutant_choosing
        )
        WORKER.click(
            widget=WORKER.plugin.ui.pushButton_choose_lucky_mutant
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        assert not WORKER.plugin.evaluator.mutant_tree_pssm_selected.empty
        with open(mutant_file, 'r') as mr:
            picked_mutants = mr.read().strip().split('\n')

        picked_mutants = WORKER.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            WORKER.plugin.evaluator.mutant_tree_pssm_selected.all_mutant_objects
        )
        KeyDataDuringTests.mutant_file=mutant_file
        

    def test_evaluate_pssm_ent_surf_mannual_pick(
        self, WORKER: TestWorker
    ):
        
        pse_path = WORKER.download_file(
            url=WORKER.test_data.EVALUATION_PSE_URL,
            md5=WORKER.test_data.EVALUATION_PSE_MD5,
        )
        WORKER.load_session_and_check(customized_session=pse_path)
        WORKER.go_to_tab(tab_name='evaluate')

        mutagenesis_dir = os.path.abspath('mutagenese')
        mutant_file = os.path.join(
            mutagenesis_dir, 'evaluate_pssm_ent_surf.mannual.mut.txt'
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_mut_table, mutant_file
        )
        set_widget_value(WORKER.plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect_2,
            WORKER.test_data.entropy_score_reversed,
        )
        _init = WORKER.plugin.ui.pushButton_reinitialize_mutant_choosing
        _next = WORKER.plugin.ui.pushButton_next_mutant
        _last = WORKER.plugin.ui.pushButton_previous_mutant
        _acp = WORKER.plugin.ui.pushButton_accept_this_mutant
        _rjct = WORKER.plugin.ui.pushButton_reject_this_mutant
        _bsh = WORKER.plugin.ui.pushButton_goto_best_hit_in_group

        WORKER.click(_init).click(_next, 2).click(_acp)

        WORKER.click(_next, 3).click(_acp)

        WORKER.click(_next, 2).click(_acp)

        WORKER.click(_next, 5).click(_bsh).click(_acp)

        assert int(get_widget_value(WORKER.plugin.ui.lcdNumber_selected_mutant))==4

        WORKER.click(_next, 2)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        assert not WORKER.plugin.evaluator.mutant_tree_pssm_selected.empty
        with open(mutant_file, 'r') as mr:
            picked_mutants = mr.read().strip().split('\n')

        picked_mutants = WORKER.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            WORKER.plugin.evaluator.mutant_tree_pssm_selected.all_mutant_objects
        )
        KeyDataDuringTests.minimum_mutant_file=mutant_file
        
        


class TestREvoDesignPlugin_TabCluster:
    def test_cluster(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='cluster')
        
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_mut_table, KeyDataDuringTests.mutant_file)
        
        set_widget_value(WORKER.plugin.ui.spinBox_num_cluster, WORKER.test_data.cluster_num)
        set_widget_value(WORKER.plugin.ui.spinBox_num_mut_minimun, WORKER.test_data.cluster_min)
        set_widget_value(WORKER.plugin.ui.spinBox_num_mut_maximum, WORKER.test_data.cluster_max)
        set_widget_value(WORKER.plugin.ui.spinBox_cluster_batchsize, WORKER.test_data.cluster_batch)
        set_widget_value(WORKER.plugin.ui.checkBox_shuffle_clustering, WORKER.test_data.cluster_shuffle)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_before_run',
        )
        WORKER.click(WORKER.plugin.ui.pushButton_run_cluster)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_after_run',
        )
        
        for mut_num in range(WORKER.test_data.cluster_min,WORKER.test_data.cluster_max+1):
            dir=f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}_{os.path.basename(KeyDataDuringTests.mutant_file).replace(".txt","")}_designs_{mut_num}'
            assert os.path.exists(dir)
            assert all([os.path.exists(os.path.join(dir, f'c.{c}.fasta')) for c in range(WORKER.test_data.cluster_num)])
            assert os.path.exists(os.path.join(dir, 'cluster_centers_stochastic.fasta'))

        


class TestREvoDesignPlugin_TabVisualize:
    def test_visualize_pssm_ddg(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver, 'PIPPack'
        )
        WORKER.go_to_tab(tab_name='visualize')

        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_mut_table_csv, KeyDataDuringTests.minimum_mutant_file)
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_output_pse_visualize, WORKER.test_data.visualize_1_pse)
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_csv_2, KeyDataDuringTests.ddg_file)
        set_widget_value(WORKER.plugin.ui.comboBox_profile_type_2, WORKER.test_data.visualize_1_profile_type)

        set_widget_value(WORKER.plugin.ui.checkBox_global_score_policy, WORKER.test_data.visualize_1_use_global_score)
        set_widget_value(WORKER.plugin.ui.checkBox_reverse_mutant_effect_3, WORKER.test_data.visualize_1_score_reversed)
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_group_name, WORKER.test_data.visualize_1_design_case)
        
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_before_run',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_run_visualizing)

        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_after_run',
        )

        assert os.path.exists(WORKER.test_data.visualize_1_pse)
        WORKER.check_existed_mutant_tree()
        

    def test_visualize_pssm_mpnn(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver, 'PIPPack'
        )
        WORKER.go_to_tab(tab_name='visualize')

        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_mut_table_csv, KeyDataDuringTests.minimum_mutant_file)
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_output_pse_visualize, WORKER.test_data.visualize_2_pse)
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_csv_2, '')
        set_widget_value(WORKER.plugin.ui.comboBox_profile_type_2, WORKER.test_data.visualize_2_profile_type)

        set_widget_value(WORKER.plugin.ui.checkBox_global_score_policy, WORKER.test_data.visualize_2_use_global_score)
        set_widget_value(WORKER.plugin.ui.checkBox_reverse_mutant_effect_3, WORKER.test_data.visualize_2_score_reversed)
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_group_name, WORKER.test_data.visualize_2_design_case)
        
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_before_run',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_run_visualizing)
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_after_run',
        )

        assert os.path.exists(WORKER.test_data.visualize_2_pse)
        WORKER.check_existed_mutant_tree()
        



class TestREvoDesignPlugin_TabConfig:
    def test_use_pippack_mpnn_design(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver, 'PIPPack'
        )
        assert (
            get_widget_value(
                WORKER.plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'ensemble'
        )

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver_model,
            'pippack_model_1',
        )
        assert (
            get_widget_value(
                WORKER.plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'pippack_model_1'
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_use_PIPPack_model_1',
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        # back to tab mutate and run mpnn redesign, saved as another file
        WORKER.go_to_tab(tab_name='mutate')

        set_widget_value(
            WORKER.plugin.ui.comboBox_profile_type,
            WORKER.test_data.mpnn_profile_type,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.mpnn_surface_residues,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.pippack_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.mpnn_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.mpnn_accept,
        )

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.mpnn_score_reversed,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.mpnn_design_case,
        )

        set_widget_value(
            WORKER.plugin.ui.doubleSpinBox_designer_temperature,
            WORKER.test_data.mpnn_temperature,
        )

        set_widget_value(
            WORKER.plugin.ui.spinBox_designer_batch,
            WORKER.test_data.mpnn_batch_designs,
        )
        set_widget_value(
            WORKER.plugin.ui.spinBox_designer_num_samples,
            WORKER.test_data.mpnn_num_designs,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_deduplicate_designs,
            WORKER.test_data.mpnn_deduplicated,
        )

        if os.path.exists(WORKER.test_data.pippack_pse):
            os.remove(WORKER.test_data.pippack_pse)

        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.method_name(),
        )
        WORKER.save_pymol_png(basename=WORKER.method_name())

        WORKER.check_existed_mutant_tree()
        



class TestREvoDesignPlugin_TabInteract:
    def test_gremlin_all2all(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='interact')

        # buttons
        _next=WORKER.plugin.ui.pushButton_next
        _prev=WORKER.plugin.ui.pushButton_previous

        _accp=WORKER.plugin.ui.pushButton_interact_accept
        _rjct=WORKER.plugin.ui.pushButton_interact_reject

        gremlin_pkl_fp=os.path.join(WORKER.EXPANDED_DIR,'gremlin_res',f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}.i90c75_aln.GREMLIN.mrf.pkl')

        set_widget_value(WORKER.plugin.ui.lineEdit_input_gremlin_mtx, gremlin_pkl_fp)
        KeyDataDuringTests.gremlin_pkl_fp=gremlin_pkl_fp

        mutfile=os.path.join('mutagenese','gremlin_a2a.mut.txt')

        WORKER.do_typing(WORKER.plugin.ui.lineEdit_output_mutant_table,mutfile )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_before_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_reinitialize_interact)

        # assert os.path.exists(WORKER.test_data.visualize_2_pse)

        #WORKER.wait_for_file(file=f'{WORKER.test_data.molecule}_GREMLIN_mtx_zscore.png', interval=100,timeout=10)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_after_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_run_interact_scan)

        WORKER.sleep(2000)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_after_scan',
        )

        WORKER.save_pymol_png(basename=f'{WORKER.method_name()}_interact_pairs')

        ce_links=[sel for sel in cmd.get_names(type='selections')if sel.startswith('ce_pairs')]
        for sel in ce_links:
            cmd.disable(sel)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_pair_0',
        )

        a2a_dir='gremlin_co_evolved_pairs/all_vs_all'

        assert os.path.exists(a2a_dir)
        csv_files=[f for f in os.listdir(a2a_dir) if f.startswith('Top.') and f.endswith('.csv')]
        assert len(csv_files) == get_widget_value(WORKER.plugin.ui.spinBox_gremlin_topN)

        WORKER.click(_next,2)
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_pair_2',
        )

        for row,col in [(6,1,), (3,13)]:
            WORKER.click(WORKER.plugin.bus.w2c.get_button_from_id(f'{row}_vs{col}',prefix='matrixButton'))

            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'{WORKER.method_name()}_pick_{row}_{col}',
            )

            WORKER.save_pymol_png(basename=f'{WORKER.method_name()}_pick_{row}_{col}')
            WORKER.check_existed_mutant_tree()

            cmd.orient(WORKER.mutant_tree.all_mutant_objects[0].short_mutant_id)
            
            WORKER.save_pymol_png(basename=f'{WORKER.method_name()}_pick_{row}_{col}_orient')
            WORKER.click(_accp)

        cmd.orient(WORKER.test_data.molecule)

        WORKER.click(_next,2).save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_next_2',
        )

        WORKER.click(_prev,7).save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_prev_7',
        )
        assert os.path.exists(mutfile)

    def test_gremlin_one2all_mpnn_score(
        self, WORKER: TestWorker
    ):
        
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='interact')

        sele_resi=295
        cmd.select('sele', f'{WORKER.test_data.molecule} and c. {WORKER.test_data.chain_id} and i. {sele_resi} and n. CA')
        cmd.enable('sele')
        
        # buttons
        _next=WORKER.plugin.ui.pushButton_next
        _prev=WORKER.plugin.ui.pushButton_previous

        _accp=WORKER.plugin.ui.pushButton_interact_accept
        _rjct=WORKER.plugin.ui.pushButton_interact_reject

        gremlin_pkl_fp=os.path.join(WORKER.EXPANDED_DIR,'gremlin_res',f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}.i90c75_aln.GREMLIN.mrf.pkl')

        set_widget_value(WORKER.plugin.ui.lineEdit_input_gremlin_mtx, gremlin_pkl_fp)
        KeyDataDuringTests.gremlin_pkl_fp=gremlin_pkl_fp

        mutfile=os.path.join('mutagenese','gremlin_o2a.mut.txt')

        WORKER.do_typing(WORKER.plugin.ui.lineEdit_output_mutant_table,mutfile )

        set_widget_value(WORKER.plugin.ui.comboBox_external_scorer, 'ProteinMPNN')

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_before_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_reinitialize_interact)

        # assert os.path.exists(WORKER.test_data.visualize_2_pse)

        #WORKER.wait_for_file(file=f'{WORKER.test_data.molecule}_GREMLIN_mtx_zscore.png', interval=100,timeout=20)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_after_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_run_interact_scan)

        WORKER.sleep(2000)
        
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_after_scan',
        )

        WORKER.save_pymol_png(basename=f'{WORKER.method_name()}_interact_pairs')

        ce_links=[sel for sel in cmd.get_names(type='selections')if sel.startswith('ce_pairs')]
        for sel in ce_links:
            cmd.disable(sel)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_pair_0',
        )

        o2a_dir=f'gremlin_co_evolved_pairs/resi_{sele_resi}'

        assert os.path.exists(o2a_dir)
        csv_files=[f for f in os.listdir(o2a_dir) if f.startswith('Top.') and f.endswith('.csv')]
        assert len(csv_files) == get_widget_value(WORKER.plugin.ui.spinBox_gremlin_topN)

        WORKER.click(_next,1)
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_pair_1',
        )

        for row,col in [(0,19,), (9,0)]:
            WORKER.click(WORKER.plugin.bus.w2c.get_button_from_id(f'{col}_vs{row}',prefix='matrixButton'))

            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'{WORKER.method_name()}_pick_{row}_{col}',
            )

            WORKER.save_pymol_png(basename=f'{WORKER.method_name()}_pick_{row}_{col}')
            WORKER.check_existed_mutant_tree()

            cmd.orient(WORKER.mutant_tree.all_mutant_objects[0].short_mutant_id)
            
            WORKER.save_pymol_png(basename=f'{WORKER.method_name()}_pick_{row}_{col}_orient')
            WORKER.click(_accp)

        cmd.orient(WORKER.test_data.molecule)

        WORKER.click(_next,2).save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_next_2',
        )

        WORKER.click(_prev,7).save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.method_name()}_prev_7',
        )
        assert os.path.exists(mutfile)
        


if __name__ == '__main__' or __name__ == 'pymol':
    pytest.main()
