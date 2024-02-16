from dataclasses import dataclass
import os, shutil
import glob
from typing import Union

from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.tools.mutant_tools import existed_mutant_tree

os.environ['PYTEST_QT_API'] = 'pyqt5'
import time
from pymol import cmd, util, CmdException
import pytest
import pooch
from pytestqt import qtbot

from pymol.Qt import QtWidgets, QtCore, QtGui
from tests.TestData import TestData

from REvoDesign import REvoDesignPlugin
from REvoDesign.tools.system_tools import CLIENT_INFO
from REvoDesign.tools.customized_widgets import (
    get_widget_value,
    set_widget_value,
)

CURSOR = QtCore.Qt.MouseButton.LeftButton

TEST_DIR = os.path.abspath('.')
os.makedirs(TEST_DIR, exist_ok=True)


@dataclass
class AUTO_TEST_DATA(TestData):
    test_data_repo: str = TEST_DIR


for sub_dirs in [
    'analysis',
    'expanded_compressed_files',
    'surface_residue_records',
    'mutagenese',
]:
    os.makedirs(sub_dirs, exist_ok=True)

test_data = AUTO_TEST_DATA()
client_info = CLIENT_INFO()


def navigate_to_tab(tab: QtWidgets.QWidget, page: QtWidgets.QWidget):
    tab.setCurrentWidget(page)

def method_name():
    import sys
    return sys._getframe(1).f_code.co_name

def save_screenshot(
    qtbot: qtbot.QtBot,
    widget: QtWidgets.QWidget,
    path: str = os.path.join(os.path.abspath('.'), 'screenshots'),
    basename: str = 'default'
):
    os.makedirs(path, exist_ok=True)
    png_file = qtbot.screenshot(widget=widget)
    moved_file = os.rename(
        png_file, os.path.join(path, f'{basename}.png')
    )
    return moved_file


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


def fetch_pdb():
    try:
        molecules = cmd.get_names()
        print(f'Before fetch: {molecules}')
        cmd.fetch(test_data.molecule)
        cmd.do(test_data.post_fetch_spell)

        molecules = cmd.get_names()
        print(f'After fetch: {molecules}')
    except CmdException:
        pass


def load_pocket_pse():
    try:
        assert os.path.exists(test_data.pocket_pse)
        print(f'loading {test_data.pocket_pse}')
        cmd.reinitialize()
        cmd.load(test_data.pocket_pse)
    except CmdException:
        pass


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
        assert revo_design_plugin.window.isVisible()


