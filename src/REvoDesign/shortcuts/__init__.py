'''
Collect all the shortcuts and extend them to pymol
'''

from pymol import cmd

from .tools.vina_tools import GetBoxHelp, autobox, getbox, movebox, resibox, rmhet, showbox

from .tools.designs import shortcut_pssm2csv
from .tools.exports import shortcut_dump_sidechains
from .tools.ligand_converters import visualize_conformer_sdf
from .tools.represents import (shortcut_color_by_mutation,
                               shortcut_color_by_plddt, shortcut_real_sc)
from .tools.structure import shortcut_find_interface

cmd.extend("pssm2csv", shortcut_pssm2csv)
cmd.extend("real_sc", shortcut_real_sc)
cmd.extend("color_by_plddt", shortcut_color_by_plddt)
cmd.extend("find_interface", shortcut_find_interface)
cmd.extend("color_by_mutation", shortcut_color_by_mutation)
cmd.extend("dump_sidechains", shortcut_dump_sidechains)
cmd.extend("visualize_conformer_sdf", visualize_conformer_sdf)

cmd.extend("getbox", getbox)
cmd.extend("showbox", showbox)
cmd.extend("autobox", autobox)
cmd.extend("resibox", resibox)
cmd.extend("GetBoxHelp", GetBoxHelp)
cmd.extend("rmhet", rmhet)
cmd.extend('movebox', movebox)


__all__ = [
    "shortcut_pssm2csv",
    "shortcut_real_sc",
    "shortcut_color_by_plddt",
    "shortcut_find_interface",
    "shortcut_color_by_mutation",
    "shortcut_dump_sidechains",
    'visualize_conformer_sdf']
