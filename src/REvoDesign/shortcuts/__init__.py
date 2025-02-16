'''
Collect all the shortcuts and extend them to pymol
'''

from pymol import cmd

from .shortcuts import (shortcut_color_by_mutation, shortcut_color_by_plddt,
                        shortcut_dump_sidechains, shortcut_find_interface,
                        shortcut_pssm2csv, shortcut_real_sc,
                        visualize_conformer_sdf)

cmd.extend("pssm2csv", shortcut_pssm2csv)
cmd.extend("real_sc", shortcut_real_sc)
cmd.extend("color_by_plddt", shortcut_color_by_plddt)
cmd.extend("find_interface", shortcut_find_interface)
cmd.extend("color_by_mutation", shortcut_color_by_mutation)
cmd.extend("dump_sidechains", shortcut_dump_sidechains)
cmd.extend("visualize_conformer_sdf", visualize_conformer_sdf)


__all__ = [
    "shortcut_pssm2csv",
    "shortcut_real_sc",
    "shortcut_color_by_plddt",
    "shortcut_find_interface",
    "shortcut_color_by_mutation",
    "shortcut_dump_sidechains",
    'visualize_conformer_sdf']