@pytest.mark.usefixtures("qtbot")
class TestREvoDesignPlugin_TabPrepare:
    def test_load_molecule(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        fetch_pdb()
        revo_design_plugin.reload_molecule_info(
            revo_design_plugin.ui.comboBox_design_molecule
        )

        navigate_to_tab(
            tab=revo_design_plugin.ui.tabWidget,
            page=revo_design_plugin.ui.tab_mutate,
        )
        
        assert revo_design_plugin.design_molecule == test_data.molecule
        assert revo_design_plugin.design_chain_id == test_data.chain_id
        assert (
            get_widget_value(revo_design_plugin.ui.comboBox_design_molecule)
            == test_data.molecule
        )
        assert (
            get_widget_value(revo_design_plugin.ui.comboBox_chain_id)
            == test_data.chain_id
        )
        save_screenshot(qtbot=qtbot, widget=revo_design_plugin.window,basename=method_name())


    def test_pocket(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        fetch_pdb()
        qtbot.wait(100)
        revo_design_plugin.reload_molecule_info(
            revo_design_plugin.ui.comboBox_design_molecule
        )

        navigate_to_tab(
            tab=revo_design_plugin.ui.tabWidget,
            page=revo_design_plugin.ui.tab_prepare,
        )
        

        set_widget_value(
            revo_design_plugin.ui.comboBox_ligand_sel, test_data.substrate
        )
        set_widget_value(
            revo_design_plugin.ui.comboBox_cofactor_sel, test_data.cofactor
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_pocket,
            test_data.pocket_pse,
        )

        qtbot.wait(100)
        qtbot.mouseClick(
            revo_design_plugin.ui.pushButton_run_pocket_detection, CURSOR
        )
        qtbot.wait(100)

        pocket_file_dir = os.path.abspath('./pockets/')
        assert os.path.exists(test_data.pocket_pse)
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
        save_screenshot(qtbot=qtbot, widget=revo_design_plugin.window,basename=method_name())


    def test_surface(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        load_pocket_pse()

        qtbot.wait(100)

        revo_design_plugin.reload_molecule_info(
            revo_design_plugin.ui.comboBox_design_molecule
        )
        navigate_to_tab(
            tab=revo_design_plugin.ui.tabWidget,
            page=revo_design_plugin.ui.tab_prepare,
        )
        

        qtbot.mouseClick(
            revo_design_plugin.ui.pushButton_run_surface_refresh, CURSOR
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
            revo_design_plugin.ui.doubleSpinBox_surface_cutoff, test_data.suface_probe
        )
        
        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_surface,
            test_data.surface_pse,
        )

        qtbot.wait(100)
        qtbot.mouseClick(
            revo_design_plugin.ui.pushButton_run_surface_detection, CURSOR
        )
        qtbot.wait(100)

        surface_dir = os.path.abspath('./surface_residue_records/')
        assert os.path.exists(test_data.surface_pse)
        assert os.path.exists(surface_dir)
        surface_files = glob.glob(os.path.join(surface_dir, '*.txt'))
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

        save_screenshot(qtbot=qtbot, widget=revo_design_plugin.window,basename=method_name())


@pytest.mark.usefixtures("qtbot")
class TestREvoDesignPlugin_TabMutate:
    def test_pssm_ent_surf(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        load_pocket_pse()
        qtbot.wait(100)

        revo_design_plugin.reload_molecule_info(
            revo_design_plugin.ui.comboBox_design_molecule
        )

        navigate_to_tab(
            tab=revo_design_plugin.ui.tabWidget,
            page=revo_design_plugin.ui.tab_mutate,
        )
        

        download_dir = os.path.abspath('downloaded')
        os.makedirs(download_dir, exist_ok=True)
        expected_downloaded_file = os.path.join(
            download_dir, os.path.basename(test_data.PSSM_GREMLIN_DATA_URL)
        )
        if not os.path.exists(expected_downloaded_file):
            pooch.retrieve(
                url=test_data.PSSM_GREMLIN_DATA_URL,
                known_hash=test_data.PSSM_GREMLIN_DATA_MD5,
                progressbar=True,
                path=download_dir,
                fname=os.path.basename(test_data.PSSM_GREMLIN_DATA_URL),
            )

        assert os.path.exists(expected_downloaded_file)
        extracted_dir = os.path.abspath('expanded_compressed_files')
        os.makedirs(extracted_dir, exist_ok=True)

        expanded_dirs = [
            p
            for p in glob.glob(os.path.join(extracted_dir, '*'))
            if test_data.molecule in p
        ]
        if not expanded_dirs:
            import zipfile

            with zipfile.ZipFile(expected_downloaded_file, mode='r') as z:
                z.extractall(path=extracted_dir)

        extracted_files = os.listdir(extracted_dir)

        assert extracted_files
        pssm_file = os.path.join(
            extracted_dir,
            'pssm_msa',
            f'{test_data.molecule}_{test_data.chain_id}_ascii_mtx_file',
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
            test_data.entro_design_pse,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_score_minima,
            test_data.entropy_min_score,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_score_maxima,
            test_data.entropy_max_score,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_reject_substitution,
            test_data.entropy_reject,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_preffer_substitution,
            test_data.entropy_accept,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_design_case,
            test_data.entropy_design_case,
        )

        if os.path.exists(test_data.entro_design_pse):
            os.remove(test_data.entro_design_pse)

        qtbot.mouseClick(
            revo_design_plugin.ui.pushButton_run_PSSM_to_pse, CURSOR
        )

        assert revo_design_plugin.design_molecule == test_data.molecule
        assert revo_design_plugin.design_chain_id == test_data.chain_id
        assert (
            get_widget_value(revo_design_plugin.ui.comboBox_design_molecule)
            == test_data.molecule
        )
        assert (
            get_widget_value(revo_design_plugin.ui.comboBox_chain_id)
            == test_data.chain_id
        )

        mutant_tree = existed_mutant_tree(
            sequences=revo_design_plugin.designable_sequences
        )

        assert not mutant_tree.empty

        save_screenshot(qtbot=qtbot, widget=revo_design_plugin.window,basename=method_name())

    def test_mpnn_surf(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        load_pocket_pse()
        qtbot.wait(100)

        revo_design_plugin.reload_molecule_info(
            revo_design_plugin.ui.comboBox_design_molecule
        )

        navigate_to_tab(
            tab=revo_design_plugin.ui.tabWidget,
            page=revo_design_plugin.ui.tab_mutate,
        )
        

        set_widget_value(revo_design_plugin.ui.comboBox_profile_type, test_data.mpnn_profile_type)
        set_widget_value(
            revo_design_plugin.ui.lineEdit_input_customized_indices,
            test_data.mpnn_surface_residues
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_output_pse_mutate,
            test_data.mpnn_design_pse,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_reject_substitution,
            test_data.mpnn_reject,
        )
        set_widget_value(
            revo_design_plugin.ui.lineEdit_preffer_substitution,
            test_data.mpnn_accept,
        )

        set_widget_value(
            revo_design_plugin.ui.checkBox_reverse_mutant_effect,
            test_data.mpnn_score_reversed,
        )

        set_widget_value(
            revo_design_plugin.ui.lineEdit_design_case,
            test_data.mpnn_design_case,
        )

        set_widget_value(
            revo_design_plugin.ui.doubleSpinBox_designer_temperature,
            test_data.mpnn_temperature,
        )

        set_widget_value(
            revo_design_plugin.ui.spinBox_designer_batch,
            test_data.mpnn_batch_designs,
        )
        set_widget_value(
            revo_design_plugin.ui.spinBox_designer_num_samples,
            test_data.mpnn_num_designs,
        )
        set_widget_value(
            revo_design_plugin.ui.checkBox_deduplicate_designs,
            test_data.mpnn_deduplicated,
        )

        if os.path.exists(test_data.mpnn_design_pse):
            os.remove(test_data.mpnn_design_pse)

        qtbot.mouseClick(
            revo_design_plugin.ui.pushButton_run_PSSM_to_pse, CURSOR
        )

        #wait_for_file(qtbot=qtbot, file=test_data.mpnn_design_pse,timeout=100)

        assert revo_design_plugin.design_molecule == test_data.molecule
        assert revo_design_plugin.design_chain_id == test_data.chain_id
        assert (
            get_widget_value(revo_design_plugin.ui.comboBox_design_molecule)
            == test_data.molecule
        )
        assert (
            get_widget_value(revo_design_plugin.ui.comboBox_chain_id)
            == test_data.chain_id
        )

        mutant_tree = existed_mutant_tree(
            sequences=revo_design_plugin.designable_sequences
        )

        assert not mutant_tree.empty

        save_screenshot(qtbot=qtbot, widget=revo_design_plugin.window,basename=method_name())

if __name__ == '__main__' or __name__ == 'pymol':
    pytest.main()
