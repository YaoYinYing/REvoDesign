'''
Collect all the shortcuts and extend them to pymol
'''

from pymol import cmd
from pymol.shortcut import Shortcut

from .tools.designs import shortcut_pssm2csv
from .tools.exports import shortcut_dump_sidechains
from .tools.ligand_converters import visualize_conformer_sdf
from .tools.represents import (shortcut_color_by_mutation,
                               shortcut_color_by_plddt, shortcut_real_sc)
from .tools.structure import shortcut_find_interface
from .tools.vina_tools import (enlargebox, get_pca_box, getbox, movebox, rmhet,
                               showaxes, showbox)

cmd.extend("pssm2csv", shortcut_pssm2csv)


# autocompletion for real_sc
# ref: https://raw.githubusercontent.com/Pymol-Scripts/Pymol-script-repo/master/scripts/spectrum_states.py

# How to set up autocompletion for a extend command with multiple arguments?
# The general format is:
# `cmd.auto_arg[<arg_id>]["<extend_command_name>"]=[<lambda_returning_Shortcut_object >, '<label_for_arg>', '<following_string>']` where
# <arg_id> is the argument index (starting from 0) that we want to set autocompletion for in the extend command
# <extend_command_name> is the name of the extend command
# <lambda_returning_Shortcut_object> is a lambda function that returns a Shortcut object
# '<label_for_arg>' is a string label for the argument that will be displayed in the autocomplete output
# '<following_string>' is a string that will be appended to the argument value

# Normally, to support autocomplete dynamically during runtime, PyMOL uses a lambda function that returns a Shortcut object
# A shortcut object defines the possible keywords for autocompletion of arguments.
# One can either bollow the existing Shortcut lambda from `cmd.auto_arg` or create a new one
# Here we borrow the existing ones for 'show' and 'select'
# To bollow the existing ones, we need to find the corresponding dict in the `cmd.auto_arg` list
# The autocompletion must be added after the extend command is defined
cmd.extend("real_sc", shortcut_real_sc)
cmd.auto_arg[0]["real_sc"]=[cmd.auto_arg[1]['select'][0], 'selection', ' ']
cmd.auto_arg[1]["real_sc"]=[cmd.auto_arg[0]['show'][0], 'representation', ' ']


cmd.extend("color_by_mutation", shortcut_color_by_mutation)
# To build a new one, we can create a lambda function that returns a Shortcut object
cmd.auto_arg[0]["color_by_mutation"]=[cmd.auto_arg[0]['enable'][0], 'obj1', '']
cmd.auto_arg[1]["color_by_mutation"]=[cmd.auto_arg[0]['enable'][0], 'obj2', '']
cmd.auto_arg[2]["color_by_mutation"]=[lambda : Shortcut(keywords=['0', '1']), 'waters', '']
cmd.auto_arg[3]["color_by_mutation"]=[lambda : Shortcut(keywords=['0', '1']), 'labels', '']
# In this case of color_by_mutation, we have 4 arguments:
# arg0: obj1 - autocompleted using the existing 'enable' shortcut
# arg1: obj2 - autocompleted using the existing 'enable' shortcut
# arg2: waters - autocompleted using a new shortcut with keywords '0' and '1'
# arg3: labels - autocompleted using a new shortcut with keywords '0' and '1'


# That's it!

cmd.extend("color_by_plddt", shortcut_color_by_plddt)
cmd.extend("find_interface", shortcut_find_interface)

cmd.extend("dump_sidechains", shortcut_dump_sidechains)
cmd.extend("visualize_conformer_sdf", visualize_conformer_sdf)

cmd.extend("getbox", getbox)
cmd.extend("get_pca_box", get_pca_box)
cmd.extend("showbox", showbox)

cmd.extend("rmhet", rmhet)
cmd.extend('movebox', movebox)
cmd.extend("showaxes", showaxes)
cmd.extend("enlargebox", enlargebox)


__all__ = [
    "shortcut_pssm2csv",
    "shortcut_real_sc",
    "shortcut_color_by_plddt",
    "shortcut_find_interface",
    "shortcut_color_by_mutation",
    "shortcut_dump_sidechains",
    'visualize_conformer_sdf']
