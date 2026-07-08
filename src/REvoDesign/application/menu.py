# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Menu builders for the REvoDesign main window.

Importing this module is cheap — all filesystem I/O is deferred until
the builder functions (*config_edit_links*, *menu_links*) are called.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from REvoDesign.basic.menu_item import MenuItem
from REvoDesign.bootstrap import REVODESIGN_CONFIG_DIR
from REvoDesign.bootstrap.set_config import list_all_config_files
from REvoDesign.Qt import QtCore

_tr = QtCore.QCoreApplication.translate

if TYPE_CHECKING:
    from REvoDesign.REvoDesign import REvoDesignPlugin

# -- helpers ----------------------------------------------------------------

_SAFE_ACTION_CHARS = re.compile(r"[^A-Za-z0-9_]")


def clean_config_name(config_name: str) -> str:
    """Strip characters that are not valid in a QAction object name."""
    return _SAFE_ACTION_CHARS.sub("", config_name)


def config_files() -> tuple[dict[str, str], dict[str, str]]:
    """Return (main_configs, secondary_configs) from the user config directory."""
    main = {
        x.removeprefix(REVODESIGN_CONFIG_DIR + os.sep).removesuffix(".yaml"): x
        for x in list_all_config_files(REVODESIGN_CONFIG_DIR)
    }
    main = dict(sorted(main.items()))
    # "main" always exists — move it to the front.
    main_config = main.pop("main", None)
    if main_config is not None:
        main = {"main": main_config, **main}

    secondary = {
        x.removeprefix(REVODESIGN_CONFIG_DIR + os.sep).removesuffix(".yaml"): x
        for x in list_all_config_files(REVODESIGN_CONFIG_DIR, tree=True)
    }
    return main, secondary


# ponytail: backward-compat shim — server.py imports all_config_files for the
# editor whitelist.  Replaced the module-level dict with a function so the
# filesystem scan still only happens on demand.
def all_config_files() -> dict[str, str]:
    """Return the merged dict of all config files (name → path)."""
    main, secondary = config_files()
    return {**main, **secondary}


# -- dynamic config-edit links ----------------------------------------------


def _edit_label(config_name: str) -> str:
    """Return the translated display text for an ``Edit <config>`` action."""
    return _tr("REvoDesignPyMOL_UI", "Edit %1").replace("%1", config_name)


def _edit_config_item(config_name: str, config_file: str, menu_section: str) -> MenuItem:
    """A single ``Edit <config>`` menu item."""
    return MenuItem(
        f"actionEditConf_{clean_config_name(config_name)}",
        "REvoDesign.editor.monaco.monaco:menu_edit_file",
        kwargs={"file_path": config_file},
        action_text=_edit_label(config_name),
        menu_section=menu_section,
    )


def config_edit_links() -> tuple[MenuItem, ...]:
    """Build config-edit and recent-experiment menu items (scans filesystem)."""
    main, secondary = config_files()
    links: list[MenuItem] = []

    for config_name, config_file in main.items():
        links.append(_edit_config_item(config_name, config_file, "menuEdit_Configuration"))

    last_section = ""
    for config_name, config_file in secondary.items():
        if config_name.startswith(("cache", "experiments")):
            continue
        current_section = config_name.split("/")[0]
        if current_section != last_section:
            links.append(MenuItem.separator("menuEdit_Configuration"))
            last_section = current_section
        links.append(_edit_config_item(config_name, config_file, "menuEdit_Configuration"))

    # recent experiments — sorted by mtime, newest first
    recent = {name: path for name, path in secondary.items() if name.startswith("experiments")}
    for config_name, config_file in sorted(recent.items(), key=lambda item: os.path.getmtime(item[1]), reverse=True):
        links.append(_edit_config_item(config_name, config_file, "menuRecent_Experiments"))

    return tuple(links)


# -- static menu-item groups ------------------------------------------------


