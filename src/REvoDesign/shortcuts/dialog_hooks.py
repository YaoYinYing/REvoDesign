'''
Utility functions for dialogs hook functions
'''
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
