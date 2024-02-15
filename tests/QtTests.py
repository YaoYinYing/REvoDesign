import os
import glob

os.environ['PYTEST_QT_API'] = 'pyqt5'
import time
from pymol import cmd, util, CmdException
import pytest
import pytestqt
from pytestqt import qtbot
from pytestqt.qt_compat import qt_api

from pymol.Qt import QtWidgets, QtCore, QtGui
from TestData import TestDataOnLocalMac

from REvoDesign import REvoDesignPlugin
from REvoDesign.tools.system_tools import CLIENT_INFO
from REvoDesign.tools.customized_widgets import (
    get_widget_value,
    set_widget_value,
)

CURSOR = QtCore.Qt.MouseButton.LeftButton


test_data = TestDataOnLocalMac()
client_info = CLIENT_INFO()


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

        qtbot.mouseClick(revo_design_plugin.ui.menuREvoDesign, CURSOR)
        # qtbot.mouseClick(revo_design_plugin.ui.actionCheck_PyMOL_session, CURSOR)
        revo_design_plugin.reload_molecule_info(
            revo_design_plugin.ui.comboBox_design_molecule
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

    def test_pocket(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        fetch_pdb()
        revo_design_plugin.reload_molecule_info(
            revo_design_plugin.ui.comboBox_design_molecule
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

        assert pocket_file_design_shell is not None

        with open(pocket_file_design_shell, 'r') as ds_fr:
            design_shell_residue_ids = ds_fr.read().strip()
            assert design_shell_residue_ids

    def test_surface(
        self, qtbot: qtbot.QtBot, revo_design_plugin: REvoDesignPlugin
    ):
        load_pocket_pse()

        revo_design_plugin.reload_molecule_info(
            revo_design_plugin.ui.comboBox_design_molecule
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

        set_widget_value(
            revo_design_plugin.ui.comboBox_surface_exclusion, hetatm_residues
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

        with open(surface_file_design_shell, 'r') as ss_fr:
            surface_residue_ids = ss_fr.read().strip()
            assert surface_residue_ids


if __name__ == '__main__':
    pytest.main()
