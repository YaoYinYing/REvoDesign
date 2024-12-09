'''
Collect all the shortcuts and extend them to pymol
'''

from pymol import cmd

from .shortcuts import (color_by_mutation, color_by_plddt, dump_sidechains,
                        find_interface, pssm2csv, real_sc,
                        visualize_conformer_sdf)

cmd.extend("pssm2csv", pssm2csv)
cmd.extend("real_sc", real_sc)
cmd.extend("color_by_plddt", color_by_plddt)
cmd.extend("find_interface", find_interface)
cmd.extend("color_by_mutation", color_by_mutation)
cmd.extend("dump_sidechains", dump_sidechains)
cmd.extend("visualize_conformer_sdf", visualize_conformer_sdf)


__all__ = [
    "pssm2csv",
    "real_sc",
    "color_by_plddt",
    "find_interface",
    "color_by_mutation",
    "dump_sidechains",
    'visualize_conformer_sdf']
