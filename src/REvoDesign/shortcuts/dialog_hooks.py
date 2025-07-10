'''
Utility functions for dialogs hook functions
'''


from REvoDesign.tools.pymol_utils import find_small_molecules_in_protein


def get_fasta_writer_choices():
    """
    Return the list of available FASTA writer choices dynamically.
    """
    from Bio import SeqIO
    return list(filter(lambda x: x.startswith("fas"), SeqIO._FormatToWriter.keys()))


def get_designable_chain_ids():
    """
    Get the chain IDs that are designable from configuration or state.
    """
    from REvoDesign.driver.ui_driver import ConfigBus
    return list(ConfigBus().get_value("designable_sequences", dict, reject_none=True).keys())


def get_selections():
    from pymol import cmd
    return [''] + list(cmd.get_names("selections"))


find_all_small_molecules_in_protein=lambda: find_small_molecules_in_protein('(all)') or None