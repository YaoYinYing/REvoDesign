# Shortcuts

The shortcuts module extends PyMOL's command language with REvoDesign-specific
commands via `cmd.extend()`, sets up CLI autocompletion via `cmd.auto_arg`, and
provides the `DialogWrapperRegistry` system for wrapping functions with
interactive dialog popups.

## PyMOL Command Registration

Commands are registered in `REvoDesign.shortcuts.__init__` and receive
autocompletion through `cmd.auto_arg`.

### Registered commands

| Command | Function | Arguments |
|---------|----------|-----------|
| `pssm2csv` | `shortcut_pssm2csv` | arg0: pssm file path |
| `real_sc` | `shortcut_real_sc` | arg0: selection, arg1: representation, arg2: hydrogen (0/1) |
| `color_by_mutation` | `shortcut_color_by_mutation` | arg0: target object, arg1: reference object, arg2: waters (0/1), arg3: labels (0/1) |
| `color_by_plddt` | `shortcut_color_by_plddt` | arg0: selection (default "all"), arg1: align_target (0/1), arg2: chain |
| `find_interface` | `shortcut_find_interface` | arg0: selection (default "all"), arg1: interact_dist |
| `dump_sidechains` | `shortcut_dump_sidechains` | arg0: sele, arg1: enabled_only, arg2: save_dir, ..., arg10: recenter |
| `visualize_conformer_sdf` | `visualize_conformer_sdf` | arg0: sdf_file_path, arg1: show_conformer |
| `getbox` | `getbox` | -- |
| `get_pca_box` | `get_pca_box` | -- |
| `showbox` | `showbox` | -- |
| `rmhet` | `rmhet` | -- |
| `movebox` | `movebox` | -- |
| `showaxes` | `showaxes` | -- |
| `enlargebox` | `enlargebox` | -- |

## Dialog Wrapper Registry

::: REvoDesign.shortcuts.utils.DialogWrapperRegistry
    options:
      show_submodules: false

## Utility Functions

::: REvoDesign.shortcuts.utils.resolve_choice_from

::: REvoDesign.shortcuts.utils.resolve_default_from

::: REvoDesign.shortcuts.function_utils.visualize_conformer_sdf

::: REvoDesign.shortcuts.function_utils.smiles_conformer_batch

::: REvoDesign.shortcuts.function_utils.smiles_conformer_single

::: REvoDesign.shortcuts.dialog_hooks.get_fasta_writer_choices

::: REvoDesign.shortcuts.dialog_hooks.get_designable_chain_ids

::: REvoDesign.shortcuts.dialog_hooks.get_selections

::: REvoDesign.shortcuts.dialog_hooks.find_all_small_molecules_in_protein

::: REvoDesign.shortcuts.dialog_hooks.get_all_chain_ids

::: REvoDesign.shortcuts.dialog_hooks.get_all_object_names

::: REvoDesign.shortcuts.dialog_hooks.get_all_selections

::: REvoDesign.shortcuts.dialog_hooks.get_all_objects

::: REvoDesign.shortcuts.dialog_hooks.get_pymol_plugin_paths

## Menu Shortcuts

::: REvoDesign.shortcuts.shortcuts_on_menu.menu_dump_sidechains
    options:
      show_submodules: false
