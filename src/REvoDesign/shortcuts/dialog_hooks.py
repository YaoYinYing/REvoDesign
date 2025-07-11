'''
Utility functions for dialogs hook functions
'''


from Bio import SeqIO
from pymol import cmd

from REvoDesign.driver.ui_driver import ConfigBus
from REvoDesign.tools.pymol_utils import find_small_molecules_in_protein

get_fasta_writer_choices = lambda: list(filter(lambda x: x.startswith("fas"), SeqIO._FormatToWriter.keys()))


get_designable_chain_ids = lambda: list(ConfigBus().get_value("designable_sequences", dict, reject_none=True).keys())
get_selections = lambda: [''] + list(cmd.get_names("selections"))


find_all_small_molecules_in_protein = lambda: find_small_molecules_in_protein('(all)') or None


get_all_chain_ids = lambda: list(ConfigBus().get_value("designable_sequences", dict, reject_none=True).keys())

get_all_object_names = lambda: cmd.get_names("objects")


get_all_selections = lambda: cmd.get_names("selections")
get_all_objects = lambda: cmd.get_names("objects")