TOOLS_MENU_LINKS: tuple[MenuItem, ...] = (
    MenuItem(
        "actionRenderPickedSidechainGroup",
        "REvoDesign.shortcuts.shortcuts_on_menu:menu_dump_sidechains",
        kwargs={"dump_all": False},
    ),
    MenuItem(
        "actionRenderAllSidechains",
        "REvoDesign.shortcuts.shortcuts_on_menu:menu_dump_sidechains",
        kwargs={"dump_all": True},
    ),
    MenuItem("actionColor_by_pLDDT", "REvoDesign.shortcuts.wrappers.represents:wrapped_color_by_plddt"),
    MenuItem("actionShow_Real_Sidechain", "REvoDesign.shortcuts.wrappers.represents:wrapped_real_sc"),
    MenuItem("actionColor_by_Mutations", "REvoDesign.shortcuts.wrappers.represents:wrapped_color_by_mutation"),
    MenuItem("actionPSSM_to_CSV", "REvoDesign.shortcuts.wrappers.designs:wrapped_pssm2csv"),
    MenuItem("actionProfile_Design", "REvoDesign.shortcuts.wrappers.designs:wrapped_profile_pick_design"),
    MenuItem(
        "actionSMILES_Conformers", "REvoDesign.shortcuts.wrappers.ligand_converters:wrapped_smiles_conformer_single"
    ),
    MenuItem(
        "actionSMILES_Conformers_Batch",
        "REvoDesign.shortcuts.wrappers.ligand_converters:wrapped_smiles_conformer_batch",
    ),
    MenuItem(
        "actionSDF_to_Rosetta_Parameters", "REvoDesign.shortcuts.wrappers.ligand_converters:wrapper_sdf2rosetta_params"
    ),
    MenuItem("actionRosettaLigand", "REvoDesign.shortcuts.wrappers.rosetta_tasks:wrapped_rosettaligand"),
    MenuItem("actionFastRelax", "REvoDesign.shortcuts.wrappers.rosetta_tasks:wrapped_fast_relax"),
    MenuItem(
        "actionRelax_w_Ca_Constraints", "REvoDesign.shortcuts.wrappers.rosetta_tasks:wrapped_relax_w_ca_constraints"
    ),
    MenuItem("actionPROSS", "REvoDesign.shortcuts.wrappers.rosetta_tasks:wrapped_pross"),
    MenuItem("actionThermoMPNN", "REvoDesign.shortcuts.wrappers.mutation_effect_predictors:wrapped_thermompnn"),
    MenuItem("actionESM_1v", "REvoDesign.shortcuts.wrappers.esm2:wrapped_esm1v"),
    MenuItem("actionAlter_Box", "REvoDesign.shortcuts.wrappers.vina_tools:wrapped_alter_box"),
    MenuItem("actionGet_PCA_Box", "REvoDesign.shortcuts.wrappers.vina_tools:wrapped_get_pca_box"),
    MenuItem("actionGet_Box", "REvoDesign.shortcuts.wrappers.vina_tools:wrapped_alter_box"),
    MenuItem("actionRemove_Het_Atoms", "REvoDesign.shortcuts.wrappers.vina_tools:wrapped_rmhet"),
    MenuItem(
        "actionRFdiffusion_General_Task",
        "REvoDesign.shortcuts.wrappers.rfdiffusion_tasks:wrapped_general_rfdiffusion_task",
    ),
    MenuItem(
        "actionSubstrate_Potential",
        "REvoDesign.shortcuts.wrappers.rfdiffusion_tasks:wrapped_visualize_substrate_potentials",
    ),
    MenuItem("actionRenumber_Residue_Index", "REvoDesign.shortcuts.wrappers.structure:wrapped_resi_renumber"),
    MenuItem("actionDump_Sequence", "REvoDesign.shortcuts.wrappers.exports:wrapped_dump_fasta_from_struct"),
    MenuItem("actionSetLogLevel", "REvoDesign.shortcuts.wrappers.utils:wrapped_logger_level_setter"),
    MenuItem("actionRMSF_to_b_factor", "REvoDesign.shortcuts.wrappers.represents:wrapped_load_b_factors"),
    MenuItem("actionMake_Residue_Range", "REvoDesign.shortcuts.wrappers.utils:wrapped_convert_residue_ranges"),
    MenuItem("actionShorten_Range", "REvoDesign.shortcuts.wrappers.utils:wrapped_short_range"),
    MenuItem("actionRun_GREMLIN", "REvoDesign.shortcuts.wrappers.evolution:wrapped_gremlin"),
)


def preferences_menu_links() -> tuple[MenuItem, ...]:
    """Menu items with translated display text (lazy — translator must be installed)."""
    return (
        MenuItem(
            "actionPreferences_Font",
            "REvoDesign.application.font.font_manager:set_font_dialog",
            menu_section="menuUI_Preferences",
            action_text=_tr("REvoDesignPyMOL_UI", "Font Setting"),
        ),
    )


def other_menu_links() -> tuple[MenuItem, ...]:
    """Menu items with translated display text (lazy — translator must be installed)."""
    return (
        MenuItem("actionRefreshEnvironVar", "REvoDesign.driver.environ_register:register_environment_variables"),
        MenuItem(
            "actionThreadPoolDashboard",
            "REvoDesign.tools.package_manager:ThreadDashboard.show_thread_dashboard",
            menu_section="menuRuntime",
            action_text=_tr("REvoDesignPyMOL_UI", "Thread Pool Dashboard"),
        ),
    )


def static_menu_links() -> tuple[MenuItem, ...]:
    """Return the union of all static (non-config-scanning) menu items."""
    return (*TOOLS_MENU_LINKS, *preferences_menu_links(), *other_menu_links())


# -- combined builders ------------------------------------------------------


def menu_links() -> tuple[MenuItem, ...]:
    """All deferred menu items: tools + config-edits + preferences + other."""
    return (*static_menu_links(), *config_edit_links())


def core_menu_links(app: REvoDesignPlugin) -> tuple[MenuItem, ...]:
    """Core application menu items wired directly to *app* methods."""
    import REvoDesign
    from REvoDesign.Qt import QtCore, QtGui
    from REvoDesign.tools.customized_widgets import notify_box

    _REPO_URL = "https://github.com/YaoYinYing/REvoDesign"

    return (
        MenuItem("actionSet_Working_Directory", app.set_working_directory),
        MenuItem("actionReconfigure", app.reload_configurations),
        MenuItem("actionSave_Configurations", app.bus.cfg_group["main"].save),
        MenuItem("action_LoadExperiment", app.load_and_save_experiment, kwargs={"mode": "r"}),
        MenuItem("action_Save_to_Experiment", app.load_and_save_experiment, kwargs={"mode": "w"}),
        MenuItem("actionReinitialize", app.reinitialize, kwargs={"delete": True}),
        MenuItem("actionSource_Code", QtGui.QDesktopServices.openUrl, (QtCore.QUrl(_REPO_URL),)),
        MenuItem(
            "actionVersion",
            notify_box,
            kwargs={"message": f"REvoDesign v.{REvoDesign.__version__}\nSrc: {_REPO_URL}"},
        ),
    )


__all__ = [
    "TOOLS_MENU_LINKS",
    "all_config_files",
    "config_edit_links",
    "core_menu_links",
    "menu_links",
    "other_menu_links",
    "preferences_menu_links",
    "static_menu_links",
]
