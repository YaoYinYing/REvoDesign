import os

from REvoDesign.basic.menu_item import MenuItem
from REvoDesign.bootstrap import REVODESIGN_CONFIG_DIR
from REvoDesign.bootstrap.set_config import list_all_config_files

all_main_config_files = {
    x.removeprefix(REVODESIGN_CONFIG_DIR + os.sep).removesuffix(".yaml"): x
    for x in list_all_config_files(REVODESIGN_CONFIG_DIR)
}

# sort by config name
all_main_config_files = {k: v for k, v in sorted(all_main_config_files.items())}

# insert main config at first
main_config = all_main_config_files.pop("main")
all_main_config_files = {"main": main_config, **all_main_config_files}

all_secondary_config_files = {
    x.removeprefix(REVODESIGN_CONFIG_DIR + os.sep).removesuffix(".yaml"): x
    for x in list_all_config_files(REVODESIGN_CONFIG_DIR, tree=True)
}

# join all configs
all_config_files = {**all_main_config_files, **all_secondary_config_files}


def _clean_config_name(config_name: str):
    invalid_chars = [
        "/",
        "\\",
        ".",
        " ",
        "-",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        "|",
        ":",
        ";",
        "'",
        '"',
        ",<",
        ">",
        ",",
        "?",
        "!",
        "@",
        "#",
        "$",
        "%",
        "^",
        "&",
        "*",
        "+",
        "=",
        "~",
        "`",
    ]
    return config_name.translate({ord(x): None for x in invalid_chars if len(x) == 1})


CONFIG_EDIT_LINKS = []


for config_name, config_file in all_main_config_files.items():
    CONFIG_EDIT_LINKS.append(
        MenuItem(
            f"actionEditConf_{_clean_config_name(config_name)}",
            f"REvoDesign.editor.monaco.monaco:menu_edit_file",
            kwargs={"file_path": config_file},
            action_text=f"Edit {config_name}",
            menu_section="menuEdit_Configuration",
        )
    )


last_section = ""
for config_name, config_file in all_secondary_config_files.items():
    # exclude cache files
    if config_name.startswith(("cache", "experiments")):
        continue
    current_section = config_name.split("/")[0]
    if current_section != last_section:
        CONFIG_EDIT_LINKS.append(MenuItem("---", "---", menu_section="menuEdit_Configuration"))
        last_section = current_section

    CONFIG_EDIT_LINKS.append(
        MenuItem(
            f"actionEditConf_{_clean_config_name(config_name)}",
            f"REvoDesign.editor.monaco.monaco:menu_edit_file",
            kwargs={"file_path": config_file},
            action_text=f"Edit {config_name}",
            menu_section="menuEdit_Configuration",
        )
    )


# recent experiments
recent_experiments = {
    config_name: config_file
    for config_name, config_file in all_secondary_config_files.items()
    if config_name.startswith("experiments")
}

# sort by config file's modified time
sorted_recent_experiments = {
    config_name: config_file
    for config_name, config_file in sorted(
        recent_experiments.items(), key=lambda x: os.path.getmtime(x[1]), reverse=True
    )
}

for config_name, config_file in sorted_recent_experiments.items():

    CONFIG_EDIT_LINKS.append(
        MenuItem(
            f"actionEditConf_{_clean_config_name(config_name)}",
            f"REvoDesign.editor.monaco.monaco:menu_edit_file",
            kwargs={"file_path": config_file},
            action_text=f"Edit {config_name}",
            menu_section="menuRecent_Experiments",
        )
    )

TOOLS_MENU_LINKS = (
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

PREFERENCES_MENU_LINKS = (
    MenuItem(
        "actionPreferences_Font",
        "REvoDesign.application.font.font_manager:set_font_dialog",
        menu_section="menuUI_Preferences",
        action_text="Font Setting",
    ),
)

OTHER_MENU_LINKS = (
    MenuItem("actionRefreshEnvironVar", "REvoDesign.driver.environ_register:register_environment_variables"),
    MenuItem(
        "actionThreadPoolDashboard", 
        "REvoDesign.tools.package_manager:ThreadDashboard.show_thread_dashboard", 
        menu_section='menuRuntime',
        action_text='Thread Pool Dashboard')
)

MENU_LINKS = (
    *TOOLS_MENU_LINKS,
    *CONFIG_EDIT_LINKS,
    *PREFERENCES_MENU_LINKS,
    *OTHER_MENU_LINKS,
)
